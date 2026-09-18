"""Real HTTP journeys for a fresh installation, using only synthetic documents."""
import base64
import io
import json
import socket
import threading
import time
import urllib.request
import urllib.error
import zipfile
from pathlib import Path
from uuid import UUID
import pytest
from legal_platform.api.server import PlatformAPI

PASSWORD = 'Synthetic testing passphrase 123'


def word_file(text):
    from xml.sax.saxutils import escape
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w') as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        paragraphs=''.join('<w:p><w:r><w:t>'+escape(p)+'</w:t></w:r></w:p>' for p in text.split('\n'))
        z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+paragraphs+'</w:body></w:document>')
    return output.getvalue()


@pytest.fixture
def live(isolated_application_data):
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    app=PlatformAPI(host='127.0.0.1',port=port)
    thread=threading.Thread(target=app.start,daemon=True);thread.start()
    base=f'http://127.0.0.1:{port}/api'
    def request(method,path,body=None,token=None,headers=None):
        request_headers={'Content-Type':'application/json',**(headers or {})}
        if token:request_headers['Authorization']='Bearer '+token
        data=json.dumps(body).encode() if body is not None else None
        req=urllib.request.Request(base+path,data=data,method=method,headers=request_headers)
        try:response=urllib.request.urlopen(req,timeout=15)
        except urllib.error.HTTPError as exc:response=exc
        with response:return response.status,json.loads(response.read()),dict(response.headers)
    for _ in range(100):
        try:
            if request('GET','/health')[0]==200:break
        except OSError:pass
        time.sleep(.05)
    code=(isolated_application_data/'setup-code.txt').read_text()
    try:yield app,request,code
    finally:app.stop();thread.join(timeout=10)


def bootstrap(request,code):
    status,data,_=request('POST','/v1/auth/bootstrap',{'username':'admin','display_name':'Test admin','password':PASSWORD,'code':code})
    assert status==201,data
    status,data,headers=request('POST','/v1/auth/login',{'username':'admin','password':PASSWORD})
    assert status==200,data
    assert 'HttpOnly' in headers['Set-Cookie'] and 'SameSite=Strict' in headers['Set-Cookie']
    return data['data']['token'],data['data']['user_id']


def test_vision_configuration_permissions_and_scan_ingestion(live):
    from test_vision_ocr import provider_server, mixed_pdf
    app,req,code=live
    token,admin=bootstrap(req,code)
    assert req('GET','/v1/ocr/config')[0]==401
    _,created,_=req('POST','/v1/auth/signup',{'username':'ocr-reader','password':PASSWORD})
    uid=created['data']['account']['id']
    assert req('PATCH','/v1/accounts/'+uid,{'state':'active'},token)[0]==200
    _,login,_=req('POST','/v1/auth/login',{'username':'ocr-reader','password':PASSWORD})
    assert req('GET','/v1/ocr/config',token=login['data']['token'])[0]==403
    with provider_server() as (url,calls):
        config={'mode':'vision','base_url':url+'/v1','model':'test-vision','api_key':'synthetic-ocr-secret'}
        assert req('POST','/v1/ocr/config',config,token)[0]==400
        config['consent']=True
        assert req('POST','/v1/ocr/config',config,token)[0]==200
        _,safe,_=req('GET','/v1/ocr/config',token=token)
        assert safe['data']['has_api_key'] and 'synthetic-ocr-secret' not in json.dumps(safe)
        _,status,_=req('GET','/v1/setup/status')
        assert status['data']['mode']=='local' and status['data']['ocr_mode']=='vision'
        _,vault,_=req('POST','/v1/vaults',{'name':'Scans','vault_type':'DEPARTMENT'},token)
        pdf=mixed_pdf()
        _,upload,_=req('POST','/v1/uploads',{'vault_id':vault['data']['id'],'title':'Scanned policy',
            'filename':'mixed.pdf','document_type':'INTERNAL_REGULATION','issuing_authority':'Synthetic fixture',
            'content_base64':base64.b64encode(pdf).decode()},token)
        did=upload['data']['document_id'];app._pipeline.process(UUID(did),user_id=admin)
        _,document,_=req('GET','/v1/documents/'+did,token=token)
        assert document['data']['processing_state']=='READY',document
        _,source,_=req('GET',f'/v1/documents/{did}/source?page=2&include_original=true',token=token)
        assert source['data']['page']['number']==2
        assert 'dự toán' in source['data']['page']['text'] and 'invent' in source['data']['extraction_warning']
        assert base64.b64decode(source['data']['content_base64'])==pdf
        assert len(calls)==1


