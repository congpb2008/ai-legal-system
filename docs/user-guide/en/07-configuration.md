# Configuration

This guide explains the configuration options available in the platform.

---

## Overview

The platform is designed to work with minimal configuration. Most settings are configured directly in the code rather than through external configuration files. This guide documents the key configuration points.

> **Note:** A formal configuration system (environment variables, config files) is planned for a future release. Currently, configuration requires code changes.

---

## Server Configuration

### Host and Port

The server listens on `0.0.0.0:8080` by default. To change this at startup:

```bash
legal-platform --host 127.0.0.1 --port 9000
```

Or via environment variables:

```bash
LEGAL_PLATFORM_HOST=127.0.0.1 LEGAL_PLATFORM_PORT=9000 legal-platform
```

If using the `PlatformAPI` class directly in code:

```python
from legal_platform.api.server import PlatformAPI

# Listen on all interfaces, port 8080
api = PlatformAPI(host='0.0.0.0', port=8080)

# Listen only on localhost, port 9000
api = PlatformAPI(host='127.0.0.1', port=9000)
```

### Maximum Upload Size

The default maximum upload size is **100 MB**. To change this, modify the `UploadService` initialization:

```python
from legal_platform.modules.upload_service.service import UploadService

# Allow up to 500 MB uploads
upload_service = UploadService(max_upload_bytes=500 * 1024 * 1024)
```

---

## Storage Configuration

### Database

By default, the platform uses **in-memory SQLite databases**. This means all data is lost when the server stops.

To use a persistent SQLite database, modify the `DocumentRegistry` initialization:

```python
from legal_platform.storage.db import connect
from legal_platform.modules.document_registry.repository import SqliteDocumentRepository

# Use a persistent database file
conn = connect('/path/to/data/platform.db')
repo = SqliteDocumentRepository(conn=conn)
```

### File Storage

Uploaded files are stored in a temporary directory by default. To use a persistent directory:

```python
from legal_platform.modules.upload_service.file_storage import LocalFileStorage

# Store files in a specific directory
file_storage = LocalFileStorage(base_path='/path/to/data/uploads')
```

---

## Search Configuration

### Number of Search Results

The default number of search results is 20. To change this:

```bash
curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "server procurement", "top_k": 50}'
```

### Search Threshold

The minimum relevance score for search results is configurable in the Reranker:

```python
from legal_platform.modules.reranker.reranker import Reranker, RerankerConfig

# Only show results with score >= 0.5
config = RerankerConfig(min_score=0.5)
reranker = Reranker(config=config)
```

---

## Reranker Configuration

The Reranker has several configuration options:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_evidence` | 8 | Maximum number of evidence items in the final set |
| `min_score` | 0.0 | Minimum score threshold for evidence retention |
| `diversity_weight` | 0.2 | Weight for diversity in scoring (0–1) |
| `freshness_weight` | 0.1 | Weight for document freshness (0–1) |
| `authority_weight` | 0.1 | Weight for document authority (0–1) |
| `redundancy_threshold` | 0.9 | Similarity threshold for deduplication |

Example:

```python
from legal_platform.modules.reranker.reranker import Reranker, RerankerConfig

config = RerankerConfig(
    max_evidence=10,
    min_score=0.3,
    diversity_weight=0.3,
)
reranker = Reranker(config=config)
```

---

## Citation Builder Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_confidence` | 0.3 | Minimum confidence for citation acceptance |
| `max_claims_per_sentence` | 5 | Maximum claims to detect per sentence |
| `enable_unsupported_detection` | True | Detect unsupported claims |
| `enable_retry` | True | Signal generation retry on unsupported claims |

---

## Alert Configuration

The Observability module includes default alert rules:

| Rule | Metric | Threshold | Severity |
|------|--------|-----------|----------|
| Search latency warning | `retrieval.latency_ms` | > 2000ms | WARNING |
| Search latency critical | `retrieval.latency_ms` | > 5000ms | CRITICAL |
| Generation latency warning | `generation.latency_ms` | > 5000ms | WARNING |
| Generation latency critical | `generation.latency_ms` | > 15000ms | CRITICAL |
| OCR failure rate | `ocr.failure_count` | > 5 | WARNING |
| Parser failure rate | `parser.failure_count` | > 5 | WARNING |
| Citation coverage low | `citation.coverage` | < 0.5 | WARNING |

To add custom alert rules:

```python
from legal_platform.modules.observability.alerts import AlertRule, AlertSeverity

rule = AlertRule(
    name="custom_rule",
    metric="api.latency_ms",
    operator="gt",
    threshold=3000.0,
    severity=AlertSeverity.WARNING,
    message_template="API latency {value}ms exceeds {threshold}ms",
)
alert_manager.add_rule(rule)
```

---

## Logging Configuration

The structured logger writes JSON-formatted log entries to stderr. The default log level is `INFO`.

To change the log level:

```python
from legal_platform.modules.observability.logger import StructuredLogger

# Only show WARN and above
logger = StructuredLogger("my-service", "my-module", level="WARN")
```

Available log levels: `DEBUG`, `INFO`, `WARN`, `ERROR`

---

## Evaluation Configuration

The Evaluation Runner supports configurable regression thresholds:

```python
# Detect regressions with 10% threshold
result = runner.detect_regressions(current_report, baseline_report, threshold=0.10)
```

The default threshold is 0.05 (5%).

---

## Release Checklist

The release checklist includes approximately 90 checks across 18 categories. All critical checks must pass before a release can be approved.

The checklist is created programmatically. See `modules/release/checklist.py` for the full list.

---

## Environment Variables

> **Planned:** Environment variable support is not yet implemented. Configuration currently requires code changes.

---

## Next Steps

- See [troubleshooting](08-troubleshooting.md) for common issues
- Check the [FAQ](09-faq.md) for frequently asked questions