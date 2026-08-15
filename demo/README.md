# Demo Dataset

This directory contains a small, deterministic demo dataset for demonstrating the Legal Knowledge Platform.

## Contents

| File | Description |
|------|-------------|
| `sample-decision-15-2026.pdf` | A fictional Vietnamese legal Decision (Quyết định 15/2026/QĐ-NH) about server procurement regulations. Clearly fictional sample data. |
| `generate-sample-doc.py` | Script to regenerate the sample PDF (requires `pymupdf`). |
| `load-demo.sh` | Script to load the demo data into a running server instance. |

## Sample Document

The sample document is a fictional Decision from the State Bank of Vietnam (Ngân hàng Nhà nước Việt Nam). It contains:

- **Title:** Quyết định 15/2026/QĐ-NH — Quy chế mua sắm máy chủ
- **Issuing authority:** Ngân hàng Nhà nước Việt Nam
- **Document number:** 15/2026/QĐ-NH
- **Effective date:** 01 June 2026
- **Structure:** 6 Articles covering scope, applicability, minimum hardware requirements, approval process, unit responsibilities, and effectiveness

### Articles

| Article | Topic |
|---------|-------|
| Điều 1 | Phạm vi điều chỉnh (Scope) |
| Điều 2 | Đối tượng áp dụng (Applicability) |
| Điều 3 | Yêu cầu cấu hình tối thiểu (Minimum hardware requirements) |
| Điều 4 | Quy trình phê duyệt (Approval process) |
| Điều 5 | Trách nhiệm của các đơn vị (Unit responsibilities) |
| Điều 6 | Hiệu lực thi hành (Effectiveness) |

## Loading the Demo Dataset

### Prerequisites

1. Start the server (see `docs/user-guide/en/02-quick-start.md`)
2. Ensure `curl` and `python3` are available

### Load

```bash
bash demo/load-demo.sh
```

Or with a custom base URL:

```bash
bash demo/load-demo.sh http://localhost:9000
```

The script:
1. Logs in (any credentials work in the MVP)
2. Creates a demo vault "Demo Legal Documents" (DEPARTMENT)
3. Uploads the sample decision document

### Important MVP Note

The current MVP does **not** automatically process uploaded documents. After upload, the document is registered but **not searchable** until processing is manually triggered via the Admin panel:

1. Open the Web UI
2. Go to **⚙️ Quản trị** (Admin)
3. Click **Re-index**, **Re-embed**, and **Re-parse**

## Suggested Demo Queries

After loading and processing, try these searches:

- `quy định mua sắm máy chủ`
- `cấu hình tối thiểu máy chủ`
- `trách nhiệm phòng công nghệ thông tin`

And these questions:

- `Quy định cấu hình tối thiểu của máy chủ là gì?`
- `Trách nhiệm của Phòng Công nghệ Thông tin là gì?`
- `Gói thầu nào phải được Tổng Giám đốc phê duyệt?`

## Disclaimer

All data in this demo dataset is **fictional**. It does not contain real personal information, confidential data, copyrighted proprietary documents, credentials, API keys, or production data. It is provided solely for demonstration and testing purposes.