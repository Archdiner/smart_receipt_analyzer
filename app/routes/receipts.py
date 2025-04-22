from fastapi import APIRouter, UploadFile, File, HTTPException
from app.services.ocr import analyze_receipt
from app.services.receipt_parser import parse_expense
from app.services.llm import llm_process_receipt

router = APIRouter()

@router.post("/analyze-expense")
async def analyze_expense_route(file: UploadFile = File(...)):
    """
    Analyze a receipt image and return organized data.
    
    This endpoint:
    1. Extracts text from the receipt image
    2. Parses the text into structured data
    3. Uses AI to clean up and categorize the items
    """
    try:
        # First, get the text from the receipt image
        receipt_text = await analyze_receipt(file)
        
        # Then, organize the text into a structured format
        parsed_data = parse_expense(receipt_text)
        
        # Finally, use AI to clean up and categorize everything
        processed_data = llm_process_receipt(receipt_text)
        
        # Return all the data we've collected
        return {
            "raw_text": receipt_text,        # The original text from the receipt
            "parsed_data": parsed_data,      # The initial organized data
            "processed_data": processed_data  # The cleaned and categorized data
        }
        
    except Exception as e:
        # If something goes wrong, let the user know
        raise HTTPException(
            status_code=500,
            detail=f"Sorry, we couldn't process your receipt: {str(e)}"
        )



