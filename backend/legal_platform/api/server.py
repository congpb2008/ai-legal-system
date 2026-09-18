"""HTTP routes and shared services for the Cheroot WSGI application.

The legacy request-handler class remains a route adapter for compatibility.
Production traffic enters through the bounded WebApplication WSGI boundary.
"""

from __future__ import annotations

import json

import mimetypes

import os
import threading

import traceback

from http.server import HTTPServer, BaseHTTPRequestHandler

from socketserver import ThreadingMixIn
from legal_platform.paths import asset_root

from pathlib import Path

from typing import Any, Optional

from urllib.parse import urlparse, parse_qs

from legal_platform.api.handlers import (

    AdminHandler,

    AnswerHandler,

    AuthHandler,

    DocumentHandler,

    HealthHandler,

    SearchHandler,

    SetupHandler,

    UploadHandler,

    VaultHandler,

)

from legal_platform.api.models import ApiError, ApiResponse, ErrorCategory
from legal_platform.api.router import ApiRouter

# Path to the frontend static files

_FRONTEND_DIR = asset_root() / "frontend"

class _RequestHandler(BaseHTTPRequestHandler):

    """HTTP request handler that routes to API domain handlers or serves static files."""

    # Shared handler instances (set by create_app)

    auth_handler: AuthHandler = AuthHandler()

    vault_handler: VaultHandler = VaultHandler()

    document_handler: DocumentHandler = DocumentHandler()

    upload_handler: UploadHandler = UploadHandler()

    search_handler: SearchHandler = SearchHandler()

    answer_handler: AnswerHandler = AnswerHandler()

    admin_handler: AdminHandler = AdminHandler()

    health_handler: HealthHandler = HealthHandler()

    setup_handler: SetupHandler = SetupHandler()

    # ------------------------------------------------------------------

    # Routing

    # ------------------------------------------------------------------

    def _route(self, method: str) -> None:

        """Parse the path and dispatch to the appropriate handler."""

        parsed = urlparse(self.path)

        path = parsed.path.rstrip("/")

        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        # Operational probes are available at their conventional root paths
        # as advertised by startup output, while /api/* aliases remain
        # backward compatible for the Web UI client.
        if path in ("/health", "/ready", "/live"):
            api_path = path
        elif not path.startswith("/api"):
            self._serve_static(path)
            return
        else:
            api_path = path[len("/api"):] or "/"

        # Read body for POST/PATCH/PUT

        body: dict[str, Any] = {}

        if method in ("POST", "PATCH", "PUT"):

            content_len = int(self.headers.get("Content-Length", 0))

            if content_len > 0:

                # Check if this is a multipart/form-data request

                content_type = self.headers.get("Content-Type", "")

                if content_type.startswith("multipart/form-data"):

                    raw = self.rfile.read(content_len)

                    # Parse multipart/form-data manually

                    body = self._parse_multipart_formdata(raw, content_type)

                else:

                    raw = self.rfile.read(content_len)

                    if raw:

                        try:

                            body = json.loads(raw)

                        except json.JSONDecodeError:

                            self._send_error(

                                ApiError(

                                    code="INVALID_JSON",

                                    message="Request body is not valid JSON.",

                                    category=ErrorCategory.VALIDATION,

                                ),

                                status=400,

                            )

                            return

        # Extract auth token

        token = self._get_token()

        try:

            response = self._dispatch(method, api_path, params, body, token)

        except Exception as exc:

            traceback.print_exc()

            response = ApiResponse.err_response(

                ApiError(

                    code="INTERNAL_ERROR",

                    message="An internal error occurred. Please check the server logs.",

                    category=ErrorCategory.INTERNAL,

                ),

                status=500,

            )

        self._send_response(response)

    def _dispatch(
        self,
        method: str,
        path: str,
        params: dict[str, str],
        body: dict[str, Any],
        token: Optional[str],
    ) -> ApiResponse:
        """Dispatch a request to the appropriate handler method."""
        router = getattr(self, "router", None)
        if router is None:
            router = ApiRouter(
                auth_handler=getattr(self, "auth_handler", None),
                vault_handler=getattr(self, "vault_handler", None),
                document_handler=getattr(self, "document_handler", None),
                upload_handler=getattr(self, "upload_handler", None),
                search_handler=getattr(self, "search_handler", None),
                answer_handler=getattr(self, "answer_handler", None),
                admin_handler=getattr(self, "admin_handler", None),
                health_handler=getattr(self, "health_handler", None),
                setup_handler=getattr(self, "setup_handler", None),
            )
        return router.dispatch(method, path, params, body, token)

    # ------------------------------------------------------------------

    # HTTP method handlers

    # ------------------------------------------------------------------

    def do_GET(self) -> None:

        self._route("GET")

    def do_POST(self) -> None:

        self._route("POST")

    def do_PATCH(self) -> None:

        self._route("PATCH")

    def do_DELETE(self) -> None:

        self._route("DELETE")

    def do_PUT(self) -> None:

        self._route("PUT")

    # ------------------------------------------------------------------

    # Helpers

    # ------------------------------------------------------------------

    def _parse_multipart_formdata(self, raw: bytes, content_type: str) -> dict[str, Any]:

        """Parse multipart/form-data request body.

        Args:

            raw: Raw request body bytes.

            content_type: Content-Type header value.

        Returns:

            Dict with form fields and files.

        """

        # Extract boundary from Content-Type

        if "boundary=" not in content_type:

            return {}

        boundary = content_type.split("boundary=")[1].strip().encode()

        result: dict[str, Any] = {}

        # Split into parts by boundary delimiter

        delimiter = b"--" + boundary

        parts = raw.split(delimiter)

        for part in parts:

            # Skip preamble/epilogue and empty parts

            if not part or len(part) < 10:

                continue

            # Strip leading CRLF that follows the boundary

            if part.startswith(b"\r\n"):

                part = part[2:]

            # Find end of headers

            header_end = part.find(b"\r\n\r\n")

            if header_end == -1:

                continue

            headers_raw = part[:header_end]

            body_content = part[header_end + 4:]

            # Strip trailing CRLF that precedes the closing boundary

            if body_content.endswith(b"\r\n"):

                body_content = body_content[:-2]

            headers = headers_raw.decode('utf-8', errors='ignore')

            # Parse Content-Disposition

            cd_line = ""

            for line in headers.split("\r\n"):

                if "content-disposition:" in line.lower():

                    cd_line = line

            if not cd_line:

                continue

            params = {}

            for param in cd_line.split(";")[1:]:

                param = param.strip()

                if "=" in param:

                    key, value = param.split("=", 1)

                    params[key.strip().lower()] = value.strip().strip('"')

            field_name = params.get("name", "")

            # Store filename separately for file parts

            if "filename" in params:

                result["file"] = body_content

                result["__content_type__"] = headers.split("\r\n")[-1] if "\r\n" in headers else ""

                result["__filename__"] = params["filename"]  # Store the filename

            elif field_name:

                result[field_name] = body_content.decode('utf-8', errors='ignore')

        return result

    def _get_token(self) -> Optional[str]:

        """Extract Bearer token from Authorization header."""

        auth = self.headers.get("Authorization", "")

        if auth.startswith("Bearer "):

            return auth[len("Bearer "):]

        return None

    def _send_response(self, response: ApiResponse) -> None:

        """Serialize and send an ApiResponse as JSON."""

        payload = json.dumps(

            response.to_dict(),

            ensure_ascii=False,

            default=str,

        )

        self.send_response(response.status)

        self.send_header("Content-Type", "application/json; charset=utf-8")

        self.send_header("X-Request-Id", response.request_id)

        self.send_header("Access-Control-Allow-Origin", "*")

        self.send_header("X-Content-Type-Options", "nosniff")

        self.send_header("X-Frame-Options", "DENY")

        self.send_header("X-XSS-Protection", "0")  # modern browsers: disable legacy

        self.end_headers()

        self.wfile.write(payload.encode("utf-8"))

    def _send_error(self, error: ApiError, *, status: int) -> None:

        """Send an error response."""

        response = ApiResponse.err_response(error, status=status)

        self._send_response(response)

    def _serve_static(self, path: str) -> None:

        """Serve a static file from the frontend directory.

        Args:

            path: the URL path (e.g. "/", "/css/main.css", "/js/app.js").

        """

        # Default to index.html for root and SPA routes

        if path == "" or path == "/":

            path = "/index.html"

        # Resolve the file path (prevent directory traversal)

        try:

            rel = Path(path.lstrip("/"))

            # Security: ensure the resolved path is within FRONTEND_DIR

            abs_path = (_FRONTEND_DIR / rel).resolve()

            abs_path.relative_to(_FRONTEND_DIR.resolve())

        except (ValueError, RuntimeError):

            self._send_error(

                ApiError(code="FORBIDDEN", message="Invalid path.",

                         category=ErrorCategory.AUTHORIZATION),

                status=403,

            )

            return

        if not abs_path.is_file():

            # SPA fallback: serve index.html for unknown routes

            index_path = _FRONTEND_DIR / "index.html"

            if index_path.is_file():

                self._send_static_file(index_path)

            else:

                self._send_error(

                    ApiError(code="NOT_FOUND", message="File not found.",

                             category=ErrorCategory.NOT_FOUND),

                    status=404,

                )

            return

        self._send_static_file(abs_path)

    def _send_static_file(self, file_path: Path) -> None:

        """Send a static file with the correct MIME type."""

        mime_type, _ = mimetypes.guess_type(str(file_path))

        if mime_type is None:

            mime_type = "application/octet-stream"

        try:

            content = file_path.read_bytes()

        except OSError:

            self._send_error(

                ApiError(code="INTERNAL_ERROR", message="Failed to read file.",

                         category=ErrorCategory.INTERNAL),

                status=500,

            )

            return

        self.send_response(200)

        self.send_header("Content-Type", mime_type)

        self.send_header("Content-Length", str(len(content)))

        self.send_header("Cache-Control", "no-cache")

        self.send_header("X-Content-Type-Options", "nosniff")

        self.send_header("X-Frame-Options", "DENY")

        self.end_headers()

        self.wfile.write(content)

    def log_message(self, format: str, *args: Any) -> None:

        """Suppress default HTTP log output (use structured logging instead)."""

        pass

