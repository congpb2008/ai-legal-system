"""Legal Knowledge Platform.

A contract-driven legal knowledge platform: turns uploaded legal documents into
a canonical Knowledge Tree and generates evidence-grounded, traceable answers.

Package layout follows the architectural layers:

- ``legal_platform.contracts``   — stable canonical contracts (02-contracts/).
- ``legal_platform.storage``     — shared storage infrastructure (technology-agnostic).
- ``legal_platform.modules``    — one package per architectural module.

The authoritative source of truth is the specification under ``AI Legal Platform/``
(00-product, 01-domain, 02-contracts, 03-architecture, 04-decisions, design/, tasks/).
This package is the implementation; code follows documentation.
"""

__version__ = "0.2.2"
