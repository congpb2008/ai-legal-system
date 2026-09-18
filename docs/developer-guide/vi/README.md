> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Hướng dẫn Phát triển — Nền tảng Pháp lý

Hướng dẫn này dành cho lập trình viên muốn làm việc trên mã nguồn Nền tảng Pháp lý.

---

## Cấu trúc thư mục

```
├── backend/legal_platform/     # Backend Python package
│   ├── api/                    # HTTP API server
│   ├── contracts/              # Data contracts
│   ├── modules/                # Business logic modules
│   └── storage/                # SQLite + audit log
├── frontend/                   # Web UI
│   ├── index.html              # SPA shell
│   ├── css/main.css            # Styles
│   └── js/                     # API client + app logic
├── tests/                      # Test suite (628 tests)
├── docs/                       # Documentation
├── tasks/                      # Task specifications
├── 00-product/                 # Product specifications
├── 01-domain/                  # Domain model
├── 02-contracts/               # Contract specifications
├── 03-architecture/            # Architecture documents
├── 04-decisions/               # ADRs
├── design/                     # Design documents
└── examples/                   # Contract examples
```

---

## Thiết lập môi trường

### Yêu cầu

- Python 3.12 trở lên
- Git

### Cài đặt

```bash
git clone <repository-url> legal-platform
cd legal-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[test]"
```

### Chạy kiểm thử

```bash
python -m pytest
```

Kết quả mong đợi: **628 tests passed**.

### Chạy ứng dụng

```bash
legal-platform
```

Hoặc:

```bash
python -m legal_platform
```

---

## Phát triển Frontend

Frontend là ứng dụng JavaScript thuần (vanilla JS), không cần build. Chỉnh sửa file trong `frontend/` và refresh trình duyệt.

- `frontend/js/api.js` — Lớp `ApiClient` gọi API backend
- `frontend/js/app.js` — Logic ứng dụng: render trang, routing, auth, form

---

## Phát triển Backend

Mỗi module trong `backend/legal_platform/modules/` có một trách nhiệm duy nhất và giao tiếp qua contracts.

### Thêm module mới

1. Tạo `backend/legal_platform/modules/<tên>/`
2. Implement service class
3. Thêm test trong `tests/test_<tên>.py`
4. Kết nối module vào API handler nếu cần

---

## Kiểm thử

- Sử dụng `pytest` (cấu hình trong `pyproject.toml`)
- File test đặt trong `tests/`, đặt tên `test_<module>.py`
- Import từ `legal_platform...` (package đã được cài đặt)
- Dùng SQLite trong bộ nhớ cho test cơ sở dữ liệu

---

## Đóng gói

```bash
pip install -e .
```

Package name: `legal-platform`. Console script: `legal-platform`. Module: `legal_platform`.

---

## Tài liệu liên quan

- [Kiến trúc](../../../03-architecture/architecture.md)
- [Module Specifications](../../../03-architecture/module-specifications.md)
- [Contracts](../../../02-contracts/)
- [ADRs](../../../04-decisions/)
- [developer-guide.md](../../../developer-guide.md) (hướng dẫn gốc)