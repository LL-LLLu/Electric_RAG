import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.database import Project, Conversation, Message
from app.models.schemas import (
    ConversationCreate, ConversationUpdate, ConversationResponse,
    ConversationDetail, MessageCreate, MessageResponse, SourceReference
)
from app.services.rag_service import rag_service

router = APIRouter()


@router.post("/projects/{project_id}/conversations", response_model=ConversationResponse)
async def create_conversation(
    project_id: int,
    data: ConversationCreate,
    db: Session = Depends(get_db)
):
    """Create a new conversation in a project"""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    conversation = Conversation(
        project_id=project_id,
        title=data.title
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


@router.get("/projects/{project_id}/conversations", response_model=List[ConversationResponse])
async def list_project_conversations(
    project_id: int,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List all conversations in a project"""
    # Verify project exists
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    conversations = db.query(Conversation).filter(
        Conversation.project_id == project_id
    ).order_by(Conversation.updated_at.desc()).offset(skip).limit(limit).all()

    return conversations


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Get conversation with all messages"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Get messages and parse sources
    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).all()

    message_responses = []
    for msg in messages:
        sources = None
        if msg.sources:
            try:
                sources = json.loads(msg.sources)
            except json.JSONDecodeError:
                sources = None

        message_responses.append(MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            sources=sources,
            created_at=msg.created_at
        ))

    return ConversationDetail(
        id=conversation.id,
        project_id=conversation.project_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=message_responses
    )


@router.put("/conversations/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: int,
    data: ConversationUpdate,
    db: Session = Depends(get_db)
):
    """Update conversation title"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if data.title is not None:
        conversation.title = data.title

    db.commit()
    db.refresh(conversation)

    return conversation


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    """Delete a conversation and all its messages"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Cascade delete will handle messages
    db.delete(conversation)
    db.commit()

    return {"message": f"Conversation {conversation_id} deleted successfully"}


@router.post("/conversations/{conversation_id}/messages", response_model=MessageResponse)
async def send_message(
    conversation_id: int,
    data: MessageCreate,
    db: Session = Depends(get_db)
):
    """Send a message and get AI response with sources"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Save user message
    user_message = Message(
        conversation_id=conversation_id,
        role="user",
        content=data.content
    )
    db.add(user_message)
    db.commit()

    # Get AI response using RAG service with project scope
    try:
        rag_response = rag_service.query(
            db=db,
            query=data.content,
            project_id=conversation.project_id,
            limit=5
        )

        # Build source references
        sources = []
        for source in rag_response.get("sources", []):
            sources.append({
                "document_id": source.get("document_id"),
                "document_name": source.get("document_name", "Unknown"),
                "page_number": source.get("page_number"),
                "snippet": source.get("snippet"),
                "bbox": source.get("bbox"),
                "equipment_tag": source.get("equipment_tag")
            })

        # Save assistant message
        assistant_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=rag_response.get("answer", "I couldn't find relevant information."),
            sources=json.dumps(sources) if sources else None
        )
        db.add(assistant_message)

        # Update conversation title if it's the first message and no title set
        if not conversation.title:
            # Use first 50 chars of user's message as title
            conversation.title = data.content[:50] + ("..." if len(data.content) > 50 else "")

        db.commit()
        db.refresh(assistant_message)

        return MessageResponse(
            id=assistant_message.id,
            conversation_id=assistant_message.conversation_id,
            role=assistant_message.role,
            content=assistant_message.content,
            sources=sources if sources else None,
            created_at=assistant_message.created_at
        )

    except Exception as e:
        # Save error message
        error_message = Message(
            conversation_id=conversation_id,
            role="assistant",
            content=f"Sorry, I encountered an error processing your request: {str(e)}"
        )
        db.add(error_message)
        db.commit()
        db.refresh(error_message)

        return MessageResponse(
            id=error_message.id,
            conversation_id=error_message.conversation_id,
            role=error_message.role,
            content=error_message.content,
            sources=None,
            created_at=error_message.created_at
        )


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: int,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """Get paginated message history"""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id
    ).first()

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = db.query(Message).filter(
        Message.conversation_id == conversation_id
    ).order_by(Message.created_at.asc()).offset(skip).limit(limit).all()

    message_responses = []
    for msg in messages:
        sources = None
        if msg.sources:
            try:
                sources = json.loads(msg.sources)
            except json.JSONDecodeError:
                sources = None

        message_responses.append(MessageResponse(
            id=msg.id,
            conversation_id=msg.conversation_id,
            role=msg.role,
            content=msg.content,
            sources=sources,
            created_at=msg.created_at
        ))

    return message_responses
