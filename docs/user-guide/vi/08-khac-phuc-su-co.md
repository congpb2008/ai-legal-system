# Khắc phục Sự cố

Hướng dẫn này giúp bạn chẩn đoán và giải quyết các vấn đề thường gặp.

---

## Server không khởi động

### Cổng đã được sử dụng
```
Address already in use
```
Đổi cổng:
```bash
legal-platform --port 9090
```
Hoặc dùng biến môi trường:
```bash
LEGAL_PLATFORM_PORT=9090 legal-platform
```

### Chưa kích hoạt môi trường ảo
```
ModuleNotFoundError: No module named 'legal_platform'
```
```bash
source .venv/bin/activate
```

### Chưa cài đặt package
```
ModuleNotFoundError: No module named 'legal_platform'
```
```bash
pip install -e .
```

### Sai thư mục
Chạy từ thư mục gốc của dự án:
```bash
cd legal-platform
```

---

## Không đăng nhập được

MVP chấp nhận bất kỳ tên đăng nhập và mật khẩu nào:
```
Tên đăng nhập: admin
Mật khẩu: admin
```

Đảm bảo server đang chạy tại `http://localhost:8080`.

---

## Tải lên thất bại

| Lỗi | Nguyên nhân | Cách khắc phục |
|-----|-------------|----------------|
| Unsupported file type | Sai định dạng | Dùng PDF hoặc DOCX |
| Uploaded file is empty | File rỗng | Chọn file có nội dung |
| File too large | File quá lớn | Giảm kích thước dưới 100 MB |
| Vault not found | Sai mã kho | Tạo kho trước |

---

## Tìm kiếm không có kết quả

- Đã tải lên tài liệu chưa?
- Thử chế độ Hybrid thay vì Keyword
- Kiểm tra quyền truy cập kho tài liệu
- Thử từ khóa khác

---

## Mất dữ liệu khi khởi động lại

Mặc định, dữ liệu lưu trong bộ nhớ tạm. Để lưu trữ bền vững, xem [Cấu hình](07-cau-hinh.md).

---

## Xem log

Log được ghi ra stderr dưới dạng JSON:

```bash
legal-platform 2> server.log
```

---

## Xây dựng lại chỉ mục

```bash
# Xây dựng lại tất cả
curl -X POST http://localhost:8080/api/v1/reindex \
  -H "Authorization: Bearer $TOKEN" \
  -d '{}'

# Xây dựng lại một tài liệu
curl -X POST http://localhost:8080/api/v1/reindex \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"document_id": "ID_TÀI_LIỆU"}'
```

---

## Kiểm tra trạng thái hệ thống

```bash
curl http://localhost:8080/api/health
curl http://localhost:8080/api/ready
curl http://localhost:8080/api/live
```

---

## Vẫn gặp vấn đề?

- Xem [Câu hỏi thường gặp](09-cau-hoi-thuong-gap.md)
- Kiểm tra log server
- Xem Báo cáo Kiểm tra Tài liệu để biết các giới hạn đã biết