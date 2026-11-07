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


class At:
    def __init__(self, qq):
        self.qq = qq


class Image(tuple):
    def __new__(cls, data):
        return super().__new__(cls, ("image", data))

    @staticmethod
    def fromBytes(data):
        return Image(data)


class MessageChain:
    def __init__(self, chain=None):
        self.chain = [] if chain is None else chain

    @property
    def text(self):
        return "".join(c.text for c in self.chain if isinstance(c, Plain))

    def message(self, text):
        self.chain.append(Plain(text))
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
        self.chains = []
        self.fail = False

    async def send_message(self, origin, chain):
        if self.fail:
            raise RuntimeError("Delivery unavailable")
        self.sent.append((origin, chain.text))
        self.chains.append(chain.chain)


@pytest.fixture
def adapter(monkeypatch):
    def decorator(*args, **kwargs):
        return lambda method: method

    class Star:
        def __init__(self, context):
            self.context = context

    modules = {
        "astrbot": {},
        "astrbot.api": {
            "logger": logging.getLogger("adapter-test"),
            "AstrBotConfig": dict,
        },
        "astrbot.api.event": {
            "AstrMessageEvent": Event,
            "MessageChain": MessageChain,
            "filter": SimpleNamespace(
                command=decorator,
                event_message_type=decorator,
                EventMessageType=SimpleNamespace(ALL="all"),
            ),
        },
        "astrbot.api.message_components": {"Image": Image, "Plain": Plain, "At": At},
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
    monkeypatch.setattr(module, "render_hint", lambda game: b"HINT")
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
        assert isinstance(guess.sent[0][0], At)
        assert guess.sent[0][0].qq == "u3"
        assert "恭喜" in guess.sent[0][1].text
        assert guess.sent[1] == [Image(b"PNG")]
        await plugin.start_idiom(a)
        await plugin.stop_idiom(b)
        assert not plugin.manager.sessions
        assert "本轮已结束" in b.sent[-2][0].text
        assert b.sent[-1] == [Image(b"PNG")]

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
        assert context.chains[-1] == [Image(b"PNG")]
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


@pytest.mark.parametrize("text", ["今天吃饭", "abcd"])
def test_non_idiom_message_gets_feedback_without_consuming_turn(adapter, text):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        now = [0]
        plugin.clock = lambda: now[0]
        start = Event()
        await plugin.start_idiom(start)
        session = plugin.manager.get(plugin._scope(start))
        now[0] = 299
        guess = Event(text)
        await plugin.on_guess(guess)
        assert guess.stopped
        assert guess.sent[0][0].text == f"{text} 不是成语呢~"
        assert len(guess.sent[0]) == 1
        assert not session.game.guesses
        assert session.game.deadline == 300
        now[0] = 300
        await plugin._expire_scope(plugin._scope(start), session)
        assert session.game.status == "timeout"
        assert not plugin.manager.sessions
        await plugin.terminate()

    asyncio.run(scenario())


def test_same_length_command_is_not_a_guess(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        start = Event()
        await plugin.start_idiom(start)
        command = Event("/abc")
        await plugin.on_guess(command)
        assert not command.stopped
        assert not command.sent
        await plugin.terminate()

    asyncio.run(scenario())


@pytest.mark.parametrize("ending", ["timeout", "stopped"])
def test_ended_game_never_reveals_answer_in_text_when_rendering_fails(
    adapter, monkeypatch, ending
):
    async def scenario():
        context = Context()
        plugin = adapter.PlaygroundPlugin(context)
        now = [0]
        plugin.clock = lambda: now[0]
        start = Event()
        await plugin.start_idiom(start)
        scope = plugin._scope(start)
        session = plugin.manager.get(scope)

        def broken(game):
            raise RuntimeError("Font unavailable")

        monkeypatch.setattr(adapter, "render_board", broken)
        if ending == "timeout":
            now[0] = 300
            await plugin._expire_scope(scope, session)
            chain = context.chains[0]
        else:
            await plugin.stop_idiom(start)
            chain = start.sent[-1]
        assert not plugin.manager.sessions
        assert all(isinstance(c, Plain) for c in chain)
        assert session.game.answer not in "".join(c.text for c in chain)
        assert "答案图片生成失败" in "".join(c.text for c in chain)
        await plugin.terminate()

    asyncio.run(scenario())


@pytest.mark.parametrize("text", ["你好", "今天天气真好", "abc", ""])
def test_wrong_length_message_is_silently_ignored(adapter, text):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        plugin.clock = lambda: 0
        start = Event()
        await plugin.start_idiom(start)
        session = plugin.manager.get(plugin._scope(start))
        message = Event(text)
        await plugin.on_guess(message)
        assert not message.sent
        assert not message.stopped
        assert session.game.deadline == 300
        assert not session.game.guesses
        await plugin.terminate()

    asyncio.run(scenario())


def test_hint_command_summarizes_shared_history_without_resetting_timer(
    adapter, monkeypatch
):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        now = [0]
        plugin.clock = lambda: now[0]
        start = Event()
        await plugin.start_idiom(start)
        session = plugin.manager.get(plugin._scope(start))
        session.game = adapter.IdiomGame.create(
            now=0, words=plugin.words, answer="画蛇添足"
        )
        now[0] = 1
        await plugin.on_guess(Event("画龙点睛"))
        snapshots = []

        def render(game):
            snapshots.append(adapter.format_hint(game))
            return b"HINT"

        monkeypatch.setattr(adapter, "render_hint", render)
        now[0] = 299
        hint = Event(sender="another-player")
        await plugin.hint_idiom(hint)
        await plugin.hint_idiom(hint)
        assert hint.stopped
        assert hint.sent[0][-1] == ("image", b"HINT")
        assert "画  huà" in snapshots[0]
        assert snapshots[0] == snapshots[1]
        assert session.game.deadline == 301
        assert len(session.game.guesses) == 1
        now[0] = 301
        await plugin.hint_idiom(hint)
        assert not plugin.manager.sessions
        assert session.game.status == "timeout"
        assert len(hint.sent) == 2  # Expired requests send the normal timeout result.
        await plugin.terminate()

    asyncio.run(scenario())


def test_hint_without_current_game_and_in_other_scope(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        hint = Event()
        await plugin.hint_idiom(hint)
        assert hint.sent[0][0].text == "当前没有正在进行的猜成语游戏。"
        await plugin.start_idiom(Event(group="other-group"))
        await plugin.hint_idiom(hint)
        assert hint.sent[-1][0].text == "当前没有正在进行的猜成语游戏。"
        await plugin.start_idiom(Event())
        session = plugin.manager.get(plugin._scope(hint))
        session.game.game_id = "another-game"
        await plugin.hint_idiom(hint)
        assert hint.sent[-1][0].text == "当前没有正在进行的猜成语游戏。"
        assert session.game.status == "playing"
        await plugin.terminate()

    asyncio.run(scenario())


def test_hint_rendering_failure_returns_only_known_information(adapter, monkeypatch):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        plugin.clock = lambda: 0
        hint = Event()
        await plugin.start_idiom(hint)
        session = plugin.manager.get(plugin._scope(hint))

        def broken(game):
            raise RuntimeError("Font unavailable")

        monkeypatch.setattr(adapter, "render_hint", broken)
        await plugin.hint_idiom(hint)
        assert hint.sent[-1][0].text == "\n".join(["?  ???"] * 4)
        assert session.game.answer not in hint.sent[-1][0].text
        assert session.game.deadline == 300
        assert not session.game.guesses
        await plugin.terminate()

    asyncio.run(scenario())


def test_configured_timeout_controls_deadlines_messages_and_new_games(adapter):
    async def scenario():
        config = {"idiom_idle_timeout_seconds": 150}
        context = Context()
        plugin = adapter.PlaygroundPlugin(context, config)
        now = [0]
        plugin.clock = lambda: now[0]
        start = Event()
        await plugin.start_idiom(start)
        scope = plugin._scope(start)
        session = plugin.manager.get(scope)
        assert session.game.deadline == 150
        assert "150 秒" in start.sent[0][0].text
        config["idiom_idle_timeout_seconds"] = 60
        word = next(w for w in plugin.words if w != session.game.answer)
        now[0] = 149
        guess = Event(word)
        await plugin.on_guess(guess)
        assert session.game.deadline == 299
        assert guess.sent == [[Image(b"PNG")]]
        await plugin.hint_idiom(Event())
        assert session.game.deadline == 299
        await plugin.on_guess(Event("今天吃饭"))
        assert session.game.deadline == 299
        now[0] = 299
        await plugin._expire_scope(scope, session)
        assert "150 秒" in context.sent[0][1]
        assert not plugin.manager.sessions
        await plugin.start_idiom(start)
        assert plugin.manager.get(scope).game.deadline == 359
        assert "60 秒" in start.sent[-2][0].text
        await plugin.terminate()

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "seconds", [0, -1, float("inf"), float("nan"), True, None, "bad"]
)
def test_invalid_plugin_timeout_falls_back_to_default(adapter, seconds):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(
            Context(), {"idiom_idle_timeout_seconds": seconds}
        )
        plugin.clock = lambda: 0
        start = Event()
        await plugin.start_idiom(start)
        assert plugin.manager.get(plugin._scope(start)).game.deadline == 300
        assert "300 秒" in start.sent[0][0].text
        await plugin.terminate()

    asyncio.run(scenario())


def test_fractional_seconds_are_not_converted_to_minutes(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(
            Context(), {"idiom_idle_timeout_seconds": 2.5}
        )
        plugin.clock = lambda: 10
        event = Event()
        await plugin.start_idiom(event)
        assert plugin.manager.get(plugin._scope(event)).game.deadline == 12.5
        assert "2.5 秒" in event.sent[0][0].text
        await plugin.terminate()

    asyncio.run(scenario())


@pytest.mark.parametrize("ending", ["timeout", "stopped"])
@pytest.mark.parametrize("has_guess", [False, True])
def test_terminal_answer_is_delivered_as_an_image(
    adapter, monkeypatch, ending, has_guess
):
    async def scenario():
        context = Context()
        plugin = adapter.PlaygroundPlugin(context)
        now = [0]
        plugin.clock = lambda: now[0]
        start = Event()
        await plugin.start_idiom(start)
        scope = plugin._scope(start)
        session = plugin.manager.get(scope)
        if has_guess:
            word = next(w for w in plugin.words if w != session.game.answer)
            await plugin.on_guess(Event(word))
        rendered = []

        def render(game):
            rendered.append((game.status, len(game.guesses)))
            return b"ANSWER-BOARD"

        monkeypatch.setattr(adapter, "render_board", render)
        if ending == "timeout":
            now[0] = session.game.deadline
            await plugin._expire_scope(scope, session)
            chain = context.chains[-1]
        else:
            await plugin.stop_idiom(start)
            chain = start.sent[-1]
        assert rendered == [(ending, int(has_guess))]
        assert chain[-1] == ("image", b"ANSWER-BOARD")
        assert session.game.answer not in "".join(
            c.text for c in chain if isinstance(c, Plain)
        )
        assert not plugin.manager.sessions
        await plugin.terminate()

    asyncio.run(scenario())


def assert_standalone_images(messages):
    for message in messages:
        if any(isinstance(c, Image) for c in message):
            assert len(message) == 1
            assert isinstance(message[0], Image)


def test_hints_and_ongoing_guesses_send_only_images(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        plugin.clock = lambda: 0
        start = Event()
        await plugin.start_idiom(start)
        session = plugin.manager.get(plugin._scope(start))
        word = next(w for w in plugin.words if w != session.game.answer)
        guess = Event(word)
        await plugin.on_guess(guess)
        assert guess.sent == [[Image(b"PNG")]]
        hint = Event()
        await plugin.hint_idiom(hint)
        assert hint.sent == [[Image(b"HINT")]]
        assert session.game.deadline == 300
        assert len(session.game.guesses) == 1
        assert_standalone_images(start.sent)
        await plugin.terminate()

    asyncio.run(scenario())


@pytest.mark.parametrize("group", ["g1", ""])
def test_winner_notice_mentions_actual_group_winner_and_keeps_image_separate(
    adapter, group
):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        start = Event(group=group, sender="starter")
        await plugin.start_idiom(start)
        session = plugin.manager.get(plugin._scope(start))
        winner = Event(
            session.game.answer,
            group=group,
            sender="winner" if group else "starter",
        )
        await plugin.on_guess(winner)
        assert len(winner.sent) == 2
        notice, board = winner.sent
        if group:
            assert isinstance(notice[0], At)
            assert notice[0].qq == "winner"
        else:
            assert not any(isinstance(c, At) for c in notice)
        assert (
            "".join(c.text for c in notice if isinstance(c, Plain)).strip()
            == "恭喜猜中！"
        )
        assert board == [Image(b"PNG")]
        assert_standalone_images(winner.sent)
        assert not plugin.manager.sessions
        await plugin.terminate()

    asyncio.run(scenario())


@pytest.mark.parametrize("ending", ["timeout", "stopped", "lost"])
def test_terminal_notice_and_board_are_delivered_as_separate_messages(adapter, ending):
    async def scenario():
        context = Context()
        plugin = adapter.PlaygroundPlugin(context)
        plugin.clock = lambda: 0
        start = Event()
        await plugin.start_idiom(start)
        scope = plugin._scope(start)
        session = plugin.manager.get(scope)
        if ending == "timeout":
            session.game.deadline = 0
            await plugin._expire_scope(scope, session)
            messages = context.chains
        elif ending == "stopped":
            start.sent.clear()
            await plugin.stop_idiom(start)
            messages = start.sent
        else:
            choices = [w for w in plugin.words if w != session.game.answer]
            for word in choices[:9]:
                session.game.submit(word, now=0)
            final_guess = Event(choices[9])
            await plugin.on_guess(final_guess)
            messages = final_guess.sent
        assert len(messages) == 2
        assert all(isinstance(c, Plain) for c in messages[0])
        assert messages[1] == [Image(b"PNG")]
        assert_standalone_images(messages)
        assert not plugin.manager.sessions
        await plugin.terminate()

    asyncio.run(scenario())


def test_notice_delivery_failure_does_not_skip_answer_image(adapter):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        start = Event()
        await plugin.start_idiom(start)
        session = plugin.manager.get(plugin._scope(start))

        class NoticeFailure(Event):
            async def send(self, chain):
                if any(isinstance(c, Plain) for c in chain):
                    raise RuntimeError("Notice delivery unavailable")
                await super().send(chain)

        winner = NoticeFailure(session.game.answer, sender="winner")
        await plugin.on_guess(winner)
        assert winner.sent == [[Image(b"PNG")]]
        assert not plugin.manager.sessions
        await plugin.terminate()

    asyncio.run(scenario())


def test_astrbot_start_passes_common_answers_to_game_creation(adapter, monkeypatch):
    async def scenario():
        plugin = adapter.PlaygroundPlugin(Context())
        selected = []

        def choose(pool):
            selected.append(tuple(pool))
            return "一心一意"

        monkeypatch.setattr(
            adapter.IdiomGame.create.__globals__["random"], "choice", choose
        )
        start = Event()
        await plugin.start_idiom(start)
        assert selected == [plugin.answers]
        assert len(plugin.answers) == 1415
        assert "一丁不识" not in plugin.answers
        assert plugin.manager.get(plugin._scope(start)).game.answer == "一心一意"
        await plugin.terminate()

    asyncio.run(scenario())
