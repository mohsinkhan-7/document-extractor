from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import StreamingResponse
from controller import CardController
import shutil
import uuid
import os
import io
from pdf_ocr_service import (
    split_pdf_into_chapters,
    split_pdf_every_n_pages,
    split_pdf_by_toc,
    translate_text,
    tts_bytes,
    chapters_to_zip,
    chapters_texts_zip,
    chapters_texts_to_docx_zip,
    has_docx,
    OCRDependencyError,
    translate_chapters_parallel,
    chapters_to_zip_parallel,
    chapter_text_to_docx_bytes,
)

app = FastAPI(title="Document Extractor API", version="1.0.0")


def _assert_pdf_file(path: str):
    """Validate that a file is a PDF by inspecting its header.
    Raises HTTPException 400 if invalid.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(1024)
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to read uploaded file.")
    if not head:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")
    # Common non-PDF: ZIP/DOCX start with 'PK\x03\x04'
    if head.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=400, detail="Uploaded file is a ZIP/DOCX, not a PDF. Please upload a PDF.")
    # Robust PDF check: look for '%PDF' near the beginning
    if b"%PDF" not in head[:1024]:
        raise HTTPException(status_code=400, detail="Uploaded file does not look like a PDF. Ensure you are sending the original PDF.")

@app.get("/health")
async def health():
    return {"status": "ok", "docx_available": bool(has_docx())}

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




@app.post("/pdf/chapters-zip")
async def pdf_chapters_zip(
    file: UploadFile = File(...),
    chapter_index: int | None = Form(default=None),
    fallback_pages: int | None = Form(default=None),
    use_toc: bool = Form(default=False),
    toc_first_page: int = Form(default=0),
    toc_last_page: int = Form(default=0),
    printed_offset: int = Form(default=0),
):
    """Split the uploaded PDF into chapters.
    - If `chapter_index` is provided (1-based), returns a single DOCX for that chapter.
    - Otherwise, returns a ZIP of per-chapter DOCX files.
    """
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    try:
        _assert_pdf_file(temp_pdf)
        if use_toc:
            fp = int(toc_first_page) if toc_first_page and toc_first_page > 0 else 1
            lp = int(toc_last_page) if toc_last_page and toc_last_page >= fp else fp
            try:
                chapters = split_pdf_by_toc(temp_pdf, toc_first_page=fp, toc_last_page=lp, printed_to_pdf_offset=int(printed_offset))
            except Exception:
                chapters = split_pdf_into_chapters(temp_pdf)
        else:
            chapters = split_pdf_into_chapters(temp_pdf)
        if len(chapters) <= 1 and fallback_pages:
            # If heuristics found only one chapter, optionally split by fixed page count
            chapters = split_pdf_every_n_pages(temp_pdf, int(fallback_pages))
        if chapter_index is not None:
            i = int(chapter_index)
            if i < 1 or i > len(chapters):
                raise HTTPException(status_code=400, detail="chapter_index out of range")
            ch = chapters[i - 1]
            data = chapter_text_to_docx_bytes(ch.get("title") or f"Chapter_{i}", ch.get("text", ""))
            filename = f"chapter_{i:02d}.docx"
            return StreamingResponse(io.BytesIO(data), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={
                "Content-Disposition": f"attachment; filename={filename}"
            })
        else:
            zip_bytes = chapters_texts_to_docx_zip(chapters)
            return StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip", headers={
                "Content-Disposition": "attachment; filename=chapters_docx.zip"
            })
    except OCRDependencyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate chapters ZIP: {e}")
    finally:
        try:
            if os.path.exists(temp_pdf):
                os.remove(temp_pdf)
        except Exception:
            pass






# ------ New endpoints: direct split, translate, and TTS ------





@app.post("/translate/chapters")
async def api_translate_chapters(
    file: UploadFile = File(...),
    target_lang: str = Form(...),
    download: bool = Form(False),
    max_workers: int = Form(3),
    chapter_index: int | None = Form(default=None),
    fallback_pages: int | None = Form(default=None),
    use_toc: bool = Form(default=False),
    toc_first_page: int = Form(default=0),
    toc_last_page: int = Form(default=0),
    printed_offset: int = Form(default=0),
):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        _assert_pdf_file(temp_pdf)
        if use_toc:
            fp = int(toc_first_page) if toc_first_page and toc_first_page > 0 else 1
            lp = int(toc_last_page) if toc_last_page and toc_last_page >= fp else fp
            try:
                chapters = split_pdf_by_toc(temp_pdf, toc_first_page=fp, toc_last_page=lp, printed_to_pdf_offset=int(printed_offset))
            except Exception:
                chapters = split_pdf_into_chapters(temp_pdf)
        else:
            chapters = split_pdf_into_chapters(temp_pdf)
        if len(chapters) <= 1 and fallback_pages:
            chapters = split_pdf_every_n_pages(temp_pdf, int(fallback_pages))
        chapters = translate_chapters_parallel(chapters, target_lang, max_workers=max_workers)
        if chapter_index is not None:
            i = int(chapter_index)
            if i < 1 or i > len(chapters):
                raise HTTPException(status_code=400, detail="chapter_index out of range")
            ch = chapters[i - 1]
            data = chapter_text_to_docx_bytes(ch.get("title") or f"Chapter_{i}", ch.get("text", ""))
            filename = f"chapter_{i:02d}_{target_lang}.docx"
            return StreamingResponse(io.BytesIO(data), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", headers={
                "Content-Disposition": f"attachment; filename={filename}"
            })
        if download:
            zip_bytes = chapters_texts_to_docx_zip(chapters)
            return StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip", headers={
                "Content-Disposition": f"attachment; filename=translated_chapters_{target_lang}.zip"
            })
        else:
            return {"chapters": chapters}
    except OCRDependencyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to translate chapters: {e}")
    finally:
        try:
            os.remove(temp_pdf)
        except OSError:
            pass


@app.post("/tts/chapters")
async def api_tts_chapters(
    file: UploadFile = File(...),
    lang: str = Form("en"),
    max_workers: int = Form(3),
    use_toc: bool = Form(default=False),
    toc_first_page: int = Form(default=0),
    toc_last_page: int = Form(default=0),
    printed_offset: int = Form(default=0),
):
    temp_pdf = f"temp_{uuid.uuid4().hex}.pdf"
    with open(temp_pdf, "wb") as f:
        shutil.copyfileobj(file.file, f)
    try:
        _assert_pdf_file(temp_pdf)
        if use_toc:
            fp = int(toc_first_page) if toc_first_page and toc_first_page > 0 else 1
            lp = int(toc_last_page) if toc_last_page and toc_last_page >= fp else fp
            try:
                chapters = split_pdf_by_toc(temp_pdf, toc_first_page=fp, toc_last_page=lp, printed_to_pdf_offset=int(printed_offset))
            except Exception:
                chapters = split_pdf_into_chapters(temp_pdf)
        else:
            chapters = split_pdf_into_chapters(temp_pdf)
        # Translate each chapter to the requested language first, then synthesize
        chapters = translate_chapters_parallel(chapters, lang, max_workers=max_workers)
        zip_bytes = chapters_to_zip_parallel(chapters, lang, max_workers=max_workers)
        return StreamingResponse(io.BytesIO(zip_bytes), media_type="application/zip", headers={
            "Content-Disposition": f"attachment; filename=chapters_audio_{lang}.zip"
        })
    except OCRDependencyError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate TTS ZIP: {e}")
    finally:
        try:
            os.remove(temp_pdf)
        except OSError:
            pass
