"""Run `python -m games.idiom_wordle` without installing AstrBot."""

import argparse
import time
from pathlib import Path

from .core import IdiomGame
from .render import render_board


def main():
    parser = argparse.ArgumentParser(description="本地猜成语；输入 /猜成语结束 退出")
    parser.add_argument("--answer", help="指定词库中的答案用于调试")
    parser.add_argument("--output", type=Path, default=Path("/tmp/idiom-wordle.png"))
    parser.add_argument("--guess", action="append", help="非交互猜测，可重复传入")
    args = parser.parse_args()
    game = IdiomGame.create(now=time.monotonic(), answer=args.answer)
    args.output.write_bytes(render_board(game))
    print(f"游戏已开始，棋盘：{args.output}")
    if args.guess is not None:
        for text in args.guess:
            print(text, game.submit(text, now=time.monotonic()))
        args.output.write_bytes(render_board(game))
        print(game.status)
        return
    while game.status == "playing":
        try:
            text = input("猜词 > ").strip()
        except (EOFError, KeyboardInterrupt):
            game.stop()
            break
        if text == "/猜成语结束":
            game.stop()
        else:
            print(game.submit(text, now=time.monotonic()))
        args.output.write_bytes(render_board(game))
        print(f"{game.status} · {args.output}")
    print(f"答案：{game.answer}")


if __name__ == "__main__":
    main()
