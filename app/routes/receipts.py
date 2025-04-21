from fastapi import APIRouter, UploadFile, File
from app.services.ocr import analyze_receipt

router = APIRouter()

@router.post("/analyze")
async def analyze_route(file: UploadFile = File(...)):
    answer = await analyze_receipt(file)
    return {"textract_response": answer}



