import tempfile
import os
from fastapi import UploadFile
import base64
from PIL import Image
import io

async def get_image_data(file: UploadFile):
    """Get the compressed image data from the uploaded file."""
    # save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    # Open and compress the image
    with Image.open(temp_file_path) as img:
        # Convert to RGB if needed
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        
        # Resize if too large (max 1024px on longest side)
        max_size = 1024
        if max(img.size) > max_size:
            ratio = max_size / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Save to bytes with compression
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        compressed_bytes = output.getvalue()
    
    # Convert to base64
    base64_image = base64.b64encode(compressed_bytes).decode('utf-8')
    
    os.remove(temp_file_path)
    return base64_image


