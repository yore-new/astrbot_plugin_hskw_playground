"""Contract tests with an AstrBot double; real delivery still needs host testing."""

import asyncio
import importlib
import logging
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest


class Plain:
    def __init__(self, text):
        self.text = text


class Image:
    @staticmethod
    def fromBytes(data):
        return ("image", data)


class MessageChain:
    def message(self, text):
        self.text = text
        return self


class Event:
    def __init__(self, text="", *, group="g1", sender="u1", platform="p1"):
        self.message_str = text
        self.group, self.sender, self.platform = group, sender, platform
        self.unified_msg_origin = f"{platform}:{group}:{sender}"
        self.sent = []
        self.stopped = False

    def get_group_id(self):
        return self.group

    def get_sender_id(self):
        return self.sender

    def get_platform_id(self):
        return self.platform

    def get_messages(self):
        return [Plain(self.message_str)]

    def stop_event(self):
        self.stopped = True

    def chain_result(self, chain):
        return chain

    async def send(self, result):
        await asyncio.sleep(0)
        self.sent.append(result)


class Context:
    def __init__(self):
        self.sent = []
        self.fail = False

    async def send_message(self, origin, chain):
        if self.fail:
            raise RuntimeError("Delivery unavailable")
        self.sent.append((origin, chain.text))


@pytest.fixture
def adapter(monkeypatch):
    def decorator(*args, **kwargs):
        return lambda method: method

    class Star:
        def __init__(self, context):
            self.context = context

    modules = {
        "astrbot": {},
        "astrbot.api": {"logger": logging.getLogger("adapter-test")},
        "astrbot.api.event": {
            "AstrMessageEvent": Event,
            "MessageChain": MessageChain,
            "filter": SimpleNamespace(
                command=decorator,
                event_message_type=decorator,
                EventMessageType=SimpleNamespace(ALL="all"),
            ),
        },
        "astrbot.api.message_components": {"Image": Image, "Plain": Plain},
        "astrbot.api.star": {"Context": Context, "Star": Star},
    }
    for name, attrs in modules.items():
        module = types.ModuleType(name)
        module.__dict__.update(attrs)
        monkeypatch.setitem(sys.modules, name, module)
    package_name = "_playground_adapter_test"
    package = types.ModuleType(package_name)
    package.__path__ = [str(Path(__file__).resolve().parents[1])]
    monkeypatch.setitem(sys.modules, package_name, package)
    module = importlib.import_module(f"{package_name}.main")
    # Real render_board is separately tested; adapter tests inspect orchestration.
    monkeypatch.setattr(module, "render_board", lambda game: b"PNG")
    yield module
    for name in list(sys.modules):
        if name.startswith(package_name):
            del sys.modules[name]


