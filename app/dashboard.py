import streamlit as st
import requests
from PIL import Image
import io
import json
import base64
from datetime import datetime
import time
import pandas as pd

# API Configuration
API_URL = "http://localhost:8000/api"

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user' not in st.session_state:
    st.session_state.user = None
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'last_token_check' not in st.session_state:
    st.session_state.last_token_check = 0

def check_session():
    """Periodically check if the session token is still valid"""
    current_time = time.time()
    # Check every 5 minutes
    if current_time - st.session_state.last_token_check > 300 and st.session_state.access_token:
        try:
            response = requests.get(
                f"{API_URL}/auth/session",
                params={"token": st.session_state.access_token}
            )
            if not response.json().get("valid"):
                st.session_state.logged_in = False
                st.session_state.user = None
                st.session_state.access_token = None
                st.rerun()
        except:
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.access_token = None
            st.rerun()
        st.session_state.last_token_check = current_time

def display_transaction_data(data):
    """Helper function to display transaction data in a consistent format"""
    # Create two columns for better layout
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Basic Information")
        st.write(f"**Vendor:** {data.get('vendor', 'N/A')}")
        st.write(f"**Date:** {data.get('date', 'N/A')}")
        st.write(f"**Total:** {data.get('currency', 'BHD')} {data.get('total', 'N/A'):.2f}")
        st.write(f"**Transaction Type:** {data.get('transaction_type', 'N/A').title()}")
        
    with col2:
        st.markdown("#### Additional Details")
        st.write(f"**Sector:** {data.get('sector', 'N/A')}")
        if data.get('uncertain_category', False):
            st.warning("⚠️ Category classification is uncertain and may need review")

def load_transactions():
    """Helper function to load transactions from the API"""
    try:
        per_page = 10
        offset = (st.session_state.get('page_number', 1) - 1) * per_page
        
        response = requests.get(
            f"{API_URL}/transactions",
            params={
                "limit": per_page,
                "offset": offset
            },
            headers={"Authorization": f"Bearer {st.session_state.access_token}"}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"API Response: {json.dumps(data, indent=2)}")  # Debug log
            st.session_state.transaction_data = data
            st.session_state.transaction_error = None
        elif response.status_code == 401:
            st.session_state.transaction_error = "Session expired. Please log in again."
            st.session_state.logged_in = False
            st.session_state.user = None
            st.session_state.access_token = None
            st.rerun()
        else:
            error_msg = "Failed to fetch transactions."
            try:
                error_detail = response.json()
                error_msg = error_detail.get('detail', error_msg)
            except:
                pass
            st.session_state.transaction_error = f"{error_msg} Please try again later."
            print(f"Error Response: {response.text}")  # Debug log
    except Exception as e:
        st.session_state.transaction_error = f"Error loading transactions: {str(e)}"
        print(f"Exception: {str(e)}")  # Debug log
    finally:
        st.session_state.transaction_loading = False

