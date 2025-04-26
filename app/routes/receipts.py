from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.services.ocr import get_image_data
from app.services.ocr_llm import ocr_llm_process_receipt
from app.services.transaction_processor import process_transaction_screenshot
from app.services.database_service import DatabaseService
from app.routes.auth import get_current_user
from app.services.supabase_client import supabase
import logging
import json
from datetime import datetime

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
                    transaction_data=processed_data['parsed_data']
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
        
        # Store the transaction(s) in database
        if processed_data and 'parsed_data' in processed_data:
            # Handle both single and multiple transactions
            transactions_data = processed_data['parsed_data']
            if not isinstance(transactions_data, list):
                transactions_data = [transactions_data]
            
            try:
                # Store each transaction
                stored_transactions = []
                for transaction in transactions_data:
                    stored_transaction = await db_service.store_transaction(
                        user_id=current_user['id'],
                        transaction_data=transaction
                    )
                    stored_transactions.append(stored_transaction)
                
                # Add the database IDs to the response
                if len(stored_transactions) == 1:
                    processed_data['transaction_id'] = stored_transactions[0]['id']
                else:
                    processed_data['transaction_ids'] = [t['id'] for t in stored_transactions]
            except ValueError as ve:
                if "Profile not found" in str(ve):
                    raise HTTPException(
                        status_code=404,
                        detail="User profile not found. Please ensure your account is properly set up."
                    )
                raise ve
        
        return processed_data
        
    except Exception as e:
        # If something goes wrong, let the user know
        error_msg = str(e)
        status_code = 404 if "Profile not found" in error_msg else 500
        raise HTTPException(
            status_code=status_code,
            detail=f"Sorry, we couldn't process your transaction screenshot: {error_msg}"
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
        print(f"DEBUG: Fetching transactions for user ID: {user_id}")
        
        # Set authorization header for the Supabase client's postgrest instance
        supabase.postgrest.auth(access_token)
        
        # Get total count of transactions for this user
        count_result = (
            supabase.table('transactions')
            .select('id', count='exact')
            .eq('user_id', user_id)
            .execute()
        )
        print(f"DEBUG: Count result: {count_result}")
        total_count = getattr(count_result, 'count', 0)
        logging.info(f"Found {total_count} transactions for user {user_id}")
        
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
                logging.error(f"Error processing transaction {trans.get('id')}: {str(e)}")
                continue
        
        result = {
            'transactions': transactions,
            'total': total_count
        }
        logging.info(f"Returning {len(transactions)} transactions out of {total_count} total")
        return result
        
    except Exception as e:
        logging.error(f"Error fetching transactions: {str(e)}")
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
            transaction_data=transaction_data
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
        # First verify the transaction belongs to the user
        response = supabase.table('transactions').select('*').eq('id', transaction_id).eq('user_id', current_user['id']).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=404,
                detail="Transaction not found or you don't have permission to delete it"
            )
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error deleting transaction: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete transaction: {str(e)}"
        )

async def update_transaction():
    ...

