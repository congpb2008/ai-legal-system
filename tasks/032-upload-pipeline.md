# Task 032 — Upload Pipeline & Vault ID Contract Repair

## Objective

Fix the document upload flow.

Current real-world failure:

Uploading documents from the Web UI fails 100%.

The UI reports:

"Xem chi tiết thất bại"

with errors:

- 4. Mẫu số 4A E-HSMT hàng hóa 1 túi.docx: 'vault_id'
- 4. Mẫu số 4B E-HSMT hàng hóa 2 túi.docx: 'vault_id'
- 4. Mẫu số 4C_E-HSMST hàng hóa sơ tuyển.docx: 'vault_id'
- ~$ Mẫu số 4A E-HSMT hàng hóa 1 túi.docx: 'vault_id'

The repeated:

`'vault_id'`

error strongly suggests a mismatch between the frontend upload payload, API handler, upload service, and/or document/vault contract.

Task 032 is ONLY about fixing upload correctness.

Do NOT continue Task 029, 030, or 031.
Do NOT add unrelated features.
Do NOT redesign the architecture.

---

## 1. Read the authoritative contracts first

Read:

- architecture documentation
- document contract
- vault contract
- upload contract
- API documentation
- upload service
- document service
- vault service
- upload API handler
- frontend upload implementation
- frontend API client
- database/repository layer
- relevant tests

Trace the complete request:

```text
Web UI
→ frontend api.js
→ HTTP multipart/form-data
→ API handler
→ upload service
→ document/vault persistence
→ response
