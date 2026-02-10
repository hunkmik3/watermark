# OTSU Watermark Tool

Một công cụ đơn giản viết bằng Python để gán watermark "OTSU" vào hình ảnh và video với thiết kế typography hiện đại (Geist Font).

## Tính năng
- Hỗ trợ gán watermark cho cả **Hình ảnh** và **Video**.
- Sử dụng font chữ **Geist** (SemiBold).
- Căn giữa tuyệt đối trên mọi khung hình.
- Tự động điều chỉnh kích thước cho phù hợp (640px cho ảnh, 320px cho video).
- Hiệu ứng làm mờ (Opacity) chuyên nghiệp.

## Cài đặt

1. Cài đặt Python 3.13+.
2. Cài đặt dependencies:
   ```bash
   pip install Pillow moviepy
   ```
3. Đảm bảo bạn đã có thư mục `geist-font` trong dự án.

## Cách sử dụng

Chạy script với đường dẫn file đầu vào:

```bash
python watermark.py input.png
python watermark.py input.mp4
```

Tùy chọn đặt tên file đầu ra:
```bash
python watermark.py input.mp4 -o output.mp4
```

## Yêu cầu hệ thống
- FFmpeg (cần thiết cho MoviePy xử lý video).
