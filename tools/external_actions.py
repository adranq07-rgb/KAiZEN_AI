"""Explicit external actions. Credentials are read only from environment at call time."""
import json
import os
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlencode, urlparse, quote

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

class ExternalAPI:
    def __init__(self, base, key, header, timeout=12):
        self.base, self.key, self.header = base.rstrip('/'), key, header
        self.timeout = min(max(float(timeout), 1), 20)

    def request(self, method, path, payload=None, content_type='application/json', timeout=None):
        if not self.key or not self.base:
            return {'ok': False, 'status': 'AUTH_REQUIRED'}
        parsed = urlparse(self.base)
        if (parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('localhost','127.0.0.1','::1'))) or parsed.username or parsed.password or parsed.query or parsed.fragment:
            return {'ok': False, 'status': 'INVALID_ENDPOINT'}
        body = json.dumps(payload).encode() if isinstance(payload, dict) else payload
        request = urllib.request.Request(self.base + path, data=body, method=method,
            headers={self.header: self.key, 'Content-Type': content_type, 'Accept':'application/json'})
        try:
            with urllib.request.build_opener(_NoRedirect()).open(request, timeout=min(self.timeout, timeout or self.timeout)) as response:
                data = response.read(2_000_001)
                if len(data) > 2_000_000:
                    return {'ok': False, 'status': 'RESPONSE_TOO_LARGE'}
                result = json.loads(data)
                return result if isinstance(result, dict) else {'ok': False, 'status': 'INVALID_RESPONSE'}
        except urllib.error.HTTPError as exc:
            return {'ok': False, 'status': 'AUTH_REQUIRED' if exc.code in (401,403) else 'HTTP_ERROR', 'http_status': exc.code}
        except Exception as exc:
            return {'ok': False, 'status': 'UNAVAILABLE', 'error_type': type(exc).__name__}

class ManusAdapter:
    def __init__(self):
        self.api = ExternalAPI('https://api.manus.ai/v2', os.getenv('MANUS_API_KEY',''), 'x-manus-api-key')
    def health(self):
        r=self.api.request('GET','/user.me')
        return {'ok': r.get('ok', False), 'status': 'AVAILABLE' if r.get('ok') else r.get('status','UNAVAILABLE')}
    def create_task(self, prompt, *, approved=False):
        if not approved: return {'ok':False,'status':'APPROVAL_REQUIRED'}
        if not isinstance(prompt,str) or not prompt.strip() or len(prompt)>8000: return {'ok':False,'status':'INVALID_INPUT'}
        r=self.api.request('POST','/task.create',{'message':{'content':prompt},'agent_profile':'lite','share_visibility':'private','interactive_mode':False})
        return {k:r[k] for k in ('ok','status','task_id','task_title','task_url','request_id','error_type','http_status') if k in r}
    def task_status(self, task_id, timeout=None):
        if not task_id or len(str(task_id))>200: return {'ok':False,'status':'INVALID_INPUT'}
        r=self.api.request('GET','/task.detail?'+urlencode({'task_id':task_id}),timeout=timeout)
        return r
    def result(self, task_id, timeout=None):
        return self.api.request('GET','/task.listMessages?'+urlencode({'task_id':task_id,'order':'desc','limit':10}),timeout=timeout)
    def follow_up(self, task_id, prompt, *, approved=False):
        if not approved: return {'ok':False,'status':'APPROVAL_REQUIRED'}
        if not task_id or not prompt or len(prompt)>8000: return {'ok':False,'status':'INVALID_INPUT'}
        return self.api.request('POST','/task.sendMessage',{'task_id':task_id,'message':{'content':prompt}})
    def poll(self, task_id, max_seconds=30):
        deadline=time.monotonic()+min(max(float(max_seconds),1),60)
        for _ in range(12):
            remaining=deadline-time.monotonic()
            if remaining<=0:break
            r=self.task_status(task_id,timeout=remaining)
            if r.get('ok') is False:return r
            task=r.get('task',r)
            status=task.get('agent_status',task.get('status','unknown'))
            if status in ('waiting','error'):return {'ok':False,'status':status,'task_id':task_id}
            if status in ('stopped','completed') and task.get('has_running_background_jobs') is False:
                remaining=deadline-time.monotonic()
                if remaining<=0:break
                result=self.result(task_id,timeout=remaining)
                return {'ok':result.get('ok',False),'status':'COMPLETED' if result.get('ok') else 'RESULT_UNAVAILABLE','task_id':task_id,'result':result}
            time.sleep(min(2,max(0,deadline-time.monotonic())))
        return {'ok':False,'status':'POLL_TIMEOUT','task_id':task_id}

class DocumensoAdapter:
    def __init__(self):
        base=os.getenv('DOCUMENSO_BASE_URL','').rstrip('/')
        if base and not base.endswith('/api/v2'):base += '/api/v2'
        self.api=ExternalAPI(base,os.getenv('DOCUMENSO_API_KEY',''),'Authorization')
    def health(self):
        r=self.api.request('GET','/envelope?page=1&perPage=1')
        return {'ok':r.get('ok',True) is not False,'status':r.get('status','AVAILABLE')}
    @staticmethod
    def metadata(r):
        if r.get('ok') is False:return {k:r[k] for k in ('ok','status','error_type','http_status') if k in r}
        value=r.get('data',r.get('envelope',r))
        return {'ok':True, **{k:value[k] for k in ('id','title','status','createdAt','updatedAt','completedAt') if k in value}}
    def status(self, envelope_id):
        if not envelope_id:return {'ok':False,'status':'INVALID_INPUT'}
        return self.metadata(self.api.request('GET','/envelope/'+quote(str(envelope_id),safe='')))
    def create_draft(self, path, title, *, approved=False):
        if not approved:return {'ok':False,'status':'APPROVAL_REQUIRED'}
        if not self.api.key or not self.api.base:return {'ok':False,'status':'AUTH_REQUIRED'}
        file=Path(path)
        if not title or len(title)>255 or file.suffix.lower()!='.pdf' or not file.is_file() or file.stat().st_size>10_000_000:
            return {'ok':False,'status':'INVALID_DOCUMENT'}
        data=file.read_bytes()
        if not data.startswith(b'%PDF-'):return {'ok':False,'status':'INVALID_DOCUMENT'}
        boundary='kaizen'+uuid.uuid4().hex
        payload=json.dumps({'title':title,'type':'DOCUMENT'})
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="payload"\r\nContent-Type: application/json\r\n\r\n{payload}\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="files"; filename="approved-document.pdf"\r\nContent-Type: application/pdf\r\n\r\n').encode()+data+f'\r\n--{boundary}--\r\n'.encode()
        # Draft only: no recipients, distribute, send, or signing endpoints.
        return self.metadata(self.api.request('POST','/envelope/create',body,'multipart/form-data; boundary='+boundary))
