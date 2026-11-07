# 常用出题池来源

- 上游：https://github.com/AllanChain/chinese-wordle
- 固定版本：`6838dde35e795ed8b81fa705d240c7f570d9d1a1`
- 来源文件：`src/assets/freq-idioms.json`，原样保存，共 1,416 条。
- 同步日期：2026-11-07
- SHA-256：`8d5d143dbc9ccecbcae68a486dd0657d7f683dadc5279732f3c313a4cb4822c8`
- 作者：Allan Chain；BSD-3-Clause 许可见 `../../LICENSE.ChineseWordle`。

上游根据 THUOCL 成语词频表及高考成语人工筛选，用独立的高频列表随机出题，
完整成语词库用于验证输入。筛选过程见上游 `data/process_idioms.py` 和 `data/reviewed.txt`。

本插件取高频列表与现有 Handle 词库的交集，生成 `../answers.json`，共 1,415 条。
仅 `追根溯源` 未在当前 Handle 词库中收录，因此不参与出题。
普通词库与多音字读音仍来自 Handle，本地读音覆盖继续生效。

从仓库根目录离线重新生成：

```sh
.venv/bin/python -m games.idiom_wordle.update_dictionary
```

后续更新应保存同一固定版本的源列表与许可，更新版本和校验值，再重新生成和测试。
不要直接编辑生成的 `../answers.json`。
