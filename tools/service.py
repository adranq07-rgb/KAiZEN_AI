"""Small headless entrypoint for Docker/Coolify; desktop remains independent."""
import hmac
import json
import os
import signal
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from config.config_manager import ConfigManager
from core.engine import KaizenEngine

def build_engine():
    config=ConfigManager()
    config.config['model']['provider']=os.getenv('KAIZEN_PROVIDER','offline')
    config.config['model']['fallback']=['offline']
    config.config['retrieval']['hybrid_enabled']=os.getenv('KAIZEN_HYBRID','false').lower()=='true'
    endpoint=os.getenv('KAIZEN_OLLAMA_URL','http://localhost:11434').rstrip('/')
    config.config['model']['local']['base_url']=endpoint+'/v1'
    config.config['retrieval']['base_url']=endpoint
    config.config['research']['base_url']=os.getenv('KAIZEN_SEARXNG_URL','http://localhost:8890')
    return KaizenEngine(config=config,data_dir=Path(os.getenv('KAIZEN_DATA_DIR','data')),
                        log_dir=Path(os.getenv('KAIZEN_LOG_DIR','logs')))

def make_handler(engine, token):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass  # Do not log prompts, headers, or credentials.
        def setup(self):
            super().setup();self.connection.settimeout(10)
        def send_json(self,status,body):
            data=json.dumps(body,ensure_ascii=False).encode('utf8')
            self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8')
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if self.path!='/health':return self.send_json(404,{'status':'NOT_FOUND'})
            self.send_json(200,{'status':'ok','app':'Kaizen-1','optional_failures':sorted(engine.component_failures)})
        def do_POST(self):
            if self.path!='/ask':return self.send_json(404,{'status':'NOT_FOUND'})
            if not token:return self.send_json(503,{'status':'API_TOKEN_REQUIRED'})
            if not hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token):
                return self.send_json(401,{'status':'UNAUTHORIZED'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=16384:return self.send_json(413,{'status':'INPUT_TOO_LARGE'})
                question=json.loads(self.rfile.read(size)).get('question','')
                if not isinstance(question,str) or not question.strip() or len(question)>4000:raise ValueError()
                # HTTP answers only; management/file commands and external actions stay local.
                answer=engine.brain.answer(question)
                self.send_json(200,{'answer':answer,'trace':engine.brain.last_trace.to_dict()})
            except (ValueError,TypeError,AttributeError):self.send_json(400,{'status':'INVALID_INPUT'})
            except Exception:self.send_json(500,{'status':'UNAVAILABLE'})
    return Handler

def main():
    engine=build_engine();server=HTTPServer((os.getenv('KAIZEN_BIND','127.0.0.1'),int(os.getenv('PORT','8768'))),make_handler(engine,os.getenv('KAIZEN_API_TOKEN','')))
    def stop(*_):threading.Thread(target=server.shutdown,daemon=True).start()
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:server.serve_forever()
    finally:server.server_close();engine.shutdown()
if __name__=='__main__':main()
