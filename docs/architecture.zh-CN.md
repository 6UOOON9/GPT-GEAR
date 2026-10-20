# 架构与开发导览

[English](architecture.md) | **简体中文**

[文档导航](README.zh-CN.md) · [项目概览](project-overview.zh-CN.md) · [贡献指南](../CONTRIBUTING.zh-CN.md)

本文面向希望理解控制流程、修改工具或接入新环境的开发者。先看进程关系与模块职责，再根据需要阅读控制、观测和参考交付。运行命令见 [单回合指南](running.zh-CN.md)。

## 进程如何协作

公共入口为 `gpt-gear`，实现在 `execution.cli`，功能包直接位于 `src/`；命令使用 `--benchmark robodojo|libero-plus|robocasa-gr1|univtac|robotwin`。benchmark 表示所选仿真任务体系，LIBERO 的 suite 则是任务标识 `suite/task_id` 的一部分。

```text
gpt-gear run / queue
  → benchmark registry: preflight → resolve_task → launch_spec
  → selected simulation Python
      → native official environment
      → common Session + DeltaController
      → owner-thread native execute / observe / official result
  → Codex → persistent STDIO MCP → localhost HTTP → Session
```

## 从哪里开始读代码

| 模块 | 主要入口 | 职责 |
|---|---|---|
| 执行 | [launcher.py](../src/execution/launcher.py)、[batch.py](../src/execution/batch.py) | 进程编排与队列 |
| 会话 | [session.py](../src/execution/session.py) | 请求调度、观测保存与回合状态 |
| 控制 | [controller.py](../src/control/controller.py)、[profiles.py](../src/control/profiles.py) | 有界伺服与环境控制能力 |
| 协议 | [mcp_server.py](../src/protocol/mcp_server.py)、[contracts.py](../src/protocol/contracts.py) | 工具服务、能力握手与交付 |
| 感知 | [perception/](../src/perception/) | 标定、深度与观测模态 |
| 环境 | [backends.py](../src/environments/backends.py) | 按环境加载适配 |
| 参考 | [demonstrations/](../src/demonstrations/) | 视频、轨迹、缓存与文字生成 |

包初始化不预加载上述实现，命令分发按需导入，保持仿真依赖与 MCP 依赖隔离。

`execution/config.py` 负责运行参数解析，单回合与队列共用 seed、深度互斥和参考输入校验。
仿真入口直接读取配置模块，不依赖启动器。`execution/artifacts.py` 提供仅依赖标准库的
原子 JSON 写盘；仿真侧显式提供 NumPy 序列化函数。协议 guard 使用 `write_guard`，
在替换文件前同步内容、替换后同步父目录，写入失败继续向上传播。

## 模型工具与结果交付

| 工具 | 作用 | 启用条件 |
|---|---|---|
| `observe` | 读取已保存的当前或历史观测，不推进仿真 | 始终启用 |
| `act` | 基于最新观测执行一个有界动作，返回反馈与新观测 | 始终启用 |
| `status` | 查询会话状态或最终结果 | 始终启用 |
| `finish` | 结束控制，成功仍由环境判定 | 始终启用 |
| `read_reference` | 一次性交付参考图片、文字和完整轨迹 | 配置了参考 |
| `read_depth` | 查询保存观测的测量深度 | GR1 启用测量深度 |

`protocol/tools/` 按工具名称组织 MCP 定义与同步调用适配：`observe`、`act`、`status`、`finish` 始终启用，`read_reference` 和 `read_depth` 随会话能力启用。`rendering.py` 共用反馈裁剪、观测身份与图片校验，参考内容的组装位于 `read_reference.py`。这些模块只由 MCP 进程加载，仿真侧继续通过 `Session` 调度控制器和感知模块。

`protocol/mcp_server.py` 统一串行化工具调用并处理取消、审计和交付确认。各工具通过共享 `ControlClient` 发起请求；动作与结束操作延迟确认交付，等到工作线程完成、取消检查通过且审计写盘后，再由服务入口解除持久化保护。参考首次观测与一次性交付状态也在该公共边界确认。

## 环境适配与进程生命周期

每个环境目录包含 `backend.py`、`simulator.py`、`native.py`、`reference.py` 和环境专属 Prompt。预检与启动配置使用标准库，仿真依赖只在选定的仿真解释器中加载。

`environments/backends.py` 按 benchmark 延迟加载 `environments/<环境>/backend.py`。各环境后端只使用标准库，负责资源定位、任务身份与子进程命令/环境；公共启动参数和参考缓存由 `environments/common.py` 复用。源码与数据路径由公共 CLI 和队列传递。

LIBERO-plus、GR1、UniVTAC 和 RoboTwin 共用 `environments/simulator.py` 的进程生命周期：
预检、环境配置、参考缓存、Session、错误结果和资源关闭由公共入口管理。
backend 声明模块来源和依赖清单；各环境入口通过回调提供原生环境构造、
启动前配置和应用初始化。
SIGINT/SIGTERM 在启动阶段中断，在活动 Session 中设置取消状态。
资源按 Session、native、应用的顺序关闭，即使某一步关闭失败也继续清理，并恢复原信号处理器。
启动失败使用已取得的身份记录原始错误，不再次解析任务。

