from PIL import Image, ImageDraw, ImageOps
import os

# Source path (Option 1)
source_path = r'C:/Users/82108/.gemini/antigravity/brain/ba1951ef-70ed-456c-a715-05fc90493e07/icon_option_1_growth_1768953839730.png'
# Target path
target_path = r'c:\Users\82108\Downloads\dividend-calculator\app.ico'

def add_rounded_corners(im, radius):
    """Adds rounded corners to an image"""
    mask = Image.new('L', im.size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([(0, 0), im.size], radius=radius, fill=255)
    
    # Ensure image has alpha channel
    output = im.convert("RGBA")
    output.putalpha(mask)
    return output

def process_and_save_icon():
    if not os.path.exists(source_path):
        print(f"Error: Source image not found at {source_path}")
        return

    print(f"Processing {source_path}...")
    img = Image.open(source_path)
    
    # Original size is 1024x1024
    width, height = img.size
    
    # 1. Center Crop (Zoom in)
    # Cropping 17% from each side effectively zooms in by ~1.5x area wise.
    left = 174
    top = 174
    right = width - 174
    bottom = height - 174
    
    print(f"Cropping to: {left}, {top}, {right}, {bottom}")
    img_cropped = img.crop((left, top, right, bottom))
    
    # 2. Apply Rounded Corners
    # Current size is 676x676. Let's use a radius of ~130px (approx 20%)
    radius = 130
    print(f"Applying rounded corners with radius {radius}...")
    img_rounded = add_rounded_corners(img_cropped, radius)
    
    # 3. Resize to standard max icon size (256x256)
    img_resized = img_rounded.resize((256, 256), Image.Resampling.LANCZOS)
    
    # 4. Save as ICO with multiple sizes
    icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img_resized.save(target_path, format='ICO', sizes=icon_sizes)
    print(f"Successfully saved new rounded icon to {target_path}")

if __name__ == "__main__":
    process_and_save_icon()
