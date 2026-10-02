from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth import get_current_user
from app.schemas.task import TaskCreate, TaskUpdate
from app.services import task_service


router = APIRouter()


# ============================================================
# CREATE TASK
# ============================================================

@router.post("/tasks")
def create_task(
    task: TaskCreate,
    user_id: str = Depends(get_current_user),
):
    try:
        return task_service.create_task(
            user_id,
            task.model_dump(),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )


# ============================================================
# LIST TASKS
# ============================================================

@router.get("/tasks")
def list_tasks(
    user_id: str = Depends(get_current_user),
    section: str = None,
    status: str = None,
    search: str = None,
    limit: int = 20,
):
    return task_service.list_tasks(
        user_id,
        section,
        status,
        search,
        limit,
    )


# ============================================================
# RECOMMENDED TASKS
#
# IMPORTANT:
# This MUST be before /tasks/{task_id}
# ============================================================

@router.get("/tasks/recommended")
def recommended_tasks(
    limit: int = Query(
        default=3,
        ge=1,
        le=100,
    ),
    energy: Optional[Literal["low", "medium", "high"]] = None,
    exclude_ids: list[str] = Query(
        default_factory=list,
    ),
    user_id: str = Depends(get_current_user),
):
    return task_service.recommend_tasks(
        user_id,
        limit=limit,
        energy=energy,
        exclude_ids=exclude_ids,
    )


# ============================================================
# GET SINGLE TASK
# ============================================================

@router.get("/tasks/{task_id}")
def get_task(
    task_id: str,
    user_id: str = Depends(get_current_user),
):
    task = task_service.get_task(
        user_id,
        task_id,
    )

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    return task


# ============================================================
# UPDATE TASK
# ============================================================

@router.patch("/tasks/{task_id}")
def update_task(
    task_id: str,
    updates: TaskUpdate,
    user_id: str = Depends(get_current_user),
):
    data = updates.model_dump(
        exclude_unset=True,
    )

    if not data:
        raise HTTPException(
            status_code=400,
            detail="No fields to update",
        )

    try:
        return task_service.update_task(
            user_id,
            task_id,
            data,
        )

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )


# ============================================================
# COMPLETE TASK
# ============================================================

@router.post("/tasks/{task_id}/complete")
def complete_task(
    task_id: str,
    user_id: str = Depends(get_current_user),
):
    try:
        return task_service.complete_tasks(
            user_id,
            [task_id],
        )

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )


# ============================================================
# DELETE TASK
# ============================================================

@router.delete("/tasks/{task_id}")
def delete_task(
    task_id: str,
    user_id: str = Depends(get_current_user),
):
    try:
        deleted = task_service.delete_tasks(
            user_id,
            [task_id],
        )

        return {
            "deleted": True,
            "id": task_id,
            "result": deleted,
        }

    except LookupError:
        raise HTTPException(
            status_code=404,
            detail="Task not found",
        )