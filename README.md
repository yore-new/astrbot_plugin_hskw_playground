# 群聊小游戏 · 猜成语 Wordle

AstrBot 插件。每个群共同玩一局，不同群、平台实例及私聊互不影响。
同一聊天最多有一个活动游戏，后续游戏也使用同一管理器互斥。

## 使用

- `/猜成语`：随机开始一局四字成语游戏。已有游戏时会提示，进度不会重置。
- 直接发送四字汉字：提交猜测，返回包含历史猜测的棋盘图片，最多 10 行。
- `/猜成语结束`：结束当前聊天的猜成语游戏并公布答案，群内任何参与者都可使用。

汉字、拼音声母/韵母、声调分别着色：绿色表示对应位置匹配，黄色表示存在但错位，灰色表示无匹配项。
拼音显示数字声调（5 表示轻声）。汉字完全一致才算猜中。

有效猜测为长度正确、可解析拼音且本轮未提交过的纯汉字消息；不要求属于成语词库。
重复猜测不消耗次数，也不会重置计时。其他长度、命令、图片等消息不作为猜测。
**开局或上一次有效猜词后 5 分钟仍没有有效猜词，本轮自动结束并公布答案。只有一个可重置的空闲截止时间，不设整局时间上限。**

## 安装与运行

需要 Python 3.10+、AstrBot 4.9.2+（5 以下），以及支持图片发送的消息平台。
将仓库安装到 AstrBot 的 `data/plugins/astrbot_plugin_hskw_playground` 下，
使用插件管理页安装依赖、启用或重载插件。第三方依赖见 `requirements.txt`。
群内猜词不要求 @机器人，但平台必须实际将普通群消息投递给 AstrBot。

游戏状态只存内存，机器人重启或插件重载会结束现有游戏。
图片在内存中绘制并发送，不向插件目录写运行时文件。超时通知使用开局消息的路由，
部分平台可能限制主动发送；即使通知失败，游戏仍会结束并释放。
当前自带 Handle 词库的 29,760 条四字成语，包含普通词库与多音字词库。
普通词条由 pypinyin 生成读音，多音字使用上游校正；本地读音覆盖优先。
词库版本、许可及离线更新命令见 [词库来源说明](games/idiom_wordle/resources/handle/SOURCES.md)。

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
遵循 [AstrBot 开发指南](https://docs.astrbot.app/dev/star/plugin-new.html)。
代码沿用仓库 AGPL-3.0 许可，见 [LICENSE](LICENSE)。
随附中文字体来自 [Noto CJK](https://github.com/notofonts/noto-cjk)，
以 SIL Open Font License 1.1 分发，字体版权及许可见
[字体许可](games/idiom_wordle/resources/fonts/OFL.txt)。

## 验证范围

自动化测试覆盖游戏规则、图片、管理器和使用 AstrBot 替身的消息接入契约。
实际 AstrBot 宿主及平台的群消息投递、图片上传、主动超时通知仍需安装后验证。
