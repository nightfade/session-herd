# session-herd

把同时开着的 Claude Code / Codex session 按话题管起来。

终端里开着十几个 agent session 时，累的不是窗口多，而是每个 session 最后都要排队等同一个人去审、去答、去批。session-herd 让这条队列变短、看得见：

- **一个话题一个 tab。** 话题有固定的家：目录、入口文档、交接文件。tab 用完就关。
- **用交接代替悬着的事。** 切走前 `/park` 写三行：现在在哪、下一步、悬着的问题。下次打开这个话题，新 session 三十秒就能接上。
- **看板告诉你谁在等你。** 每个 session 显示为「等你批」「该你了」或「在跑」，等你的排在最前面。
- **一个 agent 帮你管看板。** 在一个 Claude session 里输入 `/herd`，它就成了总管：出看板、建议先处理哪个、让闲着的 session 交接并关掉、帮你收工。

不只适合写代码，投资笔记、日记、语言练习、照片点评这类话题一样适用。

[English](README.md) · [方法论](docs/methodology.md)

## 安装

需要 macOS 上的 iTerm2，并在设置里打开 Python API（Settings → General → Magic → Enable Python API）。tmux 支持在计划中。

```bash
uv tool install git+https://github.com/nightfade/session-herd
herd init --root ~/WorkSpace --language zh   # 所有 session 都从这个目录启动
herd install                                 # 装上状态 hook 和 /park、/herd 两个 skill
```

`herd install` 会把 hook 合并进 `~/.claude/settings.json` 和 `~/.codex/hooks.json`，改之前先备份，并把 skill 链接到 `~/.claude/skills` 和 `~/.codex/skills`。升级后重新运行一次即可，`herd uninstall` 撤掉它加的全部内容。

## 日常用法

| 要做的事 | 命令 |
|---|---|
| 看有哪些话题 | `herd topics` |
| 打开话题 | `herd open invest`。已开着就跳过去，没开就新开一个带颜色和角标的 tab，读入口文档、接上次的交接 |
| 同一话题开第二条线 | `herd open api auth-refactor`，或加 `--new` |
| 看所有 session | `herd status` |
| 加话题 | `herd add garden --label 园艺 --dir notes/garden --kind think` |
| 离开一个 session | 在里面输入 `/park`，然后关 tab |
| 总管 | `herd open herd`，或在任意 Claude session 里输入 `/herd` |

建议配一个简写：`alias t='herd open'`。

### 对总管说的话

| 说法 | 总管做什么 |
|---|---|
| 现在什么情况 | 出看板：话题、状态和持续多久、在做什么、建议 |
| 跳到 X ／ 开 X | 切到或打开那个话题 |
| 收尾 | 给闲着的 session 发 `/park`，等交接完，问要不要关 |
| 给 X 说…… | 把你的原话转给一个「该你了」的 session |
| 收工 | 收尾，写当天汇总，问要不要关掉剩下的窗口 |

## 话题注册表

唯一需要手改的文件是 `~/.config/session-herd/topics.toml`，字段说明见 [README.md](README.md#the-topic-registry) 和 [examples/topics.toml](examples/topics.toml)。

两个要点：

- `language = "zh"`：命令行输出、开场白和交接标签都会变成中文。
- `kind`：区分 think（要你思考的话题，一次只开一个）和 exec（agent 自己干活，可以并行）。

## 许可

MIT
