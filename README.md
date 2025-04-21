# Smart Receipt Analyzer

AI Powered web app that extracts data from receipts and transaction messages, categorizes spending, and visualizes the data. Built with FastAPI, AWS Textract and Streamlit.



## Tech Stack:

| Layer       | Technology |
|------------|------------|
| Backend     | FastAPI, Uvicorn, Python |
| OCR         | AWS Textract via boto3 |
| Frontend (MVP) | Streamlit |
| Cloud       | AWS (Textract, optional S3) |
| Containerization | Docker |
| Data        | JSON (MVP), optional DB (PostgreSQL) |


## Planned features:

- [x] File upload API
- [ ] AWS Textract integration
- [ ] Extract vendor, items, totals, date
- [ ] AI categorization of items
- [ ] Dashboard UI with Streamlit
- [ ] Dockerized backend
- [ ] AWS deployment


## Final App Workflow:

1. User uploads receipt image  
2. FastAPI backend sends it to AWS Textract  
3. Extracted data is parsed and returned  
4. Spending categorized by LLM (Langchain?)
4. Streamlit shows data as tables/charts
5. Receipt history

## Learning Goals:

- Learn AWS from scratch
- Master FastAPI and Docker basics
- Build a real world AI pipeline
- Understand OCR and data extraction
- Explore different categorization models

## Author
Asad Rizvi: 
Smart Receipt analyzer is a solo learning project. Feel free to fork it, build on it, or use it for your own personal needs.
