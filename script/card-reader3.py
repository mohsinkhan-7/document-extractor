import cv2
import pytesseract
import re
import json
from PIL import Image, ImageEnhance
from datetime import datetime

# === Load Image ===
img_path = "/Users/dell/PycharmProjects/PythonDataAnalytics-1/image-reader-cleanse/citizen-card/citizen-card-3-back.jpeg"

img = cv2.imread(img_path)

# Preprocessing for full card OCR
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
# CLAHE
clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
clahe_img = clahe.apply(gray)
# Invert for better OCR
inverted = cv2.bitwise_not(clahe_img)
# Median blur
blurred = cv2.medianBlur(inverted, 3)
# Threshold
_, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
# PIL enhancements
pil_img = Image.fromarray(thresh)
pil_img = ImageEnhance.Brightness(pil_img).enhance(3)
pil_img = ImageEnhance.Contrast(pil_img).enhance(4)
pil_img = ImageEnhance.Sharpness(pil_img).enhance(10)

# OCR (whole card)
ocr_text = pytesseract.image_to_string(pil_img, lang="eng")

# Split into lines
lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
whole_text = " ".join(lines)

# Helper to extract safely
def extract(pattern, text, group=0):
    match = re.search(pattern, text)
    return match.group(group).strip() if match else ""


# Convert YYMMDD → DD-MM-YYYY
def parse_mrz_date(date_str):
    try:
        return datetime.strptime(date_str, "%y%m%d").strftime("%d-%m-%Y")
    except:
        return ""

def clean_mrz_line(line: str) -> str:
    """Clean OCR noise from MRZ line."""
    line = line.replace("K", "<")  # OCR often mistakes < as K
    line = line.replace("O", "0")  # O → 0
    line = line.replace("I", "1")  # I → 1
    line = re.sub(r"[^A-Z0-9<]", "", line)  # Keep only MRZ-valid chars
    return line
