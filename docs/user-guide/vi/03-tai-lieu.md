> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Tải lên Tài liệu

Hướng dẫn này giải thích cách tải lên tài liệu và hiểu về quy trình xử lý.

---

## Trước khi bắt đầu

### Yêu cầu
- Server đang chạy (xem [Bắt đầu nhanh](02-bat-dau-nhanh.md))
- Đã đăng nhập
- Có ít nhất một kho tài liệu

### Định dạng hỗ trợ

| Định dạng | Phần mở rộng | Ghi chú |
|-----------|-------------|---------|
| PDF | `.pdf` | Tài liệu số hoặc scan |
| Word | `.docx` | Tài liệu Microsoft Word |

> **Cảnh báo:** Các định dạng khác (`.doc`, `.txt`, `.png`, `.jpg`) chưa được hỗ trợ.

### Giới hạn kích thước
Tối đa **100 MB** mỗi file.

---

## Tải lên qua giao diện web

1. Nhấn **📤 Tải lên** trên thanh sidebar
2. Điền thông tin:

| Trường | Mô tả | Ví dụ |
|--------|-------|-------|
| Tệp tin | File PDF hoặc DOCX | `quy-che.pdf` |
| Tiêu đề | Tên mô tả | `Quy chế mua sắm máy chủ` |
| Cơ quan ban hành | Đơn vị ban hành | `Phòng CNTT` |
| Loại tài liệu | Thể loại | `INTERNAL_REGULATION` |
| Kho tài liệu | Nơi lưu trữ | `Tài liệu của tôi` |

3. Nhấn **Tải lên**

### Kết quả mong đợi

```
✅ Tải lên thành công
Mã tài liệu: 550e8400-e29b-41d4-a716-446655440000
Kích thước: 245.3 KB
```

---

## Tải lên qua API

```bash
# 1. Đăng nhập lấy token
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"user_id": "admin", "password": "admin"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['data']['token'])")

# 2. Mã hóa file base64
BASE64=$(base64 -w0 quy-che.pdf)

# 3. Tải lên
curl -X POST http://localhost:8080/api/v1/uploads \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{
    \"filename\": \"quy-che.pdf\",
    \"content_base64\": \"$BASE64\",
    \"title\": \"Quy chế mua sắm máy chủ\",
    \"document_type\": \"INTERNAL_REGULATION\",
    \"issuing_authority\": \"Phòng CNTT\",
    \"vault_id\": \"550e8400-e29b-41d4-a716-446655440000\"
  }"
```

---

## Quy trình xử lý tài liệu

Sau khi tải lên, tài liệu sẽ trải qua quy trình:

```
Tải lên → OCR → Phân tích → Cây tri thức → Chunk → Embedding → Index → Sẵn sàng
```

> **Lưu ý:** Trong phiên bản MVP hiện tại, tài liệu được đăng ký nhưng quy trình xử lý tự động chưa được kích hoạt. Tài liệu có thể chưa sẵn sàng để tìm kiếm.

---

## Kiểm tra trạng thái

```bash
curl -X GET http://localhost:8080/api/v1/uploads/ID_TÀI_LIỆU \
  -H "Authorization: Bearer $TOKEN"
```

Kết quả:
```json
{
  "success": true,
  "data": {
    "document_id": "550e8400-...",
    "title": "Quy chế mua sắm máy chủ",
    "status": "ACTIVE",
    "processing_state": "UPLOADED"
  }
}
```

---

## Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách khắc phục |
|-----|-------------|----------------|
| Unsupported file type | Sai định dạng file | Chuyển sang PDF hoặc DOCX |
| Uploaded file is empty | File rỗng | Chọn file có nội dung |
| Vault ... does not exist | Sai mã kho | Tạo kho tài liệu trước |

---

## Tiếp theo

- [Tìm kiếm](04-tim-kiem.md)
- [Hỏi đáp](05-hoi-dap.md)
- [Quản lý tài liệu](06-quan-ly-tai-lieu.md)