class PlatformAPI:

    """The Platform API server.

    Wraps an HTTPServer with all platform handlers wired in.

    """

    def __init__(

        self,

        host: str = "0.0.0.0",

        port: int = 8080,

    ):

        self.host = host

        self.port = port

        self._server: Optional[HTTPServer] = None
        self._configuration_lock = threading.RLock()

        # Create a single shared, persistent runtime graph.

        self._init_shared_deps()

    def _init_shared_deps(self) -> None:

        """Create shared service instances that all handlers will use."""

        from legal_platform.modules.document_registry.service import DocumentRegistry

        from legal_platform.modules.vault.service import VaultService

        from legal_platform.modules.upload_service.service import UploadService

        from legal_platform.modules.ocr_service.service import OcrService

        from legal_platform.modules.parser.service import ParserService

        from legal_platform.modules.chunking.service import ChunkingService

        from legal_platform.modules.embedding.service import EmbeddingService

        from legal_platform.modules.vector_index.service import VectorIndexService

        from legal_platform.modules.retrieval.service import RetrievalService

        from legal_platform.modules.reranker.service import RerankerService

        from legal_platform.modules.generation.service import GenerationService

        from legal_platform.modules.citation.service import CitationBuilderService
        from legal_platform.modules.observability.jobs import JobMonitor

        project_root = Path(__file__).resolve().parents[3]
        from legal_platform.paths import data_root as resolve_data_root
        data_root = resolve_data_root()
        db_path = data_root / "db" / "legal_platform.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        from legal_platform.storage.db import connect_thread_local
        self._shared_db = connect_thread_local(db_path)
        self._auth = AuthHandler(conn=self._shared_db, data_dir=data_root)

        # Create the repository with persistent DB first, then pass it to registry

        from legal_platform.modules.document_registry.repository import SqliteDocumentRepository

        self._persistent_repo = SqliteDocumentRepository(conn=self._shared_db)

        self._registry = DocumentRegistry(repo=self._persistent_repo)
        self._jobs = JobMonitor(conn=self._registry.repo.conn)
        self._recovered_jobs = self._jobs.recover_interrupted_jobs()
        from legal_platform.modules.document_registry.processing import ProcessingState
        for document in self._registry.list_documents(limit=10000):
            processing = self._registry.get_processing(document.id)
            if processing and processing not in (ProcessingState.UPLOADED, ProcessingState.READY, ProcessingState.FAILED, ProcessingState.ARCHIVED):
                self._registry.transition_processing(document.id, ProcessingState.FAILED, user_id='system', failure_reason='Processing was interrupted by a server restart. Choose Retry to resume.')
        self._vault = VaultService(registry=self._registry, conn=self._registry.repo.conn)
        self._registry.vault = self._vault
        self._upload = UploadService(
            registry=self._registry,
            vault_resolver=self._vault,
        )
        from legal_platform.modules.upload_service.file_storage import LocalFileStorage
        self._upload.storage = LocalFileStorage(base_path=data_root / "files")
        self._ocr = OcrService(registry=self._registry)
        self._parser = ParserService(registry=self._registry, ocr_service=self._ocr)
        self._chunking = ChunkingService(registry=self._registry, parser_service=self._parser)
        # Embeddings use the same configured Ollama host/key as generation by
        # default, while allowing an independent model/endpoint via explicit
        # environment variables.  The native engine normalizes an optional
        # OpenAI-compatible /v1 suffix.
        from legal_platform.modules.embedding.engine import OllamaEmbeddingEngine
        from legal_platform.modules.generation.provider import load_config
        provider_config = load_config()
        embedding_engine = self._build_embedding_engine(provider_config)
        self._embedding = EmbeddingService(
            registry=self._registry,
            engine=embedding_engine,
        )
        self._vector_index = VectorIndexService(registry=self._registry)
        self._vector_index.rebuild()
        self._retrieval = RetrievalService(registry=self._registry, vector_index=self._vector_index, embedding_service=self._embedding)
        self._reranker = RerankerService(registry=self._registry, retrieval_service=self._retrieval)
        self._generation = GenerationService(registry=self._registry, reranker_service=self._reranker)
        self._citation = CitationBuilderService(
            registry=self._registry,
            parser_service=self._parser,
        )
        from legal_platform.modules.document_registry.pipeline import DocumentPipeline
        self._pipeline = DocumentPipeline(
            registry=self._registry, storage=self._upload.storage, ocr=self._ocr,
            parser=self._parser, chunking=self._chunking, embedding=self._embedding,
            vector_index=self._vector_index,
        )
        from legal_platform.modules.generation.provider import is_configured
        if (
            "LEGAL_PLATFORM_EMBEDDING_BASE_URL" in os.environ
            or is_configured()
        ):
            self._ready_reconciliation = self._pipeline.reconcile_ready_documents()
        else:
            self._ready_reconciliation = {}

    @staticmethod
    def _build_embedding_engine(provider_config):
        """Build the native Ollama embedder from the coherent runtime config."""
        from legal_platform.modules.embedding.engine import OllamaEmbeddingEngine

        from legal_platform.modules.embedding.engine import LocalKeywordEmbedder
        from legal_platform.modules.generation.provider import is_configured
        if not is_configured() and not os.environ.get('LEGAL_PLATFORM_EMBEDDING_BASE_URL'):
            return LocalKeywordEmbedder()
        return OllamaEmbeddingEngine(
            allow_lan=provider_config.allow_lan,
            base_url=os.environ.get(
                "LEGAL_PLATFORM_EMBEDDING_BASE_URL",
                provider_config.base_url,
            ),
            api_key=os.environ.get(
                "LEGAL_PLATFORM_EMBEDDING_API_KEY",
                provider_config.api_key,
            ),
            model=os.environ.get(
                "LEGAL_PLATFORM_EMBEDDING_MODEL",
                provider_config.embedding_model,
            ),
            timeout_seconds=float(
                os.environ.get(
                    "LEGAL_PLATFORM_EMBEDDING_TIMEOUT",
                    str(provider_config.timeout_seconds),
                )
            ),
        )

    def _refresh_embedding_from_provider_config(self, provider_config) -> None:
        """Apply setup-wizard changes to ingestion/search without a restart."""
        from legal_platform.modules.document_registry.processing import ProcessingState
        with self._configuration_lock:
            previous = self._embedding.engine
            updated = self._build_embedding_engine(provider_config)
            self._embedding.engine = updated
            signature = lambda e: (e.MODEL_NAME, e.MODEL_VERSION, e.DIMENSION)
            if signature(previous) != signature(updated):
                for document in self._registry.list_documents(limit=10000):
                    if document.status.value == 'ACTIVE' and self._registry.get_processing(document.id) == ProcessingState.READY:
                        self._vector_index.delete_document_entries(document.id)
                        self._registry.requeue_processing(document.id, ProcessingState.UPLOADED, user_id='system', reason='Search mode or model changed')
                        self._jobs.ensure_pending_job('pipeline', str(document.id))

    def _start_processing_worker(self) -> None:
        """Start the background document processing worker."""
        import threading
        from legal_platform.modules.document_registry.processing import ProcessingState

        if getattr(self, "_worker_thread", None) and self._worker_thread.is_alive():
            return
        self._worker_stop = threading.Event()
        
        def worker():
            """Process documents that are in UPLOADED state."""
            while not self._worker_stop.is_set():
                try:
                    docs = self._registry.list_documents(limit=10000)
                    pending_docs = []
                    for doc in docs:
                        proc_state = self._registry.get_processing(doc.id)
                        if proc_state and proc_state.value == "UPLOADED":
                            pending_docs.append((doc, proc_state))
                    
                    if not pending_docs:
                        self._worker_stop.wait(2)
                        continue
                    
                    for doc_obj, _ in pending_docs:
                        if self._worker_stop.is_set():
                            break
                        doc_id = doc_obj.id
                        job = self._jobs.ensure_pending_job(
                            "pipeline",
                            str(doc_id),
                            metadata={"requested_by": "background-worker"},
                        )
                        try:
                            self._jobs.start_job(job.job_id)
                        except ValueError:
                            # Another request/worker owns the active claim.
                            continue
                        try:
                            with self._configuration_lock:
                                count = self._pipeline.process(doc_id)
                            self._jobs.complete_job(job.job_id)
                            print(f"Processed: {doc_obj.title} ({count} index entries)")
                        except Exception as exc:
                            reason = (
                                self._registry.get_processing_failure_reason(doc_id)
                                or str(exc)
                                or "Document processing failed"
                            )[:500]
                            self._jobs.fail_job(
                                job.job_id,
                                reason,
                            )
                            print(f"  X Processing failed for document {doc_id}: {reason}")
                    
                except Exception as e:
                    print(f"Processing worker error: {e}")
                
                self._worker_stop.wait(2)
        
        self._worker_thread = threading.Thread(target=worker, daemon=True)
        self._worker_thread.start()
        print("  X Background processing worker started")

    def start(self) -> None:

        """Start the API server (blocking)."""

        handler_cls = create_app(

            auth_handler=self._auth,

            vault_handler=VaultHandler(vault_service=self._vault),

            document_handler=DocumentHandler(
                registry=self._registry,
                vault_service=self._vault,
                vector_index=self._vector_index,
                file_storage=self._upload.storage,
                ocr_service=self._ocr,
                parser_service=self._parser,
            ),

            upload_handler=UploadHandler(
                upload_service=self._upload,
                job_monitor=self._jobs,
            ),

            search_handler=SearchHandler(

                retrieval_service=self._retrieval,

                reranker_service=self._reranker,

                vault_service=self._vault,

            ),

            answer_handler=AnswerHandler(

                generation_service=self._generation,
                ocr_service=self._ocr,

                citation_service=self._citation,

                vault_service=self._vault,

            ),

            admin_handler=AdminHandler(

                registry=self._registry,

                upload_service=self._upload,

                ocr_service=self._ocr,

                parser_service=self._parser,

                chunking_service=self._chunking,

                embedding_service=self._embedding,

                vector_index=self._vector_index,

                pipeline=self._pipeline,

                vault_service=self._vault,

                job_monitor=self._jobs,

            ),

            health_handler=HealthHandler(
                registry=self._registry,
                storage=self._upload.storage,
                vector_index=self._vector_index,
                embedding_service=self._embedding,
                worker_alive=lambda: bool(
                    getattr(self, "_worker_thread", None)
                    and self._worker_thread.is_alive()
                ),
            ),

            setup_handler=SetupHandler(
                on_config_saved=self._refresh_embedding_from_provider_config,
            ),

        )

        self.router = ApiRouter(
            auth_handler=getattr(handler_cls, "auth_handler", None),
            vault_handler=getattr(handler_cls, "vault_handler", None),
            document_handler=getattr(handler_cls, "document_handler", None),
            upload_handler=getattr(handler_cls, "upload_handler", None),
            search_handler=getattr(handler_cls, "search_handler", None),
            answer_handler=getattr(handler_cls, "answer_handler", None),
            admin_handler=getattr(handler_cls, "admin_handler", None),
            health_handler=getattr(handler_cls, "health_handler", None),
            setup_handler=getattr(handler_cls, "setup_handler", None),
        )
        from legal_platform.web import WebApplication
        from cheroot.wsgi import Server
        self._application = WebApplication(self.router, self)
        self._server = Server((self.host, self.port), self._application, numthreads=8, max=16,
                              timeout=30, shutdown_timeout=5, request_queue_size=32)
        import logging
        self._server.error_log = lambda message='', level=20, traceback=False: logging.log(level, message, exc_info=traceback)
        self._server.max_request_body_size = 40 * 1024 * 1024
        self._server.max_request_header_size = 16 * 1024
        cert, key = os.environ.get('LEGAL_PLATFORM_TLS_CERT'), os.environ.get('LEGAL_PLATFORM_TLS_KEY')
        if bool(cert) != bool(key):
            raise ValueError('Both TLS certificate and key are required.')
        if cert:
            from cheroot.ssl.builtin import BuiltinSSLAdapter
            self._server.ssl_adapter = BuiltinSSLAdapter(cert, key)
        self._start_processing_worker()
        print(f"Legal Platform: {'https' if cert else 'http'}://{self.host}:{self.port}")
        try:
            self._server.start()
        finally:
            self._worker_stop.set()

    def stop(self) -> None:

        """Stop the server."""

        if hasattr(self, "_worker_stop"):
            self._worker_stop.set()

        if self._server:

            self._server.stop()

        worker = getattr(self, "_worker_thread", None)
        if worker and worker.is_alive():
            worker.join(timeout=5)

        if hasattr(self, "_shared_db"):
            if not worker or not worker.is_alive():
                self._shared_db.close()

