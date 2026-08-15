# Quản lý Tài liệu

Hướng dẫn này giải thích cách quản lý tài liệu và kho tài liệu.

---

## Kho tài liệu (Vault)

### Kho tài liệu là gì?

Kho tài liệu là nơi chứa tài liệu, cung cấp:
- **Cách ly** — tài liệu ở kho khác nhau không thể truy cập lẫn nhau
- **Tổ chức** — nhóm tài liệu theo phòng ban, dự án
- **Bảo mật** — kiểm soát truy cập theo từng kho

### Các loại kho

| Loại | Mô tả | Ví dụ |
|------|-------|-------|
| **Common** | Kiến thức dùng chung | Luật, quy định quốc gia |
| **Department** | Tài liệu phòng ban | Chính sách IT, quy trình HR |
| **Project** | Tài liệu dự án | Dự án di chuyển hệ thống |
| **Personal** | Tài liệu cá nhân | Tài liệu riêng tư |

### Tạo kho mới

1. Nhấn **📁 Kho tài liệu**
2. Nhấn **+ Tạo mới**
3. Nhập tên và loại

---

## Tài liệu

### Xem danh sách

Nhấn **📄 Tài liệu** để xem tất cả tài liệu.

### Trạng thái tài liệu

| Trạng thái | Ý nghĩa |
|-----------|---------|
| **ACTIVE** | Tài liệu có sẵn |
| **ARCHIVED** | Tài liệu lưu trữ |

### Xóa tài liệu

> **Cảnh báo:** Xóa tài liệu là vĩnh viễn và không thể khôi phục.

```bash
curl -X DELETE http://localhost:8080/api/v1/documents/ID_TÀI_LIỆU \
  -H "Authorization: Bearer $TOKEN"
```

---

## Phân quyền

### Vai trò

| Vai trò | Quyền hạn |
|---------|-----------|
| **VIEWER** | Xem tài liệu |
| **CONTRIBUTOR** | Xem, tải lên, cập nhật |
| **MANAGER** | Xem, tải lên, cập nhật, xóa, chia sẻ, quản lý |
| **OWNER** | Toàn quyền (bao gồm quản lý thành viên) |

---

## Vòng đời tài liệu

```
Tạo → Hoạt động → Lưu trữ
```

Tài liệu không bao giờ bị xóa vĩnh viễn trong hoạt động bình thường.

---

## Mẹo

- Tạo kho theo phòng ban hoặc dự án
- Sử dụng tiêu đề mô tả cho tài liệu
- Phân quyền tối thiểu cần thiết
- Lưu trữ tài liệu cũ thay vì xóa

---

## Tiếp theo

- [Cấu hình](07-cau-hinh.md)
- [Khắc phục sự cố](08-khac-phuc-su-co.md)