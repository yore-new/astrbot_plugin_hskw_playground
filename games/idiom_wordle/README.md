# 猜成语 Wordle 开发说明

## 模块边界

`core.py` 负责初始化、猜词、拼音匹配和状态转换，不导入 AstrBot，不执行消息发送。
`resources/idioms.json` 是从 Handle 源文件生成的 29,760 条成语及数字声调读音。
每局答案从该词库选择；猜测接受任意可解析的四字汉字，不要求属于词库。
词库拼音覆盖自动转换结果；相同汉字采用答案读音，参考 Handle。

## 时间与规则

最多 10 次有效猜测；重复猜测不计次、不续时。`now` 由调用方注入单调时钟。
开局截止时间为 `now + 300`，有效猜测后重新设置为 `now + 300`。
仅有一个空闲截止时间，不设整局上限。到达截止时间的猜测不受理。
超时检查与猜词提交必须使用同一个时间点，避免两次取时跨过截止时间造成误判。
四个汉字完全一致才能获胜；汉字、拼音部件、声调独立给出匹配提示。

## 本地验证

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest games/idiom_wordle/tests -q
```

```python
from games.idiom_wordle.core import IdiomGame

game = IdiomGame.create(now=0, answer="一心一意")
assert game.submit("画蛇添足", now=10) == "accepted"
assert game.deadline == 310
```

## 实现步骤

1. 独立规则与状态，测试重复项、多音字、10 次边界和空闲截止时间。
2. 本地图片与 CLI，检查字体、颜色、尺寸及完整棋盘。
3. 统一游戏管理器与 AstrBot 路由，验证隔离、互斥、超时和卸载。
4. 文档与验收；最后将可复用流程更新至根目录 `AGENTS.md`。

每步测试通过后单独提交。自动化测试替代等待五分钟，不以缩短生产超时来验证。

## 图片与调试入口

`render.py:render_board(game)` 接受游戏对象，返回 PNG 字节，不修改状态。
字体固定使用 `resources/fonts/NotoSansCJKsc-Regular.otf`（SIL OFL 1.1），无需系统中文字体。
`python -m games.idiom_wordle --answer 一心一意 --guess 画蛇添足 --output /tmp/board.png`
可在没有 AstrBot 的环境中生成图片。省略 `--guess` 进入交互模式。
CLI 在输入时检查超时；主动超时通知由插件后台调度实现。

## 插件接入与扩展

根目录 `game_manager.py` 只管理聊天范围及活动游戏，不依赖本游戏。
添加新游戏时创建新的 `games/<game_id>/`，保留本游戏接口边界，注册开始命令前检查统一管理器。
群内任何人可提交猜词和结束游戏，参与者共享次数。
聊天范围由平台实例 ID、群/私聊类型、群 ID 或私聊用户 ID 组成。
不要直接使用可能按群成员拆分的消息会话 ID 作为游戏键；通知路由仍使用 `unified_msg_origin`。

`main.py` 中每个聊天使用异步锁，涵盖判定、绘制及发送，保证棋盘顺序。
后台扫描截止时间，各群独立发送超时通知；回调验证 Session 身份，防止误删新局。
超时通知或图片发送失败会记录异常；已受理猜测不回滚、不再次计次。
绘图失败时提供文字汉字提示，进度继续保留。
活动游戏不持久化，卸载取消后台任务并清空状态。

## 验收清单

- 自动测试：重复字/部件/声调、多音字、同音不同字、10 次边界、截止时间等号边界。
- 时间测试注入 `now` 或时钟，不等待五分钟，不设置第二个整局计时器。
- 图片测试：PNG 可读、1～10 行、结束才公开答案，人工查看真实中文字体和拼音布局。
- 管理器/接入测试：跨平台/跨群/私聊隔离、同群共同猜题、并发开始、旧回调、通知失败与卸载。
- 真实宿主：插件加载、非 @ 群猜词、图片发送、主动超时通知、重载后可重新开始。

当前自动测试使用 AstrBot 替身，不代表真实平台已联调通过。

## 词库同步流程

`resources/handle/` 保存同一上游 commit 的 `idioms.txt` 与 `polyphones.json`，
版本、校验值、作者和许可记录于该目录 `SOURCES.md`。
`update_dictionary.py` 提供独立 Python 转换函数及离线生成入口：

```sh
.venv/bin/python -m games.idiom_wordle.update_dictionary
.venv/bin/python -m pytest games/idiom_wordle/tests -q
```

生成时合并两份互不包含的词库，排序去重，自动生成普通读音，优先采用上游多音字读音，
最后应用 `resources/pronunciation_overrides.json`。缺省声调补为轻声 5。
生成前校验全部词条和读音；错误会中止，不静默删除词条。
默认词库全部参与随机出题，生僻词难度会高于原来的 30 词版本。
普通读音未经逐词人工校对；修正写入覆盖文件后重新生成，避免下一次同步覆盖。
词库更新测试检查全部上游词条均已收录、多音字、轻声以及本地覆盖优先级。
保留上游源文件与许可，记录固定 commit、校验值和生成器依赖版本；从本地快照离线生成，
不要直接修改生成的 `resources/idioms.json`。
