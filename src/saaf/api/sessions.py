"""Bounded, process-local sessions storing authoritative confirmation context."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from uuid import UUID, uuid4

from saaf.orchestration.contracts import ConversationContext

from .models import SessionInfo


class SessionMissing(LookupError):
    pass


class SessionCapacity(RuntimeError):
    pass


@dataclass
class Session:
    id: UUID
    expires_at: datetime
    context: ConversationContext = field(default_factory=ConversationContext)
    images: dict[str, Path] = field(default_factory=dict)
    lock: Lock = field(default_factory=Lock)
    active: int = 0

    def info(self) -> SessionInfo:
        return SessionInfo(session_id=self.id, farm_id=self.context.farm_id, expires_at=self.expires_at)

    def save_image(self, observation_id: str, path: Path) -> None:
        if len(self.images) >= 8:
            old = next(iter(self.images))
            self.images.pop(old).unlink(missing_ok=True)
        self.images[observation_id] = path


class Sessions:
    def __init__(self, ttl_seconds: int, capacity: int = 128) -> None:
        self.ttl = timedelta(seconds=ttl_seconds)
        self.capacity = capacity
        self._lock = Lock()
        self._sessions: dict[UUID, Session] = {}

    def _prune(self, now: datetime) -> None:
        for key, session in list(self._sessions.items()):
            if session.expires_at <= now and not session.active:
                self._remove(key)

    def _remove(self, session_id: UUID) -> None:
        session = self._sessions.pop(session_id)
        for image in session.images.values():
            image.unlink(missing_ok=True)

    def create(self) -> SessionInfo:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune(now)
            if len(self._sessions) >= self.capacity:
                raise SessionCapacity
            session = Session(uuid4(), now + self.ttl)
            self._sessions[session.id] = session
            return session.info()

    @contextmanager
    def use(self, session_id: UUID):
        now = datetime.now(timezone.utc)
        with self._lock:
            self._prune(now)
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionMissing
            session.active += 1
        try:
            with session.lock:
                session.expires_at = datetime.now(timezone.utc) + self.ttl
                yield session
        finally:
            with self._lock:
                session.active -= 1

    def delete(self, session_id: UUID) -> bool:
        with self._lock:
            self._prune(datetime.now(timezone.utc))
            session = self._sessions.get(session_id)
            if session is None:
                raise SessionMissing
            if session.active:
                return False
            self._remove(session_id)
            return True
