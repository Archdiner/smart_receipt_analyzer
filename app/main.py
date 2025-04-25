from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import receipts, auth

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(receipts.router, prefix="/api")
app.include_router(auth.router, prefix="/api/auth")


