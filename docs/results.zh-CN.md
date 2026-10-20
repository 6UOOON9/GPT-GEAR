# 结果与常见问题

[English](results.md) | **简体中文**

[文档导航](README.zh-CN.md) · [单回合运行](running.zh-CN.md) · [队列评测](queues.zh-CN.md)

回合结束后，先查看汇总，再按需要检查官方结果、录像和日志。模型最后说“完成”或调用 `finish`，都不能替代仿真环境的成功判定。

## 查看汇总

单回合和队列使用同一命令：

```bash
gpt-gear summarize outputs/libero_one
gpt-gear summarize outputs/robotwin_queue
```

命令打印 JSON，包含状态计数、有效回合数、成功率、各环境统计和逐回合记录。队列仅统计每项最新一次尝试。

| 状态 | 含义 | 进入成功率分母 |
|---|---|---|
| `success` | 运行完整、样本有效、官方判定成功 | 是 |
| `task_failure` | 运行完整、样本有效、官方判定失败 | 是 |
| `invalid` | 运行已结束，但不满足有效评测条件 | 否 |
| `runtime_error` | 运行或结果记录不完整，或结果格式不符合要求 | 否 |
| `pending` | 队列中尚未尝试的回合 | 否 |

成功率为 `success / (success + task_failure)`，没有有效回合时为 `null`。比较评测结果时，同时报告无效、运行错误和未执行的数量。

不同环境的原始得分不直接平均。UniVTAC 按触觉模式、RoboTwin 按 Clean / Random 提供额外分组。

## 去哪里找产物

| 文件或目录 | 内容 |
|---|---|
| `result.json` | `sim-result-v1` 结果：任务身份、有效性、官方成功和结束原因 |
| `launcher.json` | 启动器状态及进程退出信息 |
| `official_result.json` | 提供此文件的后端保存的官方判定详情 |
| `observations/` | 已保存的 RGB、状态及启用的其他观测 |
| `history.jsonl` | 控制会话历史 |
| `episode.mp4` / `video.json` | 公共录像及相机顺序、帧数、编码结果 |
| `host.json` | 实际源码版本与模块加载路径；公共仿真入口另记录解释器和依赖版本 |
| `codex_run.json` / `codex_events.jsonl` | 模型启动信息和会话事件 |
| `action_metrics.json` | 可关联的逐动作耗时与用量 |
| `server.log` / `codex_stderr.log` | 仿真与模型侧诊断日志 |
| `session.json` | 本地会话连接信息，含令牌，不应公开 |

RoboDojo 使用仿真目录下原生 `eval_result/` 中的评分与录像，具体路径见结果文件。LIBERO-plus 录像横向并排显示两路相机；RoboTwin 为三路，并用 `video_timeline.jsonl` 记录视频帧、物理时间与原生调用的对应关系。

RoboTwin 录像按实际物理时间以 25 fps 采样，包含初始和末态，不记录模型推理等待时间；编码失败不会发布 `episode.mp4`，已生成的 partial 文件保留，回合按 `runtime_error` 汇总，不进入成功率。其结果文件同时记录未进行专家筛选的标识。

队列产物位于 `<队列目录>/<回合ID>/attempt-0001/`。`attempt-0001.queue.log` 在该目录旁；回合尚未成功创建输出目录时，也可以从这份日志排查。

逐动作 token 无法可靠关联时保留 `null`，不表示用量为零。`host.json` 和模型启动记录有助于复现，但本地输出、资产和认证不随仓库提供。

## 常见问题

### 找不到 `gpt-gear`

确认在仓库根目录激活了 `.venvs/codex-mcp`，或直接使用 `.venvs/codex-mcp/bin/gpt-gear`。安装步骤见 [安装指南](installation.zh-CN.md)。

### `doctor` 通过了，模型仍启动失败

`doctor` 不检查模型认证。查看 `codex_stderr.log`，确认当前系统用户的认证、网络和模型访问权限。默认沿用本机模型配置；覆盖模型时使用 `--codex-model`。

### 找不到布局、任务或 HDF5

RoboDojo 的布局由任务、seed、layout 共同决定；LIBERO-plus 任务写成 `suite/task_id`；UniVTAC 任务名区分大小写。GR1 即使不使用参考也需要 `<任务名>.hdf5` 中的环境配置。按 [环境运行指南](running.zh-CN.md) 核对参数。

### 输出目录已存在

单回合换一个全新的输出路径，不要提前 `mkdir`。续跑队列则使用原配置、原队列输出目录。不要通过删除会话保护文件来继续旧动作。

### 队列计划能打印，执行却失败

计划阶段只解析配置。检查 JSON 路径是否相对配置文件解析，先为对应环境运行 `doctor`，再看回合旁的 `.queue.log`。

### 修改配置后不能续跑

续跑要求保存的队列清单与当前解析结果一致。修改任务、路径、预算或参考等配置后，请使用新的输出目录。有效任务失败不会因 `--retry-failed` 被重新执行；该选项只处理无效或中断回合。

### 仿真就绪超时

先查看 `server.log` 中的资产、渲染、GPU 或依赖错误。如果输出目录尚未创建，检查旁边的 `<输出路径>.server.log` 和 `<输出路径>.launcher.json`。确认只是加载慢后，再增大 `--codex-startup-timeout`。

### 参考校验失败

用 `reference prepare` 单独检查已有文件。常见原因包括缺少视频映射、格式不匹配、摘要不一致、路径越界，或只提供轨迹而未搭配文字或视频。纯文字参考受支持；未提供视频时不能指定 `mode`、`fps`。修正原始文件后使用新输出目录，详见 [参考输入指南](reference-protocol.zh-CN.md)。

### 动作结果不确定，或工具图片交付失败

当前会话会停止后续动作。检查 `status` 与日志；不要重放请求或删除保护文件恢复运动。队列可用 `--retry-failed` 新建尝试，从头开始。

## 分享复现或反馈问题

请提供 benchmark、任务、seed、初始化参数、源码版本、执行命令、汇总结果和相关错误日志。排除 `session.json`、认证信息和无关私人路径；大型录像可单独分享。问题模板需要的信息见 [贡献指南](../CONTRIBUTING.zh-CN.md)。
