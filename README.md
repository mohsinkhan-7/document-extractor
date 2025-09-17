# Document Extractor

OCR services for:
- ID/card data extraction (`/extract-card`)
- PDF -> chapter-wise cleaned text -> Word (`/pdf/ocr-word`, `/pdf/chapters`)

## Resolving Import Issues (pdf2image, PIL, pytesseract, docx, arabic_reshaper, bidi)
If your editor shows "Import could not be resolved":

1. Install Python dependencies:
```powershell
pip install --upgrade pip
pip install -r requirements.txt
```
2. Install Tesseract OCR (Windows):
	- Download installer: https://github.com/UB-Mannheim/tesseract/wiki
	- During install, select Arabic language data (or later copy `ara.traineddata` into `tessdata`).
	- Optionally set env var (PowerShell):
```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```
3. Install Poppler (for `pdf2image`):
	- Download Windows build: https://github.com/oschwartz10612/poppler-windows/releases (grab the ZIP, not source)
	- Extract to a simple path, e.g. `C:\poppler` or `C:\tools\poppler`.
	- After extraction you should have either:
		- `C:\poppler\bin\pdfinfo.exe` and `pdftoppm.exe`  (some builds)
		- or `C:\poppler\Library\bin\pdfinfo.exe` (others)
	- Set environment variable to the folder containing those `.exe` files:
```powershell
$env:POPPLER_PATH = "C:\poppler\bin"            # if pdfinfo.exe lives here
# or
$env:POPPLER_PATH = "C:\poppler\Library\bin"   # if pdfinfo.exe lives here
```
	- (Permanent user variable):
```powershell
[Environment]::SetEnvironmentVariable('POPPLER_PATH', 'C:\poppler\Library\bin', 'User')
```
	- The code will also auto-try common locations (`C:\poppler\bin`, `C:\poppler\Library\bin`, `C:\tools\poppler\...`).
4. Verify imports with helper script:
```powershell
python scripts\check_ocr_env.py
```
5. Restart your IDE so it picks up the new interpreter / packages.

## FastAPI Run
```powershell
uvicorn main:app --reload --port 8000
```

### Minimal vs Full Dependencies
The original `requirements.txt` contains many libraries not needed for pure OCR (pandas, selenium, etc.).

If you only need the OCR API:
```powershell
python -m pip install -r requirements.prod.txt
```

For development conveniences (reload tooling etc.):
```powershell
python -m pip install -r requirements.dev.txt
```

`requirements.txt` is left intact for backward compatibility; you can trim it later or replace it with `requirements.prod.txt`.

## Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /health | GET | Health check |
| /extract-card | POST (image file) | Extract card fields |
| /pdf/ocr-word | POST (pdf file) | Returns generated DOCX |
| /pdf/chapters | POST (pdf file) | Returns JSON chapters |
| /diagnostics/ocr | GET | Environment diagnostics (poppler / tesseract / Arabic data) |

## Direct PDF OCR Script
```powershell
python pdf_ocr_service.py input.pdf --out output.docx
```

## Troubleshooting
| Problem | Fix |
|---------|-----|
| pdf2image ImportError | Ensure Poppler installed & `POPPLER_PATH` or PATH updated |
| TesseractNotFoundError | Install Tesseract & set `TESSERACT_CMD` |
| Arabic text reversed | Ensure `arabic-reshaper` + `python-bidi` installed (in requirements) |
| Blank DOCX | Increase DPI (modify `ocr_pdf_to_pages(dpi=300)`) or check scan quality |
| Chapters not detected | Headings must contain words like `الفصل` or `باب` or be short Arabic-dominant lines |

### Arabic Output Notes
The DOCX export applies right-to-left paragraph direction and uses simple heuristic chapter detection. For higher accuracy you can post-process chapter titles manually.

## License
Internal usage example; add a proper license if distributing.
