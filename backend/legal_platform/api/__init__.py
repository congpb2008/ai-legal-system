"""Public API exports, loaded lazily to keep models independent of the server."""
from legal_platform.api.models import ApiResponse, ApiError, ErrorCategory, HealthStatus, PaginatedResponse

def __getattr__(name):
    if name in ('PlatformAPI', 'create_app'):
        from legal_platform.api import server
        return getattr(server, name)
    if name.endswith('Handler'):
        from legal_platform.api import handlers
        return getattr(handlers, name)
    raise AttributeError(name)