def display_transaction_history():
    """Display transaction history in a card-based layout"""
    st.markdown("### Transaction History")
    
    # Show loading state
    if st.session_state.transaction_loading:
        st.info("Loading transactions...")
        
    # Add refresh button at the top
    if st.button("🔄 Refresh Transactions"):
        st.session_state.transaction_loading = True
        load_transactions()
        st.rerun()
    
    # Load transactions if needed
    if not st.session_state.transaction_data or st.session_state.transaction_loading:
        with st.spinner("Fetching your transactions..."):
            load_transactions()
    
    # Show any errors
    if st.session_state.transaction_error:
        st.error(st.session_state.transaction_error)
        return
    
    # Process the data
    data = st.session_state.transaction_data
    if not data:
        st.warning("No transaction data available. Try refreshing.")
        return
        
    transactions = data.get('transactions', [])
    total_transactions = data.get('total', 0)
    
    # Show transaction count
    st.write(f"Found {total_transactions} total transactions")

    # Track which transaction is being edited
    if 'editing_transaction_id' not in st.session_state:
        st.session_state.editing_transaction_id = None
    if 'editing_row_data' not in st.session_state:
        st.session_state.editing_row_data = None
    
    # Initialize session state for delete confirmation if not exists
    if 'delete_confirmation' not in st.session_state:
        st.session_state.delete_confirmation = None
        
    if transactions:
        try:
            # Create DataFrame for display
            df = pd.DataFrame(transactions)
            
            # Show raw data in expander for debugging
            with st.expander("Debug: Raw Transaction Data"):
                st.json(transactions)
                
            # Convert date strings to datetime for better display
            df['date'] = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d')
            
            # Format currency and amount
            df['formatted_amount'] = df.apply(
                lambda x: f"{x['currency']} {x['total_amount']:.2f}", 
                axis=1
            )
            
            # Display cards in a grid layout
            st.markdown('<div class="card-grid">', unsafe_allow_html=True)
            
            # Create a card for each transaction
            for idx, row in df.iterrows():
                # Check if this card is being edited
                is_editing = st.session_state.editing_transaction_id == row['id']
                
                if not is_editing:
                    # Card container with custom HTML
                    card_html = f"""
                        <div class="transaction-card">
                            <div class="card-header">
                                <span class="card-label">Vendor:</span> 
                                <span class="vendor-name">{row['vendor_name'] or 'Unknown'}</span>
                            </div>
                            <div class="card-body">
                                <div class="card-info">
                                    <span class="card-label">Date:</span> 
                                    <span class="date-value">{row['date']}</span>
                                </div>
                                <div class="card-info">
                                    <span class="card-amount">{row['formatted_amount']}</span>
                                </div>
                                <div class="card-info">
                                    <span class="card-category">{row['category_name'] or 'Uncategorized'}</span>
                                </div>
                            </div>
                        </div>
                    """
                    st.markdown(card_html, unsafe_allow_html=True)
                    
                    # Card actions (buttons) - place in columns for better alignment
                    cols = st.columns([1, 1, 2])  # Adjust column widths for better layout
                    with cols[0]:
                        if st.button("✏️ Edit", key=f"edit_{row['id']}"):
                            st.session_state.editing_transaction_id = row['id']
                            st.session_state.editing_row_data = row
                            st.rerun()  # Rerun to show edit form
                    
                    with cols[1]:
                        if st.button("🗑️ Delete", key=f"delete_{row['id']}"):
                            st.session_state.delete_confirmation = row['id']
                else:
                    # Display edit form within this card
                    with st.container():
                        st.markdown("""
                        <div class="transaction-card editing-card">
                            <div class="card-header" style="color: white;">
                                <span class="card-label" style="color: white;">Edit Transaction</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Fetch categories for dropdown
                        try:
                            headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                            categories_response = requests.get(f"{API_URL}/categories", headers=headers)
                            categories = categories_response.json() if categories_response.status_code == 200 else []
                        except Exception as e:
                            categories = []
                        
                        category_options = {cat['name']: cat['id'] for cat in categories}
                        current_category = row.get('category_name', '')
                        current_category_id = next((cat['id'] for cat in categories if cat['name'] == current_category), None)
                        
                        # Create edit form within this card
                        with st.form(f"edit_transaction_form_{row['id']}"):
                            new_vendor = st.text_input("Vendor", value=row['vendor_name'] or '')
                            new_date = st.date_input("Date", value=pd.to_datetime(row['date']))
                            new_currency = st.text_input("Currency", value=row['currency'] or '')
                            new_total = st.number_input("Total Amount", value=row['total_amount'])
                            
                            # Handle category selection with a default option
                            category_index = 0
                            if current_category in category_options:
                                category_index = list(category_options.keys()).index(current_category)
                            
                            new_category = st.selectbox(
                                "Category", 
                                options=list(category_options.keys()), 
                                index=category_index
                            )
                            
                            # Form buttons
                            col1, col2 = st.columns(2)
                            with col1:
                                submitted = st.form_submit_button("Save Changes")
                            with col2:
                                cancelled = st.form_submit_button("Cancel")
                            
                            if submitted:
                                # First get vendor_id if needed
                                vendor_id = None
                                if new_vendor:
                                    try:
                                        # Check for vendor match
                                        vendor_match_response = requests.get(
                                            f"{API_URL}/vendors/match",
                                            params={"vendor_name": new_vendor},
                                            headers={"Authorization": f"Bearer {st.session_state.access_token}"}
                                        )
                                        
                                        if vendor_match_response.status_code == 200:
                                            match_result = vendor_match_response.json()
                                            if match_result.get("vendor_id"):
                                                vendor_id = match_result["vendor_id"]
                                    except Exception as e:
                                        st.error(f"Error matching vendor: {str(e)}")
                                
                                # If no vendor_id found through match, use the original one
                                if not vendor_id:
                                    vendor_id = row.get('vendor_id')
                                    
                                # Build the update payload with only the needed fields
                                update_data = {
                                    "vendor_id": vendor_id,
                                    "date": new_date.strftime("%Y-%m-%d"),
                                    "currency": new_currency,
                                    "total_amount": float(new_total),
                                    "category_id": category_options[new_category]
                                }
                                
                                # Send the update request
                                with st.spinner("Updating transaction..."):
                                    headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                                    response = requests.put(
                                        f"{API_URL}/update-transaction/{row['id']}",
                                        json=update_data,
                                        headers=headers
                                    )
                                    
                                    if response.status_code == 200:
                                        st.success("Transaction updated successfully!")
                                        st.session_state.editing_transaction_id = None
                                        st.session_state.transaction_loading = True
                                        load_transactions()
                                        st.rerun()
                                    else:
                                        st.error("Failed to update transaction. Please try again.")
                            
                            if cancelled:
                                st.session_state.editing_transaction_id = None
                                st.rerun()
                
                # Add spacer between cards for better visual separation
                st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)
            
            # Close the card grid div
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Handle delete confirmation
            if st.session_state.delete_confirmation:
                with st.container():
                    st.warning("Are you sure you want to delete this transaction?")
                    col3, col4 = st.columns([1, 1])
                    with col3:
                        if st.button("Yes, delete", key="confirm_delete"):
                            try:
                                headers = {"Authorization": f"Bearer {st.session_state.access_token}"}
                                response = requests.delete(
                                    f"{API_URL}/remove-transaction",
                                    params={"transaction_id": st.session_state.delete_confirmation},
                                    headers=headers
                                )
                                if response.status_code in [200, 404]:
                                    result = response.json()
                                    st.success(result.get("message", "Transaction deleted successfully!"))
                                    st.session_state.delete_confirmation = None
                                    st.session_state.transaction_loading = True
                                    load_transactions()
                                    st.rerun()
                                else:
                                    st.error(f"Error: {response.status_code} - {response.text}")
                            except Exception as e:
                                st.error(f"Failed to delete transaction: {str(e)}")
                    with col4:
                        if st.button("No, cancel", key="cancel_delete"):
                            st.session_state.delete_confirmation = None
                            st.rerun()
                            
            # Pagination controls
            per_page = 10
            total_pages = max(1, (total_transactions + per_page - 1) // per_page)
            current_page = st.session_state.get('page_number', 1)
            col1, col2, col3 = st.columns([1, 2, 1])
            with col1:
                if current_page > 1:
                    if st.button("← Previous"):
                        st.session_state.page_number = current_page - 1
                        st.session_state.transaction_loading = True
                        st.rerun()
            with col2:
                st.markdown(f"<div style='text-align: center'>Page {current_page} of {total_pages}</div>", unsafe_allow_html=True)
            with col3:
                if current_page < total_pages:
                    if st.button("Next →"):
                        st.session_state.page_number = current_page + 1
                        st.session_state.transaction_loading = True
                        st.rerun()
        except Exception as e:
            st.error(f"Error displaying transactions: {str(e)}")
            st.write("Debug information:")
            st.json(transactions)
    else:
        st.info("No transactions found. Start by analyzing some receipts or transaction screenshots!")

# Set page config
st.set_page_config(
    page_title="Smart Receipt Analyzer",
    page_icon="📝",
    layout="wide"
)

# Custom CSS for styling
st.markdown("""
    <style>
        .fixed-height-image {
            max-height: 400px !important;
            width: auto !important;
            display: block !important;
            margin: 0 auto !important;
        }
        .auth-form {
            max-width: 400px;
            margin: 0 auto;
            padding: 20px;
        }
        .stButton>button {
            width: 100%;
        }
        /* Transaction card styles */
        .transaction-card {
            background-color: #ffffff;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 15px;
            border: 1px solid #e0e0e0;
            box-shadow: 0 2px 5px rgba(0,0,0,0.05);
            transition: all 0.2s ease;
            color: #222222; /* Darker base text color for better contrast */
        }
        .transaction-card:hover {
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
            transform: translateY(-2px);
        }
        .card-header {
            border-bottom: 1px solid #f0f0f0;
            padding-bottom: 12px;
            margin-bottom: 12px;
            font-size: 1.1rem;
            color: #222222;
            font-weight: 500;
        }
        .card-body {
            padding: 5px 0;
            color: #222222;
        }
        .card-info {
            margin-bottom: 8px;
            color: #222222;
        }
        .card-label {
            font-weight: 600;
            color: #222222;
            margin-right: 5px;
            font-size: 0.9rem;
        }
        .vendor-name {
            color: #0d47a1;
            font-weight: 500;
            font-size: 1.1rem;
        }
        .date-value {
            color: #222222;
            font-weight: 500;
        }
        .card-amount {
            font-size: 1.4rem;
            font-weight: 700;
            color: #2e7d32;
            display: block;
            margin: 10px 0;
        }
        .card-category {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 20px;
            background-color: #f1f8e9;
            color: #558b2f;
            font-size: 0.85rem;
            margin-top: 8px;
            font-weight: 500;
        }
        .card-actions {
            margin-top: 15px;
            display: flex;
            justify-content: flex-end;
            gap: 10px;
        }
        .card-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        /* Editing card styles */
        .editing-card {
            background-color: #1e1e1e;
            border: 2px solid #2196f3;
            box-shadow: 0 4px 8px rgba(33, 150, 243, 0.2);
            color: #ffffff;
        }
        .stForm {
            background-color: #1e1e1e;
            padding: 10px;
            border-radius: 10px;
            color: #ffffff;
        }
        /* Make form buttons more visible */
        .stForm [data-testid="stFormSubmitButton"] button {
            background-color: #2196f3;
            color: white;
            font-weight: bold;
        }
        /* Style for form inputs with dark theme */
        .stTextInput input, .stNumberInput input, .stDateInput input, .stSelectbox > div > div {
            background-color: #2d2d2d !important;
            color: #ffffff !important;
            border-color: #444444 !important;
        }
        .stTextInput label, .stNumberInput label, .stDateInput label, .stSelectbox label {
            color: #e0e0e0 !important;
        }
        /* Datepicker styling */
        .stDateInput div[data-baseweb="calendar"] {
            background-color: #2d2d2d !important;
        }
        .stDateInput button, .stSelectbox button {
            background-color: #444444 !important;
            color: #ffffff !important;
        }
        /* Dropdown for selectbox */
        div[data-baseweb="select"] ul {
            background-color: #2d2d2d !important;
        }
        div[data-baseweb="select"] li {
            color: #ffffff !important;
        }
        div[data-baseweb="select"] li:hover {
            background-color: #444444 !important;
        }
        /* Manual entry form dark container */
        .dark-form-container {
            background-color: #1e1e1e;
            padding: 20px;
            border-radius: 10px;
            margin-bottom: 20px;
            color: #ffffff;
        }
        .dark-form-container h4 {
            color: #e0e0e0 !important;
            margin-top: 10px;
            margin-bottom: 10px;
            font-weight: 500;
        }
        /* Override markdown text color in dark forms */
        .dark-form-container p, .dark-form-container .markdown-text-container {
            color: #e0e0e0 !important;
        }
    </style>
""", unsafe_allow_html=True)

def login_page():
    st.title("Welcome to Smart Receipt Analyzer")
    
    # Tabs for login and registration
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login")
        email = st.text_input("Email", key="login_email")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login"):
            try:
                response = requests.post(
                    f"{API_URL}/auth/login",
                    json={"email": email, "password": password}
                )
                
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.logged_in = True
                    st.session_state.user = data["user"]
                    st.session_state.access_token = data["access_token"]
                    st.rerun()
                elif response.status_code == 403:
                    st.error("Please verify your email before logging in.")
                else:
                    st.error("Invalid email or password.")
            except Exception as e:
                st.error("Login failed. Please try again.")
    
    with tab2:
        st.subheader("Register")
        first_name = st.text_input("First Name")
        last_name = st.text_input("Last Name")
        email = st.text_input("Email", key="register_email")
        password = st.text_input("Password", type="password", key="register_password")
        
        if st.button("Register"):
            try:
                response = requests.post(
                    f"{API_URL}/auth/register",
                    json={
                        "email": email,
                        "password": password,
                        "first_name": first_name,
                        "last_name": last_name
                    }
                )
                
                if response.status_code == 200:
                    st.success("Registration successful! Please check your email for verification.")
                elif response.status_code == 400:
                    st.error("Email already registered.")
                else:
                    st.error("Registration failed. Please try again.")
            except Exception as e:
                st.error("Registration failed. Please try again.")

def main_app():
    # Check session validity
    check_session()
    
    st.title("Smart Receipt Analyzer")
    
    # Add logout button in sidebar
    if st.sidebar.button("Logout"):
        st.session_state.logged_in = False
        st.session_state.user = None
        st.session_state.access_token = None
        st.rerun()
    
    # Initialize transaction data in session state if not exists
    if 'transaction_data' not in st.session_state:
        st.session_state.transaction_data = None
        st.session_state.transaction_loading = False
        st.session_state.transaction_error = None
        st.session_state.page_number = 1
    
    # Create tabs for analysis and history
    tab1, tab2 = st.tabs(["Receipt Analysis", "Transaction History"])
    
    with tab1:
        st.markdown("Upload a receipt image or SMS message for analysis")

        # Mode toggle
        mode = st.radio(
            "Select Analysis Mode",
            ["Receipt Analysis", "SMS Analysis", "Manual Entry"],
            horizontal=True
        )

        if mode == "Manual Entry":
            st.markdown("### Manual Transaction Entry")
            
            # Create a container with dark theme styling
            st.markdown('<div class="dark-form-container">', unsafe_allow_html=True)
            
            # Create a form for manual entry
            with st.form("manual_transaction_form"):
                # Basic Information
                st.markdown("#### Basic Information")
                vendor = st.text_input("Vendor Name", key="manual_vendor")
                date = st.date_input("Transaction Date", key="manual_date")
                total = st.number_input("Total Amount", min_value=0.0, step=0.01, key="manual_total")
                currency = st.selectbox("Currency", ["BHD", "USD", "EUR", "GBP"], key="manual_currency")
                
                # Additional Details
                st.markdown("#### Additional Details")
                sector = st.selectbox(
                    "Business Sector",
                    [
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
                    ],
                    key="manual_sector"
                )
                transaction_type = st.selectbox(
                    "Transaction Type",
                    ["manual", "receipt", "sms"],
                    key="manual_transaction_type"
                )
                
                # Submit button
                submitted = st.form_submit_button("Submit Transaction")
                
                if submitted:
                    if not vendor or not date or not total:
                        st.error("Please fill in all required fields (Vendor, Date, and Total)")
                    else:
                        try:
                            # Prepare transaction data
                            transaction_data = {
                                "vendor": vendor,
                                "date": date.strftime("%Y-%m-%d"),
                                "total": float(total),
                                "currency": currency,
                                "sector": sector,
                                "transaction_type": transaction_type,
                                "uncertain_category": False
                            }
                            
                            # Make API request
                            headers = {
                                "Authorization": f"Bearer {st.session_state.access_token}"
                            }
                            
                            with st.spinner("Saving transaction..."):
                                # First, check for vendor matches
                                response = requests.get(
                                    f"{API_URL}/vendors/match",
                                    params={"vendor_name": vendor},
                                    headers=headers
                                )
                                
                                if response.status_code == 200:
                                    match_result = response.json()
                                    if match_result.get("matched_vendor"):
                                        st.info(f"Found matching vendor: {match_result['matched_vendor']}")
                                        transaction_data["vendor"] = match_result["matched_vendor"]
                                
                                # Now save the transaction
                                response = requests.post(
                                    f"{API_URL}/transactions",
                                    json=transaction_data,
                                    headers=headers
                                )
                            
                            if response.status_code == 200:
                                result = response.json()
                                st.success("✅ Transaction saved successfully!")
                                st.markdown("View this transaction in your [transaction history](#transaction-history).")
                                
                                # Display the saved transaction
                                st.markdown("### Saved Transaction")
                                display_transaction_data(transaction_data)
                                
                                # Trigger transaction reload
                                st.session_state.transaction_loading = True
                                load_transactions()
                            else:
                                error_msg = f"Error: {response.status_code}"
                                try:
                                    error_detail = response.json()
                                    error_msg += f" - {error_detail.get('detail', 'Unknown error')}"
                                except:
                                    error_msg += f" - {response.text}"
                                st.error(error_msg)
                                
                        except Exception as e:
                            st.error(f"Failed to save transaction: {str(e)}")
            
            # Close the container div
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            # File uploader for image-based analysis
            uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png"])

            if uploaded_file is not None:
                try:
                    # Display the uploaded image
                    image = Image.open(uploaded_file)
                    
                    # Resize image while maintaining aspect ratio
                    max_height = 400
                    aspect_ratio = image.width / image.height
                    new_height = min(max_height, image.height)
                    new_width = int(new_height * aspect_ratio)
                    image = image.resize((new_width, int(new_height)), Image.Resampling.LANCZOS)
                    
                    # Convert to bytes for display
                    img_bytes = io.BytesIO()
                    image.save(img_bytes, format=image.format if image.format else 'JPEG')
                    
                    # Display image with fixed height
                    st.markdown(f'<img src="data:image/jpeg;base64,{base64.b64encode(img_bytes.getvalue()).decode()}" class="fixed-height-image">', unsafe_allow_html=True)
                    
                    # Add submit button
                    if st.button("Analyze Image"):
                        # Convert original image to bytes for API
                        img_byte_arr = io.BytesIO()
                        Image.open(uploaded_file).save(img_byte_arr, format='JPEG')
                        
                        # Create files dictionary for multipart form data
                        files = {
                            "file": ("image.jpg", img_byte_arr.getvalue(), "image/jpeg")
                        }
                        
                        # Add authorization header
                        headers = {
                            "Authorization": f"Bearer {st.session_state.access_token}"
                        }
                        
                        # Make API request based on selected mode
                        endpoint = "/analyze-expense" if mode == "Receipt Analysis" else "/analyze-transaction"
                        try:
                            with st.spinner("Analyzing image..."):
                                response = requests.post(
                                    f"{API_URL}{endpoint}",
                                    files=files,
                                    headers=headers,
                                    timeout=30
                                )
                            
                            if response.status_code == 200:
                                result = response.json()
                                
                                # Display success message with link to history
                                st.success("✅ Analysis complete! Transaction saved successfully.")
                                st.markdown("View this transaction in your [transaction history](#transaction-history).")
                                
                                # Display results in a nice format
                                st.markdown("### Analysis Results")
                                
                                # Handle multiple transactions for SMS mode
                                if mode == "SMS Analysis" and isinstance(result.get('parsed_data'), list):
                                    for idx, transaction in enumerate(result['parsed_data']):
                                        st.markdown(f"#### Transaction {idx + 1}")
                                        display_transaction_data(transaction)
                                else:
                                    # Single receipt or transaction
                                    display_transaction_data(result.get('parsed_data', {}))
                                
                                # Display raw data in expandable section
                                with st.expander("View Raw Data"):
                                    st.json(result.get('raw_data', {}))
                                
                                # Trigger transaction reload
                                st.session_state.transaction_loading = True
                                load_transactions()
                            else:
                                error_msg = f"Error: {response.status_code}"
                                try:
                                    error_detail = response.json()
                                    error_msg += f" - {error_detail.get('detail', 'Unknown error')}"
                                except:
                                    error_msg += f" - {response.text}"
                                st.error(error_msg)
                                
                        except requests.exceptions.RequestException as e:
                            st.error(f"Failed to connect to the API server: {str(e)}")
                            
                except Exception as e:
                    st.error(f"Error processing image: {str(e)}")
    
    with tab2:
        display_transaction_history()

# Main flow control
if not st.session_state.logged_in:
    login_page()
else:
    main_app() 