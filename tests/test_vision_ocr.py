"""Vision OCR and explicit LAN providers, using synthetic pages and a real local HTTP fixture."""
import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
from urllib.error import URLError
from urllib.request import Request
from uuid import uuid4

import pytest

from legal_platform.provider_http import validate_provider_url, provider_urlopen
from legal_platform.modules.generation.provider import ProviderConfig, OpenAICompatibleProvider
from legal_platform.modules.embedding.engine import OllamaEmbeddingEngine
from legal_platform.modules.ocr_service.config import OcrConfig, load_ocr_config, save_ocr_config, merge_ocr_config
from legal_platform.modules.ocr_service.engine import AutoOcrEngine, OcrEngineError, Pdf2ImageTesseractEngine
from legal_platform.modules.ocr_service.vision import ConfiguredImageEngine, VisionOcrEngine


@contextmanager
def provider_server():
    calls=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_): pass
        def do_GET(self): self.reply()
        def do_POST(self): self.reply()
        def reply(self):
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
            calls.append((self.path, body, dict(self.headers)))
            if self.path == '/redirect':
                self.send_response(302);self.send_header('Location','/credential-trap');self.end_headers();return
            if self.path.endswith('/models'): result={'data':[{'id':'test-vision'}]}
            elif self.path == '/api/tags': result={'models':[{'name':'test-embed:latest','digest':'test-digest'}]}
            elif self.path == '/api/embed': result={'embeddings':[[1,0,0] for _ in body['input']]}
            else: result={'choices':[{'finish_reason':body.get('test_finish','stop'), 'message':{'content':'Điều 2. Hồ sơ mua sắm cần dự toán và phê duyệt.'}}]}
            raw=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try: yield f'http://127.0.0.1:{server.server_port}',calls
    finally: server.shutdown();server.server_close();thread.join(timeout=5)


@pytest.mark.parametrize('address', ['10.1.2.3','172.20.2.3','192.168.2.3','[fd12::123]'])
def test_lan_requires_explicit_setting(address):
    assert not validate_provider_url('http://'+address+':11434/v1')[0]
    assert validate_provider_url('http://'+address+':11434/v1',allow_lan=True)[0]


@pytest.mark.parametrize('url', ['http://169.254.169.254/v1','http://[fe80::1]/v1','http://0.0.0.0/v1',
    'http://224.0.0.1/v1','http://[::]/v1','http://127.0.0.2/v1','http://localhost:0/v1',
    'http://name:secret@localhost/v1','http://localhost/v1?api_key=secret','http://localhost/v1#fragment',
    'http://localhost\n/v1','file:///etc/passwd','http://[::ffff:169.254.169.254]/v1'])
def test_lan_does_not_allow_special_destinations(url):
    assert not validate_provider_url(url,allow_lan=True)[0]


def test_unresolved_and_mixed_dns_are_rejected(monkeypatch):
    def missing(*a,**k): raise socket.gaierror()
    monkeypatch.setattr('legal_platform.provider_http.socket.getaddrinfo',missing)
    assert not validate_provider_url('http://missing.test/v1',allow_lan=True)[0]
    monkeypatch.setattr('legal_platform.provider_http.socket.getaddrinfo',lambda *a,**k:
        [(2,1,6,'',('93.184.216.34',80)),(2,1,6,'',('169.254.169.254',80))])
    assert not validate_provider_url('http://mixed.test/v1',allow_lan=True)[0]


