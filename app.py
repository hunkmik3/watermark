import os
import uuid
from flask import Flask, render_template, request, send_file, jsonify
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoFileClip, CompositeVideoClip, ImageClip

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Watermark settings
WATERMARK_TEXT = "OTSU"
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geist-font/geist-font/Geist/ttf/Geist-SemiBold.ttf")
IMAGE_FONT_SIZE = 1280
VIDEO_FONT_SIZE = 640
LETTER_SPACING = -0.04
OPACITY = 25

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}


def add_watermark_to_image(input_path, output_path):
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)
        font = ImageFont.truetype(FONT_PATH, IMAGE_FONT_SIZE)

        total_width = 0
        spacing = IMAGE_FONT_SIZE * LETTER_SPACING
        chars_info = []
        for char in WATERMARK_TEXT:
            bbox = draw.textbbox((0, 0), char, font=font)
            char_w = bbox[2] - bbox[0]
            chars_info.append((char, char_w))
            total_width += char_w + spacing
        total_width -= spacing

        start_x = (img.width - total_width) / 2
        center_y = img.height / 2

        current_x = start_x
        for char, char_w in chars_info:
            draw.text((current_x, center_y), char, font=font, fill=(255, 255, 255, OPACITY), anchor="lm")
            current_x += char_w + spacing

        out = Image.alpha_composite(img, txt_layer)
        if output_path.lower().endswith(('.jpg', '.jpeg')):
            out = out.convert("RGB")
        out.save(output_path)


def add_watermark_to_video(input_path, output_path):
    video = VideoFileClip(input_path)

    txt_img_w = int(video.w)
    txt_img_h = int(video.h)
    txt_img = Image.new('RGBA', (txt_img_w, txt_img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_img)
    font = ImageFont.truetype(FONT_PATH, VIDEO_FONT_SIZE)

    total_width = 0
    spacing = VIDEO_FONT_SIZE * LETTER_SPACING
    chars_info = []
    for char in WATERMARK_TEXT:
        char_bbox = draw.textbbox((0, 0), char, font=font)
        char_w = char_bbox[2] - char_bbox[0]
        chars_info.append((char, char_w))
        total_width += char_w + spacing
    total_width -= spacing

    start_x = (txt_img_w - total_width) / 2
    center_y = txt_img_h / 2

    for char, char_w in chars_info:
        draw.text((start_x, center_y), char, font=font, fill=(255, 255, 255, OPACITY), anchor="lm")
        start_x += char_w + spacing

    temp_txt_path = os.path.join(OUTPUT_FOLDER, f"temp_wm_{uuid.uuid4().hex}.png")
    txt_img.save(temp_txt_path)

    watermark = (ImageClip(temp_txt_path)
                 .with_duration(video.duration)
                 .with_position("center"))

    result = CompositeVideoClip([video, watermark])
    result.write_videofile(output_path, codec="libx264", audio_codec="aac")

    if os.path.exists(temp_txt_path):
        os.remove(temp_txt_path)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
        return jsonify({'error': f'Unsupported file format: {ext}'}), 400

    # Save uploaded file
    unique_id = uuid.uuid4().hex
    input_filename = f"{unique_id}{ext}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    # Process watermark
    output_filename = f"watermarked_{unique_id}{ext}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    try:
        if ext in IMAGE_EXTS:
            add_watermark_to_image(input_path, output_path)
            file_type = 'image'
        else:
            add_watermark_to_video(input_path, output_path)
            file_type = 'video'

        # Clean up uploaded file
        os.remove(input_path)

        return jsonify({
            'success': True,
            'filename': output_filename,
            'original_name': file.filename,
            'type': file_type
        })
    except Exception as e:
        if os.path.exists(input_path):
            os.remove(input_path)
        return jsonify({'error': str(e)}), 500


@app.route('/download/<filename>')
def download(filename):
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(file_path, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
