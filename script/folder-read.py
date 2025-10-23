import os
import cv2
import pytesseract
import re
import json
from PIL import Image, ImageEnhance
from datetime import datetime
import pandas as pd

def clean_mrz_line(line: str) -> str:
    line = line.replace("K", "<")
    line = line.replace("O", "0")
    line = line.replace("I", "1")
    line = re.sub(r"[^A-Z0-9<]", "", line)
    return line

def parse_mrz_date(date_str):
    try:
        return datetime.strptime(date_str, "%y%m%d").strftime("%d-%m-%Y")
    except:
        return ""

def extract(pattern, text, group=0):
    match = re.search(pattern, text)
    return match.group(group).strip() if match else ""

def extract_chip_number(img, card_number):
    chip_region = img[450:520, 100:320]
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
        if chip_number != card_number:
            return chip_number
    return ""

def process_citizen_card_images():
    folder = "image-reader-cleanse/citizen-card"
    results = []
    for filename in os.listdir(folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            path = os.path.join(folder, filename)
            img = cv2.imread(path)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            ocr_text = pytesseract.image_to_string(thresh, lang="eng")
            lines = [line.strip() for line in ocr_text.split("\n") if line.strip()]
            whole_text = " ".join(lines)

            data = {
                "Card_Number": "",
                "Chip_Number": "",
                "Occupation": "",
                "Issuing_Place": "",
                "MRZ_Line1": "",
                "MRZ_Line2": "",
                "MRZ_Line3": "",
                "Surname": "",
                "Given_Names": "",
                "Nationality": "",
                "Date_of_Birth": "",
                "Gender": "",
                "Expiry_Date": "",
                "Filename": filename
            }

            # Card Number
            data["Card_Number"] = extract(r"(\b\d{8,12}\b)", whole_text, 1)
            # Chip Number
            data["Chip_Number"] = extract_chip_number(img, data["Card_Number"])
            # Occupation
            for line in lines:
                if "Housewife" in line:
                    data["Occupation"] = "Housewife"
            # Issuing Place
            for line in lines:
                if "Dubai" in line:
                    data["Issuing_Place"] = "Dubai"
            # MRZ lines
            mrz_lines = [line for line in lines if re.search(r"[<]{2,}|[A-Z0-9]{15,}", line)]
            for i in range(min(3, len(mrz_lines))):
                data[f"MRZ_Line{i+1}"] = mrz_lines[i]
            # Surname & Given Names
            if data["MRZ_Line3"]:
                parts = data["MRZ_Line3"].split("<")
                if parts:
                    data["Surname"] = parts[0].replace("<", "").strip()
                    data["Given_Names"] = " ".join([p for p in parts[1:] if p]).replace("<", " ").strip()
            # Extract from MRZ Line2
            if data["MRZ_Line2"]:
                line2 = clean_mrz_line(data["MRZ_Line2"])
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
            results.append(data)
    df = pd.DataFrame(results)
    df.to_excel("Output/citizen_cards.xlsx", index=False)
    print("Excel file saved to Output/citizen_cards.xlsx")

if __name__ == "__main__":
    process_citizen_card_images()
import os

folder_path = "/Users/dell/Downloads/output"
output_file = "xml_filenames.txt"

with open(output_file, "w") as f:
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".xml"):
                f.write(f'"{file}"\n')

print("XML filenames saved to:", os.path.abspath(output_file))
