from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.ocr import get_image_data
from app.services.ocr_llm import ocr_llm_process_receipt
from app.services.transaction_processor import process_transaction_screenshot
from app.services.database_service import DatabaseService
from app.routes.auth import get_current_user
from app.services.supabase_client import supabase
import logging
import json
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

def json_serial(obj):
    """JSON serializer for objects not serializable by default json code"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

router = APIRouter()
db_service = DatabaseService()

@router.post("/analyze-expense")
async def analyze_expense_route(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze a receipt image and return organized data.
    
    This endpoint uses AI to directly analyze the receipt image and extract:
    - Vendor name
    - Date
    - Total amount
    - Individual items with quantities and prices
    - VAT amount (if present)
    - Overall category
    
    Then stores the data in the database with proper relationships.
    """
    try:
        # Log the current user info for debugging
        logging.info(f"Processing expense for user: {current_user['id']}")
        
        # Get the image data
        image_data = await get_image_data(file)
        
        # Process the receipt using AI
        processed_data = ocr_llm_process_receipt(image_data)
        logging.info(f"Processed receipt data: {json.dumps(processed_data, default=json_serial, indent=2)}")
        
        # Store the transaction in database
        if processed_data and 'parsed_data' in processed_data:
            try:
                stored_transaction = await db_service.store_transaction(
                    user_id=current_user['id'],
                    transaction_data=processed_data['parsed_data'],
                    access_token=current_user['access_token']
                )
                # Add the database ID to the response
                processed_data['transaction_id'] = stored_transaction['id']
                logging.info(f"Successfully stored transaction: {json.dumps(stored_transaction, default=json_serial, indent=2)}")
            except ValueError as ve:
                if "Profile not found" in str(ve):
                    logging.error(f"Profile not found error: {str(ve)}")
                    raise HTTPException(
                        status_code=404,
                        detail="User profile not found. Please ensure your account is properly set up."
                    )
                logging.error(f"Other ValueError in transaction storage: {str(ve)}")
                raise ve
            except Exception as e:
                logging.error(f"Unexpected error storing transaction: {str(e)}")
                raise
        
        return processed_data
        
    except Exception as e:
        # If something goes wrong, let the user know
        error_msg = str(e)
        status_code = 404 if "Profile not found" in error_msg else 500
        logging.error(f"Final error in analyze-expense: {error_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=f"Sorry, we couldn't process your receipt: {error_msg}"
        )

