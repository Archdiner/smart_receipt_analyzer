from fastapi import APIRouter, UploadFile, File
from app.services.ocr import analyze_receipt
from app.services.receipt_parser import parse_expense

router = APIRouter()

@router.post("/analyze-expense")
async def analyze_expense_route(file: UploadFile = File(...)):
    raw = await analyze_receipt(file)
    processed = parse_expense(raw)
    return processed



