import os
import uuid
import re
from urllib.parse import quote
import threading
import time
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
WATERMARK_TEXT = "OTSU LABS"
FONT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "geist-font/geist-font/Geist/ttf/Geist-SemiBold.ttf")
LETTER_SPACING = -0.04
OPACITY = 25
TARGET_WIDTH_RATIO = 0.65  # 65% of media width

# --- Task Management ---
TASKS = {}
TASKS_LOCK = threading.Lock()

def update_task_status(task_id, status, result=None, error=None):
    with TASKS_LOCK:
        TASKS[task_id] = {
            'status': status,
            'result': result,
            'error': error,
            'timestamp': time.time()
        }

def cleanup_old_tasks():
    # Simple cleanup to prevent memory leak (remove tasks older than 1 hour)
    with TASKS_LOCK:
        current_time = time.time()
        to_remove = [tid for tid, info in TASKS.items() if current_time - info.get('timestamp', 0) > 3600]
        for tid in to_remove:
            del TASKS[tid]


def get_optimal_font_size(img_width):
    """Calculate font size to match target width ratio."""
    # Start with a reference size
    ref_size = 100
    try:
        font = ImageFont.truetype(FONT_PATH, ref_size)
    except OSError:
        # Fallback if specific font not found during dev
        font = ImageFont.load_default()
        return int(img_width * 0.1) # Rough fallback

    # Measure text width at reference size
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)
    
    total_width = 0
    spacing = ref_size * LETTER_SPACING
    
    for char in WATERMARK_TEXT:
        bbox = draw.textbbox((0, 0), char, font=font)
        # some fonts might give negative x, ensure width is positive
        char_w = bbox[2] - bbox[0]
        total_width += char_w + spacing
    
    total_width -= spacing # remove last spacing
    
    if total_width <= 0:
        return ref_size # Should not happen

    # Calculate scale needed to reach target width
    target_width = img_width * TARGET_WIDTH_RATIO
    scale_factor = target_width / total_width
    
    return int(ref_size * scale_factor)


IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}


def add_watermark_to_image(input_path, output_path):
    with Image.open(input_path) as img:
        img = img.convert("RGBA")
        txt_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_layer)
        
        # Calculate dynamic font size
        font_size = get_optimal_font_size(img.width)
        font = ImageFont.truetype(FONT_PATH, font_size)

        total_width = 0
        spacing = font_size * LETTER_SPACING
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


import subprocess

