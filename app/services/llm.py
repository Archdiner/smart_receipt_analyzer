import os
import json
from typing import Dict
from openai import OpenAI
from pydantic import BaseModel

# Initialize the OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Define what a receipt looks like
class ReceiptData(BaseModel):
    vendor: str      # Store name
    date: str        # Purchase date
    total: str       # Total amount
    sector: str      # Overall category for this receipt

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

def create_processing_prompt(raw_text: str) -> str:
    """Create instructions for the AI to process the receipt text."""
    return f"""
Please help me understand this receipt:

{raw_text}

Instructions:
1. Find these key details:
   - Store name (clean it up, remove any extra text)
   - Date of purchase
   - Total amount paid
2. Based on the items listed, determine the overall category from these options: {', '.join(SECTORS)}
   - Choose the category that best represents the majority of items
   - If items are mixed, choose the most significant category

IMPORTANT: You must respond with ONLY valid JSON, no other text. The JSON must follow this exact structure:
{{
  "vendor": "clean store name",
  "date": "purchase date",
  "total": "total amount",
  "sector": "overall category"
}}

Example:
Input:
LuLu glg
04.02.2025
Total: 3.370
5322 Grnola Rasp ChsCke 35g 0.790
1 X 0.390 S8

Output:
{{
  "vendor": "LuLu",
  "date": "04.02.2025",
  "total": "3.37",
  "sector": "Groceries & Household Supplies"
}}
"""

def llm_process_receipt(raw_text: str) -> Dict:
    """
    Use AI to extract key information from receipt.
    
    Args:
        raw_text: The messy text from the receipt
        
    Returns:
        A clean, organized version of the receipt data
        
    Raises:
        ValueError: If something goes wrong with the processing
    """
    try:
        # Create instructions for the AI
        prompt = create_processing_prompt(raw_text)
        
        # Ask the AI to process the receipt
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You're helping me understand my receipts. You must respond with ONLY valid JSON, no other text."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        # Get the raw response for debugging
        raw_response = response.choices[0].message.content.strip()
        print("\nAI Response:", raw_response)  # Debug print
        
        # Clean the response to ensure it's valid JSON
        if raw_response.startswith("```json"):
            raw_response = raw_response[7:]
        if raw_response.endswith("```"):
            raw_response = raw_response[:-3]
        raw_response = raw_response.strip()
        
        # Try to parse the response
        try:
            cleaned_data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            print(f"\nJSON Parse Error: {str(e)}")
            print(f"Raw response that failed to parse: {raw_response}")
            raise ValueError(f"Sorry, I couldn't understand the AI's response. Here's what it said: {raw_response}")
            
        # Validate the data structure
        try:
            receipt_data = ReceiptData(**cleaned_data)
        except Exception as e:
            print(f"\nData Validation Error: {str(e)}")
            print(f"Parsed data that failed validation: {cleaned_data}")
            raise ValueError(f"Sorry, the AI's response wasn't in the right format. Here's what it said: {raw_response}")
        
        return receipt_data.dict()
        
    except Exception as e:
        print(f"\nGeneral Error: {str(e)}")
        raise ValueError(f"Something went wrong while processing your receipt: {str(e)}") 