def test_accounts_approval_sessions_and_single_use_recovery(live):
    app,req,code=live
    assert req('POST','/v1/auth/login',{'username':'admin','password':'anything'})[0]==401
    assert req('POST','/v1/auth/bootstrap',{'username':'attacker','password':PASSWORD,'code':'wrong'})[0]==403
    token,admin=bootstrap(req,code)
    assert req('POST','/v1/auth/bootstrap',{'username':'second','password':PASSWORD,'code':code})[0]==403
    status,pending,_=req('POST','/v1/auth/signup',{'username':'member','password':PASSWORD})
    assert status==201 and pending['data']['requires_approval']
    member=pending['data']['account']['id']
    assert req('POST','/v1/auth/login',{'username':'member','password':PASSWORD})[0]==403
    assert req('PATCH','/v1/accounts/'+member,{'state':'active'},token)[0]==200
    status,login,_=req('POST','/v1/auth/login',{'username':'member','password':PASSWORD})
    member_token=login['data']['token'];assert status==200
    assert req('GET','/v1/setup/config',token=member_token)[0]==403
    assert req('PATCH','/v1/accounts/'+admin,{'state':'disabled'},token)[0]==409
    status,recovery,_=req('POST','/v1/accounts/'+member+'/reset-code',{},token)
    assert status==200
    reset={'code':recovery['data']['code'],'new_password':'Changed testing passphrase 456'}
    assert req('POST','/v1/auth/reset',reset)[0]==200
    assert req('GET','/v1/auth/me',token=member_token)[0]==401
    assert req('POST','/v1/auth/reset',reset)[0]==400
    # Persisted credentials are salted hashes, not names or plaintext passwords.
    stored=app._auth.account(member)
    assert PASSWORD not in stored['password_hash'] and stored['password_hash'].startswith('scrypt$')


def test_upload_search_versions_history_and_access_revocation(live):
    app,req,code=live
    token,admin=bootstrap(req,code)
    status,vault,_=req('POST','/v1/vaults',{'name':'Procurement policies','vault_type':'DEPARTMENT'},token)
    assert status==201 or status==200,vault
    vid=vault['data']['id']
    original=word_file('QUY CHẾ MUA SẮM\nĐiều 1. Hồ sơ mua sắm\nHồ sơ mua sắm máy chủ phải có đề nghị, dự toán và phê duyệt của giám đốc.\nĐiều 2. Ngoại lệ\nTrường hợp khẩn cấp phải báo cáo bằng văn bản trong vòng ba ngày.')
    body={'vault_id':vid,'title':'Quy chế mua sắm máy chủ','document_type':'INTERNAL_REGULATION','issuing_authority':'Synthetic organization','filename':'procurement.docx','content_base64':base64.b64encode(original).decode()}
    status,uploaded,_=req('POST','/v1/uploads',body,token)
    assert status==201 or status==200,uploaded
    did=uploaded['data']['document_id']
    app._pipeline.process(UUID(did),user_id=admin)
    status,document,_=req('GET','/v1/documents/'+did,token=token)
    assert status==200,document
    assert document['data']['processing_state']=='READY',document
    version=document['data']['versions'][0]['version_id']
    status,answer,_=req('POST','/v1/answers',{'query':'Hồ sơ mua sắm máy chủ cần gì?','vault_id':vid},token)
    assert status==200,answer
    result=answer['data']
    assert result['citations'],result
    assert result['confidence'] is None
    assert 'dự toán' in result['response']['content']
    citation=result['citations'][0]
    status,source,_=req('GET',f'/v1/documents/{did}/source?version_id={version}&node_id={citation["knowledge_node_id"]}&include_original=true',token=token)
    assert status==200,source
    assert base64.b64decode(source['data']['content_base64'])==original
    status,invitation,_=req('POST','/v1/invitations',{},token)
    assert status==200
    status,new,_=req('POST','/v1/auth/signup',{'username':'colleague','password':PASSWORD,'code':invitation['data']['code']})
    assert status==201 and not new['data']['requires_approval']
    member=new['data']['account']['id']
    _,signed,_=req('POST','/v1/auth/login',{'username':'colleague','password':PASSWORD})
    colleague=signed['data']['token']
    assert req('GET','/v1/documents/'+did,token=colleague)[0]==403
    assert req('POST','/v1/vaults/'+vid+'/members',{'user_id':member,'role':'VIEWER'},token)[0]==200
    assert req('GET','/v1/documents/'+did,token=colleague)[0]==200
    _,saved,_=req('POST','/v1/answers',{'query':'Hồ sơ mua sắm máy chủ','vault_id':vid},colleague)
    hid=saved['data']['history_id']
    assert req('DELETE','/v1/vaults/'+vid+'/members/'+member,token=token)[0]==200
    assert req('GET','/v1/history/'+hid,token=colleague)[0]==404
    replacement=word_file('QUY CHẾ MỚI\nĐiều 1. Hồ sơ mua sắm\nHồ sơ mua sắm máy chủ mới phải có dự toán cập nhật và hai báo giá để xét duyệt.')
    status,revision,_=req('POST','/v1/uploads',{'replace_document_id':did,'filename':'revision.docx','content_base64':base64.b64encode(replacement).decode()},token)
    assert status==201,revision
    app._pipeline.process(UUID(did),user_id=admin)
    _,old,_=req('GET',f'/v1/documents/{did}/source?version_id={version}&include_original=true',token=token)
    assert base64.b64decode(old['data']['content_base64'])==original
    _,current,_=req('GET',f'/v1/documents/{did}/source?include_original=true',token=token)
    assert base64.b64decode(current['data']['content_base64'])==replacement
    assert current['data']['document_version_id']!=version


