import os
import sys
import argparse
from PIL import Image, ImageDraw, ImageFont
from moviepy import VideoFileClip, TextClip, CompositeVideoClip

# Constants for the watermark
WATERMARK_TEXT = "OTSU"
# Updated to SemiBold for "đậm hơn 1 chút"
FONT_PATH = os.path.join(os.getcwd(), "geist-font/geist-font/Geist/ttf/Geist-SemiBold.ttf")
# Increased by 100%
IMAGE_FONT_SIZE = 1280
VIDEO_FONT_SIZE = 640
LETTER_SPACING = -0.04  # -4%
# Reduced by 25% (100 -> 75)
OPACITY = 75 

def add_watermark_to_image(input_path, output_path):
    print(f"Applying watermark to image: {input_path}")
    try:
        with Image.open(input_path) as img:
            # Work in RGBA for transparency
            img = img.convert("RGBA")
            
            # Create a separate layer for the watermark
            txt_layer = Image.new("RGBA", img.size, (0,0,0,0))
            draw = ImageDraw.Draw(txt_layer)
            
            # Load font
            font = ImageFont.truetype(FONT_PATH, IMAGE_FONT_SIZE)
            
            # Calculate total width with negative spacing
            total_width = 0
            spacing = IMAGE_FONT_SIZE * LETTER_SPACING
            chars_info = []
            for char in WATERMARK_TEXT:
                bbox = draw.textbbox((0, 0), char, font=font)
                char_w = bbox[2] - bbox[0]
                chars_info.append((char, char_w))
                total_width += char_w + spacing
            total_width -= spacing # remove last spacing
            
            # Get height from a sample char (or bbox of full text)
            full_bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
            text_height = full_bbox[3] - full_bbox[1]
            
            # Center position
            start_x = (img.width - total_width) / 2
            center_y = img.height / 2
            
            # Draw character by character using anchor='lm' (left middle) for vertical centering
            current_x = start_x
            for char, char_w in chars_info:
                draw.text((current_x, center_y), char, font=font, fill=(255, 255, 255, OPACITY), anchor="lm")
                current_x += char_w + spacing
                
            # Composite layers
            out = Image.alpha_composite(img, txt_layer)
            
            # Convert back to RGB for final saving (optional, but good for JPG)
            if output_path.lower().endswith(('.jpg', '.jpeg')):
                out = out.convert("RGB")
            
            out.save(output_path)
            print(f"Saved watermarked image to: {output_path}")
    except Exception as e:
        print(f"Error processing image: {e}")

def add_watermark_to_video(input_path, output_path):
    print(f"Applying watermark to video: {input_path}")
    try:
        video = VideoFileClip(input_path)
        
        # Create an image for the text (larger for 400% scale)
        txt_img_w = int(video.w) # cover full width if needed
        txt_img_h = int(video.h)
        txt_img = Image.new('RGBA', (txt_img_w, txt_img_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(txt_img)
        font = ImageFont.truetype(FONT_PATH, VIDEO_FONT_SIZE)
        
        # Calculate text width with spacing
        total_width = 0
        spacing = VIDEO_FONT_SIZE * LETTER_SPACING
        chars_info = []
        for char in WATERMARK_TEXT:
            char_bbox = draw.textbbox((0, 0), char, font=font)
            char_w = char_bbox[2] - char_bbox[0]
            chars_info.append((char, char_w))
            total_width += char_w + spacing
        total_width -= spacing
        
        # Center position
        start_x = (txt_img_w - total_width) / 2
        center_y = txt_img_h / 2
        
        for char, char_w in chars_info:
            draw.text((start_x, center_y), char, font=font, fill=(255, 255, 255, OPACITY), anchor="lm")
            start_x += char_w + spacing
            
        temp_txt_path = "temp_watermark.png"
        txt_img.save(temp_txt_path)
        
        from moviepy import ImageClip
        
        watermark = (ImageClip(temp_txt_path)
                     .with_duration(video.duration)
                     .with_position("center"))
        
        result = CompositeVideoClip([video, watermark])
        result.write_videofile(output_path, codec="libx264", audio_codec="aac")
        
        if os.path.exists(temp_txt_path):
            os.remove(temp_txt_path)
            
        print(f"Saved watermarked video to: {output_path}")
    except Exception as e:
        print(f"Error processing video: {e}")

def main():
    parser = argparse.ArgumentParser(description="Add OTSU watermark to images and videos.")
    parser.add_argument("input", help="Input file path (image or video)")
    parser.add_argument("-o", "--output", help="Output file path (optional)")
    
    args = parser.parse_args()
    
    input_file = args.input
    if not os.path.exists(input_file):
        print(f"Error: File {input_file} not found.")
        sys.exit(1)
        
    ext = os.path.splitext(input_file)[1].lower()
    output_file = args.output
    
    if not output_file:
        output_file = f"watermarked_{os.path.basename(input_file)}"
        
    image_exts = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp']
    video_exts = ['.mp4', '.mov', '.avi', '.mkv', '.webm']
    
    if ext in image_exts:
        add_watermark_to_image(input_file, output_file)
    elif ext in video_exts:
        add_watermark_to_video(input_file, output_file)
    else:
        print(f"Unsupported file format: {ext}")
        sys.exit(1)

if __name__ == "__main__":
    main()