def create_app(

    *,

    auth_handler: "AuthHandler | None" = None,

    vault_handler: "VaultHandler | None" = None,

    document_handler: "DocumentHandler | None" = None,

    upload_handler: "UploadHandler | None" = None,

    search_handler: "SearchHandler | None" = None,

    answer_handler: "AnswerHandler | None" = None,

    admin_handler: "AdminHandler | None" = None,

    health_handler: "HealthHandler | None" = None,

    setup_handler: "SetupHandler | None" = None,

) -> type[_RequestHandler]:

    """Create a configured request handler class with injected dependencies.

    Usage::

        handler_cls = create_app(...)

        server = HTTPServer(("0.0.0.0", 8080), handler_cls)

        server.serve_forever()

    """

    handler_cls = type("InstallationHandlers", (_RequestHandler,), {})

    if auth_handler is not None:

        handler_cls.auth_handler = auth_handler

    if vault_handler is not None:

        handler_cls.vault_handler = vault_handler

    if document_handler is not None:

        handler_cls.document_handler = document_handler

    if upload_handler is not None:

        handler_cls.upload_handler = upload_handler

    if search_handler is not None:

        handler_cls.search_handler = search_handler

    if answer_handler is not None:

        handler_cls.answer_handler = answer_handler

    if admin_handler is not None:

        handler_cls.admin_handler = admin_handler

    if health_handler is not None:

        handler_cls.health_handler = health_handler

    if setup_handler is not None:

        handler_cls.setup_handler = setup_handler

    return handler_cls
