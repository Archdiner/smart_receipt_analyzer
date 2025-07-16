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

# SECTORS is now imported from base_processor.py - no duplicate import needed

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