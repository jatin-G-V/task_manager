from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel

from app.db.supabase_client import supabase
from app.auth import get_current_user
from app.services.task_parser import parse_task_text

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

class ParseRequest(BaseModel):
    text: str


@app.post("/parse-task")
def parse_task(
    req: ParseRequest,
    user_id: str = Depends(get_current_user)
):
    if not req.text.strip():
        raise HTTPException(
            status_code=400,
            detail="text is required"
        )

    try:
        return parse_task_text(req.text)

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )