import os, tempfile
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException
from src.loader import load_text
from src.extractor import extract_fields, CSV_COLUMNS

app = FastAPI(title="Agreement Metadata Extractor")

ALLOWED = {".docx", ".png", ".jpg", ".jpeg"}


@app.get("/")
def health():
    return {"status": "ok"}


@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED:
        raise HTTPException(
            400, f"Unsupported file type '{ext}'. Use .docx, .png or .jpg"
        )

    # save the upload to a temp file so the loader can read it
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(await file.read())
        path = tmp.name
    try:
        text = load_text(path)
        if not text.strip():
            raise HTTPException(422, "No text could be read from the file")
        result = extract_fields(text)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {e}")
    finally:
        os.remove(path)

    # return with the same column names as train.csv
    return {CSV_COLUMNS[k]: v for k, v in result.items()}
