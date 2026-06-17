"""WebSocket 연결 관리.

전체 broadcast, 팀별 broadcast, 개인 message 전송을 담당.
18명 규모라 메모리 기반 관리로 충분.
"""

from collections import defaultdict
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        # user_id -> list of WebSockets (한 유저가 여러 탭 가능성)
        self._user_connections: dict[int, list[WebSocket]] = defaultdict(list)
        # team_id -> set of user_ids
        self._team_members: dict[int, set[int]] = defaultdict(set)
        # session_id -> set of user_ids (게임 상세 페이지 접속자 = 그 세션의 방)
        self._session_watchers: dict[int, set[int]] = defaultdict(set)
        # role=admin인 user_id 집합 (운영자 전용 broadcast 라우팅용)
        self._admin_users: set[int] = set()

    async def connect(
        self,
        websocket: WebSocket,
        user_id: int,
        team_id: int | None,
        is_admin: bool = False,
    ) -> None:
        await websocket.accept()
        self._user_connections[user_id].append(websocket)
        if team_id is not None:
            self._team_members[team_id].add(user_id)
        if is_admin:
            self._admin_users.add(user_id)

    def disconnect(self, websocket: WebSocket, user_id: int, team_id: int | None) -> None:
        if websocket in self._user_connections[user_id]:
            self._user_connections[user_id].remove(websocket)
        if not self._user_connections[user_id]:
            self._user_connections.pop(user_id, None)
            if team_id is not None:
                self._team_members[team_id].discard(user_id)
            # 마지막 연결이 끊기면 모든 세션 방 및 admin 집합에서 제거
            for watchers in self._session_watchers.values():
                watchers.discard(user_id)
            self._admin_users.discard(user_id)

    def join_session(self, session_id: int, user_id: int) -> None:
        self._session_watchers[session_id].add(user_id)

    def leave_session(self, session_id: int, user_id: int) -> None:
        self._session_watchers[session_id].discard(user_id)

    async def send_to_user(self, user_id: int, message: dict[str, Any]) -> None:
        for ws in self._user_connections.get(user_id, []):
            await ws.send_json(message)

    async def send_to_team(self, team_id: int, message: dict[str, Any]) -> None:
        for user_id in self._team_members.get(team_id, set()):
            await self.send_to_user(user_id, message)

    async def broadcast_to_session(
        self, session_id: int, message: dict[str, Any]
    ) -> None:
        for user_id in list(self._session_watchers.get(session_id, set())):
            await self.send_to_user(user_id, message)

    async def broadcast_to_session_admins(
        self, session_id: int, message: dict[str, Any]
    ) -> None:
        """세션을 보고 있는 운영자(role=admin)에게만 송신."""
        watchers = self._session_watchers.get(session_id, set())
        for user_id in list(watchers):
            if user_id in self._admin_users:
                await self.send_to_user(user_id, message)

    async def broadcast_to_admins(self, message: dict[str, Any]) -> None:
        """현재 접속 중인 모든 운영자에게 송신."""
        for user_id in list(self._admin_users):
            await self.send_to_user(user_id, message)

    async def broadcast(self, message: dict[str, Any]) -> None:
        for user_id in list(self._user_connections.keys()):
            await self.send_to_user(user_id, message)


manager = ConnectionManager()
