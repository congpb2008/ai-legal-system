# Hướng dẫn Quản trị — Nền tảng Pháp lý

Hướng dẫn này dành cho người chịu trách nhiệm cài đặt, cấu hình, vận hành và bảo trì hệ thống Nền tảng Pháp lý.

---

## Tổng quan

Nền tảng Pháp lý là một ứng dụng Python độc lập. Bao gồm:
- **Backend** (`backend/legal_platform/`) — cung cấp REST API và phục vụ giao diện web
- **Frontend** (`frontend/`) — ứng dụng trang đơn tĩnh do backend phục vụ
- **SQLite** — lưu trữ metadata tài liệu và nhật ký kiểm toán (mặc định trong bộ nhớ tạm)
- **Hệ thống file** — lưu trữ file tải lên (mặc định trong thư mục tạm)

Ứng dụng chạy hoàn toàn ngoại tuyến, **không cần kết nối internet**.

---

## Cài đặt

### Yêu cầu

| Yêu cầu | Tối thiểu | Khuyến nghị |
|---------|-----------|-------------|
| Python | 3.12 | 3.12 trở lên |
| RAM | 2 GB | 4 GB trở lên |
| Dung lượng ổ đĩa | 500 MB | 2 GB |
| Hệ điều hành | Linux, macOS | Linux (Ubuntu 22.04+) |

### Cài đặt

```bash
# Tạo môi trường ảo
python3 -m venv .venv
source .venv/bin/activate

# Cài đặt package và thư viện
pip install -e .

# (Tùy chọn) Cài đặt công cụ kiểm thử
pip install -e ".[test]"
```

### Kiểm tra cài đặt

```bash
python -m pytest
```

Kết quả mong đợi: `628 passed`.

---

## Cấu hình

### Biến môi trường

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `LEGAL_PLATFORM_HOST` | `0.0.0.0` | Địa chỉ IP để lắng nghe |
| `LEGAL_PLATFORM_PORT` | `8080` | Cổng TCP |

Ví dụ:

```bash
export LEGAL_PLATFORM_HOST=127.0.0.1
export LEGAL_PLATFORM_PORT=9000
legal-platform
```

### Tham số dòng lệnh

```bash
legal-platform --host 127.0.0.1 --port 9000
```

---

## Khởi động

### Lệnh khởi động chính thức

```bash
legal-platform
```

Hoặc:

```bash
python -m legal_platform
```

### Chạy nền

```bash
nohup legal-platform > server.log 2>&1 &
```

### Kiểm tra hoạt động

Server in ra:

```
Platform API listening on http://0.0.0.0:8080
  Health:  http://0.0.0.0:8080/health
  API v1:  http://0.0.0.0:8080/v1/...
```

---

## Dừng server

Nhấn `Ctrl+C` trong terminal đang chạy server.

Với tiến trình nền:

```bash
pgrep -f "legal-platform"
kill <PID>
```

---

## Kiểm tra sức khỏe

| Endpoint | Mục đích |
|----------|----------|
| `GET /api/health` | Tổng quan sức khỏe hệ thống |
| `GET /api/ready` | Sẵn sàng phục vụ |
| `GET /api/live` | Tiến trình còn sống |

```bash
curl http://localhost:8080/api/health
```

---

## Nhật ký (Logs)

Ứng dụng ghi log JSON ra **stderr**:

```bash
legal-platform 2> server.log
```

Mức log: `DEBUG`, `INFO`, `WARN`, `ERROR`.

---

## Lưu trữ

### Mặc định (trong bộ nhớ tạm)

- Metadata tài liệu lưu trong SQLite bộ nhớ tạm
- File tải lên lưu trong thư mục tạm
- **Mất hết dữ liệu khi tắt server**

### Lưu trữ bền vững

> **CHƯA TRIỂN KHAI:** Lưu trữ bền vững chưa được tích hợp vào luồng khởi động mặc định. Cần thay đổi mã nguồn để cấu hình.

---

## Sao lưu và Phục hồi

> **CHƯA TRIỂN KHAI:** Chưa có cơ chế sao lưu tự động.

---

## Cập nhật ứng dụng

> **CHƯA TRIỂN KHAI:** Chưa có quy trình nâng cấp chính thức.

---

## Giới hạn MVP

- Quy trình xử lý tài liệu tự động chưa được kích hoạt
- Lưu trữ trong bộ nhớ tạm mặc định
- Chưa có xác thực thực sự
- Chưa có sao lưu/phục hồi tự động
- Chưa có TLS/HTTPS
- Chưa có giới hạn tốc độ
- Engine embedding tạm thời (chất lượng tìm kiếm ngữ nghĩa hạn chế)

---

## Tiếp theo

- [Hướng dẫn API](../../api-guide/vi/)
- [Hướng dẫn Phát triển](../../developer-guide/vi/)
- [Hướng dẫn Người dùng](../../user-guide/vi/)