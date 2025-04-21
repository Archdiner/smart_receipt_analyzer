import boto3
import tempfile
import os
from fastapi import UploadFile

async def analyze_receipt(file: UploadFile):

    # save uploaded file to temp location
    with tempfile.NamedTemporaryFile(delete=False) as temp_file:
        content = await file.read()
        temp_file.write(content)
        temp_file_path = temp_file.name

    # initialize textract client
    textract = boto3.client('textract')

    # read file as bytes

    with open(temp_file_path, 'rb') as file: # read binary
        file_bytes = file.read()
    
    # call textract to analyze receipt
    response = textract.analyze_document(
        Document = {"Bytes": file_bytes},
        FeatureTypes = ["TABLES", "FORMS"]
    )
    
    os.remove(temp_file_path)

    return response


