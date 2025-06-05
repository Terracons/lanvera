from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, List
from app.database import get_db
from app.security import get_user_by_token, get_current_user
from app.models import models
from app.schemas import schemas

import json

router = APIRouter(prefix="/messages", tags=["Messaging"])

# In-memory connections map: user_id -> WebSocket
active_connections: Dict[int, WebSocket] = {}

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    user = get_user_by_token(token, db)
    if not user:
        await websocket.close(code=1008)  # Policy Violation
        return

    await websocket.accept()
    active_connections[user.id] = websocket

    try:
        while True:
            data = await websocket.receive_text()
            payload = json.loads(data)

            message = models.Message(
                sender_id=user.id,
                receiver_id=payload["receiver_id"],
                content=payload["content"],
                property_id=payload.get("property_id")
            )
            db.add(message)
            db.commit()
            db.refresh(message)

            response = {
                "id": message.id,
                "content": message.content,
                "sender_id": message.sender_id,
                "receiver_id": message.receiver_id,
                "property_id": message.property_id
            }

            # Send to receiver if connected
            receiver_ws = active_connections.get(payload["receiver_id"])
            if receiver_ws:
                await receiver_ws.send_text(json.dumps(response))

            # Optionally send confirmation back to sender
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        active_connections.pop(user.id, None)



@router.get("/inbox", response_model=List[schemas.MessageOut])
def get_inbox_messages(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    messages = db.query(models.Message).filter(
        models.Message.receiver_id == current_user.id
    ).order_by(models.Message.id.desc()).all()

    return messages
