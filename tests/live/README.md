# tests/live — 实机验证脚本

这里的脚本**不是 pytest 测试**（文件名故意不匹配 `test_*.py` / `*_test.py`，pytest
收集不到它们）：它们会拉起真实的 MCP 服务进程和真实的 Aseprite 可执行文件，输出
pass/fail 报告并用退出码表态。`pytest` 本身保持快速且不依赖 Aseprite；需要实机证据时
手动跑这些。

```bash
# Windows：先告诉脚本 Aseprite 在哪（也支持 PATH / 常见安装位置的自动探测）
set ASEPRITE_PATH=D:\path\to\aseprite.exe

python tests/live/probe_server_version.py       # 仓库这份代码行为对不对？
python tests/live/live_smoke.py                 # 默认跑 core
python tests/live/live_smoke.py bounds gates runlua
python tests/live/live_smoke.py --all           # 全套（含大画布计时，约 1 分钟）
python tests/live/ws_probe.py                   # WebSocket 桥接四段
```

中间产物在 `.build/`（已 gitignore）。

## 为什么需要它们

pytest 里的 e2e 只覆盖"服务能跑通一条真实链路"；而这一轮修复涉及的很多契约是
**只有在真实 Aseprite 上才暴露**的：越界绘制被静默丢弃、`atomic=false` 全量回滚、
工作目录外 `paint_grid` 的门闩、失败批次的画布回滚、大画布洪泛填充超时。上面两个脚本
把这些契约逐条变成断言，而不是靠"没报错"当通过。

## 三个脚本各管什么

| 脚本 | 覆盖 |
| --- | --- |
| `probe_server_version.py` | 4 条最小断言：越界报错、`atomic=false` 部分成功、干净批次零警告、`paint_grid` 门闩 |
| `live_smoke.py` | 8 个场景：`core`（信封字段 + inspect 指标 + undo/redo）、`codegen`（原子 / 部分成功）、`atomic_rollback`、`bounds`、`gates`、`animation`、`runlua`（快照回滚）、`perf`（2048/4096 大画布计时预算） |
| `ws_probe.py` | 桥接协议 4 段：畸形响应不挂死、模拟扩展端到端（真实 `aseprite -b` 执行脚本）、无扩展时报错质量、ws 端口被占时回落 CLI |

## 已知边界

- 无头 `aseprite -b` **完全没有撤销历史**（`app.command.Undo()` 是静默空操作），
  所以 `live_smoke.py` 里的 undo/redo 只校验 CLI 模式下的文件快照语义；
  原生多级撤销只能在 GUI Aseprite + Live 模式下人工点验。
- `ws_probe.py` 用**模拟扩展**（一个假 ws 客户端，收到脚本后用真实 `aseprite -b` 跑），
  因为真实 `extension/main.lua` 需要 GUI Aseprite 会话。扩展侧 Lua 行为目前只有代码评审覆盖。
- `perf` 的预算是"抓数量级回归"用的宽松上限，不是性能 SLA。
- 4096x4096 整幅洪泛填充实测约 20s（Lua 逐行扫描，线性但不快），而默认
  `ASEPRITE_TIMEOUT` 是 30s —— 要在最大画布上做整幅填充，得先把超时调大。