def test_lan_chat_and_embeddings_use_same_transport_policy(monkeypatch):
    with provider_server() as (url,calls):
        real_connect=socket.create_connection;port=int(url.rsplit(':',1)[1]);destinations=[]
        def mapped(address,*args,**kwargs):
            destinations.append(address)
            assert address[0]=='192.168.50.40'
            return real_connect(('127.0.0.1',port),*args,**kwargs)
        monkeypatch.setattr('legal_platform.provider_http.socket.create_connection',mapped)
        base=f'http://192.168.50.40:{port}/v1'
        provider=OpenAICompatibleProvider(ProviderConfig(base_url=base,allow_lan=True,model='test-vision',api_key='synthetic-key'))
        assert provider.check_connectivity()[0]
        assert 'dự toán' in provider.generate(system_prompt='Quote',evidence_text='test',question='test')
        embed=OllamaEmbeddingEngine(base_url=base,allow_lan=True,model='test-embed:latest',expected_dimension=3)
        assert embed.embed('test')==[1.,0.,0.]
        assert len(destinations)==4
        assert [call[0] for call in calls]==['/v1/models','/v1/chat/completions','/api/tags','/api/embed']
        assert calls[0][2]['Authorization']=='Bearer synthetic-key'


def test_transport_pins_dns_and_never_follows_redirects(monkeypatch):
    with provider_server() as (url,calls):
        real_connect=socket.create_connection;port=int(url.rsplit(':',1)[1]);lookups=[]
        def resolve(*args,**kwargs):
            lookups.append(args)
            return [(2,1,6,'',('93.184.216.34' if len(lookups)==1 else '169.254.169.254',port))]
        monkeypatch.setattr('legal_platform.provider_http.socket.getaddrinfo',resolve)
        def connect(address,timeout,source_address):
            assert address[0]=='93.184.216.34'
            # A manually connected socket avoids the patched resolver entirely.
            sock=socket.socket();sock.settimeout(timeout);sock.connect(('127.0.0.1',port));return sock
        monkeypatch.setattr('legal_platform.provider_http.socket.create_connection',connect)
        with pytest.raises(URLError,match='redirect'):
            with provider_urlopen(Request(f'http://provider.test:{port}/redirect',headers={'Authorization':'Bearer synthetic-key'}),5): pass
        assert len(lookups)==1 and len(calls)==1


def mixed_pdf():
    import pymupdf
    with pymupdf.open() as pdf:
        page=pdf.new_page();page.insert_text((40,40),'Digital source paragraph with more than fifty characters. Keep this embedded text unchanged.')
        page=pdf.new_page();page.draw_rect((30,30,200,150),color=(0,0,0),fill=(.7,.7,.7))
        return pdf.tobytes()


def test_vision_only_receives_scanned_page_and_preserves_original_page_number(isolated_application_data):
    with provider_server() as (url,calls):
        save_ocr_config(OcrConfig(mode='vision',base_url=url+'/v1',model='test-vision'))
        result=AutoOcrEngine(image_engine=ConfiguredImageEngine()).extract(content=mixed_pdf(),document_id=uuid4(),version_id=uuid4())
        assert result.ocr_mode=='hybrid' and len(result.pages)==2
        assert result.pages[0].text.startswith('Digital source paragraph')
        assert result.pages[1].page_number==2 and 'dự toán' in result.pages[1].text
        assert len(calls)==1
        image_url=calls[0][1]['messages'][1]['content'][1]['image_url']['url']
        assert base64.b64decode(image_url.split(',')[1]).startswith(b'\x89PNG')
        assert result.pages[1].confidence is None and result.confidence.page_average is None
        assert any('invent' in warning for warning in result.warnings)
        assert (isolated_application_data/'.configured').exists() is False


def test_tesseract_failure_falls_back_only_when_enabled(isolated_application_data,monkeypatch):
    def unavailable(*a,**k): raise OcrEngineError('Tesseract is unavailable')
    monkeypatch.setattr(Pdf2ImageTesseractEngine,'extract',unavailable)
    with provider_server() as (url,calls):
        config=OcrConfig(mode='tesseract',base_url=url+'/v1',model='test-vision');save_ocr_config(config)
        engine=AutoOcrEngine(image_engine=ConfiguredImageEngine())
        with pytest.raises(OcrEngineError,match='Page 2'):
            engine.extract(content=mixed_pdf(),document_id=uuid4(),version_id=uuid4())
        assert not calls
        config.mode='tesseract_then_vision';save_ocr_config(config)
        result=engine.extract(content=mixed_pdf(),document_id=uuid4(),version_id=uuid4())
        assert result.engine=='vision:test-vision' and len(calls)==1


