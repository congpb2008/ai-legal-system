# Hướng dẫn Cài đặt

Hướng dẫn này giải thích cách cài đặt Nền tảng Pháp lý trên hệ thống của bạn.

---

## Yêu cầu hệ thống

| Yêu cầu | Tối thiểu | Khuyến nghị |
|----------|-----------|-------------|
| Python | 3.12 | 3.12 trở lên |
| RAM | 2 GB | 4 GB trở lên |
| Dung lượng ổ đĩa | 500 MB | 2 GB |
| Hệ điều hành | Linux, macOS | Linux (Ubuntu 22.04+) |

---

## Bước 1: Kiểm tra Python

Mở terminal và kiểm tra phiên bản Python:

```bash
python3 --version
```

Kết quả mong đợi:
```
Python 3.12.3
```

Nếu chưa có Python 3.12, hãy cài đặt:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.12 python3.12-venv
```

---

## Bước 2: Tải dự án

Giải nén hoặc clone dự án:

```bash
cd legal-platform
```

---

## Bước 3: Tạo môi trường ảo

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Khi kích hoạt thành công, terminal sẽ hiển thị `(.venv)` ở đầu dòng.

---

## Bước 4: Cài đặt thư viện

Dự án được đóng gói dưới dạng package Python có thể cài đặt được. Từ thư mục gốc của dự án, cài đặt package (bao gồm các thư viện phụ thuộc) vào môi trường ảo:

```bash
pip install -e .
```

Lệnh này cài đặt package `legal-platform`, các thư viện phụ thuộc, và câu lệnh `legal-platform` để khởi động hệ thống. **Không cần thiết lập `PYTHONPATH`**.

> **Lưu ý:** Các thư viện chính bao gồm `pydantic`, `pymupdf`, `pdf2image`, và `pytesseract`. Để cài đặt thêm công cụ kiểm thử (`pytest`), dùng:
>
> ```bash
> pip install -e ".[test]"
> ```

> **Lưu ý:** OCR tài liệu quét (scan) yêu cầu thêm chương trình `tesseract` trên hệ thống. Xem [Khắc phục Sự cố](08-khac-phuc-su-co.md).

---

## Bước 5: Kiểm tra cài đặt

Chạy bộ kiểm thử:

```bash
python3 -m pytest
```

Kết quả mong đợi:
```
619 passed in 2.36s
```

Nếu tất cả 619 bài kiểm tra đều pass, việc cài đặt đã thành công.

---

## Bước 6: Cấu hình lưu trữ (Tùy chọn)

Mặc định, hệ thống lưu trữ dữ liệu **trong bộ nhớ tạm**. Dữ liệu sẽ mất khi tắt server. Xem [Cấu hình](07-cau-hinh.md) để thiết lập lưu trữ bền vững.

---

## Cấu trúc thư mục

```
legal-platform/
├── backend/legal_platform/   # Mã nguồn backend
│   ├── api/                  # API HTTP server
│   ├── contracts/            # Hợp đồng dữ liệu
│   ├── modules/              # Module nghiệp vụ
│   └── storage/              # Cơ sở dữ liệu
├── frontend/                 # Giao diện web
├── tests/                    # Bộ kiểm thử
└── docs/                     # Tài liệu
```

---

## Tiếp theo

Sau khi cài đặt xong, hãy xem [Bắt đầu nhanh](02-bat-dau-nhanh.md).