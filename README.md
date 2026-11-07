# 群聊小游戏 · 猜成语 Wordle

AstrBot 插件。每个群共同玩一局，不同群、平台实例及私聊互不影响。
同一聊天最多有一个活动游戏，后续游戏也使用同一管理器互斥。

## 使用

- `/猜成语`：随机开始一局四字成语游戏，仅发送开局说明，不发送空图。已有游戏时会提示，进度不会重置。
- 直接发送四字成语：提交猜测，返回包含历史猜测的棋盘图片，最多 10 次猜测。
- `/猜成语提示`：汇总历史中位置正确的汉字和拼音，未知部分显示 `?`，不消耗次数、不重置计时。
- `/猜成语结束`：结束当前聊天的猜成语游戏并公布答案，群内任何参与者都可使用。

汉字、拼音声母/韵母、声调分别着色：绿色表示对应位置匹配，黄色表示存在但错位，灰色表示无匹配项。
声调使用拼音右上角的 1–5 表示（如 `hua⁴`），5 表示轻声，未知声调用 `?` 占位。汉字完全一致才算猜中。
图片采用淡黄色背景、淡灰色字框与清晰的绿色反馈，拼音和声调放大显示。
棋盘只保留方框、汉字和拼音；规则在开局时通过独立文字消息说明。
普通猜测与提示命令只发图；所有图片独立成条，避免文字挤占图片预览。
群聊猜中时会 @ 猜中者并简短祝贺，再发送终局图片。
主动结束、超时或 10 次未猜中时，历史猜测下方追加一行全绿答案（图片最多 11 行）；
猜中时不重复追加正确行。所有结束路径都通过图片展示答案，文字仅说明结束原因；
图片生成失败时会提示失败，不通过文字公布答案。

有效猜测为词库已收录、长度正确且本轮未提交过的四字成语。
同长度且全是汉字的输入未被词库识别为成语时回复“xxxx 不是成语呢~”，不消耗次数，也不重置计时。
重复猜测同样不计次、不续时。长度不一致或包含非汉字时直接忽略，不提示；其他命令、图片等消息不作为猜测。
**开局或上一次有效猜词后超过配置的间隔（默认 300 秒）仍无有效猜词，本轮自动结束并公布答案。只有一个可重置的空闲截止时间，不设整局时间上限。**

## 安装与运行

需要 Python 3.10+、AstrBot 4.9.2+（5 以下），以及支持图片发送的消息平台。
将仓库安装到 AstrBot 的 `data/plugins/astrbot_plugin_hskw_playground` 下，
使用插件管理页安装依赖、启用或重载插件。第三方依赖见 `requirements.txt`。
群内猜词不要求 @机器人，但平台必须实际将普通群消息投递给 AstrBot。

游戏状态只存内存，机器人重启或插件重载会结束现有游戏。
图片在内存中绘制并发送，不向插件目录写运行时文件。超时通知使用开局消息的路由，
部分平台可能限制主动发送；即使通知失败，游戏仍会结束并释放。
随机出题使用 1,415 条经过高频与人工筛选的常用成语，避免抽到大量偏门词。
猜测校验保留 Handle 词库的 29,760 条四字成语，包含普通词库与多音字词库。
普通词条由 pypinyin 生成读音，多音字使用上游校正；本地读音覆盖优先。
词库版本、许可及离线更新命令见 [完整词库来源](games/idiom_wordle/resources/handle/SOURCES.md)
及 [常用出题池来源](games/idiom_wordle/resources/chinese_wordle/SOURCES.md)。

## 插件配置

在 AstrBot WebUI 的插件配置中设置“猜成语有效猜词间隔（秒）”
（`idiom_idle_timeout_seconds`），默认 `300`，支持正数与小数，如 `150` 或 `2.5`。
无效值回退为 300 秒。每局开局时读取设置，修改后对新局生效；重载会结束当前游戏。
提示命令、非成语、重复猜测和长度不符的消息都不会重置计时。

## 本地开发与调试

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

不需要安装或启动 AstrBot 即可测试游戏初始化、猜词及图片生成：

```sh
.venv/bin/python -m games.idiom_wordle --answer 一心一意
.venv/bin/python -m games.idiom_wordle --answer 一心一意 --guess 画蛇添足 --guess 一心一意 --output /tmp/idiom-wordle.png
```

交互 CLI 用于本地规则/图片调试，输入返回时检查空闲截止时间；机器人中的后台任务会主动结束超时游戏。
详见 [游戏开发文档](games/idiom_wordle/README.md)。

## 来源与许可

游戏设计及拼音匹配规则参考 [汉兜 Handle / Anthony Fu](https://github.com/antfu/handle)
及 [在线游戏](https://handle.antfu.me/)。拼音判定按 Handle 的算法移植为 Python，保留 [原始 MIT 许可](games/idiom_wordle/LICENSE.Handle)；成语及多音字数据也来自 Handle，保留同一 MIT 许可。
出题池参考 [AllanChain/chinese-wordle](https://github.com/AllanChain/chinese-wordle)，
来源项目采用 BSD-3-Clause，保留 [原始许可](games/idiom_wordle/LICENSE.ChineseWordle)。
遵循 [AstrBot 开发指南](https://docs.astrbot.app/dev/star/plugin-new.html)。
代码沿用仓库 AGPL-3.0 许可，见 [LICENSE](LICENSE)。
随附中文字体来自 [Noto CJK](https://github.com/notofonts/noto-cjk)，
以 SIL Open Font License 1.1 分发，字体版权及许可见
[字体许可](games/idiom_wordle/resources/fonts/OFL.txt)。

## 验证范围

自动化测试覆盖游戏规则、图片、管理器和使用 AstrBot 替身的消息接入契约。
实际 AstrBot 宿主及平台的群消息投递、图片上传、主动超时通知仍需安装后验证。
