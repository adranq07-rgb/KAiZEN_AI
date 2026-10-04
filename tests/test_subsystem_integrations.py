import io
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from tools.external_actions import ManusAdapter, DocumensoAdapter, ExternalAPI
from tools.subsystem_tools import register, capability_status
from tools.tool_manager import ToolManager
from research.scrapling_adapter import ScraplingAdapter
from research.fetcher import FetchOutcome
from research.models import FETCH_OK, FETCH_HTTP_ERROR

def test_subsystem_approval_and_trace():
    with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, {}, clear=True):
        manager=ToolManager(log_dir=Path(d));register(manager)
        assert isinstance(manager.run_tool('manus_create_task','hello'),str)
        assert not hasattr(manager,'last_trace')
        result=manager.run_tool('manus_create_task','hello',approved=True)
        assert result['status']=='AUTH_REQUIRED'
        assert manager.last_trace.external_actions[0]['system']=='Manus'
        assert manager.run_tool('documenso_create_draft','missing.pdf','draft',approved=True)['status']=='AUTH_REQUIRED'
        assert capability_status()['Coolify']['status']=='HOST_REQUIRED'

def test_external_auth_isolation_and_direct_guards():
    with patch.dict(os.environ,{},clear=True), patch('urllib.request.OpenerDirector.open',side_effect=AssertionError('network')):
        assert ManusAdapter().health()['status']=='AUTH_REQUIRED'
        assert DocumensoAdapter().health()['status']=='AUTH_REQUIRED'
        assert ManusAdapter().create_task('x')['status']=='APPROVAL_REQUIRED'
        assert DocumensoAdapter().create_draft('x','x')['status']=='APPROVAL_REQUIRED'

def test_manus_contract_and_unknown_poll_never_completed():
    a=ManusAdapter()
    with patch.object(a.api,'request',return_value={'ok':True,'task_id':'abc'}) as request:
        assert a.create_task('harmless',approved=True)['task_id']=='abc'
        assert request.call_args.args[1]=='/task.create'
        assert request.call_args.args[2]['share_visibility']=='private'
    with patch.object(a,'task_status',return_value={'ok':True,'task':{'agent_status':'stopped'}}),patch('tools.external_actions.time.sleep'):
        assert a.poll('abc',1)['status']=='POLL_TIMEOUT'
    with patch.object(a,'task_status',return_value={'ok':True,'task':{'agent_status':'waiting'}}):
        assert a.poll('abc')['status']=='waiting'

def test_documenso_draft_contract_hides_signing_tokens():
    with patch.dict(os.environ,{'DOCUMENSO_API_KEY':'test-key','DOCUMENSO_BASE_URL':'https://example.com'}),tempfile.TemporaryDirectory() as d:
        a=DocumensoAdapter();p=Path(d)/'approved.pdf';p.write_bytes(b'%PDF-1.7 test')
        with patch.object(a.api,'request',return_value={'id':'envelope_1','status':'DRAFT','recipients':[{'token':'must-not-leak'}]}) as request:
            r=a.create_draft(p,'Approved',approved=True)
            assert r=={'ok':True,'id':'envelope_1','status':'DRAFT'}
            assert request.call_args.args[1]=='/envelope/create'
            assert b'\r\n' in request.call_args.args[2]
            assert b'recipients' not in request.call_args.args[2]

def test_external_transport_errors_are_sanitized():
    api=ExternalAPI('https://example.com','secret','Authorization')
    with patch('urllib.request.OpenerDirector.open',side_effect=TimeoutError('secret')):
        r=api.request('GET','/health')
        assert r['status']=='UNAVAILABLE' and 'secret' not in str(r)
    assert ExternalAPI('http://remote.example','secret','Authorization').request('GET','/')['status']=='INVALID_ENDPOINT'

def test_scrapling_preserves_denials_and_falls_back_on_failure():
    s=ScraplingAdapter()
    with patch.object(s._primary,'fetch',return_value=FetchOutcome(status=FETCH_HTTP_ERROR,url='https://example.com',http_status=403)),patch.object(s._fallback,'fetch') as fallback:
        assert s.fetch('https://example.com').status==FETCH_HTTP_ERROR
        fallback.assert_not_called()
    with patch.object(s._primary,'fetch',side_effect=ImportError()),patch.object(s._fallback,'fetch',return_value=FetchOutcome(status=FETCH_OK,url='https://example.com',body=b'content')):
        assert s.fetch('https://example.com').body==b'content'
        assert s.metrics['scrapling_fallback_used']

def test_scrapling_blocks_localhost_before_import():
    s=ScraplingAdapter()
    assert not s.fetch('http://127.0.0.1/private').ok
    assert not s.metrics['scrapling_attempted']

def test_scrapling_extraction_consumed():
    from research.scrapling_adapter import ScraplingOutcome
    from research.extractor import extract
    r=ScraplingOutcome(status=FETCH_OK,url='https://example.com',content_type='text/html',body=b'<h1>Title</h1>',extracted_text='Real extracted body')
    assert extract(r).text=='Real extracted body'


def test_container_gateway_is_local_but_other_hosts_are_not():
    from core.ai.local_provider import LocalProvider
    from core.ai.embedding_client import OllamaEmbeddingClient
    for cls in (LocalProvider,OllamaEmbeddingClient):
        assert cls(base_url='http://host.docker.internal:11434',model_name='test').is_ready()
        assert not cls(base_url='https://untrusted.example',model_name='test').is_ready()

def test_service_auth_does_not_invoke_engine():
    import threading
    import urllib.request
    import urllib.error
    from http.server import HTTPServer
    from tools.service import make_handler
    class Engine:
        component_failures={}
    server=HTTPServer(('127.0.0.1',0),make_handler(Engine(),'test-only-secret'))
    worker=threading.Thread(target=server.serve_forever);worker.start()
    try:
        base='http://127.0.0.1:'+str(server.server_port)
        assert json.load(urllib.request.urlopen(base+'/health'))['status']=='ok'
        request=urllib.request.Request(base+'/ask',data=b'{"question":"2+2"}')
        try:urllib.request.urlopen(request)
        except urllib.error.HTTPError as exc:assert exc.code==401
        else:raise AssertionError('Unauthenticated request accepted')
    finally:server.shutdown();server.server_close();worker.join()


import pytest

def test_scrapling_transport_case_insensitive_headers_and_size_cap():
    pytest.skip("scrapling library not installed")
    from types import SimpleNamespace
    from urllib.request import Request
    from scrapling.fetchers import Fetcher
    from research.scrapling_adapter import _SizeLimit
    s=ScraplingAdapter(max_bytes=4)
    def fetch(url,**kwargs):
        assert kwargs['follow_redirects'] is False and kwargs['retries']==1
        kwargs['content_callback'](b'abcd')
        return SimpleNamespace(status=200,headers={'content-type':'text/plain'})
    with patch.object(Fetcher,'get',side_effect=fetch):
        r=s._primary._opener.open(Request('https://example.com/page'),1)
        assert r.headers.get('Content-Type')=='text/plain' and r.read()==b'abcd'
    def oversized(url,**kwargs):
        assert kwargs['content_callback'](b'abcde')==0
        raise ConnectionError('bounded abort')
    with patch.object(Fetcher,'get',side_effect=oversized):
        try:s._primary._opener.open(Request('https://example.com/page'),1)
        except _SizeLimit:pass
        else:raise AssertionError('size cap did not abort')
