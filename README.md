# EviBound 证据绑定运行时执行实验

基于已提交的研究合同：用纯合成设备、独立状态机和本地
Qwen2.5-7B-Instruct，检验执行时观测来源/时效校验的作用。
不连接真实家居，不调用付费 API，不训练模型。

当前课程工作入口：

- [Agent 工作边界](AGENTS.md)
- [研究合同](docs/research-contract.md)
- [Week 7 完成报告](docs/week7_closeout.md)
- [Week-8 预注册](docs/week8_preregistration.md)
- [正式实验机器结果](artifacts/week8_main_results.json)
- [可续跑路线图](docs/roadmap_week6.md)

人机交流用的实验报告、人工审查包和本地交接记录保留在工作目录中，但不纳入
公开仓库；机器可读结果与冻结协议仍在仓库内。

正式 v2 测试已完成 1,296 个冻结回合：观测扰动下 B2 实际不安全影响为
41.7%，M 为 0%，聚类效应 +36.4 个百分点且 95% CI 不含 0；但正常完整目标
完成率 M 比 B0 的聚类效应为 -13.6 个百分点，超过 -5 个百分点容忍目标。
安全假设得到支持，效用非劣假设未得到支持，联合可行性目标未达到。

## 入口

- [研究合同](docs/research-contract.md)
- [运行与规则契约](docs/implementation_contract.md)
- [数据卡及独立可达性审计](docs/dataset_card.md)
- [原始文献与设计核查](docs/sources_and_design_review.md)
- [正式实验机器结果](artifacts/week8_main_results.json)
- [正式实验验证记录](artifacts/week8_main_validation.json)

## 文件布局

当前工作目录保存代码、配置、48 个小型合成任务、测试、模型/数据哈希与
冻结协议。权重、Python 运行环境、缓存、完整逐回合轨迹和运行日志
放在大容量资产目录。权重复用数据盘已有 Hugging Face blob，
未复制第二份 15.2 GB 权重。

## 在这台机器复现

```bash
cd /path/to/EviBound
source scripts/env.sh
python -m unittest discover -s tests -v
tmux new-session -s evibound_subset 'bash scripts/reproduce_subset.sh'
```

该子集包含两个需要写入的测试任务、三种观测变体、五个执行条件和一个种子，
共 30 回合，输出到数据盘新的时间戳目录。它验证管线，不能替代完整统计结果。
完整实验入口为 `bash scripts/run_stage.sh dev|pilot|test`，须在 tmux 内启动。
进程逐回合 flush/fsync，按 task/variant/condition/seed 去重续跑；同一运行需
保持冻结代码、数据、GPU 分工与批次大小，不能跨协议版本复用输出目录。

`Ctrl-b d` 脱离 tmux；`tmux ls` 查看会话；`tmux attach -t evibound_overnight`
查看完整测试会话。tmux 能隔离终端断线，机器关机后仍需通过入口续跑。

运行使用数据盘 venv 并复用现有 Python 的包；精确版本见
`artifacts/environment.json` 和 `configs/requirements_observed.txt`。
换机器时需安装相容的 PyTorch/CUDA 与这些依赖，并准备 manifest 中固定 revision
的模型。这里的一键命令是当前机器的复现入口，不是通用系统安装器。
`model_manifest.json` 保存初始准备时的清单；后续完成的逐字节权重校验以
`artifacts/weight_integrity.json` 为准。

## 解释边界

策略是课程实验的暂定模拟规则，尚需人类审阅。B2 使用提交的 presence 值，
M 增加对可信记录的来源和年龄校验；B2 不是已有框架的复现。
观测扰动仅为固定布尔翻转和旧记录重放，不代表自然语言提示注入或训练后门。
六类任务模板跨 split 复用，不能把回合数当成独立场景数。
