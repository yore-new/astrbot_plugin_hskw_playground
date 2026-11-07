from game_manager import GameManager, Scope
from games.idiom_wordle.core import IdiomGame


def test_isolation_and_shared_exclusivity():
    manager = GameManager()
    a = Scope("qq-1", "group", "123")
    b = Scope("qq-1", "group", "456")
    c = Scope("qq-2", "group", "123")
    d = Scope("qq-1", "private", "123")
    for scope in (a, b, c, d):
        assert manager.start(scope, IdiomGame.create(now=0), "origin")
    other = IdiomGame.create(now=0)
    other.game_id = "other"
    other.display_name = "其他游戏"
    assert not manager.start(a, other, "origin")
    session = manager.get(a)
    assert manager.release(a, session)
    assert manager.start(a, other, "origin")
    assert not manager.release(a, session)
    assert manager.get(a).game is other
