import pytesseract
from PIL import Image

# === Step 1: Path to your image ===
image_path = "WhatsApp Image 2025-08-29 at 17.14.47.jpeg"   # Replace with your image file path

# === Step 2: Run OCR on the image ===
# Open image
img = Image.open(image_path)

# Extract text using pytesseract
extracted_text = pytesseract.image_to_string(img)

# === Step 3: Save text to a file ===
output_file = "output_text1.txt"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(extracted_text)

print(f"OCR completed! Extracted text saved to {output_file}")