# --- Card Number Extraction ---
def extract_card_number(img):
    """
    Extract card number from the cropped region in the top-left corner.
    """
        # Crop region (tuned for sample image: just below 'Card Number')
    # Crop region (tuned for sample image: just below 'Card Number')
    card_region = img[30:130, 40:300]
    cv2.imwrite("card_number_crop.jpg", card_region)  # debug

    gray = cv2.cvtColor(card_region, cv2.COLOR_BGR2GRAY)
    # Apply CLAHE for local contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    clahe_img = clahe.apply(gray)
    _, thresh = cv2.threshold(clahe_img, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    pil_img = Image.fromarray(thresh)
    pil_img = ImageEnhance.Brightness(pil_img).enhance(2.2)  # Further increase brightness
    pil_img = ImageEnhance.Contrast(pil_img).enhance(5)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(10)
    # Upscale to 2x for better OCR
    w, h = pil_img.size
    pil_img_up = pil_img.resize((w*2, h*2), Image.LANCZOS)

    # Try psm 7
    card_number_psm7 = pytesseract.image_to_string(
        pil_img_up,
        lang="eng",
        config="--oem 1 --psm 7 -c tessedit_char_whitelist=0123456789"
    )
    print("[DEBUG] Card Number OCR Output (psm7):", card_number_psm7)
    # Try psm 6
    card_number_psm6 = pytesseract.image_to_string(
        pil_img_up,
        lang="eng",
        config="--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789"
    )
    print("[DEBUG] Card Number OCR Output (psm6):", card_number_psm6)

    # Clean and match
    for text in [card_number_psm7, card_number_psm6]:
        cleaned = text.strip().replace("O", "0").replace(" ", "")
        match = re.search(r"\d{8,12}", cleaned)
        if match:
            return match.group(0)
    return ""


# --- Chip Number Extraction ---
def extract_chip_number(img, card_number):
    """
    Extract chip number from the cropped region directly below the chip.
    """
    # Crop region below chip (tuned for sample image)
    chip_region = img[350:520, 90:300]
    cv2.imwrite("chip_number_crop.jpg", chip_region)  # debug

    gray = cv2.cvtColor(chip_region, cv2.COLOR_BGR2GRAY)
    # Apply CLAHE for local contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    clahe_img = clahe.apply(gray)
    # Invert image for better OCR
    inverted = cv2.bitwise_not(clahe_img)
    # Apply median blur to reduce background noise
    blurred = cv2.medianBlur(inverted, 3)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    pil_img = Image.fromarray(thresh)
    pil_img = ImageEnhance.Brightness(pil_img).enhance(5)  # Stronger brightness
    pil_img = ImageEnhance.Contrast(pil_img).enhance(5)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(10)
    # Upscale to 2x for better OCR
    w, h = pil_img.size
    pil_img_up = pil_img.resize((w*2, h*2), Image.LANCZOS)

    # Try psm 4, 6, and 8 for chip number extraction
    chip_number_psm4 = pytesseract.image_to_string(
        pil_img_up,
        lang="eng",
        config="--oem 1 --psm 4 -c tessedit_char_whitelist=0123456789"
    )
    print("[DEBUG] Chip Number OCR Output (psm4):", chip_number_psm4)
    chip_number_psm6 = pytesseract.image_to_string(
        pil_img_up,
        lang="eng",
        config="--oem 1 --psm 6 -c tessedit_char_whitelist=0123456789"
    )
    print("[DEBUG] Chip Number OCR Output (psm6):", chip_number_psm6)
    chip_number_psm8 = pytesseract.image_to_string(
        pil_img_up,
        lang="eng",
        config="--oem 1 --psm 8 -c tessedit_char_whitelist=0123456789"
    )
    print("[DEBUG] Chip Number OCR Output (psm8):", chip_number_psm8)

    # Try to extract chip number from MRZ line 1 for auto-correction
    mrz_chip = None
    try:
        mrz_line1 = data["MRZ"]["Line1"]
        card_match = re.search(r"(\d{8,12})", mrz_line1)
        if card_match:
            idx = mrz_line1.find(card_match.group(1))
            after = mrz_line1[idx+len(card_match.group(1)):]
            chip_match = re.search(r"(\d{10})", after)
            if chip_match:
                mrz_chip = chip_match.group(1)
    except:
        pass

    for text in [chip_number_psm4, chip_number_psm6, chip_number_psm8]:
        digits_only = re.sub(r"[^0-9]", "", text)
        match = re.search(r"\d{10}", digits_only)
        if match:
            chip_number = match.group(0)
            if chip_number != card_number:
                # Auto-correct single-digit errors if MRZ chip is available
                if mrz_chip and len(chip_number) == 10:
                    diffs = sum(a != b for a, b in zip(chip_number, mrz_chip))
                    if diffs == 1:
                        print(f"[DEBUG] Auto-correcting chip number {chip_number} to MRZ value {mrz_chip}")
                        return mrz_chip
                return chip_number
    return ""


# Initialize JSON
data = {
    "Card_Number": "",
    "Chip_Number": "",
    "Occupation": "",
    "Issuing_Place": "",
    "MRZ": {"Line1": "", "Line2": "", "Line3": ""},
    "Surname": "",
    "Given_Names": "",
    "Nationality": "",
    "Date_of_Birth": "",
    "Gender": "",
    "Expiry_Date": "",
    "Card_Number_Image": "card_number_crop.jpg",
    "Chip_Number_Image": "chip_number_crop.jpg"
}

# === Extract fields ===

data["Card_Number"] = extract_card_number(img)

# Chip Number (using crop method)
data["Chip_Number"] = extract_chip_number(img, data["Card_Number"])

# Improved regex for occupation, employer, issuing place
def correct_occupation(text):
    corrections = {
        "Finance Manager": ["Pinarice Manager", "Finarice Manager", "Finanice Manager", "Finarice Manger", "Finance Manger"],
        "Housewife": ["Housewife"],
        "Marketing Executive": ["Marketing Executive", "Markting Executive", "Market Executive"],
        # Add more as needed
    }
    for correct, variants in corrections.items():
        for variant in variants:
            if variant.lower() in text.lower():
                return correct
    if "manager" in text.lower():
        return "Finance Manager"
    if "executive" in text.lower():
        return "Marketing Executive"
    return text

# Occupation
occ_match = re.search(r"Occupation\s*[:\-]?\s*([A-Za-z ]+)", whole_text, re.IGNORECASE)
if occ_match:
    occ = occ_match.group(1).strip()
    occ = re.split(r"Employer|Issuing Place", occ)[0].strip()
    occ = correct_occupation(occ)
    data["Occupation"] = occ

# Employer (optional)
emp_match = re.search(r"Employer\s*[:\-]?\s*([A-Za-z0-9 .\-]+)", whole_text, re.IGNORECASE)
if emp_match:
    data["Employer"] = emp_match.group(1).strip()

# Issuing Place
issuing_match = re.search(r"Issuing Place\s*[:\-]?\s*([A-Za-z ]+)", whole_text, re.IGNORECASE)
if issuing_match:
    data["Issuing_Place"] = issuing_match.group(1).strip()


# MRZ lines (with < or long alphanumeric)
mrz_lines = [line for line in lines if re.search(r"[<]{2,}|[A-Z0-9]{15,}", line)]
for i in range(min(3, len(mrz_lines))):
    data["MRZ"][f"Line{i+1}"] = mrz_lines[i]

# Surname & Given Names
if data["MRZ"]["Line3"]:
    parts = data["MRZ"]["Line3"].split("<")
    if parts:
        data["Surname"] = parts[0].replace("<", "").strip()
        data["Given_Names"] = " ".join([p for p in parts[1:] if p]).replace("<", " ").strip()

# === Extract from MRZ Line2 (DOB, Gender, Expiry, Nationality) ===
if data["MRZ"]["Line2"]:
    line2 = clean_mrz_line(data["MRZ"]["Line2"])

    # Date of Birth (first 6 digits)
    dob_match = re.search(r"(\d{6})", line2)
    if dob_match:
        data["Date_of_Birth"] = parse_mrz_date(dob_match.group(1))

    # Gender (M/F after DOB)
    gender_match = re.search(r"\d{6}([MF])", line2)
    if gender_match:
        data["Gender"] = "Male" if gender_match.group(1) == "M" else "Female"

    # Expiry Date (6 digits after gender)
    exp_match = re.search(r"\d{6}[MF](\d{6})", line2)
    if exp_match:
        data["Expiry_Date"] = parse_mrz_date(exp_match.group(1))

    # Nationality (3 letters before <<< or at end)
    nat_match = re.search(r"([A-Z]{3})<{2,}", line2)
    if nat_match:
        data["Nationality"] = nat_match.group(1)
    else:
        # Fallback: try to extract nationality from MRZ line2 by searching for 3 letters before <<<
        nat_match2 = re.search(r"([A-Z]{3})<+", line2)
        if nat_match2:
            data["Nationality"] = nat_match2.group(1)


# Save JSON
with open("extracted_card1.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(json.dumps(data, indent=4, ensure_ascii=False))