def add_watermark_to_video(input_path, output_path):
    # Get video dimensions using ffprobe
    cmd_probe = [
        'ffprobe', '-v', 'error', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height', '-of', 'csv=s=x:p=0', input_path
    ]
    try:
        dim = subprocess.check_output(cmd_probe).decode('utf-8').strip().split('x')
        width, height = int(dim[0]), int(dim[1])
    except Exception as e:
        print(f"Error getting video dimensions: {e}")
        # Fallback default if probe fails
        width, height = 1920, 1080

    # Create a transparent image with the watermark text
    # We still use PIL to generate the watermark image because it's easier for text styling
    txt_img_w = width
    txt_img_h = height
    txt_img = Image.new('RGBA', (txt_img_w, txt_img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(txt_img)
    
    # Calculate dynamic font size
    font_size = get_optimal_font_size(txt_img_w)
    font = ImageFont.truetype(FONT_PATH, font_size)

    total_width = 0
    spacing = font_size * LETTER_SPACING
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

    # Save watermark image to a temp file
    temp_wm_path = os.path.join(OUTPUT_FOLDER, f"temp_wm_overlay_{uuid.uuid4().hex}.png")
    txt_img.save(temp_wm_path)

    try:
        # Use simple ffmpeg command to overlay image
        # -movflags faststart: Optimizes for web playback
        # -preset ultrafast: Prioritizes speed over compression
        cmd_ffmpeg = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-i', temp_wm_path,
            '-filter_complex', 'overlay=0:0',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
            '-c:a', 'copy',
            '-movflags', '+faststart',
            output_path
        ]
        
        subprocess.run(cmd_ffmpeg, check=True)
        
    except subprocess.CalledProcessError as e:
        # If overlay fails (e.g. format issues), try re-encoding audio
        print(f"FFmpeg overlay failed, trying with audio re-encode: {e}")
        try:
             cmd_ffmpeg = [
                'ffmpeg', '-y',
                '-i', input_path,
                '-i', temp_wm_path,
                '-filter_complex', 'overlay=0:0',
                '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '23',
                '-c:a', 'aac', # Force audio re-encode
                '-movflags', '+faststart',
                output_path
            ]
             subprocess.run(cmd_ffmpeg, check=True)
        except Exception as ex:
             raise Exception(f"FFmpeg failed: {ex}") 
    finally:
        if os.path.exists(temp_wm_path):
            os.remove(temp_wm_path)


def process_task(task_id, input_path, output_path, ext, original_filename):
    """Background worker function."""
    try:
        update_task_status(task_id, 'processing')
        
        file_type = 'unknown'
        if ext in IMAGE_EXTS:
            add_watermark_to_image(input_path, output_path)
            file_type = 'image'
        elif ext in VIDEO_EXTS:
            add_watermark_to_video(input_path, output_path)
            file_type = 'video'
        
        # Cleanup input
        if os.path.exists(input_path):
            os.remove(input_path)
            
        update_task_status(task_id, 'completed', result={
            'filename': os.path.basename(output_path),
            'original_name': original_filename,
            'type': file_type
        })
        
    except Exception as e:
        print(f"Task {task_id} failed: {e}")
        update_task_status(task_id, 'failed', error=str(e))
        if os.path.exists(input_path):
            os.remove(input_path)


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    # Cleanup old tasks occasionally
    cleanup_old_tasks()

    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
        return jsonify({'error': f'Unsupported file format: {ext}'}), 400

    # Save uploaded file
    task_id = uuid.uuid4().hex
    input_filename = f"{task_id}{ext}"
    input_path = os.path.join(UPLOAD_FOLDER, input_filename)
    file.save(input_path)

    output_filename = f"watermarked_{task_id}{ext}"
    output_path = os.path.join(OUTPUT_FOLDER, output_filename)

    # Initialize task status
    update_task_status(task_id, 'queued')

    # Start processing in a background thread
    thread = threading.Thread(target=process_task, args=(task_id, input_path, output_path, ext, file.filename))
    thread.start()

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': 'File uploaded, processing started.'
    })


@app.route('/status/<task_id>')
def status(task_id):
    with TASKS_LOCK:
        task_info = TASKS.get(task_id)
    
    if not task_info:
        return jsonify({'error': 'Task not found'}), 404
        
    return jsonify(task_info)


@app.route('/preview/<filename>')
def preview(filename):
    """Serve file inline for preview (no download forced)."""
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    return send_file(file_path)


@app.route('/download/<filename>')
def download(filename):
    """Force download with the correct original filename."""
    file_path = os.path.join(OUTPUT_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404
    
    original_name = request.args.get('original_name', filename)
    ext = os.path.splitext(filename)[1]  # e.g. .mp4, .png
    
    # Ensure the original name has the correct extension
    orig_base, orig_ext = os.path.splitext(original_name)
    if not orig_ext:
        original_name += ext
        orig_ext = ext
    
    download_name = f"watermarked_{original_name}"
    
    # Sanitize for ASCII fallback: remove problematic characters
    safe_name = re.sub(r'[^\w\s\-.]', '', download_name)
    safe_name = re.sub(r'\s+', '_', safe_name)
    # Ensure extension is preserved in safe name
    if not safe_name.lower().endswith(orig_ext.lower()):
        safe_name = os.path.splitext(safe_name)[0] + orig_ext
    
    # Use RFC 5987 encoding for full Unicode support
    encoded_name = quote(download_name)
    
    response = send_file(file_path, as_attachment=True, download_name=safe_name)
    response.headers['Content-Disposition'] = (
        f"attachment; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"
    )
    return response


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