def test_concurrent_start_group_sharing_and_stop(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        plugin.clock = lambda: 0
        a, b = Event(sender="u1"), Event(sender="u2")
        await asyncio.gather(plugin.start_idiom(a), plugin.start_idiom(b))
        assert len(plugin.manager.sessions) == 1
        assert "不可以开始" in b.sent[0][0].text
        session = plugin.manager.get(plugin._scope(a))
        answer = session.game.answer
        guess = Event(answer, sender="u3")
        await plugin.on_guess(guess)
        assert guess.stopped
        assert not plugin.manager.sessions
        assert "恭喜" in guess.sent[0][0].text
        await plugin.start_idiom(a)
        await plugin.stop_idiom(b)
        assert not plugin.manager.sessions
        assert "本轮已结束" in b.sent[-1][0].text

    asyncio.run(scenario())


def test_timer_reset_invalid_duplicate_and_passive_expiry(adapter):
    async def scenario():
        context = Context()
        plugin = adapter.PlaygroundPlugin(context)
        now = [0]
        plugin.clock = lambda: now[0]
        a = Event()
        await plugin.start_idiom(a)
        scope = plugin._scope(a)
        session = plugin.manager.get(scope)
        word = next(w for w in plugin.words if w != session.game.answer)
        now[0] = 299
        await plugin.on_guess(Event(word))
        assert session.game.deadline == 599
        now[0] = 500
        await plugin.on_guess(Event(word))
        invalid = Event("hello")
        await plugin.on_guess(invalid)
        assert not invalid.stopped
        assert session.game.deadline == 599
        now[0] = 599
        await plugin._expire_scope(scope, session)
        assert plugin.manager.get(scope) is None
        assert session.game.status == "timeout"
        assert context.sent[0][0] == a.unified_msg_origin
        assert session.game.answer in context.sent[0][1]
        # A stale expiry callback must leave the new game untouched.
        await plugin.start_idiom(a)
        await plugin._expire_scope(scope, session)
        assert plugin.manager.get(scope) is not None
        await plugin.terminate()

    asyncio.run(scenario())


def test_different_groups_platforms_and_private_users(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        events = [
            Event(),
            Event(group="g2"),
            Event(platform="p2"),
            Event(group="", sender="u1"),
            Event(group="", sender="u2"),
        ]
        await asyncio.gather(*(plugin.start_idiom(e) for e in events))
        assert len(plugin.manager.sessions) == 5
        await plugin.terminate()
        assert not plugin.manager.sessions

    asyncio.run(scenario())


def test_delivery_and_render_failure_do_not_break_lifecycle(adapter, monkeypatch):
    async def scenario():
        context = Context()
        context.fail = True
        plugin = adapter.PlaygroundPlugin(context)
        now = [0]
        plugin.clock = lambda: now[0]
        a = Event()
        await plugin.start_idiom(a)
        now[0] = 300
        await plugin._expire_scope(
            plugin._scope(a), plugin.manager.get(plugin._scope(a))
        )
        assert not plugin.manager.sessions

        def broken(game):
            raise RuntimeError("Font error")

        monkeypatch.setattr(adapter, "render_board", broken)
        await plugin.start_idiom(a)
        session = plugin.manager.get(plugin._scope(a))
        word = next(w for w in plugin.words if w != session.game.answer)
        guess = Event(word)
        await plugin.on_guess(guess)
        assert len(session.game.guesses) == 1
        assert any(
            "进度已保留" in c.text for c in guess.sent[0] if isinstance(c, Plain)
        )
        await plugin.terminate()

    asyncio.run(scenario())


def test_background_expiry_and_termination(adapter):
    async def scenario():
        context = Context()
        plugin = adapter.PlaygroundPlugin(context)
        now = [0]
        plugin.clock = lambda: now[0]
        await plugin.initialize()
        await plugin.start_idiom(Event())
        now[0] = 300
        # Poll the scheduler, not a five-minute production sleep.
        for _ in range(30):
            if context.sent:
                break
            await asyncio.sleep(0.05)
        assert context.sent
        assert not plugin.manager.sessions
        task = plugin.expiry_task
        await plugin.terminate()
        assert task.done()

    asyncio.run(scenario())


def test_simultaneous_guesses_cannot_exceed_ten(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        event = Event()
        await plugin.start_idiom(event)
        game = plugin.manager.get(plugin._scope(event)).game
        words = [w for w in plugin.words if w != game.answer][:12]
        guesses = [Event(w, sender=f"u{i}") for i, w in enumerate(words)]
        await asyncio.gather(*(plugin.on_guess(e) for e in guesses))
        assert len(game.guesses) == 10
        assert game.status == "lost"
        assert not plugin.manager.sessions
        assert sum(bool(e.sent) for e in guesses) == 10

    asyncio.run(scenario())


def test_start_after_expiry_and_wrong_game_end(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        now = [0]
        plugin.clock = lambda: now[0]
        event = Event()
        await plugin.start_idiom(event)
        old = plugin.manager.get(plugin._scope(event))
        now[0] = 300
        await plugin.start_idiom(event)
        current = plugin.manager.get(plugin._scope(event))
        assert current is not old
        assert old.game.status == "timeout"
        current.game.game_id = "another"
        current.game.display_name = "其他游戏"
        await plugin.stop_idiom(event)
        assert plugin.manager.get(plugin._scope(event)) is current
        await plugin.start_idiom(event)
        assert "其他游戏" in event.sent[-1][0].text
        await plugin.terminate()

    asyncio.run(scenario())


def test_send_failure_does_not_double_count(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        event = Event()
        await plugin.start_idiom(event)
        game = plugin.manager.get(plugin._scope(event)).game
        word = next(w for w in plugin.words if w != game.answer)

        class BrokenEvent(Event):
            async def send(self, result):
                raise RuntimeError("Upload unavailable")

        await plugin.on_guess(BrokenEvent(word))
        assert len(game.guesses) == 1
        retry = Event(word)
        await plugin.on_guess(retry)
        assert len(game.guesses) == 1
        assert "已经提交过" in retry.sent[0][0].text
        await plugin.terminate()

    asyncio.run(scenario())


def test_submission_uses_one_timestamp_at_deadline_boundary(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        plugin.clock = lambda: 0
        event = Event()
        await plugin.start_idiom(event)
        game = plugin.manager.get(plugin._scope(event)).game
        word = next(w for w in plugin.words if w != game.answer)
        times = iter([299.999, 300])
        plugin.clock = lambda: next(times)
        await plugin.on_guess(Event(word))
        assert len(game.guesses) == 1
        assert game.status == "playing"
        assert game.deadline == 599.999
        await plugin.terminate()

    asyncio.run(scenario())
