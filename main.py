from fastapi import FastAPI, UploadFile, File, HTTPException
from controller import CardController
import shutil
import uuid
import os

app = FastAPI()

@app.get("/health")
async def health():
    return {"status": "ok"}

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
