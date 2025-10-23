import cv2
import pytesseract
from PIL import Image

# Load image with OpenCV
img = cv2.imread("WhatsApp Image 2025-08-29 at 17.14.51.jpeg")

# Convert to grayscale
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

# Apply thresholding (binarization)
_, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)

# Save temp processed image
cv2.imwrite("processed.png", thresh)

# Run OCR
extracted_text = pytesseract.image_to_string(Image.open("processed.png"), lang="ara+eng")

# Save output
with open("output_text3.txt", "w", encoding="utf-8") as f:
    f.write(extracted_text)

print("OCR with preprocessing done. Saved to: output_text3.txt")
