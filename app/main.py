from fastapi import FastAPI
from app.routes import receipts

app = FastAPI()

app.include_router(receipts.router, prefix="/api")


