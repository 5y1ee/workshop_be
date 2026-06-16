"""WebSocket 엔드포인트.

연결 시 토큰을 query parameter로 받아 인증.
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_token
from app.websocket.handlers import MessageContext, dispatch
from app.websocket.manager import manager

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = int(payload["sub"])
    team_id = payload.get("team_id")
    is_admin = payload.get("role") == "admin"

    await manager.connect(websocket, user_id, team_id, is_admin=is_admin)
    ctx = MessageContext(
        websocket=websocket, manager=manager, user_id=user_id, team_id=team_id
    )
    try:
        while True:
            data = await websocket.receive_json()
            await dispatch(ctx, data)
    except WebSocketDisconnect:
        manager.disconnect(websocket, user_id, team_id)
