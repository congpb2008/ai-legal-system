#!/usr/bin/env python3
"""Generate a sample Vietnamese legal document for the demo dataset.

Creates demo/sample-decision-15-2026.pdf — a fictional Decision
from the State Bank of Vietnam about server procurement regulations.
"""

import pymupdf
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent / "sample-decision-15-2026.pdf"

doc = pymupdf.open()
page = doc.new_page()

text = """NGÂN HÀNG NHÀ NƯỚC VIỆT NAM
--------------
Số: 15/2026/QĐ-NH

CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM
Độc lập - Tự do - Hạnh phúc
--------------
Hà Nội, ngày 01 tháng 6 năm 2026

QUYẾT ĐỊNH
Về việc ban hành Quy chế mua sắm máy chủ phục vụ hạ tầng công nghệ thông tin

THỐNG ĐỐC NGÂN HÀNG NHÀ NƯỚC

Căn cứ Luật Ngân hàng Nhà nước Việt Nam số 46/2010/QH12;
Căn cứ Luật Công nghệ thông tin số 67/2006/QH11;
Căn cứ Nghị định số 73/2019/NĐ-CP về quản lý đầu tư ứng dụng công nghệ thông tin;

QUYẾT ĐỊNH:

Điều 1. Phạm vi điều chỉnh
Quy chế này quy định việc mua sắm máy chủ phục vụ hạ tầng công nghệ thông tin của Ngân hàng Nhà nước và các đơn vị trực thuộc.

Điều 2. Đối tượng áp dụng
Quy chế này áp dụng đối với toàn bộ đơn vị trực thuộc Khối Công nghệ Thông tin và các đơn vị có liên quan trong hoạt động mua sắm máy chủ.

Điều 3. Yêu cầu cấu hình tối thiểu
1. Máy chủ phải có tối thiểu 32GB RAM (Random Access Memory).
2. Máy chủ phải có tối thiểu 04 lõi CPU (Central Processing Unit) với tốc độ tối thiểu 2.5GHz.
3. Ổ cứng phải là SSD (Solid State Drive) với dung lượng tối thiểu 1TB.
4. Hệ thống phải hỗ trợ RAID 1 hoặc RAID 5 để đảm bảo dự phòng dữ liệu.
5. Máy chủ phải có tối thiểu 02 nguồn điện dự phòng (Redundant Power Supply).

Điều 4. Quy trình phê duyệt
1. Việc mua sắm máy chủ phải được lập kế hoạch và trình Trưởng phòng Công nghệ Thông tin phê duyệt.
2. Đối với gói thầu có giá trị trên 500 triệu đồng, phải được Phó Tổng Giám đốc phê duyệt.
3. Đối với gói thầu có giá trị trên 02 tỷ đồng, phải được Tổng Giám đốc phê duyệt.

Điều 5. Trách nhiệm của các đơn vị
1. Phòng Công nghệ Thông tin: Lập kế hoạch, đề xuất cấu hình kỹ thuật, tham gia nghiệm thu.
2. Phòng Đấu thầu: Tổ chức đấu thầu theo quy định của pháp luật.
3. Phòng Tài chính Kế toán: Kiểm tra nguồn kinh phí, thực hiện thanh toán.
4. Phòng Pháp chế: Kiểm tra tính tuân thủ pháp luật của hồ sơ mua sắm.

Điều 6. Hiệu lực thi hành
Quyết định này có hiệu lực kể từ ngày ký và thay thế Quyết định số 08/2024/QĐ-NH.

Nơi nhận:
- Ban Lãnh đạo NHNN;
- Các đơn vị trực thuộc;
- Lưu: VT, CNTT.

KT. THỐNG ĐỐC
PHÓ THỐNG ĐỐC
(Đã ký)
Nguyễn Văn A"""

page.insert_text((72, 72), text, fontsize=10, fontname="helv")
doc.save(str(OUTPUT))
print(f"Sample document created: {OUTPUT}")
print(f"Size: {OUTPUT.stat().st_size} bytes")