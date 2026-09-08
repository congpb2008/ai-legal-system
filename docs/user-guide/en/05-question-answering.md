> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Question Answering

This guide explains how to ask questions and get evidence-based answers from the platform.

---

## Overview

The platform provides AI-powered question answering that is:

- **Evidence-based** — answers are generated only from retrieved documents
- **Traceable** — every claim is linked to its source citation
- **Confidence-rated** — the system tells you how confident it is
- **Honest about uncertainty** — if evidence is insufficient, the system says so

---

## Asking a Question

### Via the Web Interface

1. Click **❓ Hỏi đáp** (Ask) in the sidebar
2. Type your question in the text area
3. Press `Ctrl+Enter` or click **Gửi câu hỏi** (Send)

### Via the API

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

curl -X POST http://localhost:8080/api/v1/answers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "What are the server procurement requirements?"}'
```

---

## Understanding the Answer

### Answer Status

| Status | Meaning |
|--------|---------|
| **SUCCESS** | Answer generated with sufficient evidence |
| **PARTIAL** | Answer generated but some information is missing |
| **NO_EVIDENCE** | No relevant documents found — no answer generated |
| **ERROR** | An error occurred during processing |

### Example Answer

```
Status: SUCCESS
Confidence: HIGH (95%)

Kết quả tra cứu

Thông tin tìm thấy
Theo Điều 1 của Quyết định số 15/2026/QĐ-NH, quy chế áp dụng cho các đơn vị
tham gia mua sắm, thẩm định và phê duyệt.

Trích dẫn
- **Điều 1** — Document 550e8400-e29b-41d4-a716-446655440001
- **Điều 2** — Document 550e8400-e29b-41d4-a716-446655440001
```

### Answer Components

| Component | Description |
|-----------|-------------|
| **Status** | Whether the answer is complete |
| **Confidence** | How reliable the answer is (HIGH/MEDIUM/LOW) |
| **Content** | The generated answer text |
| **Citations** | Expandable source references |
| **Limitations** | Any caveats or missing information |

---

## Confidence Levels

The platform reports confidence based on evidence quality, not model confidence:

| Level | Score Range | Meaning |
|-------|-------------|---------|
| **HIGH** | 0.8–1.0 | Strong evidence from multiple sources |
| **MEDIUM** | 0.5–0.79 | Moderate evidence, may be incomplete |
| **LOW** | 0.0–0.49 | Weak evidence, consider uploading more documents |

The confidence bar shows the score visually:

```
[████████░░░░░░░░░░░░] 95%
```

---

## Exploring Citations

Each citation is expandable. Click on a citation to see:

- **Document ID** — the source document
- **Knowledge Node ID** — the specific article/clause
- **Source location** — the canonical reference (e.g., "Điều 1")

Citations are the foundation of the platform's traceability:

```
Answer → Citation → Knowledge Node → Knowledge Tree → Document Version → Original File
```

---

## No Evidence Answers

When the platform cannot find relevant evidence, it returns:

```
Status: NO_EVIDENCE
Confidence: LOW (0%)

Không tìm thấy bằng chứng
Không có tài liệu nào trong phạm vi truy xuất chứa thông tin liên quan
đến câu hỏi của bạn.

Gợi ý:
- Hãy thử tải lên các tài liệu liên quan.
- Mở rộng phạm vi tìm kiếm.
- Diễn đạt lại câu hỏi với từ khóa khác.
```

The platform **never fabricates** information. If evidence is insufficient, it clearly states so.

---

## Asking Effective Questions

### ✅ Do
- Ask specific questions about document content
- Use legal terminology from the documents
- Reference specific articles or clauses
- Ask one question at a time

Examples:
```
"What does Article 3 say about procurement limits?"
"Điều 5 quy định gì về trách nhiệm của phòng IT?"
"What are the exceptions to the server requirements?"
```

### ❌ Don't
- Ask for legal advice or opinions
- Ask about topics outside the uploaded documents
- Ask vague or overly broad questions
- Expect the system to remember previous questions

Examples of what NOT to ask:
```
❌ "What should I do in this legal situation?" (legal advice)
❌ "Tell me about everything in all documents" (too broad)
❌ "What did I ask yesterday?" (no conversation memory)
```

---

## Limitations

The platform has important limitations:

| Limitation | Description |
|------------|-------------|
| **No legal advice** | The platform assists research but does not provide legal opinions |
| **Document-dependent** | Answers are only as good as the uploaded documents |
| **No conversation memory** | Each question is independent — the system does not remember context |
| **Vietnamese primary** | The platform is optimized for Vietnamese legal documents |
| **MVP processing** | Documents must be fully processed (OCR → Parse → Embed → Index) before they are searchable |

---

## Next Steps

- Learn how to [manage documents](06-document-management.md)
- Review [configuration options](07-configuration.md)
- See [troubleshooting](08-troubleshooting.md) for common issues