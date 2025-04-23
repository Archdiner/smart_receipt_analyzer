from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ocr import get_image_data
from app.services.ocr_llm import ocr_llm_process_receipt
from app.services.transaction_processor import process_transaction_screenshot

router = APIRouter()

@router.post("/analyze-expense")
async def analyze_expense_route(file: UploadFile = File(...)):
    """
    Analyze a receipt image and return organized data.
    
    This endpoint uses AI to directly analyze the receipt image and extract:
    - Vendor name
    - Date
    - Total amount
    - Individual items with quantities and prices
    - VAT amount (if present)
    - Overall category
    """
    try:
        # Get the image data
        image_data = await get_image_data(file)
        
        # Process the receipt using AI
        processed_data = ocr_llm_process_receipt(image_data)
        
        return processed_data
        
    except Exception as e:
        # If something goes wrong, let the user know
        raise HTTPException(
            status_code=500,
            detail=f"Sorry, we couldn't process your receipt: {str(e)}"
        )

@router.post("/analyze-transaction")
async def analyze_transaction_route(file: UploadFile = File(...)):
    """
    Analyze a bank transaction screenshot and return organized data.
    
    This endpoint uses AI to analyze transaction notification screenshots and extract:
    - Vendor/merchant name
    - Transaction amount and currency
    - Transaction date
    - Business sector
    """
    try:
        # Get the image data
        image_data = await get_image_data(file)
        
        # Process the transaction screenshot
        processed_data = process_transaction_screenshot(image_data)
        
        return processed_data
        
    except Exception as e:
        # If something goes wrong, let the user know
        raise HTTPException(
            status_code=500,
            detail=f"Sorry, we couldn't process your transaction screenshot: {str(e)}"
        )



