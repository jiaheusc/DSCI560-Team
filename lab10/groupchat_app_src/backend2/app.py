from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from routes import register_routes
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT)

app = FastAPI(title="GroupChat + Therapist System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

register_routes(app)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/", StaticFiles(directory="../frontend", html=True), name="frontend")