@pytest.mark.parametrize('text,finish', [('', 'stop'),('[UNREADABLE]', 'stop'),('[BLANK]', 'stop'),('partial text','length'),('```text\nhello\n```','stop')])
def test_vision_rejects_empty_unreadable_or_truncated_output(text,finish,monkeypatch):
    @contextmanager
    def reply(*a,**k):
        class Response:
            def read(self):return json.dumps({'choices':[{'finish_reason':finish,'message':{'content':text}}]}).encode()
        yield Response()
    monkeypatch.setattr('legal_platform.modules.ocr_service.vision.provider_urlopen',reply)
    with pytest.raises(OcrEngineError):VisionOcrEngine(OcrConfig(mode='vision',model='test')).transcribe_image(b'test')


def test_ocr_settings_are_independent_and_keys_do_not_move(isolated_application_data):
    isolated_application_data.mkdir(parents=True,exist_ok=True)
    (isolated_application_data/'.local-mode').write_text('local')
    config=OcrConfig(mode='vision',base_url='http://127.0.0.1:11434/v1',model='vision',api_key='synthetic-secret')
    save_ocr_config(config)
    assert load_ocr_config().api_key=='synthetic-secret'
    assert 'api_key' not in load_ocr_config().safe_dict()
    assert (isolated_application_data/'.local-mode').exists()
    updated=merge_ocr_config(config,{'base_url':'http://192.168.1.40:11434/v1','allow_lan':True})
    assert updated.api_key=='' and config.api_key=='synthetic-secret'
    assert merge_ocr_config(config,{'model':'other'}).api_key=='synthetic-secret'
    with pytest.raises(ValueError):merge_ocr_config(config,{'allow_lan':'false'})


def test_vision_page_limit_rejects_before_sending_images(isolated_application_data):
    import pymupdf
    with provider_server() as (url,calls):
        save_ocr_config(OcrConfig(mode='vision',base_url=url+'/v1',model='test',max_vision_pages=1))
        with pymupdf.open() as pdf:
            pdf.new_page();pdf.new_page();content=pdf.tobytes()
        with pytest.raises(OcrEngineError,match='vision-page limit'):
            ConfiguredImageEngine().extract(content=content,document_id=uuid4(),version_id=uuid4())
        assert not calls


def test_successful_tesseract_does_not_send_page_to_fallback(isolated_application_data,monkeypatch):
    from legal_platform.modules.ocr_service.models import OcrResult, OcrPage, OcrConfidence
    monkeypatch.setattr(Pdf2ImageTesseractEngine,'extract',lambda *a,**k: OcrResult(
        pages=[OcrPage(page_number=1,text='Local recognition',confidence=.9)],
        confidence=OcrConfidence(page_average=.9,page_min=.9),warnings=['Check numbers.']))
    with provider_server() as (url,calls):
        save_ocr_config(OcrConfig(mode='tesseract_then_vision',base_url=url+'/v1',model='test'))
        result=AutoOcrEngine(image_engine=ConfiguredImageEngine()).extract(content=mixed_pdf(),document_id=uuid4(),version_id=uuid4())
        assert not calls and result.engine=='tesseract'
        assert result.pages[1].text=='Local recognition' and result.pages[1].page_number==2
        assert result.confidence.page_average==.9 and 'Page 2: Check numbers.' in result.warnings


def test_provider_response_size_is_bounded():
    from legal_platform.provider_http import _BoundedResponse, MAX_RESPONSE_BYTES
    class Response:
        def read(self, size):
            assert size==MAX_RESPONSE_BYTES+1
            return b'x'*size
    with pytest.raises(URLError,match='size limit'):_BoundedResponse(Response()).read()
