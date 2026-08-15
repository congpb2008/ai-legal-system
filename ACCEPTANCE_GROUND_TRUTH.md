# Demo acceptance ground truth

Prepared directly from the original files under `Luat-DT-QH15/` before black-box testing. This is verification evidence, not legal advice.

## Ask acceptance set

| ID | Class | Natural Vietnamese question | Expected source-grounded fact |
|---|---|---|---|
| D1 | Direct | Luật số 90/2025/QH15 có hiệu lực từ ngày nào? | Law 90, final implementation provision: 01-07-2025. |
| D2 | Direct | Nghị định 214 giải thích đấu thầu bền vững gồm những yếu tố nào? | Decree 214, Article 2(2): environment, society, and economy; integrated through planning, dossier preparation/evaluation, contracting, and contract performance. |
| D3 | Direct | Thông tư 79/2025/TT-BTC hướng dẫn những nhóm nội dung chính nào? | Circular 79, Article 1: publication/provision of procurement information, templates for plans and online procurement dossiers, evaluation/approval forms, and related online contractor-selection forms. |
| D4 | Direct | Trong Mẫu 4A, “ngày” được tính thế nào và múi giờ trên Hệ thống là gì? | Template 4A, clauses 2.2–2.3: calendar day including weekends/public/Tết holidays; system time is GMT+7. |
| D5 | Direct | Mẫu số 5A dùng cho loại gói thầu và phương thức nào? | Template 5A: online non-consulting services, single-stage one-envelope method. |
| P1 | Paraphrase | Từ 01/07/2025, tài liệu hướng dẫn chuyển tiếp nói Hệ thống mạng đấu thầu quốc gia thay đổi ra sao? | Transition guide I.1/V.1: system upgrade for Law 90 from 01-07-2025 and transitional handling under the amended Procurement Law and still-compatible guidance until replacement decree takes effect. |
| P2 | Paraphrase | Kế hoạch lựa chọn nhà thầu đã duyệt nhưng chưa phát hành hồ sơ khi Luật 90 có hiệu lực thì chủ đầu tư được làm gì? | Law 90 transition provision: may adjust the approved contractor-selection plan to implement the new law, subject to the stated exception. |
| P3 | Paraphrase | Sau khi ban hành kế hoạch tổng thể lựa chọn nhà thầu, bao lâu phải đăng lên Hệ thống? | Decree 214: no later than 05 working days from issuance. |
| N1 | Numeric/date | Thông tư 79 có hiệu lực ngày nào, và chào giá trực tuyến rút gọn cho gói xây lắp bắt đầu trên Hệ thống ngày nào? | 04-08-2025 generally; 01-09-2025 for compact online quotation of construction packages. |
| N2 | Numeric/date | Nghị định 214/2025/NĐ-CP có hiệu lực khi nào? | From the signing date; the document is dated 04-08-2025. |
| M1 | Multi-document | Luật 90, Nghị định 214 và Thông tư 79 liên hệ với nhau như thế nào trong lựa chọn nhà thầu? | Law 90 amends the governing law; Decree 214 details provisions/implementation measures; Circular 79 provides national-system information/publication guidance and dossier/forms under that framework. |
| M2 | Multi-document | So sánh phạm vi sử dụng Mẫu 4A và Mẫu 5A. | Both are online single-stage one-envelope E-HSMT templates under Circular 79; 4A is for goods, 5A for non-consulting services. |
| I1 | Insufficient evidence | Ai vô địch FIFA World Cup 2026? | Must return `NO_EVIDENCE`; corpus has no support. |
| I2 | Insufficient evidence | Mức phạt cụ thể cho hành vi tấn công mạng theo luật an ninh mạng là bao nhiêu? | Must return `NO_EVIDENCE`; that legal source is not in the demo corpus. |

## Search-only queries

- `hiệu lực Luật 90/2025/QH15`
- `đấu thầu bền vững môi trường xã hội kinh tế`
- `thời hạn đăng tải kế hoạch tổng thể lựa chọn nhà thầu`
- `chào giá trực tuyến rút gọn gói thầu xây lắp`
- `mẫu hồ sơ mời thầu hàng hóa một túi`
- `dịch vụ phi tư vấn qua mạng`
- `điều chỉnh kế hoạch khi chưa phát hành hồ sơ`

## Result vocabulary

Each Ask result will be classified as `PASS`, `PARTIAL`, `FAIL`, `NO_EVIDENCE_CORRECT`, `SYSTEM_ERROR`, or `UI_ERROR` in `FINAL_VALIDATION.md`.
