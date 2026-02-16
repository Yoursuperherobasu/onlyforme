"""
Approval API Router

Handles agent approval/rejection workflows.
Uses sample JSON data (no database).
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from loguru import logger

# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class SubmittedBy(BaseModel):
    name: str
    avatar: Optional[str] = None


class ApprovalAgent(BaseModel):
    id: str
    title: str
    status: str  # pending, approved, rejected
    description: str
    submittedBy: SubmittedBy
    project: str
    submitted: str
    version: str
    recentChanges: str


class ApproveRequest(BaseModel):
    comments: str


class RejectRequest(BaseModel):
    comments: str
    reason: Optional[str] = None


class ApprovalResponse(BaseModel):
    success: bool
    message: str
    agentId: str
    newStatus: str
    timestamp: str
    approvedBy: Optional[str] = None


# ============================================================================
# SAMPLE DATA (In-Memory Storage)
# ============================================================================

SAMPLE_AGENTS = [
    {
        "id": "agent-001",
        "title": "Customer Support Agent",
        "status": "pending",
        "description": "Handles customer inquiries with context-aware responses and sentiment analysis.",
        "submittedBy": {"name": "Max Leiter", "avatar": None},
        "project": "E-Commerce Platform",
        "submitted": "2h ago",
        "version": "v2.1.0",
        "recentChanges": "Updated NLP model, improved response accuracy",
    },
    {
        "id": "agent-002",
        "title": "Data Analysis Pipeline",
        "status": "pending",
        "description": "Processes large datasets with anomaly detection and insight generation.",
        "submittedBy": {"name": "Arya Manisha", "avatar": None},
        "project": "Analytics Dashboard",
        "submitted": "5h ago",
        "version": "v1.8.2",
        "recentChanges": "Added real-time processing",
    },
    {
        "id": "agent-003",
        "title": "Email Campaign Manager",
        "status": "pending",
        "description": "Automates email marketing campaigns with A/B testing and personalization.",
        "submittedBy": {"name": "Sarah Johnson", "avatar": None},
        "project": "Marketing Automation",
        "submitted": "1h ago",
        "version": "v1.5.0",
        "recentChanges": "Improved template rendering",
    },
]

# In-memory store (simulating database)
AGENTS_STORE = SAMPLE_AGENTS.copy()

# File uploads storage (simulating file system)
UPLOADED_FILES = {}

router = APIRouter(
    prefix="/approvals",
    tags=["approvals"],
)


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("", response_model=List[ApprovalAgent])
async def get_approvals():
    """
    GET /api/approvals
    
    Fetch all agents awaiting approval.
    Returns list of agents with pending, approved, or rejected status.
    """
    try:
        logger.info(f"Fetching all approvals. Total agents: {len(AGENTS_STORE)}")
        return AGENTS_STORE
    except Exception as e:
        logger.error(f"Error fetching approvals: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch approvals"
        )


@router.post("/{agent_id}/approve", response_model=ApprovalResponse)
async def approve_agent(agent_id: str, request: ApproveRequest):
    """
    POST /api/approvals/{agent_id}/approve
    
    Approve an agent with optional comments.
    Updates agent status from pending to approved.
    
    Request Body:
        {
            "comments": "Looks good, approved for deployment"
        }
    """
    try:
        logger.info(f"Approving agent: {agent_id}")
        
        # Find agent in store
        agent = None
        for a in AGENTS_STORE:
            if a["id"] == agent_id:
                agent = a
                break
        
        if not agent:
            logger.warning(f"Agent not found: {agent_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        # Update agent status
        agent["status"] = "approved"
        
        # Log the approval
        logger.info(f"Agent {agent_id} approved. Comments: {request.comments}")
        
        return ApprovalResponse(
            success=True,
            message="Agent approved successfully",
            agentId=agent_id,
            newStatus="approved",
            timestamp=datetime.utcnow().isoformat() + "Z",
            approvedBy="system@example.com"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve agent"
        )


@router.post("/{agent_id}/reject", response_model=ApprovalResponse)
async def reject_agent(agent_id: str, request: RejectRequest):
    """
    POST /api/approvals/{agent_id}/reject
    
    Reject an agent with comments and optional reason.
    Updates agent status from pending to rejected.
    
    Request Body:
        {
            "comments": "Needs improvement in error handling",
            "reason": "Security concerns"
        }
    """
    try:
        logger.info(f"Rejecting agent: {agent_id}")
        
        # Find agent in store
        agent = None
        for a in AGENTS_STORE:
            if a["id"] == agent_id:
                agent = a
                break
        
        if not agent:
            logger.warning(f"Agent not found: {agent_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        # Update agent status
        agent["status"] = "rejected"
        
        # Log the rejection
        reason = request.reason or "Not specified"
        logger.info(
            f"Agent {agent_id} rejected. "
            f"Reason: {reason}. "
            f"Comments: {request.comments}"
        )
        
        return ApprovalResponse(
            success=True,
            message="Agent rejected",
            agentId=agent_id,
            newStatus="rejected",
            timestamp=datetime.utcnow().isoformat() + "Z",
            approvedBy="system@example.com"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting agent {agent_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject agent"
        )


@router.post("/{agent_id}/attachments")
async def upload_attachments(
    agent_id: str,
    attachments: List[UploadFile] = File(...)
):
    """
    POST /api/approvals/{agent_id}/attachments
    
    Upload files/attachments for an agent approval.
    Stores files in memory (simulating file system).
    
    Request:
        multipart/form-data with "attachments" field containing files
    
    Response:
        {
            "success": true,
            "message": "Attachments uploaded successfully",
            "agentId": "agent-123",
            "uploadedFiles": [
                {
                    "filename": "test-results.pdf",
                    "size": 2048,
                    "uploadedAt": "2024-01-30T10:30:00Z",
                    "url": "/files/attachment-001"
                }
            ]
        }
    """
    try:
        logger.info(f"Uploading attachments for agent: {agent_id}")
        
        # Validate agent exists
        agent_exists = any(a["id"] == agent_id for a in AGENTS_STORE)
        if not agent_exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        uploaded_files = []
        
        # Process each uploaded file
        for file in attachments:
            # Validate file size (max 10MB)
            contents = await file.read()
            file_size = len(contents)
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"File {file.filename} is too large. Max size is 10MB"
                )
            
            # Store file in memory
            file_id = f"attachment-{len(UPLOADED_FILES) + 1:03d}"
            UPLOADED_FILES[file_id] = {
                "filename": file.filename,
                "content": contents,
                "size": file_size,
                "agent_id": agent_id,
            }
            
            uploaded_files.append({
                "filename": file.filename,
                "size": file_size,
                "uploadedAt": datetime.utcnow().isoformat() + "Z",
                "url": f"/files/{file_id}"
            })
            
            logger.info(
                f"File uploaded: {file.filename} ({file_size} bytes) "
                f"for agent {agent_id}"
            )
        
        return {
            "success": True,
            "message": "Attachments uploaded successfully",
            "agentId": agent_id,
            "uploadedFiles": uploaded_files
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading attachments: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to upload attachments"
        )


@router.get("/{agent_id}")
async def get_agent_details(agent_id: str):
    """
    GET /api/approvals/{agent_id}
    
    Get detailed information about a specific agent.
    
    Response:
        ApprovalAgent object with full details
    """
    try:
        # Find agent
        agent = None
        for a in AGENTS_STORE:
            if a["id"] == agent_id:
                agent = a
                break
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        return agent
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching agent details: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch agent details"
        )


@router.post("/{agent_id}/reset-status")
async def reset_agent_status(agent_id: str):
    """
    POST /api/approvals/{agent_id}/reset-status
    
    Reset agent status back to pending (for testing/demo purposes).
    Useful for demo/testing the approval flow multiple times.
    """
    try:
        logger.info(f"Resetting agent status: {agent_id}")
        
        # Find and update agent
        agent = None
        for a in AGENTS_STORE:
            if a["id"] == agent_id:
                agent = a
                break
        
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent {agent_id} not found"
            )
        
        agent["status"] = "pending"
        
        return {
            "success": True,
            "message": "Agent status reset to pending",
            "agentId": agent_id,
            "newStatus": "pending"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resetting agent status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reset agent status"
        )


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_router():
    """Return the approval router for mounting in main app"""
    return router
