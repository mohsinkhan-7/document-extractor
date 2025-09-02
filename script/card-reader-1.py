import cv2
import pytesseract
import re
import json
from PIL import Image, ImageEnhance
from datetime import datetime

# === Load Image ===
img_path = "citizen-card-3-back.jpeg"
img = cv2.imread(img_path)

# Preprocessing (grayscale + threshold for clarity)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

# OCR (whole card)
ocr_text = pytesseract.image_to_string(thresh, lang="eng")

# Split into lines
lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
whole_text = " ".join(lines)


# === Helpers ===
def extract(pattern, text, group=0):
    match = re.search(pattern, text)
    return match.group(group).strip() if match else ""


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
    """Extract card number from cropped region (top-left)."""
    card_region = img[55:95, 30:220]  # adjust if needed
    cv2.imwrite("card_number_crop.jpg", card_region)  # debug

    gray = cv2.cvtColor(card_region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    pil_img = Image.fromarray(thresh)
    pil_img = ImageEnhance.Contrast(pil_img).enhance(2)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2)

    card_number_text = pytesseract.image_to_string(
        pil_img,
        lang="eng",
        config="--oem 1 --psm 8 -c tessedit_char_whitelist=0123456789"
    )

    card_number_text = card_number_text.strip().replace("O", "0").replace(" ", "")
    match = re.search(r"\d{8,12}", card_number_text)
    if match:
        return match.group(0)
    return ""


# --- Chip Number Extraction ---
def extract_chip_number(img, card_number):
    """Extract chip number from cropped region below chip."""
    chip_region = img[170:210, 60:260]  # adjust if needed
    cv2.imwrite("chip_number_crop.jpg", chip_region)  # debug

    gray = cv2.cvtColor(chip_region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    pil_img = Image.fromarray(thresh)
    pil_img = ImageEnhance.Contrast(pil_img).enhance(2)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2)

    chip_number_text = pytesseract.image_to_string(
        pil_img,
        lang="eng",
        config="--oem 1 --psm 8 -c tessedit_char_whitelist=0123456789"
    )

    chip_number_text = chip_number_text.strip().replace("O", "0").replace(" ", "")
    match = re.search(r"\d{8,12}", chip_number_text)
    if match:
        chip_number = match.group(0)
        if chip_number != card_number:  # avoid same number
            return chip_number
    return ""


# === Initialize JSON ===
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
data["Chip_Number"] = extract_chip_number(img, data["Card_Number"])

# Occupation
occupation_match = re.search(r"Occupation\s*:\s*([A-Za-z ]+)", whole_text)
if occupation_match:
    occ = occupation_match.group(1).strip()
    occ = re.split(r"Issuing Place", occ)[0].strip()
    data["Occupation"] = occ

# Issuing Place
issuing_place_match = re.search(r"Issuing Place\s*:\s*([A-Za-z ]+)", whole_text)
if issuing_place_match:
    data["Issuing_Place"] = issuing_place_match.group(1).strip()

# MRZ lines
mrz_lines = [line for line in lines if re.search(r"[<]{2,}|[A-Z0-9]{15,}", line)]
for i in range(min(3, len(mrz_lines))):
    data["MRZ"][f"Line{i+1}"] = mrz_lines[i]

# Surname & Given Names
if data["MRZ"]["Line3"]:
    parts = data["MRZ"]["Line3"].split("<")
    if parts:
        data["Surname"] = parts[0].replace("<", "").strip()
        data["Given_Names"] = " ".join([p for p in parts[1:] if p]).replace("<", " ").strip()

# Extract from MRZ Line2
if data["MRZ"]["Line2"]:
    line2 = clean_mrz_line(data["MRZ"]["Line2"])

    dob_match = re.search(r"(\d{6})", line2)
    if dob_match:
        data["Date_of_Birth"] = parse_mrz_date(dob_match.group(1))

    gender_match = re.search(r"\d{6}([MF])", line2)
    if gender_match:
        data["Gender"] = "Male" if gender_match.group(1) == "M" else "Female"

    exp_match = re.search(r"\d{6}[MF](\d{6})", line2)
    if exp_match:
        data["Expiry_Date"] = parse_mrz_date(exp_match.group(1))

    nat_match = re.search(r"([A-Z]{3})<{2,}", line2)
    if nat_match:
        data["Nationality"] = nat_match.group(1)

# === Save JSON ===
with open("extracted_card-sample.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

print(json.dumps(data, indent=4, ensure_ascii=False))