@router.post("/analyze-transaction")
async def analyze_transaction_route(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    """
    Analyze a bank transaction screenshot and return organized data.
    
    This endpoint uses AI to analyze transaction notification screenshots and extract:
    - Vendor/merchant name
    - Transaction amount and currency
    - Transaction date
    - Business sector
    
    Then stores the data in the database with proper relationships.
    """
    try:
        # Get the image data
        image_data = await get_image_data(file)
        
        # Process the transaction screenshot
        processed_data = process_transaction_screenshot(image_data)
        print(f"Processed transaction data: {json.dumps(processed_data, default=json_serial, indent=2)}")
        
        # Store the transaction(s) in database
        if processed_data and 'parsed_data' in processed_data:
            try:
                # Ensure we have all required fields
                transaction_data = processed_data['parsed_data']
                if isinstance(transaction_data, list):
                    transaction_data = transaction_data[0]  # Take first transaction if multiple
                
                # Add transaction type if not present
                if 'transaction_type' not in transaction_data:
                    transaction_data['transaction_type'] = 'sms'
                
                print(f"Storing transaction data: {json.dumps(transaction_data, default=json_serial, indent=2)}")
                
                stored_transaction = await db_service.store_transaction(
                    user_id=current_user['id'],
                    transaction_data=transaction_data,
                    access_token=current_user['access_token']
                )
                # Add the database ID to the response
                processed_data['transaction_id'] = stored_transaction['id']
                print(f"Successfully stored transaction: {json.dumps(stored_transaction, default=json_serial, indent=2)}")
            except ValueError as ve:
                if "Profile not found" in str(ve):
                    print(f"Profile not found error: {str(ve)}")
                    raise HTTPException(
                        status_code=404,
                        detail="User profile not found. Please ensure your account is properly set up."
                    )
                print(f"Other ValueError in transaction storage: {str(ve)}")
                raise ve
            except Exception as e:
                print(f"Unexpected error storing transaction: {str(e)}")
                raise
        
        return processed_data
        
    except Exception as e:
        # If something goes wrong, let the user know
        error_msg = str(e)
        status_code = 404 if "Profile not found" in error_msg else 500
        print(f"Final error in analyze-transaction: {error_msg}")
        raise HTTPException(
            status_code=status_code,
            detail=f"Sorry, we couldn't process your transaction: {error_msg}"
        )

@router.get("/transactions")
async def get_user_transactions(
    current_user: dict = Depends(get_current_user),
    limit: int = 10,
    offset: int = 0
):
    """Get user's transactions with pagination."""
    try:
        user_id = current_user['id']
        access_token = current_user.get('access_token')
        print(f"Fetching transactions for user ID: {user_id}")
        
        # Set authorization header for the Supabase client's postgrest instance
        supabase.postgrest.auth(access_token)
        
        try:
            # Get total count of transactions for this user
            count_result = (
                supabase.table('transactions')
                .select('id', count='exact')
                .eq('user_id', user_id)
                .execute()
            )
            total_count = getattr(count_result, 'count', 0)
            print(f"Found {total_count} transactions for user {user_id}")
            
            if total_count == 0:
                return {
                    'transactions': [],
                    'total': 0
                }
            
            # Fetch transactions with pagination
            response = (
                supabase.table('transactions')
                .select('''
                    id,
                    date,
                    currency,
                    total_amount,
                    raw_data,
                    created_at,
                    user_id,
                    vendor_id,
                    category_id
                ''')
                .eq('user_id', user_id)
                .order('created_at', desc=True)
                .range(offset, offset + limit - 1)
                .execute()
            )
            
            transactions = []
            for trans in response.data:
                try:
                    # Get vendor name
                    if trans.get('vendor_id'):
                        vendor = supabase.table('vendors').select('name').eq('id', trans['vendor_id']).execute()
                        vendor_name = vendor.data[0]['name'] if vendor.data else None
                    else:
                        vendor_name = None
                    
                    # Get category name
                    if trans.get('category_id'):
                        category = supabase.table('categories').select('name').eq('id', trans['category_id']).execute()
                        category_name = category.data[0]['name'] if category.data else None
                    else:
                        category_name = None
                    
                    formatted_transaction = {
                        'id': trans.get('id'),
                        'date': trans.get('date'),
                        'currency': trans.get('currency'),
                        'total_amount': float(trans.get('total_amount', 0)),
                        'vendor_name': vendor_name,
                        'category_name': category_name,
                        'created_at': trans.get('created_at'),
                        'raw_data': trans.get('raw_data')
                    }
                    transactions.append(formatted_transaction)
                except Exception as e:
                    print(f"Error processing transaction {trans.get('id')}: {str(e)}")
                    continue
            
            result = {
                'transactions': transactions,
                'total': total_count
            }
            print(f"Returning {len(transactions)} transactions out of {total_count} total")
            return result
            
        except Exception as e:
            error_msg = str(e)
            if "42501" in error_msg:  # Permission denied
                raise HTTPException(
                    status_code=403,
                    detail="Permission denied. Please ensure you have the necessary permissions."
                )
            elif "23503" in error_msg:  # Foreign key violation
                raise HTTPException(
                    status_code=404,
                    detail="Referenced record does not exist."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error fetching transactions: {error_msg}"
                )
                
    except Exception as e:
        print(f"Error fetching transactions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching transactions: {str(e)}"
        )

@router.post("/transactions")
async def create_transaction(
    transaction_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Create a new transaction directly.
    
    Required fields in transaction_data:
    - vendor: str (vendor name)
    - date: str (YYYY-MM-DD)
    - total: float (transaction amount)
    - sector: str (business sector/category) ***NOTE: LATER ADD AI TO DETERMINE THIS
    - currency: str (e.g., BHD, USD)
    
    Optional fields:
    - transaction_type: str (defaults to "manual")
    - uncertain_category: bool (defaults to False) ***NOTE: LATER ADD AI TO DETERMINE THIS
    """
    try:
        # Validate required fields
        required_fields = ['vendor', 'date', 'total', 'sector', 'currency']
        missing_fields = [field for field in required_fields if field not in transaction_data]
        if missing_fields:
            raise HTTPException(
                status_code=400,
                detail=f"Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Store the transaction
        stored_transaction = await db_service.store_transaction(
            user_id=current_user['id'],
            transaction_data=transaction_data,
            access_token=current_user['access_token']
        )
        
        return {
            "message": "Transaction created successfully",
            "transaction": stored_transaction
        }
        
    except ValueError as ve:
        if "Profile not found" in str(ve):
            raise HTTPException(
                status_code=404,
                detail="User profile not found. Please ensure your account is properly set up."
            )
        raise HTTPException(
            status_code=400,
            detail=str(ve)
        )
    except Exception as e:
        logging.error(f"Error creating transaction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create transaction: {str(e)}"
        )

@router.delete("/remove-transaction")
async def remove_transaction(
    transaction_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a transaction from the database.
    
    Args:
        transaction_id: The ID of the transaction to remove (as query parameter)
        current_user: The current authenticated user
        
    Returns:
        dict: Success message and removed transaction details
    """
    try:
        # Set authentication token
        supabase.postgrest.auth(current_user['access_token'])
        
        try:
            # First verify the transaction belongs to the user
            response = supabase.table('transactions').select('*').eq('id', transaction_id).eq('user_id', current_user['id']).execute()
            
            if not response.data:
                # Transaction doesn't exist or doesn't belong to user
                return {
                    "message": "Transaction not found or already deleted",
                    "transaction_id": transaction_id
                }
            
            # Delete the transaction
            delete_response = supabase.table('transactions').delete().eq('id', transaction_id).execute()
            
            if not delete_response.data:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to delete transaction"
                )
            
            return {
                "message": "Transaction deleted successfully",
                "transaction_id": transaction_id
            }
            
        except Exception as e:
            error_msg = str(e)
            if "42501" in error_msg:  # Permission denied
                raise HTTPException(
                    status_code=403,
                    detail="Permission denied. Please ensure you have the necessary permissions."
                )
            elif "23503" in error_msg:  # Foreign key violation
                raise HTTPException(
                    status_code=404,
                    detail="Referenced record does not exist."
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to delete transaction: {error_msg}"
                )
                
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting transaction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete transaction: {str(e)}"
        )

