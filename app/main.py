from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import receipts, auth
import os

app = FastAPI(
    title="Smart Receipt Analyzer API",
    description="API for analyzing receipts and transactions",
    version="1.0.0"
)

# Get allowed origins from environment variable or use default
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8501").split(",")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(receipts.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth")

@app.get("/")
async def root():
    return {"message": "Welcome to Smart Receipt Analyzer API"}


