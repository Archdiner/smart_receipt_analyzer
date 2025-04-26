from typing import Dict, List, Optional, Tuple, Union, Any
import os
from openai import OpenAI
from thefuzz import fuzz
from functools import lru_cache
import re
from datetime import datetime
import json
import logging
from .supabase_client import supabase

# Initialize OpenAI client
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"
)

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

class VendorMatcher:
    def __init__(self):
        self.similarity_cache = {}
    
    @lru_cache(maxsize=1000)
    def normalize_vendor_name(self, vendor: str) -> str:
        """Normalize vendor name for initial comparison."""
        # Remove special characters and extra spaces
        normalized = re.sub(r'[^\w\s]', '', vendor.lower().strip())
        # Remove common words that don't affect matching
        stop_words = {'the', 'and', 'or', 'ltd', 'limited', 'inc', 'incorporated'}
        return ' '.join(word for word in normalized.split() if word not in stop_words)
    
    async def verify_with_openai(self, new_vendor: str, existing_vendor: str) -> bool:
        """Use OpenAI to verify if vendors are similar."""
        prompt = f"""
        Are these two vendor names referring to the same business?
        Vendor 1: {new_vendor}
        Vendor 2: {existing_vendor}
        
        Consider:
        - Different spellings/formats (e.g., "Talabt TMART" vs "talabt mart")
        - Common abbreviations
        - Branch indicators (e.g., "Lulu Hypermarket" vs "Lulu")
        - Different store types (e.g., "supermarket" vs "hypermarket")
        
        Respond with ONLY 'true' or 'false'.
        """
        
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a vendor name matching expert. Respond only with 'true' or 'false'."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0
            )
            return response.choices[0].message.content.strip().lower() == 'true'
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            return False
    
    async def find_matching_vendor(self, new_vendor: str, existing_vendors: List[Dict]) -> Optional[Dict]:
        """
        Find matching vendor using hybrid approach.
        Returns the matching vendor dict if found, None otherwise.
        """
        normalized_new = self.normalize_vendor_name(new_vendor)
        
        for vendor in existing_vendors:
            normalized_existing = self.normalize_vendor_name(vendor['name'])
            ratio = fuzz.token_sort_ratio(normalized_new, normalized_existing)
            
            # Direct match if ratio > 85
            if ratio > 85:
                return vendor
            
            # OpenAI verification if ratio between 70 and 85
            if 70 <= ratio <= 85:
                cache_key = f"{new_vendor}|||{vendor['name']}"
                
                # Check cache first
                if cache_key in self.similarity_cache:
                    if self.similarity_cache[cache_key]:
                        return vendor
                    continue
                
                # Verify with OpenAI
                is_similar = await self.verify_with_openai(new_vendor, vendor['name'])
                self.similarity_cache[cache_key] = is_similar
                
                if is_similar:
                    return vendor
        
        return None

class DatabaseService:
    def __init__(self):
        self.vendor_matcher = VendorMatcher()
    
    async def _get_vendor_id(self, vendor_name: str) -> str:
        """
        Get the vendor ID for a given vendor name, creating a new vendor if it doesn't exist.
        Uses fuzzy matching with OpenAI verification for vendor matching.
        
        Args:
            vendor_name (str): The name of the vendor to look up
            
        Returns:
            str: The vendor ID
        """
        if not vendor_name:
            raise ValueError("Vendor name cannot be empty")
            
        try:
            # Get all existing vendors
            response = supabase.table('vendors').select('id, name').execute()
            existing_vendors = response.data if response.data else []
            
            # If we have existing vendors, try to find a match
            if existing_vendors:
                matched_vendor = await self.vendor_matcher.find_matching_vendor(
                    vendor_name,
                    existing_vendors
                )
                
                if matched_vendor:
                    return matched_vendor['id']
            
            # If no match found or no existing vendors, create a new vendor
            new_vendor = {
                'name': vendor_name,
                'created_at': datetime.utcnow().isoformat()
            }
            
            response = supabase.table('vendors').insert(new_vendor).execute()
            if not response.data:
                raise ValueError("Failed to create new vendor")
                
            return response.data[0]['id']
            
        except Exception as e:
            logging.error(f"Error in _get_vendor_id: {str(e)}")
            raise
    
    def get_category_id(self, category_name: str) -> str:
        """Get category ID from category name."""
        try:
            # First try to find exact match
            response = supabase.table('categories').select('id').eq('name', category_name).execute()
            
            if response.data:
                return response.data[0]['id']
            
            # If no exact match, try case-insensitive match
            response = supabase.table('categories').select('id').ilike('name', category_name).execute()
            
            if response.data:
                return response.data[0]['id']
            
            # If still no match, get ID for 'Uncategorized'
            response = supabase.table('categories').select('id').eq('name', 'Uncategorized').execute()
            if not response.data:
                raise ValueError("Could not find 'Uncategorized' category")
                
            return response.data[0]['id']
            
        except Exception as e:
            logging.error(f"Error in get_category_id: {str(e)}")
            raise
    
    async def store_transaction(self, user_id: str, transaction_data: Dict) -> Dict:
        """Store transaction in database with proper relationships."""
        try:
            # Validate required fields
            required_fields = ['vendor', 'date', 'total', 'sector', 'currency']
            missing_fields = [field for field in required_fields if field not in transaction_data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Get or create vendor
            vendor_id = await self._get_vendor_id(transaction_data['vendor'])
            
            # Get category ID
            category_id = self.get_category_id(transaction_data['sector'])
            
            # Prepare transaction data
            new_transaction = {
                'user_id': user_id,  # This references profiles.id which is the same as auth.users.id
                'vendor_id': vendor_id,
                'category_id': category_id,
                'date': transaction_data['date'],
                'currency': transaction_data['currency'],
                'total_amount': float(transaction_data['total']),  # Ensure numeric
                'raw_data': json.dumps(transaction_data, default=json_serial),  # Store only the parsed data
                'receipt_url': None,  # Will be updated later when cloud storage is implemented
                'created_at': datetime.utcnow().isoformat()
            }
            
            # Insert transaction
            response = supabase.table('transactions').insert(new_transaction).execute()
            if not response.data:
                raise ValueError("Failed to create transaction")
                
            return response.data[0]
            
        except Exception as e:
            logging.error(f"Error in store_transaction: {str(e)}")
            raise 