@router.put("/update-transaction/{transaction_id}")
async def update_transaction(
    transaction_id: str,
    update_data: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Update a transaction with partial updates.
    Args:
        transaction_id: The ID of the transaction to update
        update_data: Dictionary containing fields to update (vendor_id, date, currency, category_id, total_amount)
        current_user: The current authenticated user
    Returns:
        dict: Updated transaction details
    """
    try:
        print(f"Starting update for transaction {transaction_id}")
        
        # Set authentication token
        supabase.postgrest.auth(current_user['access_token'])
        
        # First verify the transaction belongs to the user and get current data
        response = supabase.table('transactions').select('*').eq('id', transaction_id).eq('user_id', current_user['id']).execute()
        
        if not response.data:
            print(f"Transaction {transaction_id} not found or doesn't belong to user {current_user['id']}")
            raise HTTPException(
                status_code=404,
                detail="Transaction not found or doesn't belong to user"
            )
        
        current_transaction = response.data[0]
        
        # If vendor is being updated, check for matches
        if 'vendor' in update_data and update_data['vendor'] is not None:
            print(f"Checking for vendor match: {update_data['vendor']}")
            vendor_match_response = await match_vendor(update_data['vendor'], current_user)
            
            if vendor_match_response.get('vendor_id'):
                update_data['vendor_id'] = vendor_match_response['vendor_id']
                print(f"Set vendor_id to: {update_data['vendor_id']}")
        
        # Extract fields that can be updated
        updated_fields = {}
        allowed_fields = ['vendor_id', 'date', 'currency', 'category_id', 'total_amount']
        
        # Check which fields to update
        for field in allowed_fields:
            if field in update_data and update_data[field] is not None:
                updated_fields[field] = update_data[field]
                print(f"Will update {field}: {update_data[field]}")
        
        # Ensure numeric values
        if 'total_amount' in updated_fields:
            updated_fields['total_amount'] = float(updated_fields['total_amount'])
        
        if not updated_fields:
            return {
                "message": "No fields to update",
                "transaction": current_transaction
            }
        
        # Execute the actual update
        update_response = (
            supabase.table('transactions')
            .update(updated_fields)
            .eq('id', transaction_id)
            .execute()
        )
        
        if update_response.data:
            print(f"Update successful: {json.dumps(update_response.data[0], default=json_serial)}")
            return {
                "message": "Transaction updated successfully",
                "transaction": update_response.data[0]
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to update transaction: No data returned"
            )
    
    except HTTPException:
        raise
    except Exception as e:
        error_msg = str(e)
        print(f"Error updating transaction: {error_msg}")
        
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update transaction: {error_msg}"
        )

@router.get("/vendors/match")
async def match_vendor(
    vendor_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Match a vendor name against existing vendors using fuzzy matching.
    
    Args:
        vendor_name: The vendor name to match
        current_user: The current authenticated user
        
    Returns:
        dict: Matching vendor information if found
    """
    try:
        # Set authentication token
        supabase.postgrest.auth(current_user['access_token'])
        
        # Get all existing vendors
        response = supabase.table('vendors').select('id, name').execute()
        existing_vendors = response.data if response.data else []
        
        # If we have existing vendors, try to find a match
        if existing_vendors:
            matched_vendor = await db_service.vendor_matcher.find_matching_vendor(
                vendor_name,
                existing_vendors
            )
            
            if matched_vendor:
                return {
                    "matched_vendor": matched_vendor['name'],
                    "vendor_id": matched_vendor['id']
                }
        
        return {"matched_vendor": None}
        
    except Exception as e:
        print(f"Error in match_vendor: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to match vendor: {str(e)}"
        )

@router.get("/categories")
async def get_categories(current_user: dict = Depends(get_current_user)):
    """
    Get all available categories for the dropdown.
    """
    try:
        supabase.postgrest.auth(current_user['access_token'])
        response = supabase.table('categories').select('id, name').execute()
        if not response.data:
            return []
        return response.data
    except Exception as e:
        print(f"Error fetching categories: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch categories: {str(e)}"
        )

@router.get("/debug-transaction-rls/{transaction_id}")
async def debug_transaction_rls(
    transaction_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Debug endpoint to check RLS policy for a specific transaction.
    
    This endpoint attempts a minimal update (same values) to test if RLS allows it.
    """
    try:
        print(f"[DEBUG] Testing RLS for transaction {transaction_id}")
        
        # Set authentication token
        supabase.postgrest.auth(current_user['access_token'])
        
        # Get current transaction data
        response = supabase.table('transactions').select('*').eq('id', transaction_id).eq('user_id', current_user['id']).execute()
        
        if not response.data:
            return {"error": "Transaction not found or access denied", "status": "failed"}
        
        current_transaction = response.data[0]
        print(f"[DEBUG] Current transaction: {json.dumps(current_transaction, default=json_serial)}")
        
        # Create an update with exactly the same values (no changes)
        # This should always succeed if RLS policy is configured correctly
        debug_fields = {
            'vendor_id': current_transaction.get('vendor_id'),
            'date': current_transaction.get('date'),
            'currency': current_transaction.get('currency'),
            'category_id': current_transaction.get('category_id'),
            'total_amount': current_transaction.get('total_amount'),
            'raw_data': current_transaction.get('raw_data'),
            'receipt_url': current_transaction.get('receipt_url'),
            'created_at': current_transaction.get('created_at'),
            'user_id': current_transaction.get('user_id')
        }
        
        print(f"[DEBUG] Testing update with identical values: {json.dumps(debug_fields, default=json_serial)}")
        
        # Try the update
        try:
            debug_response = (
                supabase.table('transactions')
                .update(debug_fields)
                .eq('id', transaction_id)
                .execute()
            )
            
            if debug_response.data:
                return {
                    "message": "RLS test passed! Policy allows updates.",
                    "status": "success",
                    "fields_allowed": list(debug_fields.keys())
                }
            else:
                return {
                    "message": "Update succeeded but returned no data.",
                    "status": "warning"
                }
                
        except Exception as e:
            error_msg = str(e)
            return {
                "message": f"RLS test failed! Error: {error_msg}",
                "status": "failed",
                "error": error_msg,
                "attempted_fields": list(debug_fields.keys())
            }
            
    except Exception as e:
        error_msg = str(e)
        print(f"[DEBUG] Error in RLS test: {error_msg}")
        
        return {
            "message": f"Debug operation failed: {error_msg}",
            "status": "error"
        }

