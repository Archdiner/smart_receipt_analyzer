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
from .base_processor import BaseProcessor, BaseTransactionData, SECTORS

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

class ReceiptProcessor(BaseProcessor):
    """Processor for receipt images."""
    
    def process_receipt(self, base64_image: str) -> dict:
        """
        Process a receipt image using OCR and LLM analysis.
        
        Args:
            base64_image: Base64 encoded image data
            
        Returns:
            Dict containing both parsed receipt data and raw outputs
            
        Raises:
            ValueError: If processing fails
        """
        # Use the base processor's process_image method with receipt type
        result = self.process_image(base64_image, "receipt")
        
        # Add receipt-specific data if needed
        result['parsed_data']['transaction_type'] = "receipt"
        
        return result

# Create a singleton instance
receipt_processor = ReceiptProcessor()

def ocr_llm_process_receipt(base64_image: str) -> dict:
    """Wrapper function to maintain backward compatibility."""
    return receipt_processor.process_receipt(base64_image) 