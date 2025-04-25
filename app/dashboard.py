import streamlit as st
import requests
from PIL import Image
import io
import json
import base64
from datetime import datetime
import time

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
        st.write(f"**Total:** ${data.get('total', 'N/A'):.2f}")
        
    with col2:
        st.markdown("#### Additional Details")
        st.write(f"**Sector:** {data.get('sector', 'N/A')}")
        if 'currency' in data:
            st.write(f"**Currency:** {data.get('currency', 'N/A')}")
        if 'needs_research' in data:
            st.write(f"**Needs Research:** {'Yes' if data.get('needs_research') else 'No'}")

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
    
    st.markdown("Upload a receipt image or SMS message for analysis")

    # Mode toggle
    mode = st.radio(
        "Select Analysis Mode",
        ["Receipt Analysis", "SMS Analysis"],
        horizontal=True
    )

    # File uploader
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
                response = requests.post(
                    f"{API_URL}{endpoint}",
                    files=files,
                    headers=headers,
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
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

# Main flow control
if not st.session_state.logged_in:
    login_page()
else:
    main_app() 