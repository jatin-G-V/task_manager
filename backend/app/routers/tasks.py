from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from app.auth import get_current_user
from app.db.supabase_client import supabase
from app.schemas.task import TaskCreate, TaskUpdate


router = APIRouter()


@router.post("/tasks")
def create_task(
    task: TaskCreate,
    user_id: str = Depends(get_current_user)
):
    row = task.model_dump()

    row["user_id"] = user_id
    row["status"] = "pending"

    result = (
        supabase
        .table("tasks")
        .insert(row)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to create task"
        )

    return result.data[0]


@router.patch("/tasks/{task_id}")
def update_task(
    task_id: str,
    updates: TaskUpdate,
    user_id: str = Depends(get_current_user)
):
    existing = (
        supabase
        .table("tasks")
        .select("*")
        .eq("id", task_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )

    if not existing.data:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    update_data = updates.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update"
        )

    # Merge existing DB row + incoming PATCH
    merged = {
        **existing.data,
        **update_data
    }

    # Validate final schedule state
    if merged["schedule_type"] == "scheduled":

        if not merged.get("scheduled_start"):
            raise HTTPException(
                status_code=400,
                detail="scheduled task requires scheduled_start"
            )

        if merged.get("deadline"):
            raise HTTPException(
                status_code=400,
                detail="scheduled task cannot have a deadline"
            )

    else:

        if merged.get("scheduled_start"):
            raise HTTPException(
                status_code=400,
                detail="flexible task cannot have scheduled_start"
            )

    result = (
        supabase
        .table("tasks")
        .update(update_data)
        .eq("id", task_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=500,
            detail="Failed to update task"
        )

    return result.data[0]


@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str,
    user_id: str = Depends(get_current_user)
):
    result = (
        supabase
        .table("tasks")
        .update({
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat()
        })
        .eq("id", task_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return result.data[0]


@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user)
):
    result = (
        supabase
        .table("tasks")
        .delete()
        .eq("id", task_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail="Task not found"
        )

    return {
        "deleted": True,
        "id": task_id
    }


@router.get("/tasks")
def list_tasks(
    user_id: str = Depends(get_current_user),
    section: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 20,
):
    query = supabase.table("tasks").select("*").eq("user_id", user_id)

    if section:
        query = query.eq("section", section)

    if status:
        query = query.eq("status", status)
    else:
        query = query.neq("status", "completed")  # default: hide completed unless explicitly asked

    if search:
        query = query.ilike("title", f"%{search}%")

    result = query.order("created_at", desc=True).limit(limit).execute()
    return result.data


@router.get("/tasks/{task_id}")
def get_task(task_id: str, user_id: str = Depends(get_current_user)):
    result = (
        supabase.table("tasks")
        .select("*")
        .eq("id", task_id)
        .eq("user_id", user_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Task not found")
    return result.data