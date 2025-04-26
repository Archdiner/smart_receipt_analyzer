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
from .base_processor import BaseProcessor, BaseTransactionData, SECTORS

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
    "uncertain_category": boolean,
    "transaction_type": "sms"
}}

Do not include any text outside the JSON. Use ONLY information found in the provided text. If currency is not found, default to "BHD"."""

class TransactionProcessor(BaseProcessor):
    """Processor for transaction screenshots."""
    
    def process_transaction(self, base64_image: str) -> dict:
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
            # Use the base processor's process_image method with transaction type
            result = self.process_image(base64_image, "transaction")
            
            # Ensure the parsed data has all required fields
            if 'parsed_data' in result:
                parsed_data = result['parsed_data']
                if isinstance(parsed_data, list):
                    parsed_data = parsed_data[0]  # Take first transaction if multiple
                
                # Add transaction type if not present
                if 'transaction_type' not in parsed_data:
                    parsed_data['transaction_type'] = 'sms'
                
                # Ensure all required fields are present
                required_fields = ['vendor', 'date', 'total', 'sector', 'currency']
                missing_fields = [field for field in required_fields if field not in parsed_data]
                if missing_fields:
                    raise ValueError(f"Missing required fields in parsed data: {', '.join(missing_fields)}")
                
                result['parsed_data'] = parsed_data
            
            return result
            
        except Exception as e:
            print(f"Error in process_transaction: {str(e)}")
            raise

# Create a singleton instance
transaction_processor = TransactionProcessor()

def process_transaction_screenshot(base64_image: str) -> dict:
    """Wrapper function to maintain backward compatibility."""
    return transaction_processor.process_transaction(base64_image) 