def test_cookie_csrf_and_request_limits(live):
    _,req,code=live
    token,uid=bootstrap(req,code)
    assert req('POST','/v1/vaults',{'name':'Forbidden'},headers={'Cookie':'legal_session='+token})[0]==403
    assert req('POST','/v1/vaults',{'name':'Forbidden'},token,headers={'Origin':'https://unrelated.example'})[0]==403
    assert req('POST','/v1/answers',{'query':'a'*4001},token)[0]==400
    assert req('POST','/v1/answers',{'query':'a'*140000},token)[0]==413


def test_encrypted_backup_roundtrip_and_tamper_rejection(live,tmp_path,isolated_application_data):
    from legal_platform.operations import backup,restore
    app,req,code=live
    token,uid=bootstrap(req,code)
    from legal_platform.modules.ocr_service.config import OcrConfig, save_ocr_config
    save_ocr_config(OcrConfig(mode='vision', model='test-vision', api_key='synthetic-ocr-secret', allow_lan=True))
    archive=backup(isolated_application_data,tmp_path/'library.legalbackup',PASSWORD)
    assert b'Synthetic testing' not in archive.read_bytes()
    with pytest.raises(ValueError):restore(archive,tmp_path/'wrong','wrong password of sufficient length')
    target=restore(archive,tmp_path/'restored',PASSWORD)
    restored_ocr=json.loads((target/'ocr_config.json').read_text())
    assert restored_ocr['api_key']=='synthetic-ocr-secret' and restored_ocr['allow_lan'] is True
    from legal_platform.accounts import AuthHandler
    from legal_platform.storage.db import connect_thread_local
    conn=connect_thread_local(target/'db/legal_platform.db')
    try:
        restored=AuthHandler(conn=conn,data_dir=target)
        assert restored.resolve_user(token) is None
        assert restored.login({'username':'admin','password':PASSWORD}).success
    finally:conn.close()
    with pytest.raises(ValueError):restore(archive,target,PASSWORD)
    content=bytearray(archive.read_bytes());content[-18]^=1
    (tmp_path/'tampered').write_bytes(content)
    with pytest.raises(ValueError):restore(tmp_path/'tampered',tmp_path/'tampered-out',PASSWORD)


def test_grounding_rejects_invented_quote_and_filters_dates():
    from legal_platform.grounding import verify_selections,applicable
    from legal_platform.contracts.retrieval import Evidence
    from legal_platform.modules.document_registry.service import DocumentRegistry
    from uuid import uuid4
    registry=DocumentRegistry()
    doc=registry.register_document(user_id='test',document_type='LAW',title='Synthetic rule',issuing_authority='Test',vault_id=uuid4(),organization_id=uuid4(),metadata={'effective_date':'2025-01-01','expiration_date':'2025-12-31'})
    e=Evidence(id=uuid4(),knowledge_node_id=uuid4(),document_id=doc.id,document_version_id=doc.current_version.version_id,score=.9,rank=1,text='Approval is required except in an emergency.')
    with pytest.raises(ValueError):verify_selections(json.dumps({'answerable':True,'passages':[{'evidence_id':str(e.id),'quote':'Approval is never required.'}]}),[e])
    assert verify_selections(json.dumps({'answerable':True,'passages':[{'evidence_id':str(e.id),'quote':'Approval is required'}]}),[e])[0].text.endswith('in an emergency.')
    assert applicable([e],registry,'2024-12-31')==[]
    assert applicable([e],registry,'2025-06-01')==[e]
    assert applicable([e],registry,'2026-01-01')==[]


def test_backup_share_fallback_preserves_other_files(live, tmp_path, isolated_application_data, monkeypatch):
    from legal_platform import operations
    _, req, code = live
    bootstrap(req, code)
    target = tmp_path / 'shared.legalbackup'
    other = tmp_path / 'shared.legalbackup.partial'
    other.write_bytes(b'Another backup in progress')
    def unsupported_link(*args):
        raise OSError('This share does not support hard links')
    monkeypatch.setattr(operations.os, 'link', unsupported_link)
    operations.backup(isolated_application_data, target, PASSWORD)
    original = target.read_bytes()
    with pytest.raises(ValueError, match='never overwritten'):
        operations.backup(isolated_application_data, target, PASSWORD)
    assert target.read_bytes() == original
    assert other.read_bytes() == b'Another backup in progress'
    restored = operations.restore(target, tmp_path / 'shared-restored', PASSWORD)
    assert (restored / 'db/legal_platform.db').is_file()
