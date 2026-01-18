from PIL import Image
import os

# Source path (artifact)
source_path = r'C:/Users/MINI-PC/.gemini/antigravity/brain/e6e18597-af2b-4143-a908-b8e097399067/uploaded_image_1768097722736.png'
# Target path
target_path = 'app.ico'

if not os.path.exists(source_path):
    print(f"Error: Source image not found at {source_path}")
    exit(1)

print(f"Converting {source_path} to {target_path}...")

img = Image.open(source_path)

# Crop transparent borders (if any)
bbox = img.getbbox()
if bbox:
    img = img.crop(bbox)

# Create a clear square canvas to center the image (standard ICO size base)
max_size = 256
canvas = Image.new('RGBA', (max_size, max_size), (0, 0, 0, 0))

# Resize image to fit within max_size x max_size while keeping aspect ratio
img_ratio = img.width / img.height
if img_ratio > 1:
    new_width = max_size
    new_height = int(max_size / img_ratio)
else:
    new_height = max_size
    new_width = int(max_size * img_ratio)

img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

# Center the image on the canvas
x = (max_size - new_width) // 2
y = (max_size - new_height) // 2
canvas.paste(img, (x, y))

icon_sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
canvas.save(target_path, format='ICO', sizes=icon_sizes)

print("Conversion complete.")
