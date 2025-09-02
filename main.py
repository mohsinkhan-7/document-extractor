from fastapi import FastAPI, UploadFile, File
from controller import CardController
import shutil
import uuid

app = FastAPI()

@app.post("/extract-card")
async def extract_card(file: UploadFile = File(...)):
    # Save temp file
    temp_filename = f"temp_{uuid.uuid4().hex}.jpg"
    with open(temp_filename, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Process with controller
    data = CardController.process_card(temp_filename)

    return {"status": "success", "data": data}
