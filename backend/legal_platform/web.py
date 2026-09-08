"""Bounded WSGI boundary for the LAN and HTTPS server."""
from __future__ import annotations
import io
import json
import logging
import mimetypes
import os
import re
import threading
import time
from collections import deque
from email.parser import BytesParser
from email.policy import default
from http import HTTPStatus
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs
from uuid import UUID, uuid4

from legal_platform.api.models import ApiResponse
from legal_platform.modules.vault.models import Permission
from legal_platform.paths import asset_root


class WebApplication:
    def __init__(self, handler_cls, platform):
        self.router = object.__new__(handler_cls)
        self.platform = platform
        self.auth = self.router.auth_handler
        self.conn = self.auth.conn
        self.conn.executescript('''CREATE TABLE IF NOT EXISTS answer_history (
            id TEXT PRIMARY KEY, user_id TEXT NOT NULL, question TEXT NOT NULL,
            answer_json TEXT NOT NULL, created_at REAL NOT NULL, feedback TEXT,
            note TEXT NOT NULL DEFAULT '');''')
        self.conn.commit()
        self._rates = {}
        self._rate_lock = threading.Lock()
        self._upload_lock = threading.Lock()

    def _limited(self, key, count, period=60):
        now = time.monotonic()
        with self._rate_lock:
            if len(self._rates) > 10000:
                self._rates = {k: v for k, v in self._rates.items() if v and v[-1] > now - 3600}
                if len(self._rates) > 10000:
                    return True
            queue = self._rates.setdefault(key, deque())
            while queue and queue[0] < now - period:
                queue.popleft()
            if len(queue) >= count:
                return True
            queue.append(now)
            return False

    def __call__(self, env, start_response):
        path = env.get('PATH_INFO', '/').rstrip('/') or '/'
        method = env.get('REQUEST_METHOD', 'GET')
        api_path = path[4:] if path.startswith('/api/') else path
        token = None
        auth_header = env.get('HTTP_AUTHORIZATION', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
        cookie = SimpleCookie()
        try:
            cookie.load(env.get('HTTP_COOKIE', ''))
        except Exception:
            pass
        if not token and cookie.get('legal_session'):
            token = cookie['legal_session'].value
        uid = self.auth.resolve_user(token)
        status_code, payload, headers = 200, b'', []
        try:
            if not path.startswith('/api/') and path not in ('/health', '/ready', '/live'):
                return self._static(path, method, start_response)
            public = api_path in ('/health', '/ready', '/live', '/v1/setup/status',
                                   '/v1/auth/login', '/v1/auth/signup', '/v1/auth/bootstrap', '/v1/auth/reset')
            if not public and not uid:
                response = self.auth.error('Please sign in.', 401, 'NOT_AUTHENTICATED')
            elif method not in ('GET', 'POST', 'PATCH', 'DELETE'):
                response = self.auth.error('Method not allowed.', 405)
            elif self._limited(('ip', env.get('REMOTE_ADDR', '')), 180):
                response = self.auth.error('Too many requests. Please wait a minute.', 429)
            elif method != 'GET' and env.get('HTTP_ORIGIN') and env['HTTP_ORIGIN'] != env.get('wsgi.url_scheme', 'http') + '://' + env.get('HTTP_HOST', ''):
                response = self.auth.error('Cross-site request rejected.', 403)
            elif method != 'GET' and cookie.get('legal_session') and not auth_header and env.get('HTTP_X_REQUESTED_WITH') != 'LegalPlatform':
                response = self.auth.error('Refresh the page and try again.', 403)
            elif api_path.startswith('/v1/auth/') and method == 'POST' and self._limited(('auth', env.get('REMOTE_ADDR', '')), 20):
                response = self.auth.error('Too many account requests. Please wait a minute.', 429)
            else:
                body = self._body(env, api_path) if method in ('POST', 'PATCH', 'DELETE') else {}
                params = {k: v[0] for k, v in parse_qs(env.get('QUERY_STRING', '')).items()}
                for name in ('limit', 'offset', 'top_k'):
                    if name in body:
                        body[name] = max(0 if name == 'offset' else 1, min(int(body[name]), 10000 if name == 'offset' else 100))
                    if name in params:
                        params[name] = str(max(0 if name == 'offset' else 1, min(int(params[name]), 10000 if name == 'offset' else 100)))
                if 'query' in body and (not isinstance(body['query'], str) or len(body['query']) > 4000):
                    raise ValueError('Questions must be text with at most 4,000 characters.')
                if api_path == '/v1/uploads' and method == 'POST':
                    with self._upload_lock:
                        quota = int(os.environ.get('LEGAL_PLATFORM_STORAGE_LIMIT_MB', '2048')) * 1024 * 1024
                        size = sum(p.stat().st_size for p in self.platform._upload.storage.base_path.rglob('*') if p.is_file())
                        incoming = body.get('file', b'')
                        if not incoming and body.get('content_base64'):
                            incoming = __import__('base64').b64decode(body['content_base64'], validate=True)
                        if len(incoming) > 25 * 1024 * 1024 or size + len(incoming) > quota:
                            response = self.auth.error('This server has reached its document storage limit. Contact your administrator.', 413)
                        else:
                            response = self.dispatch(method, api_path, params, body, token, uid)
                else:
                    response = self.dispatch(method, api_path, params, body, token, uid)
                if api_path == '/v1/auth/login' and response.success:
                    secure = '; Secure' if env.get('wsgi.url_scheme') == 'https' else ''
                    headers.append(('Set-Cookie', 'legal_session=' + response.data['token'] + '; Path=/; Max-Age=43200; HttpOnly; SameSite=Strict' + secure))
                if api_path == '/v1/auth/logout':
                    headers.append(('Set-Cookie', 'legal_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Strict'))
            status_code = response.status
            payload = json.dumps(response.to_dict(), ensure_ascii=False, default=str).encode('utf-8')
        except OverflowError as exc:
            status_code = 413
            payload = json.dumps(self.auth.error(str(exc), 413).to_dict()).encode()
        except json.JSONDecodeError:
            status_code = 400
            payload = json.dumps(self.auth.error('The request contains invalid JSON.', 400, 'INVALID_JSON').to_dict()).encode()
        except (ValueError, TypeError, KeyError) as exc:
            status_code = 400
            payload = json.dumps(self.auth.error('Check the submitted fields, IDs and dates.').to_dict()).encode()
        except Exception:
            logging.exception('Request failed: %s %s', method, api_path)
            status_code = 500
            payload = json.dumps(self.auth.error('The request could not be completed. Contact your administrator.', 500).to_dict()).encode()
        headers += self.headers() + [('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(payload)))]
        start_response(f'{status_code} {HTTPStatus(status_code).phrase}', headers)
        return [payload]

    @staticmethod
    def headers():
        return [('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                ('X-Frame-Options', 'DENY'), ('Referrer-Policy', 'no-referrer'),
                ('Permissions-Policy', 'camera=(), microphone=(), geolocation=()'),
                ('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")]

    def _static(self, path, method, start_response):
        root = (asset_root() / 'frontend').resolve()
        relative = 'index.html' if path == '/' else path.lstrip('/')
        target = (root / relative).resolve()
        if method not in ('GET', 'HEAD') or not target.is_relative_to(root) or not target.is_file():
            start_response('404 Not Found', self.headers() + [('Content-Type', 'text/plain')])
            return [b'Not found']
        data = target.read_bytes()
        content_type = {'.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html'}.get(target.suffix, mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
        start_response('200 OK', self.headers() + [('Content-Type', content_type + '; charset=utf-8'), ('Content-Length', str(len(data)))])
        return [data if method == 'GET' else b'']

    def _body(self, env, path):
        size = int(env.get('CONTENT_LENGTH') or 0)
        maximum = 35 * 1024 * 1024 if path == '/v1/uploads' else 128 * 1024
        if size < 0 or size > maximum:
            # Drain a bounded rejected body so Windows can deliver the 413 response.
            remaining = size if 0 < size <= 40 * 1024 * 1024 else 0
            while remaining:
                chunk = env['wsgi.input'].read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            raise OverflowError('The file is too large. Upload files of at most 25 MB.')
        raw = env['wsgi.input'].read(size)
        content_type = env.get('CONTENT_TYPE', '')
        if content_type.startswith('multipart/form-data') and path == '/v1/uploads':
            message = BytesParser(policy=default).parsebytes(b'Content-Type: ' + content_type.encode('ascii') + b'\r\nMIME-Version: 1.0\r\n\r\n' + raw)
            result = {}
            for part in message.iter_parts():
                name = part.get_param('name', header='content-disposition')
                value = part.get_payload(decode=True) or b''
                if part.get_filename():
                    if len(value) > 25 * 1024 * 1024:
                        raise OverflowError('Upload files of at most 25 MB.')
                    result['file'] = value
                    result['__filename__'] = part.get_filename()
                    result['mime_type'] = part.get_content_type()
                elif name and len(value) < 16000:
                    result[name] = value.decode('utf-8')
            return result
        if raw and not content_type.startswith('application/json'):
            raise ValueError('Use JSON or a file upload.')
        body = json.loads(raw) if raw else {}
        if not isinstance(body, dict):
            raise ValueError('JSON object required')
        return body

    def dispatch(self, method, path, params, body, token, uid):
        a = self.auth
        if path == '/v1/setup/status' and method == 'GET':
            from legal_platform.modules.generation.provider import is_configured
            return ApiResponse.ok(data={'needs_admin': a.needs_admin(), 'configured': is_configured(),
                'first_run': a.needs_admin(), 'mode': 'ai' if is_configured() else 'local',
                'signup': 'approval', 'max_upload_mb': 25})
        if path == '/v1/auth/bootstrap' and method == 'POST':
            return a.register(body, bootstrap=True)
        if path == '/v1/auth/signup' and method == 'POST':
            return a.register(body)
        if path == '/v1/auth/reset' and method == 'POST':
            return a.reset_password(body)
        if path in ('/health', '/live', '/ready'):
            original = self.router.health_handler.ready() if path == '/ready' else self.router.health_handler.live()
            return ApiResponse.ok(data={'status': 'ready' if path == '/ready' else 'alive'}) if original.success else a.error('Server is not ready.', 503)
        if not uid:
            return self.router._dispatch(method, path, params, body, token)
        if path == '/v1/account' and method == 'PATCH':
            return a.profile(uid, body)
        if path == '/v1/account/password' and method == 'POST':
            return a.change_password(uid, body)
        if path == '/v1/account/sessions' and method == 'GET':
            return a.sessions(uid, token)
        if path.startswith('/v1/account/sessions/') and method == 'DELETE':
            return a.revoke(uid, path.split('/')[-1])
        if path.startswith('/v1/accounts') or path == '/v1/invitations':
            if not a.is_admin(uid):
                return a.error('Administrator access required.', 403)
            if path == '/v1/accounts' and method == 'GET':
                return a.list_accounts()
            if path == '/v1/invitations' and method == 'POST':
                return a.issue_code('invite', email=str(body.get('email') or ''))
            if path.endswith('/reset-code') and method == 'POST':
                return a.issue_code('reset', uid=path.split('/')[-2])
            if method == 'PATCH':
                return a.update_account(uid, path.split('/')[-1], body)
        if path == '/v1/people' and method == 'GET':
            return ApiResponse.ok(data=[{k: r[k] for k in ('id', 'username', 'display_name')} for r in self.conn.execute("SELECT id,username,display_name FROM account WHERE state='active' ORDER BY display_name")])
        if re.fullmatch(r'/v1/vaults/[^/]+/members(?:/[^/]+)?', path):
            vid = UUID(path.split('/')[3])
            vault = self.platform._vault.get_vault(vid)
            if not vault or not vault.has_permission(uid, Permission.MANAGE):
                return a.error('You cannot manage this collection.', 403)
            if method == 'GET':
                members = [{'user_id': vault.owner, 'role': 'OWNER'}] + [{'user_id': m.user_id, 'role': m.role.value} for m in vault.members.values() if m.user_id != vault.owner]
                for m in members:
                    account = a.account(m['user_id'])
                    m['name'] = account['display_name'] if account else 'Legacy account'
                return ApiResponse.ok(data=members)
            target = body.get('user_id') if method == 'POST' else path.split('/')[-1]
            if target == vault.owner:
                return a.error('The owner cannot be removed through member settings.', 409)
            if method == 'DELETE':
                self.platform._vault.remove_member(vid, target)
            elif method == 'POST':
                row = a.account(target)
                role = body.get('role', 'VIEWER')
                if not row or row['state'] != 'active' or role not in ('VIEWER', 'CONTRIBUTOR', 'MANAGER'):
                    return a.error('Choose an active account and a valid role.')
                if vault.has_member(target):
                    self.platform._vault.update_member_role(vid, target, role=role)
                else:
                    self.platform._vault.add_member(vid, target, role=role)
            return ApiResponse.ok(data={'message': 'Sharing updated.'})
        if path == '/v1/history' and method == 'GET':
            rows = self.conn.execute('SELECT * FROM answer_history WHERE user_id=? ORDER BY created_at DESC LIMIT 100', (uid,))
            return ApiResponse.ok(data=[{'id': r['id'], 'question': r['question'], 'created_at': r['created_at'], 'feedback': r['feedback']} for r in rows if self._history_allowed(r, uid)])
        if path.startswith('/v1/history/'):
            row = self.conn.execute('SELECT * FROM answer_history WHERE id=? AND user_id=?', (path.split('/')[-1], uid)).fetchone()
            if not row or not self._history_allowed(row, uid):
                return a.error('Saved answer is unavailable or its collection access has changed.', 404)
            if method == 'DELETE':
                self.conn.execute('DELETE FROM answer_history WHERE id=? AND user_id=?', (row['id'], uid))
                self.conn.commit()
                return ApiResponse.ok(data={'message': 'Saved answer deleted.'})
            if method == 'PATCH':
                feedback = body.get('feedback')
                if feedback not in ('useful', 'wrong_source', 'outdated', 'incomplete', 'unsupported', None):
                    return a.error('Choose a feedback reason.')
                self.conn.execute('UPDATE answer_history SET feedback=?,note=? WHERE id=? AND user_id=?', (feedback, str(body.get('note') or '')[:2000], row['id'], uid))
                self.conn.commit()
            return ApiResponse.ok(data={'id': row['id'], 'question': row['question'], 'answer': json.loads(row['answer_json']), 'feedback': row['feedback']})
        if path in ('/v1/retry', '/v1/restore') and method == 'POST':
            from legal_platform.modules.document_registry.processing import ProcessingState
            did = UUID(body['document_id'])
            doc = self.platform._registry.get_document(did)
            if not doc or not self.platform._vault.check_permission(doc.vault_id, uid, Permission.MANAGE):
                return a.error('Collection manager access required.', 403)
            if path == '/v1/restore':
                self.platform._registry.restore_document(did, user_id=uid)
                self.platform._vector_index.set_document_status(did, 'ACTIVE')
            else:
                current = self.platform._registry.get_processing(did)
                if current not in (ProcessingState.FAILED, ProcessingState.READY):
                    return a.error('This document is already queued or processing.', 409)
                self.platform._vector_index.delete_document_entries(did)
                self.platform._registry.requeue_processing(did, ProcessingState.UPLOADED, user_id=uid, reason='User requested retry')
                self.platform._jobs.ensure_pending_job('pipeline', str(did))
            return ApiResponse.ok(data={'message': 'Document updated.'})
        if path == '/v1/setup/local' and method == 'POST':
            if not a.is_admin(uid):
                return a.error('Administrator access required.', 403)
            from legal_platform.modules.generation.provider import _data_dir, load_config
            (_data_dir() / '.local-mode').write_text('Local processing enabled by administrator.')
            self.platform._refresh_embedding_from_provider_config(load_config())
            return ApiResponse.ok(data={'message': 'Local mode enabled.'})
        if path == '/v1/vaults' and method == 'POST':
            body['organization_id'] = a.organization_id
        if path == '/v1/uploads' and method == 'POST' and body.get('replace_document_id'):
            from legal_platform.modules.document_registry.processing import ProcessingState
            from legal_platform.modules.upload_service.service import _sanitize_filename
            did = UUID(body['replace_document_id'])
            doc = self.platform._registry.get_document(did)
            if not doc or not self.platform._vault.check_permission(doc.vault_id, uid, Permission.MANAGE):
                return a.error('Collection manager access required.', 403)
            if self.platform._registry.get_processing(did) not in (ProcessingState.READY, ProcessingState.FAILED):
                return a.error('Wait for processing to finish before adding a version.', 409)
            content = body.get('file') or __import__('base64').b64decode(body.get('content_base64',''), validate=True)
            filename = body.get('__filename__') or body.get('filename', 'source.pdf')
            upload = self.platform._upload
            mime = upload._resolve_mime_type(filename, body.get('mime_type'))
            upload._validate(content, mime)
            stored = upload.storage.store(content=content, filename=_sanitize_filename(filename), mime_type=mime)
            updated = self.platform._registry.add_version(did, user_id=uid)
            self.platform._registry.save_version_source(did, updated.current_version.version_id, stored, uid, filename)
            self.platform._vector_index.delete_document_entries(did)
            self.platform._registry.requeue_processing(did, ProcessingState.UPLOADED, user_id=uid, reason='New source version uploaded')
            self.platform._jobs.ensure_pending_job('pipeline', str(did))
            return ApiResponse.ok(data={'document_id': str(did), 'version_id': str(updated.current_version.version_id)}, status=201)
        if path == '/v1/uploads' and method == 'POST':
            body['organization_id'] = a.organization_id
            body.setdefault('issuing_authority', 'Unspecified — review document metadata')
        if path == '/v1/answers' and method == 'POST':
            if self._limited(('ask', uid), 15):
                return a.error('You have reached the question limit for this minute. Please wait.', 429)
        response = self.router._dispatch(method, path, params, body, token)
        if path == '/v1/answers' and method == 'POST' and response.success:
            hid = str(uuid4())
            response.data['history_id'] = hid
            self.conn.execute('INSERT INTO answer_history (id,user_id,question,answer_json,created_at) VALUES (?,?,?,?,?)', (hid, uid, body['query'], json.dumps(response.data, ensure_ascii=False), time.time()))
            self.conn.execute('DELETE FROM answer_history WHERE user_id=? AND id NOT IN (SELECT id FROM answer_history WHERE user_id=? ORDER BY created_at DESC LIMIT 1000)', (uid, uid))
            self.conn.commit()
        return response

    def _history_allowed(self, row, uid):
        for citation in json.loads(row['answer_json']).get('citations', []):
            document = self.platform._registry.get_document(UUID(citation['document_id']))
            if not document or not self.platform._vault.check_permission(document.vault_id, uid, Permission.READ):
                return False
        return True