`Session` 不读取宿主 env 的专用字段，依赖 native 的 `benchmark`、`identity`、`control_profile`、`control_metadata()`、`observe()`、`execute()`、`status()`、`ended()`、`finalize()`、`result()`。宿主接口的调用与结果转换由各环境适配器实现，见 [各环境的适配差异](#各环境的适配差异)。

需要按模型动作计数的适配器可实现 `after_policy_action()`：Session 在一次控制器调用返回后、
保存新观测前调用一次，返回停止原因或 `None`。被拒绝或去重的请求不会触发它。
UniVTAC 通过此回调管理模型动作预算，Session 不读写其内部计数器、终止字段或启动参数。
触觉观测则按 observation profile 声明选择，不在保存层判断环境名称。

## 控制契约与预算

控制协议为 `sim-codex-v1`，能力版本为 `sim-control-v2`，反馈格式为 `compact-arms-v1`。握手绑定 benchmark、控制 profile、观测 profile、测量深度和参考摘要，版本不匹配立即拒绝，旧活动会话不兼容。动作形状是 `action.arms[arm_id]`，所有配置的臂必须显式出现。单臂 robot0 与双臂 left/right 共用有界闭环伺服，位移以米为单位，在能力配置声明的环境坐标系中解释；增量四元数为 wxyz 左乘。每臂可独立完成/到达预算并保持，原生执行仍为一个同步步骤。

夹爪按能力使用连续比例、open/close、米制手指位置或六维手部目标。预算单位和初始化计数规则由后端声明。

米制夹爪范围由控制 profile 的每臂 `gripper_position_limits_m` 声明，
公共控制器和 MCP 参数 schema 从同一配置读取。
完成判定使用 profile 中的 `gripper_tolerance_m`，控制器不导入具体环境的夹爪模块。
范围字段参与完整能力握手，缺失或被修改的配置会被拒绝。

## 观测与标定

相机 RGB 和机器人本体状态通过白名单交付。固定标定只读取一次，移动相机的外参由当前实测本体姿态与固定挂载组合；不提供物体真值。Session 按观测 profile 交付所选模态，MCP 校验图像集合、规格及相关单位和坐标系，历史观测遵循同一契约。普通相机与触觉图像分开标定。官方 wrapper 的视觉扰动保留，不通过另一次渲染绕过。

## 参考输入与缓存

使用方法和数据格式见 [参考输入指南](reference-protocol.zh-CN.md)。

参考缓存为 `sim-reference-v1`，显式绑定 benchmark；五个 benchmark 的轨迹验证器分开，共用视频处理、摘要、路径边界和交付状态机。先成功交付 observe，再一次性 read_reference，然后才允许 act。原始完整轨迹数值不重写。

`demonstrations/reference.py` 只负责 CLI；`media.py` 负责视角扫描、采样、解码和图片校验，
`trajectory.py` 负责环境验证器分发和无损轨迹打包，`cache.py` 负责缓存组装、读取及输出预算。
环境验证器从 `common.py` 复用帧序号、帧数、有限向量和单位四元数校验，动作含义、
夹爪未知值、双臂结构和采样缺口等规则继续由各环境定义。

所有环境的 reference 都由使用者在评测前准备，包括 RoboDojo。视频导出与轨迹生成
在项目之外完成；本项目仅为已有视频提供可选的文字生成。`run` / `queue --run` 仅对已有文件执行校验、视频抽帧、
缓存组装及交付，不调用文字生成器。`reference prepare` 是该缓存流程的
离线预检入口，不负责从原始数据生成示范。

五个环境的文字生成共用 `video_to_steps.py` 与 `prepare_reference_text.py`：
环境 `reference.py` 声明所需相机和可选图片上限，各环境的 `prompts/reference_text.md`
描述视觉标注规则（包括 RoboDojo），生成器按环境加载，不使用公共标注提示词回退；
公共层负责独立视频采样、只读模型调用、编号格式校验、原子发布和审计。
RoboTwin 保留三路相机与合计 42 张图片上限；采样率可由 `--reference-fps` 指定，
默认 1 FPS，实际采样率写入提示词、审计及已有 provenance。

## 故障处理与运行隔离

仅仿真主线程访问环境。请求去重、最新观测校验、持久化 pending/uncertain/delivery guards、超时取消及失败关闭保留。旧活动会话不恢复；队列重试是全新进程和 attempt。输出目录独占，运行错误与官方任务失败分开统计。

动作指标通过参数指纹关联事件与 MCP 耗时。没有指纹的旧日志不再按调用顺序匹配；
无法关联的记录保留为缺失或未匹配项。旧参考参数由命令行解析器按未知参数拒绝。

仿真 Python 与 MCP Python 隔离：核心仿真模块兼容 Python 3.10，MCP SDK 要求 Python 3.11+。LIBERO_CONFIG_PATH、PYTHONPATH 和缓存只作用于子进程，不改变全局配置或 editable 安装。

## 各环境的适配差异

以下按环境说明宿主接口、动作转换和观测差异。启动、控制契约与交付机制见前面的公共章节。

### RoboDojo

RoboDojo 使用原版工厂和 `run_eval`，临时引用替换在创建环境后恢复，控制方法只绑定当前实例，不修改宿主源码。动作通过原生 IK 和 `take_action` 执行，`result(eval_result)` 包装原生评分。布局与运行选项见 [RoboDojo 环境配置](environments/robodojo.zh-CN.md)。

### LIBERO-plus

LIBERO-plus 调用原版 `OffScreenRenderEnv`、`set_init_state`、`step` 和 `check_success`，不修改宿主源码。`prepare_environment` 在导入宿主模块前生成回合专属 `libero_config/config.yaml`，并从预检身份中取得 suite/task_id。

动作按 `OSC_POSE` 的实际输入/输出范围反解缩放，控制点为真实 grip site；初始化步骤计入原生步预算。`result()` 包装 `check_success` 和录像。任务与初始化选项见 [LIBERO-plus 环境配置](environments/libero-plus.zh-CN.md)。

### RoboCasa GR1

入口为 `environments.robocasa_gr1.simulator`，从 HDF5 的 `env_args` 读取环境配置。GR1 在公共 servo 中按能力选择 `reference_trajectory`，推进独立于测量滞后的参考目标；native 将同步双臂世界坐标目标转换成原生 absolute/base IK 动作。每臂可选 `hand` 是六个原始弧度目标，已停止的臂保留最近目标。

GR1 默认保存 RGB 对齐测量深度，开启测量深度时关闭模型深度估计声明，两者互斥。`read_depth` 只读取带摘要的保存帧，用同份观测的内外参反投影，不刷新相机或物理时间；其他环境不提供测量深度。头部相机外参由当前本体姿态组合。运行与深度选项见 [GR1 环境配置](environments/robocasa-gr1.zh-CN.md)。

### UniVTAC

入口为 `environments.univtac.simulator`，在导入任务前启动 Isaac Lab。动作使用 robot_base 坐标系、必填的 `robot0.gripper_position_m` 和 gripper-center DLS；手指目标限速为每物理步 0.0005 m，范围复用控制 profile 中的 `gripper_position_limits_m`。完成判定同时检查位姿与实测夹爪误差，控制循环、物理 tick 与模型动作分别记账。

四种触觉模式只改变公开输入，内部触觉更新保留。图像与合力独立选择，无合力模式不要求 UIPC `contact_gradient` 接口。腕部相机外参由当前本体姿态组合。运行与触觉选项见 [UniVTAC 环境配置](environments/univtac.zh-CN.md)。

### RoboTwin

RoboTwin 的 backend 通过所选仿真 Python 检查 YAML、基础依赖与录像编码器。任务按宿主名称查找，clean/random 映射原生配置并参与回合身份；不采用原包的排序任务编号、专家筛选或有效名额调度。

native 将每个活动臂的增量转为绝对 EE 位姿，保持未活动臂的实测位姿及最近夹爪目标，以一个 16 维双臂向量调用 take_action(ee)。调用次数与物理步数分别计数；计数异常或执行中断令回合不确定并停止。规划失败作为已执行调用的反馈保留。成功由 eval_success 或 check_success 判定，finish 不改写成功。

观测为 head_camera / left_camera / right_camera 与本体状态，采用公共固定标定和腕部外参组合。录像在实例 scene.step 后按物理时间采样 RGB，编码和产物收尾复用 EpisodeVideo；退出时恢复实例钩子。参考使用独立 RoboTwin 轨迹验证器，保留完整源数值及未知夹爪命令，缓存与一次性交付仍由公共层负责。环境选项见 [RoboTwin 环境配置](environments/robotwin.zh-CN.md)，接口检查见 [运行指南](running.zh-CN.md#无模型接口检查)。

## Prompt 如何组装

`prompts.evaluation_prompt` 使用包资源读取公共规则和 `environments/<环境>/prompts/` 下的专属规则。所有环境都有独立的 `control.md`；GR1 额外保存 `measured_depth.md`。公共 Prompt 不再列举其他环境的夹爪语义，深度估计声明按实际配置的机械臂集合约束。能力 JSON、参考开关和深度开关继续随回合配置生成；启动器保存最终文本并计算摘要。wheel 同时包含公共与环境专属 Prompt，读取不依赖工作目录。

## 接入新环境的建议顺序

先定义任务身份、控制与观测能力，再实现原生适配并接入公共生命周期。通过离线契约测试后，在真实仿真中检查观测、保持动作和资源关闭，最后运行固定初始条件的模型回合。需要提供的测试与复现信息见 [贡献指南](../CONTRIBUTING.zh-CN.md)。
