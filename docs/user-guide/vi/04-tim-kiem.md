# Tìm kiếm

Hướng dẫn này giải thích cách tra cứu thông tin pháp lý trong nền tảng.

---

## Chế độ tìm kiếm

| Chế độ | Mô tả | Phù hợp nhất |
|--------|-------|-------------|
| **Hybrid** | Kết hợp từ khóa và ngữ nghĩa | Hầu hết truy vấn (khuyến nghị) |
| **Semantic** | Tìm theo ý nghĩa và khái niệm | Nghiên cứu khám phá |
| **Keyword** | Tìm theo từ khóa chính xác | Trích dẫn hoặc thuật ngữ đã biết |

---

## Thực hiện tìm kiếm

### Qua giao diện web

1. Nhấn **🔍 Tra cứu** trên thanh sidebar
2. Chọn chế độ tìm kiếm
3. Nhập câu hỏi
4. Nhấn `Enter` hoặc **Tìm kiếm**

### Qua API

```bash
# Tìm kiếm Hybrid (khuyến nghị)
curl -X POST http://localhost:8080/api/v1/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "quy định mua sắm máy chủ", "top_k": 20}'

# Tìm kiếm Semantic
curl -X POST http://localhost:8080/api/v1/search/semantic \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "quy định mua sắm máy chủ"}'

# Tìm kiếm Keyword
curl -X POST http://localhost:8080/api/v1/search/keyword \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Điều 1 mua sắm máy chủ"}'
```

---

## Kết quả tìm kiếm

Mỗi kết quả bao gồm:

```
Kết quả #1
Điều 1. Phạm vi điều chỉnh: Quy chế này quy định việc mua sắm máy chủ.
[95%]  [📋 Sao chép]
```

| Trường | Mô tả |
|--------|-------|
| **Thứ hạng** | Vị trí trong kết quả (1 = liên quan nhất) |
| **Trích dẫn** | Tham chiếu pháp lý (ví dụ: "Điều 1") |
| **Nội dung** | Đoạn trích với từ khóa được tô sáng |
| **Điểm số** | Phần trăm liên quan (cao hơn = tốt hơn) |
| **Sao chép** | Sao chép trích dẫn vào clipboard |

### Giải thích điểm số

| Điểm | Ý nghĩa |
|------|---------|
| 80–100% | Rất liên quan |
| 50–79% | Tương đối liên quan |
| Dưới 50% | Ít liên quan |

---

## Mẹo tìm kiếm

### Viết câu hỏi tự nhiên
```
✅ "Quy định về mua sắm máy chủ là gì?"
✅ "Điều kiện để được phê duyệt mua sắm"
```

### Sử dụng thuật ngữ pháp lý
```
✅ "Điều 1 mua sắm máy chủ"
✅ "Khoản 2 Điều 3 quy chế mua sắm"
```

### Cụ thể hóa
```
✅ "Yêu cầu cấu hình tối thiểu cho máy chủ"
❌ "máy chủ"
```

---

## Không tìm thấy kết quả?

- Thử từ khóa khác
- Chuyển sang chế độ Hybrid
- Đảm bảo đã tải lên tài liệu
- Kiểm tra quyền truy cập kho tài liệu

---

## Tiếp theo

- [Hỏi đáp](05-hoi-dap.md)
- [Quản lý tài liệu](06-quan-ly-tai-lieu.md)