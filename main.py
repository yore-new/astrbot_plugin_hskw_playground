"""AstrBot adapter. Rules, rendering and registry remain locally testable."""

import asyncio
import math
import time
from collections import defaultdict

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import At, Image, Plain
from astrbot.api.star import Context, Star

from .game_manager import GameManager, Scope, Session
from .games.idiom_wordle.core import IDLE_SECONDS, IdiomGame, load_answers, load_words
from .games.idiom_wordle.hints import format_hint
from .games.idiom_wordle.render import render_board, render_hint


class PlaygroundPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig | None = None):
        super().__init__(context)
        self.config = config if config is not None else {}
        self.manager = GameManager()
        self.locks = defaultdict(asyncio.Lock)
        self.words = load_words()
        self.answers = load_answers(self.words)
        self.clock = time.monotonic
        self.expiry_task = None
        self.expiry_workers = set()

    async def initialize(self):
        # Fail early if the bundled font cannot be loaded.
        await asyncio.to_thread(
            render_board,
            IdiomGame.create(
                now=self.clock(), words=self.words, answer_pool=self.answers
            ),
        )
        self.expiry_task = asyncio.create_task(self._watch_expiry())

    @staticmethod
    def _scope(event: AstrMessageEvent) -> Scope:
        group = event.get_group_id()
        return Scope(
            event.get_platform_id(),
            "group" if group else "private",
            str(group or event.get_sender_id()),
        )

    def _idle_seconds(self) -> float:
        """Read the configured interval when a new game starts."""
        value = self.config.get("idiom_idle_timeout_seconds", IDLE_SECONDS)
        try:
            if isinstance(value, bool):
                raise ValueError("Boolean timeout is invalid")
            seconds = float(value)
            if not math.isfinite(seconds) or seconds <= 0:
                raise ValueError("Timeout must be finite and positive")
        except (TypeError, ValueError, OverflowError):
            logger.warning("猜成语超时配置无效，使用默认 300 秒")
            return IDLE_SECONDS
        return seconds

    async def _build_chain(self, text, game=None):
        chain = [Plain(text)] if text else []
        if game is not None:
            try:
                png = await asyncio.to_thread(render_board, game)
                chain.append(Image.fromBytes(png))
            except Exception:
                logger.exception("猜成语棋盘绘制失败")
                if game.status != "playing":
                    chain.append(Plain("答案图片生成失败，本轮已结束。"))
                    return chain
                chain.append(Plain("棋盘绘制失败，进度已保留。"))
                for guess in game.guesses:
                    marks = {"exact": "🟩", "misplaced": "🟨", "none": "⬜"}
                    chain.append(
                        Plain(
                            "\n"
                            + guess.text
                            + " "
                            + "".join(marks[c.char_match] for c in guess.cells)
                        )
                    )
        return chain

    @staticmethod
    def _image_messages(chain):
        """Keep each image in its own message, preserving component order."""
        messages = []
        pending = []
        for component in chain:
            if isinstance(component, Image):
                if pending:
                    messages.append(pending)
                    pending = []
                messages.append([component])
            else:
                pending.append(component)
        if pending:
            messages.append(pending)
        return messages

    async def _deliver(self, chain, send):
        for message in self._image_messages(chain):
            try:
                await asyncio.wait_for(send(message), timeout=30)
            except Exception:
                # A failed notice must not prevent the standalone board delivery.
                logger.exception("游戏消息发送失败")

    async def _send(self, event, text=None, game=None, *, mention=None):
        chain = await self._build_chain(text, game)
        if mention is not None:
            chain.insert(0, At(qq=mention))
        # Await delivery inside the scope lock to preserve board order.
        await self._deliver(chain, lambda parts: event.send(event.chain_result(parts)))

    async def _expire(
        self, scope: Scope, session: Session, *, now: float | None = None
    ) -> bool:
        if not session.game.expire(self.clock() if now is None else now):
            return False
        self.manager.release(scope, session)
        game = session.game if isinstance(session.game, IdiomGame) else None
        text = (
            f"{game.idle_seconds:g} 秒未猜词，本轮结束。"
            if game is not None
            else f"{session.game.display_name}游戏超时结束。"
        )
        chain = await self._build_chain(text, game)
        await self._deliver(
            chain,
            lambda parts: self.context.send_message(
                session.origin, MessageChain(chain=parts)
            ),
        )
        return True

    async def _expire_scope(self, scope, session):
        async with self.locks[scope]:
            if self.manager.get(scope) is session:
                await self._expire(scope, session)

    async def _watch_expiry(self):
        while True:
            await asyncio.sleep(1)
            now = self.clock()
            for scope, session in list(self.manager.sessions.items()):
                # Separate tasks keep a slow adapter from delaying other groups.
                if now >= session.game.deadline and not self.locks[scope].locked():
                    task = asyncio.create_task(self._expire_scope(scope, session))
                    self.expiry_workers.add(task)
                    task.add_done_callback(self.expiry_workers.discard)

    @filter.command("猜成语", priority=10)
    async def start_idiom(self, event: AstrMessageEvent):
        """开始一局四字成语 Wordle，最多猜十次。"""
        event.stop_event()
        scope = self._scope(event)
        async with self.locks[scope]:
            session = self.manager.get(scope)
            if session and await self._expire(scope, session):
                session = None
            if session:
                await self._send(
                    event,
                    f"「{session.game.display_name}」游戏正在进行中，不可以开始新的游戏哦。",
                )
                return
            game = IdiomGame.create(
                now=self.clock(),
                words=self.words,
                idle_seconds=self._idle_seconds(),
                answer_pool=self.answers,
            )
            self.manager.start(scope, game, event.unified_msg_origin)
            await self._send(
                event,
                f"猜成语开始！共 10 次，每次有效猜词后有 {game.idle_seconds:g} 秒。\n"
                "汉字、拼音部件和声调分别提示：绿=位置正确，黄=存在但错位，灰=无匹配。\n"
                "轻声不标调。/猜成语提示 查看线索，/猜成语结束 结束。",
                game,
            )

    @filter.command("猜成语提示", priority=10)
    async def hint_idiom(self, event: AstrMessageEvent):
        """汇总已知的正确汉字和拼音，不消耗次数或重置计时。"""
        event.stop_event()
        scope = self._scope(event)
        async with self.locks[scope]:
            session = self.manager.get(scope)
            if session and await self._expire(scope, session):
                return
            if not session or session.game.game_id != "idiom_wordle":
                await self._send(event, "当前没有正在进行的猜成语游戏。")
                return
            game = session.game
            chain = []
            try:
                png = await asyncio.to_thread(render_hint, game)
                chain.append(Image.fromBytes(png))
            except Exception:
                logger.exception("猜成语提示绘制失败")
                chain.append(Plain(format_hint(game)))
            await self._deliver(
                chain, lambda parts: event.send(event.chain_result(parts))
            )

    @filter.command("猜成语结束", priority=10)
    async def stop_idiom(self, event: AstrMessageEvent):
        """结束当前聊天中的猜成语游戏并公布答案。"""
        event.stop_event()
        scope = self._scope(event)
        async with self.locks[scope]:
            session = self.manager.get(scope)
            if session and await self._expire(scope, session):
                return
            if not session or session.game.game_id != "idiom_wordle":
                await self._send(event, "当前没有正在进行的猜成语游戏。")
                return
            session.game.stop()
            self.manager.release(scope, session)
            await self._send(event, "本轮已结束。", session.game)

    @filter.event_message_type(filter.EventMessageType.ALL, priority=0)
    async def on_guess(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        if (
            len(text) != 4
            or text.startswith("/")
            or any(not isinstance(c, Plain) for c in event.get_messages())
        ):
            return
        scope = self._scope(event)
        if not self.manager.get(scope):
            return
        async with self.locks[scope]:
            session = self.manager.get(scope)
            if not session or session.game.game_id != "idiom_wordle":
                return
            event.stop_event()
            # Use one timestamp for expiry and submission, including the boundary.
            now = self.clock()
            if await self._expire(scope, session, now=now):
                return
            game = session.game
            result = game.submit(text, now=now)
            if result == "not_idiom":
                await self._send(event, f"{text} 不是成语呢~")
                return
            if result == "duplicate":
                await self._send(
                    event, "这个猜测已经提交过啦，不消耗次数，也不会重新计时。"
                )
                return
            if result != "accepted":
                await self._send(event, "无法解析该猜测，请发送四个可识别的汉字。")
                return
            if game.status != "playing":
                self.manager.release(scope, session)
            if game.status == "won":
                await self._send(
                    event,
                    " 恭喜猜中！",
                    game,
                    mention=event.get_sender_id() if event.get_group_id() else None,
                )
            elif game.status == "lost":
                await self._send(event, "机会用完啦。", game)
            else:
                await self._send(event, game=game)

    async def terminate(self):
        tasks = list(self.expiry_workers)
        if self.expiry_task:
            tasks.append(self.expiry_task)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.manager.clear()
        self.locks.clear()
