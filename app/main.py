
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import Literal
from fastapi import Query
from app.agent.agent import run_agent
from app.approval_service import (
    create_approval_request,
    get_approval_request,
    approve_request,
    reject_request,
    list_approval_requests,
    get_approval_summary,
)
from app.action_executor import execute_approved_request
from fastapi.responses import JSONResponse


app = FastAPI(
    title="Nova - Enterprise AI Agent",
    description="A local-first AI agent platform.",
    version="0.2.0",
)


# ---------- Request and response models ----------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str


class ApprovalCreateRequest(BaseModel):
    ticket_id: int = Field(gt=0, strict=True)


# ---------- Health and chat ----------

@app.get("/health")
def health_check():
    """Return the API health status."""
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Generate an agent response to a chat message.

    Args:
        request: Validated chat message.

    Returns:
        The generated response.
    """
    try:
        response = run_agent(request.message)
        return ChatResponse(response=response)
    except Exception as exc:
        print(f"LLM ERROR: {type(exc).__name__}: {exc}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not generate a response from the local LLM.",
        ) from exc


# ---------- Approval workflow ----------

@app.post(
    "/approvals",
    status_code=status.HTTP_201_CREATED,
)
def create_approval(request: ApprovalCreateRequest):
    """Create a pending ticket-closure approval request.

    Args:
        request: Validated ticket ID for the proposed action.

    Returns:
        The created approval request.
    """
    result = create_approval_request(request.ticket_id)

    if not result["success"]:
        error = result["error"]

        if "was not found" in error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error,
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error,
        )

    return result["request"]


@app.get("/list_approvals")
def list_approvals(
    status: Literal[
        "pending",
        "approved",
        "rejected",
        "executed",
        "failed",
    ] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    """List approval requests filtered by status and result limit.

    Args:
        status: Optional status used to filter requests.
        limit: Maximum number of requests to return.

    Returns:
        Matching approval requests or an API error response.
    """
    result = list_approval_requests(
        status=status,
        limit=limit,
    )

    if not result.get("success"):
        return JSONResponse(
            status_code=500,
            content=result,
        )

    return result

@app.get("/approvals/summary")
def approval_summary():
    """Return approval request counts by status."""
    result = get_approval_summary()

    if not result.get("success"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result["error"],
        )

    return result

@app.get("/approvals/{request_id}")
def read_approval(request_id: int):
    """Retrieve an approval request by ID.

    Args:
        request_id: ID of the request to retrieve.

    Returns:
        The matching approval request.
    """
    result = get_approval_request(request_id)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=result["error"],
        )

    return result["request"]


@app.post("/approvals/{request_id}/approve")
def approve_approval(request_id: int):
    """Approve a pending request without executing it.

    Args:
        request_id: ID of the request to approve.

    Returns:
        The updated approval request.
    """
    existing = get_approval_request(request_id)

    if not existing["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=existing["error"],
        )

    result = approve_request(request_id)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result["error"],
        )

    return result["request"]


@app.post("/approvals/{request_id}/reject")
def reject_approval(request_id: int):
    """Reject a pending request.

    Args:
        request_id: ID of the request to reject.

    Returns:
        The updated approval request.
    """
    existing = get_approval_request(request_id)

    if not existing["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=existing["error"],
        )

    result = reject_request(request_id)

    if not result["success"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=result["error"],
        )

    return result["request"]


@app.post("/approvals/{request_id}/execute")
def execute_approval(request_id: int):
    """Execute an approved request.

    Args:
        request_id: ID of the approved request to execute.

    Returns:
        The action execution result.
    """
    existing = get_approval_request(request_id)

    if not existing["success"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=existing["error"],
        )

    result = execute_approved_request(request_id)

    if not result["success"]:
        error = result["error"]

        if "Database error" in error:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error,
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=error,
        )

    return result
