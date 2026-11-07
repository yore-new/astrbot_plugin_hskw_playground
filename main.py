"""AstrBot adapter. Rules, rendering and registry remain locally testable."""

import asyncio
import time
from collections import defaultdict

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Image, Plain
from astrbot.api.star import Context, Star

from .game_manager import GameManager, Scope, Session
from .games.idiom_wordle.core import IdiomGame, is_candidate, load_words
from .games.idiom_wordle.render import render_board


class PlaygroundPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.manager = GameManager()
        self.locks = defaultdict(asyncio.Lock)
        self.words = load_words()
        self.clock = time.monotonic
        self.expiry_task = None
        self.expiry_workers = set()

    async def initialize(self):
        # Fail early if the bundled font cannot be loaded.
        await asyncio.to_thread(
            render_board, IdiomGame.create(now=self.clock(), words=self.words)
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

    async def _send(self, event, text, game=None):
        chain = [Plain(text)]
        if game is not None:
            try:
                png = await asyncio.to_thread(render_board, game)
                chain.append(Image.fromBytes(png))
            except Exception:
                logger.exception("猜成语棋盘绘制失败")
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
        # Await delivery inside the scope lock to preserve board order.
        try:
            await asyncio.wait_for(event.send(event.chain_result(chain)), timeout=30)
        except Exception:
            logger.exception("猜成语消息发送失败；不回滚已受理的猜词")

    async def _expire(
        self, scope: Scope, session: Session, *, now: float | None = None
    ) -> bool:
        if not session.game.expire(self.clock() if now is None else now):
            return False
        self.manager.release(scope, session)
        text = f"{session.game.display_name}游戏因 5 分钟没有有效猜词而结束。"
        if isinstance(session.game, IdiomGame):
            text += f"答案：{session.game.answer}"
        try:
            await asyncio.wait_for(
                self.context.send_message(session.origin, MessageChain().message(text)),
                timeout=30,
            )
        except Exception:
            logger.exception("游戏超时通知发送失败，游戏已释放")
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
            game = IdiomGame.create(now=self.clock(), words=self.words)
            self.manager.start(scope, game, event.unified_msg_origin)
            await self._send(
                event,
                "猜成语开始！发送四字汉字猜词，共 10 次机会。\n"
                "汉字、拼音部件和声调分别提示：绿=位置正确，黄=存在但错位，灰=无匹配。\n"
                "群内共同猜题；重复猜测不计次、不续时。"
                "5 分钟没有有效猜词会结束；发送 /猜成语结束 可提前结束。",
                game,
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
            await self._send(
                event, f"本轮已结束。答案：{session.game.answer}", session.game
            )

    @filter.event_message_type(filter.EventMessageType.ALL, priority=0)
    async def on_guess(self, event: AstrMessageEvent):
        text = event.message_str.strip()
        if not is_candidate(text) or any(
            not isinstance(c, Plain) for c in event.get_messages()
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
                message = f"恭喜猜中！共用 {len(game.guesses)} 次。答案：{game.answer}"
            elif game.status == "lost":
                message = f"10 次机会已用完。答案：{game.answer}"
            else:
                message = f"第 {len(game.guesses)}/10 次猜测；请在 5 分钟内继续猜词。"
            await self._send(event, message, game)

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
