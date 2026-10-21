# RoboDojo 环境配置

[English](robodojo.md) | **简体中文**

[文档导航](../README.zh-CN.md) · [安装](../installation.zh-CN.md) · [单回合命令](../running.zh-CN.md#robodojo) · [队列评测](../queues.zh-CN.md)

RoboDojo 提供双臂操作、三视角 RGB 和按 seed / layout 选择的评测场景。本页说明源码、布局和评测选项；公共运行流程见 [运行指南](../running.zh-CN.md)。

## 源码与资产

使用已安装的 RoboDojo 源码与配套仿真 Python，准备好子模块和 `Assets`。`--env-root` 指向 RoboDojo 目录，任务需要对应的评测布局：

```text
Assets/Eval_Layout/RoboDojo/arx_x5/<seed>/<task>_<layout_id>.json
```

`seed` 和 `layout_id` 共同选择初始场景；布局缺失时预检会报错。仿真使用已有解释器与依赖，可使用已准备好的 Python 3.11 环境。

## 任务与观测选项

| 参数或能力 | 默认值与语义 |
|---|---|
| 任务 | 宿主任务名，如 `align_blocks`，需有对应评测布局 |
| 初始化 | `--seed 0 --layout-id 0` |
| 观测 | head / left_wrist / right_wrist RGB 与双臂状态 |
| 预算与结果 | 使用宿主原生执行预算、评分与录像 |
| 深度 | 默认开启模型深度估计声明；`--depth-estimation false` 关闭，不提供测量深度 |

RoboDojo 不接受 `--init-state-index` 或 `--max-native-steps`。先运行公共 `doctor` 预检，再按 [单回合命令](../running.zh-CN.md#robodojo) 验证实际运行；当前不提供公共 `--smoke` 入口。

## 参考与评测配置

参考文件需在评测前准备。轨迹格式为 `robodojo-codex-trajectory-v1`，使用双臂 `left_ee` / `right_ee` 语义；轨迹与视频格式见 [上下文学习指南](../reference-protocol.zh-CN.md#robodojo)，文字生成见 [视频文字教程](../reference-format.zh-CN.md)。

[单任务配置](../../configs/single_task/robodojo.json) 使用 `align_blocks`、seed 0、layout 0。[队列配置](../../configs/queues/robodojo.json) 包含 42 个任务，使用 seed 0、layout 9，其中 34 个带参考；运行前需修改环境路径及参考路径。执行与续跑步骤见 [队列指南](../queues.zh-CN.md)。
