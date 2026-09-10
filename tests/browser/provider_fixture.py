"""Controlled Ollama-compatible fixture. Simulated LAN traffic stays on loopback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading


def start_provider():
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self): self.reply()
        def do_POST(self): self.reply()
        def reply(self):
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
            if self.path.endswith('/models'): result={'data':[{'id':'test-vision'},{'id':'test-chat'}]}
            elif self.path=='/api/tags': result={'models':[{'name':'test-embed:latest','digest':'fixture'}]}
            elif self.path=='/api/embed': result={'embeddings':[[1,0,0] for _ in body['input']]}
            else: result={'choices':[{'finish_reason':'stop','message':{'content':'LIBRARY OCR TEST 4827'}}]}
            raw=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    connect=socket.create_connection
    def mapped(address,*args,**kwargs):
        if address==('192.168.50.40',server.server_port):
            address=('127.0.0.1',server.server_port)
        return connect(address,*args,**kwargs)
    socket.create_connection=mapped
    return server
