from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
import shutil
import uuid
import os

from controller import CardController, PDFController
from pdf_ocr_service import diagnose_environment, OCRConfigurationError, OCRDependencyError

app = FastAPI(title="Document Extractor API", version="1.0.0")

# Global dictionary to store temporary processed files
processed_files = {}

@app.get("/")
async def root():
    return {
        "service": "document-extractor",
        "endpoints": [
            "GET /", "GET /health", "GET /diagnostics/ocr",
            "POST /extract-card", "POST /pdf/ocr-word", "POST /pdf/chapters", 
            "POST /pdf/chapters-docx", "POST /pdf/chapters-zip", "GET /files/{filename}",
            "POST /pdf/toc", "POST /pdf/chapters-zip-from-toc"
        ]
    }

@app.get("/diagnostics/ocr")
async def ocr_diagnostics():
    return diagnose_environment()


@app.post("/extract-card")
async def extract_card(file: UploadFile = File(...)):
    temp_filename = f"temp_{uuid.uuid4().hex}.jpg"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        data = CardController.process_card(temp_filename)
        return {"status": "success", "data": data}
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract card data")
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

@app.post("/pdf/chapters")
async def pdf_chapters(file: UploadFile = File(...), start_page: int = 1):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    base_name = os.path.splitext(file.filename)[0]
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        chapters = PDFController.extract_chapters(temp_pdf, start_page=start_page)
        chapter_files = []
        for i, chapter in enumerate(chapters, start=1):
            chapter_filename = f"{base_name}_chapter_{i}.docx"
            chapter_path = PDFController.chapters_to_word([chapter], chapter_filename)
            chapter_files.append({"id": i, "title": chapter["title"], "path": chapter_path})

        processed_files[base_name] = {"pdf": temp_pdf, "chapters": chapter_files}

        return {
            "status": "success",
            "pdf": file.filename,
            "chapters": [
                {
                    "id": c["id"],
                    "title": c["title"],
                    "download_url": f"/files/{os.path.basename(c['path'])}"
                }
                for c in chapter_files
            ],
        }
    except (OCRConfigurationError, OCRDependencyError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract chapters")


@app.post("/pdf/chapters-zip")
async def pdf_chapters_zip(file: UploadFile = File(...), start_page: int = 1):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    zip_name = f"chapters_{uuid.uuid4().hex}.zip"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        result = PDFController.chapters_zip(temp_pdf, zip_name, start_page=start_page)
        return FileResponse(
            result["zip_path"],
            media_type="application/zip",
            filename=os.path.basename(result["zip_path"]),
        )
    except (OCRConfigurationError, OCRDependencyError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate chapters ZIP")
    finally:
        if os.path.exists(temp_pdf):
            os.remove(temp_pdf)

    @app.post("/upload-pdf/")
    async def upload_pdf(file: UploadFile = File(...)):
        temp_pdf = f"/tmp/{file.filename}"
        with open(temp_pdf, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        temp_zip = f"/tmp/{os.path.splitext(file.filename)[0]}_chapters.zip"
        export_chapters_to_zip(temp_pdf, temp_zip)

        return FileResponse(temp_zip, filename=os.path.basename(temp_zip))