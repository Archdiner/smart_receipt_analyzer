import os
from typing import Dict
from openai import OpenAI
from pydantic import BaseModel
from paddleocr import PaddleOCR
import base64
import tempfile
from PIL import Image
import io
import json

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"
)

# Initialize PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')

# Define transaction data structure
class TransactionData(BaseModel):
    vendor: str      # Store/merchant name
    total: float     # Transaction amount
    date: str        # Transaction date
    sector: str      # Business sector
    currency: str    # Transaction currency
    transaction_type: str = "sms"  # Type of transaction
    uncertain_category: bool = False   # Flag for uncertain categorization

# Import sectors from existing OCR_LLM service
from .ocr_llm import SECTORS

def extract_text_with_ocr(image_path: str) -> str:
    """Extract text from transaction screenshot using PaddleOCR."""
    result = ocr.ocr(image_path, cls=True)
    
    extracted_text = []
    for line in result:
        for item in line:
            text = item[1][0]  # Get the text
            confidence = item[1][1]  # Get confidence score
            if confidence > 0.5:  # Only include text with good confidence
                extracted_text.append(text)
    
    return "\n".join(extracted_text)

def create_transaction_prompt(extracted_text: str) -> str:
    """Create instructions for the AI to process the transaction text."""
    sectors_str = '", "'.join(SECTORS)
    return f"""
Analyze the following text extracted from a bank transaction notification:

{extracted_text}

Extract these key details:
1. Vendor/Merchant name: Carefully analyze the text to find the business name. It might be:
   - In a website URL (e.g., 'something.com' -> 'Something')
   - Part of a longer string with extra characters
   - Mixed with transaction codes or IDs
   - Using asterisks or special characters (e.g., 'STORE*NAME' -> 'Store Name')
   Make the final name as readable as possible by:
   - Removing special characters, transaction codes, and unnecessary spaces
   - Converting URL-style names to proper business names
   - Using proper capitalization
   - Making abbreviations more readable if their meaning is clear
   - Removing location codes or merchant IDs (e.g., numbers after the name)

2. Total amount (as a number)
3. Date of transaction (convert to YYYY-MM-DD format)
4. Currency (e.g., BHD, USD). If not found, default to BHD
5. Business sector (MUST be one of: "{sectors_str}")
6. Uncertain category: Set to true if you're not confident about the sector classification

If you're unsure about the business sector for a vendor, you should:
1. Set uncertain_category to true
2. Make an educated guess based on the vendor name and transaction details
3. If you can't determine the sector confidently, use "Miscellaneous"

Respond with ONLY valid JSON in this structure:
{{
    "vendor": "merchant_name",
    "total": amount_as_number,
    "date": "YYYY-MM-DD",
    "currency": "currency_code",
    "sector": "one of the predefined categories",
    "uncertain_category": boolean
}}

Do not include any text outside the JSON. Use ONLY information found in the provided text. If currency is not found, default to "BHD"."""

def process_transaction_screenshot(base64_image: str) -> Dict:
    """
    Process a transaction screenshot using OCR and LLM analysis.
    
    Args:
        base64_image: Base64 encoded image data
        
    Returns:
        Dict containing both parsed transaction data and raw outputs
        
    Raises:
        ValueError: If processing fails
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
            prompt = create_transaction_prompt(extracted_text)
            
            # Process with LLM
            response = client.chat.completions.create(
                model="gpt-4o-mini",  # Using GPT-4 for better accuracy
                messages=[
                    {
                        "role": "system",
                        "content": "You are analyzing bank transaction notifications. Respond with JSON objects separated by '***' for multiple transactions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0,
                response_format={"type": "text"}  # Changed to text to allow multiple JSONs
            )
            
            # Get the response and split into individual transactions
            result = response.choices[0].message.content.strip()
            print("\nRaw LLM Response:", result)
            
            # Split the response into individual transaction JSONs
            transaction_jsons = result.split('***')
            parsed_transactions = []
            
            for idx, transaction_json in enumerate(transaction_jsons):
                try:
                    # Clean and parse the JSON
                    cleaned_json = transaction_json.strip()
                    if not cleaned_json:  # Skip empty strings
                        continue
                        
                    parsed_result = json.loads(cleaned_json)
                    print(f"\nParsed JSON {idx + 1}:", parsed_result)
                    
                    # Validate against TransactionData model
                    transaction_data = TransactionData(**parsed_result)
                    parsed_transactions.append(transaction_data.dict())
                    
                except json.JSONDecodeError as e:
                    print(f"\nJSON Parse Error in transaction {idx + 1}: {str(e)}")
                    print(f"Problematic JSON: {cleaned_json}")
                    continue
                except Exception as e:
                    print(f"\nValidation Error in transaction {idx + 1}: {str(e)}")
                    continue
            
            if not parsed_transactions:
                raise ValueError("No valid transactions could be parsed from the response")
            
            # Return both the structured data and raw outputs
            return {
                "parsed_data": parsed_transactions,
                "raw_data": {
                    "ocr_text": extracted_text,
                    "llm_response": result
                }
            }
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                
    except Exception as e:
        raise ValueError(f"Failed to process transaction screenshot: {str(e)}") 