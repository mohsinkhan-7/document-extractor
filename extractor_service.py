import cv2
import pytesseract
import os
from dotenv import load_dotenv
import re
import json
from PIL import Image, ImageEnhance
from datetime import datetime

"""
Tesseract configuration
- We load environment variables from .env if present.
- You can set TESSERACT_CMD (preferred) to the full path of tesseract.exe on Windows
  e.g., C:\\Program Files\\Tesseract-OCR\\tesseract.exe
  If not set, we try common install locations on Windows.
"""

load_dotenv()

_tesseract_cmd = os.getenv("TESSERACT_CMD") or os.getenv("TESSERACT_PATH")
if _tesseract_cmd and os.path.exists(_tesseract_cmd):
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd
else:
    # Try common Windows install paths
    for _candidate in (
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
    ):
        if os.path.exists(_candidate):
            pytesseract.pytesseract.tesseract_cmd = _candidate
            break


def parse_mrz_date(date_str):
    try:
        return datetime.strptime(date_str, "%y%m%d").strftime("%d-%m-%Y")
    except:
        return ""


def clean_mrz_line(line: str) -> str:
    line = line.replace("K", "<").replace("O", "0").replace("I", "1")
    line = re.sub(r"[^A-Z0-9<]", "", line)
    return line


def extract_card_number(img):
    card_region = img[55:95, 30:220]
    gray = cv2.cvtColor(card_region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    pil_img = Image.fromarray(thresh)
    pil_img = ImageEnhance.Contrast(pil_img).enhance(2)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2)

    card_number_text = pytesseract.image_to_string(
        pil_img, lang="eng",
        config="--oem 1 --psm 8 -c tessedit_char_whitelist=0123456789"
    )

    card_number_text = card_number_text.strip().replace("O", "0").replace(" ", "")
    match = re.search(r"\d{8,12}", card_number_text)
    return match.group(0) if match else ""


def extract_chip_number(img, card_number):
    chip_region = img[170:210, 60:260]
    gray = cv2.cvtColor(chip_region, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    pil_img = Image.fromarray(thresh)
    pil_img = ImageEnhance.Contrast(pil_img).enhance(2)
    pil_img = ImageEnhance.Sharpness(pil_img).enhance(2)

    chip_number_text = pytesseract.image_to_string(
        pil_img, lang="eng",
        config="--oem 1 --psm 8 -c tessedit_char_whitelist=0123456789"
    )

    chip_number_text = chip_number_text.strip().replace("O", "0").replace(" ", "")
    match = re.search(r"\d{8,12}", chip_number_text)
    if match:
        chip_number = match.group(0)
        if chip_number != card_number:
            return chip_number
    return ""


def extract_card_data(image_path: str):
    # Fail fast if Tesseract is unavailable, with a clearer message
    try:
        _ = pytesseract.get_tesseract_version()
    except Exception as e:
        raise RuntimeError(
            "Tesseract OCR engine is not installed or not configured. "
            "Install Tesseract and/or set TESSERACT_CMD to the full path to tesseract.exe."
        ) from e

    img = cv2.imread(image_path)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

    ocr_text = pytesseract.image_to_string(thresh, lang="eng")
    lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
    whole_text = " ".join(lines)

    data = {
        "Card_Number": extract_card_number(img),
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
    }

    data["Chip_Number"] = extract_chip_number(img, data["Card_Number"])

    occupation_match = re.search(r"Occupation\s*:\s*([A-Za-z ]+)", whole_text)
    if occupation_match:
        data["Occupation"] = re.split(r"Issuing Place", occupation_match.group(1))[0].strip()

    issuing_place_match = re.search(r"Issuing Place\s*:\s*([A-Za-z ]+)", whole_text)
    if issuing_place_match:
        data["Issuing_Place"] = issuing_place_match.group(1).strip()

    mrz_lines = [line for line in lines if re.search(r"[<]{2,}|[A-Z0-9]{15,}", line)]
    for i in range(min(3, len(mrz_lines))):
        data["MRZ"][f"Line{i+1}"] = mrz_lines[i]

    if data["MRZ"]["Line3"]:
        parts = data["MRZ"]["Line3"].split("<")
        if parts:
            data["Surname"] = parts[0].replace("<", "").strip()
            data["Given_Names"] = " ".join([p for p in parts[1:] if p]).replace("<", " ").strip()

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

    return data
