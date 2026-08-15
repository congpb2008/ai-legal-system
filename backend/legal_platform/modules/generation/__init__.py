"""Generation Service (tasks/011-generation.md, module Generation).

The Generation Service converts retrieved evidence into a clear, structured
response for the user. It explains retrieved evidence — it never invents legal
facts, never retrieves additional evidence, and never reads original documents.
"""

from legal_platform.modules.generation.provider import (
    GenerationProvider,
    GenerationProviderError,
    OpenAICompatibleProvider,
    ProviderConfig,
    is_configured,
    is_first_run,
    load_config,
    mark_configured,
    save_config,
)
from legal_platform.modules.generation.service import GenerationService

__all__ = [
    "GenerationService",
    "GenerationProvider",
    "GenerationProviderError",
    "OpenAICompatibleProvider",
    "ProviderConfig",
    "load_config",
    "save_config",
    "is_configured",
    "is_first_run",
    "mark_configured",
]