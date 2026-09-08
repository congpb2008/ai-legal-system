> Historical prototype documentation. For the implemented LAN release, use the [Windows quickstart](../../WINDOWS-QUICKSTART.md) and [maintainer guide](../../MAINTAINER-GUIDE.md). Account, setup, UI and deployment instructions below may be outdated.

# Hỏi đáp

Hướng dẫn này giải thích cách đặt câu hỏi và nhận câu trả lời dựa trên bằng chứng.

---

## Đặt câu hỏi

### Qua giao diện web

1. Nhấn **❓ Hỏi đáp** trên thanh sidebar
2. Nhập câu hỏi
3. Nhấn `Ctrl+Enter` hoặc **Gửi câu hỏi**

### Qua API

```bash
curl -X POST http://localhost:8080/api/v1/answers \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"query": "Quy định về mua sắm máy chủ là gì?"}'
```

---

## Hiểu câu trả lời

### Trạng thái

| Trạng thái | Ý nghĩa |
|-----------|---------|
| **SUCCESS** | Câu trả lời đầy đủ với bằng chứng |
| **PARTIAL** | Câu trả lời nhưng thiếu một số thông tin |
| **NO_EVIDENCE** | Không tìm thấy bằng chứng — không trả lời |
| **ERROR** | Lỗi xử lý |

### Ví dụ

```
Trạng thái: SUCCESS
Mức độ tin cậy: CAO (95%)

Theo Điều 1 của Quyết định số 15/2026/QĐ-NH, quy chế áp dụng cho các đơn vị
tham gia mua sắm, thẩm định và phê duyệt.

Trích dẫn
- **Điều 1** — Tài liệu 550e8400-...
- **Điều 2** — Tài liệu 550e8400-...
```

### Mức độ tin cậy

| Mức độ | Điểm | Ý nghĩa |
|--------|------|---------|
| **CAO** | 0.8–1.0 | Bằng chứng mạnh từ nhiều nguồn |
| **TRUNG BÌNH** | 0.5–0.79 | Bằng chứng vừa phải |
| **THẤP** | 0.0–0.49 | Bằng chứng yếu |

---

## Không có bằng chứng

Khi không tìm thấy bằng chứng:

```
Trạng thái: NO_EVIDENCE
Không tìm thấy bằng chứng
Không có tài liệu nào trong phạm vi truy xuất chứa thông tin liên quan.

Gợi ý:
- Hãy thử tải lên các tài liệu liên quan.
- Mở rộng phạm vi tìm kiếm.
- Diễn đạt lại câu hỏi.
```

Nền tảng **không bao giờ bịa đặt** thông tin. Nếu bằng chứng không đủ, hệ thống sẽ nói rõ.

---

## Mẹo đặt câu hỏi

### ✅ Nên
- Hỏi cụ thể về nội dung tài liệu
- Sử dụng thuật ngữ pháp lý
- Tham chiếu điều khoản cụ thể
- Hỏi một câu tại một thời điểm

Ví dụ:
```
"Điều 3 quy định gì về giới hạn mua sắm?"
"Trách nhiệm của phòng IT là gì?"
```

### ❌ Không nên
- Xin tư vấn pháp lý
- Hỏi ngoài phạm vi tài liệu
- Hỏi quá rộng
- Mong đợi hệ thống nhớ câu hỏi trước

---

## Giới hạn

| Giới hạn | Mô tả |
|----------|-------|
| **Không tư vấn pháp lý** | Chỉ hỗ trợ nghiên cứu |
| **Phụ thuộc tài liệu** | Câu trả lời chỉ tốt như tài liệu đã tải |
| **Không nhớ ngữ cảnh** | Mỗi câu hỏi độc lập |
| **Ưu tiên tiếng Việt** | Tối ưu cho tài liệu pháp lý Việt Nam |

---

## Tiếp theo

- [Quản lý tài liệu](06-quan-ly-tai-lieu.md)
- [Khắc phục sự cố](08-khac-phuc-su-co.md)