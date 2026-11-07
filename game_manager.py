"""Framework-free, synchronous registry shared by every game type.

Callers serialize operations for each scope; no plugin or game-specific imports.
"""

from dataclasses import dataclass
from typing import Protocol


class Game(Protocol):
    game_id: str
    display_name: str
    status: str
    deadline: float

    def expire(self, now: float) -> bool: ...

    def stop(self) -> None: ...


@dataclass(frozen=True)
class Scope:
    platform: str
    kind: str
    target: str


@dataclass
class Session:
    game: Game
    origin: str


class GameManager:
    def __init__(self):
        self.sessions: dict[Scope, Session] = {}

    def get(self, scope: Scope) -> Session | None:
        return self.sessions.get(scope)

    def start(self, scope: Scope, game: Game, origin: str) -> bool:
        if scope in self.sessions:
            return False
        self.sessions[scope] = Session(game, origin)
        return True

    def release(self, scope: Scope, session: Session) -> bool:
        """Identity guard prevents stale callbacks from removing a new game."""
        if self.sessions.get(scope) is session:
            del self.sessions[scope]
            return True
        return False

    def clear(self) -> None:
        self.sessions.clear()
