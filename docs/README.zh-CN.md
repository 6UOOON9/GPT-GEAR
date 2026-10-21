# 文档导航

[English](README.md) | **简体中文**

[返回项目首页](../README.zh-CN.md)

第一次使用 GPT-GEAR，建议从安装和一个无参考任务开始；跑通后，再加入队列或参考示范。文档提供英文与简体中文版本，可通过每篇标题下方的链接切换；命令、参数和数据字段保留代码中的名称。

推荐阅读顺序：[安装](installation.zh-CN.md) → [运行一个任务](running.zh-CN.md) → [查看结果](results.zh-CN.md)。只需阅读你所用环境的配置与命令。

所有命令默认在仓库根目录、已激活工具环境的终端中执行。`/path/to/...` 是需替换的本机路径；单回合 `run` 使用全新输出目录，队列可按原配置续跑。

## 开始使用

| 文档 | 你会完成什么 |
|---|---|
| [安装与环境准备](installation.zh-CN.md) | 安装工具，准备仿真依赖与独立解释器 |
| [运行第一个任务](running.zh-CN.md) | 选择一个环境，检查并启动单回合任务 |
| [结果与常见问题](results.zh-CN.md) | 读取官方结果、定位日志、排查启动问题 |
| [队列与批量评测](queues.zh-CN.md) | 跑通单回合后，编写配置、检查计划、执行和续跑 |
| [项目概览](project-overview.zh-CN.md) | 按需了解模型、工具、控制器和仿真环境各自的作用 |

## 参考示范（可选）

| 文档 | 适用场景 |
|---|---|
| [参考输入与格式协议](reference-protocol.zh-CN.md) | 将视频、轨迹和文字加入评测，或编写格式转换工具 |
| [从视频生成文字步骤](reference-format.zh-CN.md) | 已有示范视频，希望生成可读的操作描述；已有文字时可跳过 |

## 环境配置

所有支持的环境使用相同的安装、运行和队列流程。环境专属文档集中在 `environments/`，说明对应环境的源码、资产、专属选项和评测差异。

| 环境 | 专属配置 |
|---|---|
| [RoboDojo](environments/robodojo.zh-CN.md) | 子模块与评测布局、seed / layout 选择 |
| [LIBERO-plus](environments/libero-plus.zh-CN.md) | 任务变体、初始化状态与原生步预算 |
| [LIBERO-GeoMotion](environments/libero-geomotion.zh-CN.md) | 固定几何场景、初始化与参考示范 |
| [RoboCasa GR1](environments/robocasa-gr1.zh-CN.md) | HDF5 环境配置、双臂操作与测量深度 |
| [UniVTAC](environments/univtac.zh-CN.md) | 触觉模式、连续夹爪与控制步频 |
| [RoboTwin](environments/robotwin.zh-CN.md) | Clean / Random 场景、双臂操作与样本选择 |

## 开发参考（可选）

运行任务无需阅读以下文档；修改实现或提交贡献时再查阅。

| 文档 | 内容 |
|---|---|
| [架构说明](architecture.zh-CN.md) | 进程、模块、工具交付、控制与环境适配 |
| [贡献指南](../CONTRIBUTING.zh-CN.md) | 提交问题、运行测试、修改文档和接入环境 |
