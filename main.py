from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from controller import CardController, PDFController
import shutil
import uuid
import os
from pdf_ocr_service import diagnose_environment, OCRConfigurationError, OCRDependencyError

app = FastAPI(title="Document Extractor API", version="1.0.0")

@app.get("/")
async def root():
    return {
        "service": "document-extractor",
        "endpoints": [
            "GET /", "GET /health", "GET /diagnostics/ocr",
            "POST /extract-card", "POST /pdf/ocr-word", "POST /pdf/chapters", "POST /pdf/chapters-docx", "POST /pdf/chapters-zip", "GET /files/{filename}",
            "POST /pdf/toc", "POST /pdf/chapters-zip-from-toc"
        ]
    }

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/diagnostics/ocr")
async def ocr_diagnostics():
    return diagnose_environment()

@app.post("/extract-card")
async def extract_card(file: UploadFile = File(...)):
    # Save temp file
    temp_filename = f"temp_{uuid.uuid4().hex}.jpg"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        # Process with controller
        data = CardController.process_card(temp_filename)
        return {"status": "success", "data": data}
    except RuntimeError as e:
        # Surface configuration errors (e.g., Tesseract missing)
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to extract card data")
    finally:
        try:
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
        except Exception:
            pass

@app.post("/pdf/ocr-word")
async def pdf_ocr_word(file: UploadFile = File(...), start_page: int = 1):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    output_docx = f"output_{uuid.uuid4().hex}.docx"
    try:
        path = PDFController.pdf_to_word(temp_pdf, output_docx, start_page=start_page)
        return FileResponse(path, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=os.path.basename(path))
    except (OCRConfigurationError, OCRDependencyError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to process PDF")
    finally:
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except Exception:
            pass

@app.post("/pdf/chapters")
async def pdf_chapters(file: UploadFile = File(...), start_page: int = 1):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        chapters = PDFController.extract_chapters(temp_pdf, start_page=start_page)
        return {"status": "success", "chapters": chapters}
    except (OCRConfigurationError, OCRDependencyError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to extract chapters")
    finally:
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except Exception:
            pass


@app.post("/pdf/chapters-docx")
async def pdf_chapters_and_docx(file: UploadFile = File(...), download: bool = False, start_page: int = 1):
    """Full flow: OCR PDF -> chapters JSON -> DOCX built from chapters (ensures consistent segmentation)."""
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    output_docx = f"chapters_{uuid.uuid4().hex}.docx"
    try:
        chapters = PDFController.extract_chapters(temp_pdf, start_page=start_page)
        PDFController.chapters_to_word(chapters, output_docx)
        if download:
            return FileResponse(
                output_docx,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=os.path.basename(output_docx),
            )
        else:
            return {
                "status": "success",
                "chapters": chapters,
                "docx_filename": output_docx
            }
    except (OCRConfigurationError, OCRDependencyError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to process PDF")
    finally:
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except Exception:
            pass


@app.get("/files/{filename}")
async def download_file(filename: str):
    # Prevent path traversal, only serve files from CWD
    safe_name = os.path.basename(filename)
    path = os.path.join(os.getcwd(), safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=safe_name,
    )


@app.post("/pdf/chapters-zip")
async def pdf_chapters_zip(file: UploadFile = File(...), start_page: int = 1):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    zip_name = f"chapters_{uuid.uuid4().hex}.zip"
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
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except Exception:
            pass


@app.post("/pdf/toc")
async def pdf_toc(file: UploadFile = File(...), toc_page: int = 5):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        entries = PDFController.toc_entries(temp_pdf, toc_page=toc_page)
        return {"status": "success", "entries": entries}
    except (OCRConfigurationError, OCRDependencyError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to parse TOC")
    finally:
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except Exception:
            pass


@app.post("/pdf/chapters-zip-from-toc")
async def pdf_chapters_zip_from_toc(
    file: UploadFile = File(...), toc_page: int = 5, printed_to_pdf_offset: int = 0
):
    """
    Export per-chapter DOCX using TOC page numbers on a specific page.
    - toc_page: the 1-based PDF page index where the TOC exists (e.g., 5)
    - printed_to_pdf_offset: difference between printed page numbers and actual PDF page numbers.
      Example: if printed page 1 corresponds to PDF page 6, offset = 5.
    """
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    zip_name = f"chapters_toc_{uuid.uuid4().hex}.zip"
    try:
        result = PDFController.chapters_zip_from_toc(
            temp_pdf, zip_name, toc_page=toc_page, printed_to_pdf_offset=printed_to_pdf_offset
        )
        return FileResponse(
            result["zip_path"],
            media_type="application/zip",
            filename=os.path.basename(result["zip_path"]),
        )
    except (OCRConfigurationError, OCRDependencyError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Failed to generate TOC-based chapters ZIP")
    finally:
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except Exception:
            pass
