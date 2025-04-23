import streamlit as st
import requests
from PIL import Image
import io
import json
import base64
from datetime import datetime

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

# Custom CSS for image sizing
st.markdown("""
    <style>
        .fixed-height-image {
            max-height: 400px !important;
            width: auto !important;
            display: block !important;
            margin: 0 auto !important;
        }
    </style>
""", unsafe_allow_html=True)

# Title and description
st.title("Smart Receipt Analyzer")
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
        
        # Make API request based on selected mode
        endpoint = "/analyze-expense" if mode == "Receipt Analysis" else "/analyze-transaction"
        try:
            response = requests.post(
                f"http://localhost:8000/api{endpoint}",
                files=files,
                timeout=30  # Add timeout to prevent hanging
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