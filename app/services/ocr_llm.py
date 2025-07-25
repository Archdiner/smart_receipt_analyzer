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

# SECTORS is now imported from base_processor.py - no duplicate definition needed

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