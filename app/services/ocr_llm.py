import os
import json
from typing import Dict, List
from openai import OpenAI
from pydantic import BaseModel
from paddleocr import PaddleOCR
import tempfile
from PIL import Image
import io
import base64

# Initialize the OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"
)

# Initialize PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')

# Define what a receipt looks like
class ReceiptData(BaseModel):
    vendor: str      # Store name
    date: str        # Purchase date
    total: float     # Total amount
    sector: str      # Overall category for this receipt
    currency: str    # Transaction currency
    transaction_type: str = "receipt"  # Type of transaction
    uncertain_category: bool = False   # Flag for uncertain categorization

# Categories for categorizing receipts
SECTORS = [
    "Groceries & Household Supplies",
    "Dining & Cafés",
    "Utilities & Bills",
    "Transportation & Fuel",
    "Auto & Vehicle",
    "Health & Pharma",
    "Personal Care & Beauty",
    "Entertainment & Leisure",
    "Education & Books",
    "Apparel & Accessories",
    "Electronics & Appliances",
    "Home & Furnishings",
    "Travel & Accommodation",
    "Finance & Insurance",
    "Miscellaneous"
]

def extract_text_with_ocr(image_path: str) -> str:
    """
    Extract text from receipt image using PaddleOCR.
    
    Args:
        image_path: Path to the image file
        
    Returns:
        Extracted text from the receipt
    """
    result = ocr.ocr(image_path, cls=True)
    
    # Extract text from OCR results
    extracted_text = []
    for line in result:
        for item in line:
            text = item[1][0]  # Get the text from the OCR result
            confidence = item[1][1]  # Get the confidence score
            if confidence > 0.5:  # Only include text with good confidence
                extracted_text.append(text)
    
    return "\n".join(extracted_text)

def create_processing_prompt(extracted_text: str) -> str:
    """
    Create a precise instruction prompt for the AI to extract
    vendor, date, total, and sector from raw OCR text.
    """
    sectors_str = '", "'.join(SECTORS)
    return f"""
Analyze the following text extracted from a receipt image using OCR:

{extracted_text}

Extract these key details from the provided text ONLY:
1. Vendor/Store name: Identify the primary retail brand or store name by:
   - Prioritizing main brand names over parent companies or subsidiaries
   - Checking receipt header, product names, and store identifiers
   - Formatting for readability (proper case, remove unnecessary text)

2. Date: Find any date in the text and convert it to YYYY-MM-DD format
3. Total amount: Identify the final total amount, typically found with indicators like 'Total', 'GROSS', 'NET'
4. Currency: Identify the currency code (e.g., BHD, USD). If not found, default to BHD
5. Business sector: Classify the business into exactly one of these categories:
"{sectors_str}"

6. Uncertain category: Set to true if you're not confident about the sector classification

Respond with ONLY valid JSON in this structure:
{{
    "vendor": "business_name",
    "date": "YYYY-MM-DD",
    "total": number,
    "currency": "currency_code",
    "sector": "matching_category",
    "uncertain_category": boolean
}}

Use ONLY information found in the provided OCR text. If currency is not found, default to "BHD"."""

def calculate_token_usage(response) -> Dict:
    """Calculate and return token usage information from the API response."""
    usage = response.usage
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens
    }

def ocr_llm_process_receipt(base64_image: str) -> Dict:
    """
    Process receipt using OCR first, then LLM for final parsing.
    
    Args:
        base64_image: Base64 encoded image data
        
    Returns:
        Dict containing both parsed receipt data and raw outputs
        
    Raises:
        ValueError: If something goes wrong with the processing
    """
    try:
        # Convert base64 to image file
        image_data = base64.b64decode(base64_image)
        with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name

        try:
            # Extract text using OCR
            extracted_text = extract_text_with_ocr(temp_file_path)
            print("\nExtracted Text:", extracted_text)
            
            # Create instructions for the AI
            prompt = create_processing_prompt(extracted_text)
            
            # Ask the AI to process the extracted text
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are analyzing receipt text. Extract only the information present in the provided text. Respond with ONLY valid JSON."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            # Get the raw response for debugging
            raw_response = response.choices[0].message.content.strip()
            print("\nAI Response:", raw_response)
            
            # Try to parse the response
            try:
                cleaned_data = json.loads(raw_response)
                print("\nParsed JSON:", cleaned_data)
            except json.JSONDecodeError as e:
                print(f"\nJSON Parse Error: {str(e)}")
                print(f"Raw response that failed to parse: {raw_response}")
                raise ValueError(f"Failed to parse LLM response as JSON: {raw_response}")
            
            # Validate the data structure
            try:
                receipt_data = ReceiptData(**cleaned_data)
            except Exception as e:
                print(f"\nValidation Error: {str(e)}")
                raise ValueError(f"Invalid receipt data format: {str(e)}")
            
            # Return both the structured data and raw outputs
            return {
                "parsed_data": receipt_data.dict(),
                "raw_data": {
                    "ocr_text": extracted_text,
                    "llm_response": raw_response
                }
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except Exception as e:
        print(f"\nGeneral Error: {str(e)}")
        raise ValueError(f"Failed to process receipt: {str(e)}") 