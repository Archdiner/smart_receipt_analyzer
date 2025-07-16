from typing import Dict, List, Optional
from pydantic import BaseModel
from openai import OpenAI
from paddleocr import PaddleOCR
import base64
import tempfile
import json
import os
import logging
from datetime import datetime

# Initialize OpenAI client
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"
)

# Initialize PaddleOCR
ocr = PaddleOCR(use_angle_cls=True, lang='en')

# Common sectors for both processors - SINGLE SOURCE OF TRUTH
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

class BaseTransactionData(BaseModel):
    """Base model for transaction data that both processors will use."""
    vendor: str      # Store/merchant name
    total: float     # Transaction amount
    date: str        # Transaction date
    sector: str      # Business sector
    currency: str    # Transaction currency
    transaction_type: str  # Type of transaction
    uncertain_category: bool = False   # Flag for uncertain categorization

class BaseProcessor:
    """Base class for both receipt and transaction processors."""
    
    def __init__(self):
        self.ocr = ocr
        self.client = client
    
    def extract_text_with_ocr(self, image_path: str) -> str:
        """Extract text from image using PaddleOCR."""
        result = self.ocr.ocr(image_path, cls=True)
        
        extracted_text = []
        for line in result:
            for item in line:
                text = item[1][0]  # Get the text
                confidence = item[1][1]  # Get confidence score
                if confidence > 0.5:  # Only include text with good confidence
                    extracted_text.append(text)
        
        return "\n".join(extracted_text)
    
    def get_sectors_string(self) -> str:
        """Get sectors as a formatted string for prompts."""
        return '", "'.join(SECTORS)
    
    def create_processing_prompt(self, extracted_text: str, prompt_type: str) -> str:
        """Create a prompt for the AI based on the type of document."""
        sectors_str = self.get_sectors_string()
        
        if prompt_type == "receipt":
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
        else:  # transaction/sms
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
    
    def process_image(self, base64_image: str, prompt_type: str) -> Dict:
        """
        Process an image using OCR and LLM analysis.
        
        Args:
            base64_image: Base64 encoded image data
            prompt_type: Type of document ("receipt" or "transaction")
            
        Returns:
            Dict containing both parsed data and raw outputs
            
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
                extracted_text = self.extract_text_with_ocr(temp_file_path)
                print("\nExtracted Text:", extracted_text)
                
                # Create instructions for the AI
                prompt = self.create_processing_prompt(extracted_text, prompt_type)
                
                # Process with LLM
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are analyzing document text. Respond with ONLY valid JSON."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    temperature=0,
                    response_format={"type": "json_object"}
                )
                
                # Get the response
                result = response.choices[0].message.content.strip()
                print("\nRaw LLM Response:", result)
                
                # Parse and validate the response
                try:
                    parsed_result = json.loads(result)
                    print("\nParsed JSON:", parsed_result)
                    
                    # Ensure transaction_type is present
                    if "transaction_type" not in parsed_result:
                        parsed_result["transaction_type"] = prompt_type

                    # Validate against BaseTransactionData model
                    transaction_data = BaseTransactionData(**parsed_result)
                    
                    # Return both the structured data and raw outputs
                    return {
                        "parsed_data": transaction_data.dict(),
                        "raw_data": {
                            "ocr_text": extracted_text,
                            "llm_response": result
                        }
                    }
                    
                except json.JSONDecodeError as e:
                    print(f"\nJSON Parse Error: {str(e)}")
                    print(f"Raw response that failed to parse: {result}")
                    raise ValueError(f"Failed to parse LLM response as JSON: {result}")
                except Exception as e:
                    print(f"\nValidation Error: {str(e)}")
                    raise ValueError(f"Invalid transaction data format: {str(e)}")
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                    
        except Exception as e:
            print(f"\nGeneral Error: {str(e)}")
            raise ValueError(f"Failed to process document: {str(e)}") 