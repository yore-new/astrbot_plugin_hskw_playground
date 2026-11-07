# Handle 词库来源

- 上游：https://github.com/antfu/handle
- 固定版本：`2003b777f507ed18c1c80304fd6894280c56ad58`
- 同步日期：2026-11-07
- 作者：Anthony Fu；许可：MIT，见 `../../LICENSE.Handle`。
- `idioms.txt`：26,359 条普通成语；`polyphones.json`：3,401 条独立多音字成语。
- 两份源文件按上游原样保存，合并后共 29,760 条，全部为四字汉字。

源文件 SHA-256：

- `idioms.txt`: `ed8ca4bbc5c667116df9d9088b1851ae0c696e5fddb7d1ad987df35fc50af792`
- `polyphones.json`: `03fdbdb60d209b2e670d8975017d61c2265ba113cec07397ff01c378cff6c086`

使用 pypinyin 0.55.0 为普通成语生成数字声调拼音；多音字优先使用上游读音，
省略声调标号时补为轻声 5。本地 `../pronunciation_overrides.json` 优先级最高。
普通成语的自动生成读音未经逐条人工校对；发现问题时添加本地覆盖。

从仓库根目录重新生成（无需网络，也不启动 AstrBot）：

```sh
.venv/bin/python -m games.idiom_wordle.update_dictionary
```

后续同步时，从同一上游 commit 更新两份源文件，更新本说明的版本和校验值，
然后重新生成并运行测试。不要直接修改生成的 `../idioms.json`。
