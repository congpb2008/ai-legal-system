# Search and Retrieval

This guide explains how to search for legal information in the platform.

---

## Overview

The platform provides three search modes:

| Mode | Description | Best For |
|------|-------------|----------|
| **Hybrid** | Combines keyword and semantic search | Most queries (recommended) |
| **Semantic** | Finds documents by meaning and concept | Exploratory research |
| **Keyword** | Finds documents by exact word matches | Known citations or terms |

---

## Performing a Search

### Via the Web Interface

1. Click **🔍 Tra cứu** (Search) in the sidebar
2. Select a search mode from the dropdown
3. Type your query
4. Press `Enter` or click **Tìm kiếm** (Search)

### Via the API

```bash
# Hybrid search (recommended)
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "server procurement requirements", "top_k": 20}'

# Semantic search
curl -X POST http://localhost:8080/api/v1/search/semantic \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "server procurement requirements"}'

# Keyword search
curl -X POST http://localhost:8080/api/v1/search/keyword \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Điều 1 mua sắm máy chủ"}'
```

---

## Understanding Search Results

Each search result contains:

```
Kết quả #1
Điều 1. Phạm vi điều chỉnh: Quy chế này quy định việc mua sắm máy chủ.
[95%]  [📋 Sao chép]
```

| Field | Description |
|-------|-------------|
| **Rank** | Position in the results (1 = most relevant) |
| **Canonical reference** | Legal reference (e.g., "Điều 1", "Khoản 2") |
| **Preview** | Text excerpt with highlighted search terms |
| **Score** | Relevance percentage (higher = more relevant) |
| **Copy citation** | Copies the reference for use in documents |

### Score Interpretation

| Score | Meaning |
|-------|---------|
| 80–100% | Highly relevant — strong match |
| 50–79% | Moderately relevant — partial match |
| Below 50% | Weakly relevant — may not be useful |

---

## Search Parameters

### Via the API

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | string | (required) | The search query |
| `top_k` | integer | 20 | Maximum number of results |
| `vault_id` | UUID | null | Restrict to a specific vault |
| `document_id` | UUID | null | Restrict to a specific document |

### Example with Filters

```bash
# Search within a specific vault
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

curl -X POST http://localhost:8080/api/v1/search \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query": "procurement rules",
    "vault_id": "YOUR_VAULT_ID",
    "top_k": 10
  }'
```

---

## How Search Works

The platform uses a **hybrid retrieval** approach:

1. **Query understanding** — the system identifies search intent
2. **Semantic search** — finds documents by meaning using vector embeddings
3. **Keyword search** — finds documents by exact word matching
4. **Fusion** — results are combined using Reciprocal Rank Fusion (RRF)
5. **Reranking** — results are scored and reordered for precision
6. **Deduplication** — redundant results are removed

```
Your Query
    ↓
[Semantic Search] ──→ [Keyword Search]
    ↓                       ↓
[Fusion (RRF)]
    ↓
[Reranker]
    ↓
[Final Results]
```

---

## Search Tips

### Write Natural Queries
The semantic search understands meaning, not just keywords:

```
✅ "What are the requirements for server procurement?"
✅ "Quy định về mua sắm máy chủ"
```

### Use Legal Terminology
Include legal references for better keyword results:

```
✅ "Điều 1 mua sắm máy chủ"
✅ "Khoản 2 Điều 3 quy chế mua sắm"
```

### Be Specific
More specific queries return better results:

```
✅ "Minimum configuration requirements for database servers"
❌ "servers"
```

### Use Hybrid Mode
Hybrid mode is recommended for most queries — it combines the strengths of both semantic and keyword search.

---

## Common Search Issues

### No Results Found
If you see "Không tìm thấy kết quả phù hợp":
- Try different keywords
- Use hybrid mode instead of keyword-only
- Ensure documents have been uploaded and indexed
- Check that you have access to the vault containing the documents

### Low Relevance Scores
If results have low scores:
- Try rephrasing your query
- Use more specific legal terminology
- Upload more relevant documents

---

## Next Steps

- Learn how to [ask questions](05-question-answering.md) and get AI-generated answers
- Explore [document management](06-document-management.md)
- Review [configuration options](07-configuration.md)