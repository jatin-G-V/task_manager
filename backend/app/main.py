from fastapi import FastAPI
from app.db.supabase_client import supabase

app = FastAPI()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/test-db")
def test_db():
    response = supabase.table("tasks").select("*").execute()
    return response.data

@app.get("/users")
def get_users():
    response = supabase.table("user_profile").select("*").execute()
    return response.data