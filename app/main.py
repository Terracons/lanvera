from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, properties, messaging
from app.database import engine 
from app.models import models   # <-- This is necessary BEFORE create_all
from starlette.middleware.sessions import SessionMiddleware
import os
from dotenv import load_dotenv

load_dotenv()




models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="lanvera",
    description="Luxury Real Estate Marketplace",
    version="1.0.0"
)
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY"))
origins = [
    "http://localhost:3000",  # React/Vue frontend dev
    "http://localhost:5173"  # Replace in prod
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth.router)
app.include_router(properties.router)
app.include_router(messaging.router)


@app.get("/")
def read_root():
    return {"message": "🏡 Welcome to lanvera Real Estate Platform"}
