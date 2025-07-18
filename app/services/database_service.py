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
from .utils import json_serial, format_json_for_logging

# Initialize OpenAI client
openai_client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url="https://api.openai.com/v1"
)

# json_serial function is now imported from utils.py - no duplicate definition needed

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
        result = ' '.join(word for word in normalized.split() if word not in stop_words)
        print(f"Normalized vendor name '{vendor}' to '{result}'")
        return result
    
    def calculate_similarity_score(self, new_vendor: str, existing_vendor: str) -> float:
        """Calculate similarity score using multiple methods."""
        # Normalize both names
        norm_new = self.normalize_vendor_name(new_vendor)
        norm_existing = self.normalize_vendor_name(existing_vendor)
        
        # Get individual words
        new_words = set(norm_new.split())
        existing_words = set(norm_existing.split())
        
        # Calculate similarity scores - only keep the most useful ones
        token_set_ratio = fuzz.token_set_ratio(norm_new, norm_existing)
        
        # Calculate word overlap
        common_words = new_words.intersection(existing_words)
        word_overlap = len(common_words) / max(len(new_words), len(existing_words)) * 100
        
        # Check for common store name patterns
        is_store_variation = False
        store_types = {'market', 'hypermarket', 'supermarket', 'store', 'shop', 'mart'}
        new_words_no_type = new_words - store_types
        existing_words_no_type = existing_words - store_types
        
        # If the core names match after removing store types, it's likely a variation
        if new_words_no_type == existing_words_no_type and new_words_no_type:
            is_store_variation = True
        
        # Calculate final score with optimized weights
        final_score = (
            token_set_ratio * 0.40 +      # Word order independent similarity (increased)
            word_overlap * 0.40 +         # Word overlap (increased)
            (100 if is_store_variation else 0) * 0.20  # Store variation bonus (increased)
        )
        
        print(f"\nSimilarity scores for '{new_vendor}' vs '{existing_vendor}':")
        print(f"Token set ratio: {token_set_ratio}%")
        print(f"Word overlap: {word_overlap}%")
        print(f"Is store variation: {is_store_variation}")
        print(f"Final score: {final_score}%")
        
        return final_score
    
    async def verify_with_openai(self, new_vendor: str, existing_vendor: str) -> bool:
        """Use OpenAI to verify if vendors are similar."""
        print(f"\nVerifying vendors with OpenAI:")
        print(f"New vendor: {new_vendor}")
        print(f"Existing vendor: {existing_vendor}")
        
        prompt = f"""
        Are these two vendor names referring to the same business?
        Vendor 1: {new_vendor}
        Vendor 2: {existing_vendor}
        
        Consider:
        - Different spellings/formats (e.g., "Talabt TMART" vs "talabt mart")
        - Common abbreviations
        - Branch indicators (e.g., "Lulu Hypermarket" vs "Lulu")
        - Different store types (e.g., "supermarket" vs "hypermarket")
        - Partial matches (e.g., "Lulu Market" is the same as "Lulu Hypermarket")
        
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
            result = response.choices[0].message.content.strip().lower() == 'true'
            print(f"OpenAI verification result: {result}")
            return result
        except Exception as e:
            print(f"OpenAI API error: {str(e)}")
            return False
    
    async def find_matching_vendor(self, new_vendor: str, existing_vendors: List[Dict]) -> Optional[Dict]:
        """
        Find matching vendor using hybrid approach.
        Returns the matching vendor dict if found, None otherwise.
        """
        print(f"\nFinding match for vendor: {new_vendor}")
        print(f"Number of existing vendors to check: {len(existing_vendors)}")
        
        best_match = None
        best_score = 0
        
        for vendor in existing_vendors:
            print(f"\nChecking against existing vendor: {vendor['name']}")
            score = self.calculate_similarity_score(new_vendor, vendor['name'])
            
            if score > best_score:
                best_score = score
                best_match = vendor
        
        if best_match:
            print(f"\nBest match found: {best_match['name']} with score {best_score}%")
            
            # Direct match if score > 80 (increased from 60)
            if best_score > 80:
                print(f"Found direct match with score {best_score}%")
                return best_match
            
            # OpenAI verification if score between 65 and 80 (adjusted range)
            if 65 <= best_score <= 80:
                print(f"Score {best_score}% is in verification range (65-80)")
                cache_key = f"{new_vendor}|||{best_match['name']}"
                
                # Check cache first
                if cache_key in self.similarity_cache:
                    print(f"Found cached result: {self.similarity_cache[cache_key]}")
                    if self.similarity_cache[cache_key]:
                        return best_match
                    return None
                
                # Verify with OpenAI
                print("No cached result, verifying with OpenAI...")
                is_similar = await self.verify_with_openai(new_vendor, best_match['name'])
                self.similarity_cache[cache_key] = is_similar
                
                if is_similar:
                    print("OpenAI confirmed match")
                    return best_match
                else:
                    print("OpenAI rejected match")
        
        print("No matching vendor found")
        return None

class DatabaseService:
    def __init__(self):
        self.vendor_matcher = VendorMatcher()
    
    def _set_auth_token(self, access_token: str):
        """Set the authentication token for Supabase client."""
        supabase.postgrest.auth(access_token)
    
    def _handle_supabase_error(self, e: Exception) -> None:
        """Handle Supabase-specific errors."""
        error_msg = str(e)
        if "42501" in error_msg:  # Permission denied
            raise ValueError("Permission denied. Please ensure you have the necessary permissions.")
        elif "23505" in error_msg:  # Unique violation
            raise ValueError("A record with this information already exists.")
        elif "23503" in error_msg:  # Foreign key violation
            raise ValueError("Referenced record does not exist.")
        else:
            raise e
    
    async def _get_vendor_id(self, vendor_name: str, access_token: str) -> str:
        """
        Get the vendor ID for a given vendor name, creating a new vendor if it doesn't exist.
        Uses fuzzy matching with OpenAI verification for vendor matching.
        
        Args:
            vendor_name (str): The name of the vendor to look up
            access_token (str): The user's access token for authentication
            
        Returns:
            str: The vendor ID
        """
        if not vendor_name:
            raise ValueError("Vendor name cannot be empty")
            
        try:
            # Set authentication token
            self._set_auth_token(access_token)
            
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
            
            try:
                response = supabase.table('vendors').insert(new_vendor).execute()
                if not response.data:
                    raise ValueError("Failed to create new vendor")
                return response.data[0]['id']
            except Exception as e:
                self._handle_supabase_error(e)
            
        except Exception as e:
            print(f"Error in _get_vendor_id: {str(e)}")
            raise
    
    def get_category_id(self, category_name: str, access_token: str) -> str:
        """Get category ID from category name."""
        try:
            # Set authentication token
            self._set_auth_token(access_token)
            
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
            print(f"Error in get_category_id: {str(e)}")
            self._handle_supabase_error(e)
    
    async def store_transaction(self, user_id: str, transaction_data: Dict, access_token: str) -> Dict:
        """Store transaction in database with proper relationships."""
        try:
            # Set authentication token
            self._set_auth_token(access_token)
            
            # Validate required fields
            required_fields = ['vendor', 'date', 'total', 'sector', 'currency']
            missing_fields = [field for field in required_fields if field not in transaction_data]
            if missing_fields:
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
            # Get or create vendor
            vendor_id = await self._get_vendor_id(transaction_data['vendor'], access_token)
            
            # Get category ID
            category_id = self.get_category_id(transaction_data['sector'], access_token)
            
            # Prepare transaction data
            new_transaction = {
                'user_id': user_id,  # This references profiles.id which is the same as auth.users.id
                'vendor_id': vendor_id,
                'category_id': category_id,
                'date': transaction_data['date'],
                'currency': transaction_data['currency'],
                'total_amount': float(transaction_data['total']),  # Ensure numeric
                'raw_data': format_json_for_logging(transaction_data),  # Store only the parsed data
                'receipt_url': None,  # Will be updated later when cloud storage is implemented
                'created_at': datetime.utcnow().isoformat()
            }
            
            try:
                # Insert transaction
                response = supabase.table('transactions').insert(new_transaction).execute()
                if not response.data:
                    raise ValueError("Failed to create transaction")
                return response.data[0]
            except Exception as e:
                self._handle_supabase_error(e)
            
        except Exception as e:
            print(f"Error in store_transaction: {str(e)}")
            raise 