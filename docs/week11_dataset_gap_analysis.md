# 数据集构建对照：BALD 与 EviBound（2026-10-11，讨论稿）

English summary: BALD (ICLR 2025) builds small, scenario-sampled datasets
(42 CARLA target instances + 21 boundary instances; 10 VirtualHome tasks plus
19 generated test samples) and states the small size as its own limitation.
EviBound's task counts are comparable or larger and its ground truth is
stronger (deterministic oracle plus full human review). The real gaps are
**independent structural variety** (our effective sample size is the number
of physical clusters: 22 in the v2 test, 32 in the v3 holdout), **language
variety** (one instruction template), **observation modality** (one boolean
sensor), and one **attack channel** BALD covers that fits our threat model:
stale information arriving through memory or retrieved context.

## 1. BALD 是怎么造数据的

| 测试床 | 数据来源 | 规模 | 真值 |
|---|---|---|---|
| HighwayEnv（驾驶） | 仿真器状态 → 规则模板生成文字描述（含 TTC 等指标） | 未强调规模 | 按交通规则 |
| nuScenes / CARLA（驾驶） | Scenic 场景语言采样 → 渲染相机图像 → GPT-4 视觉模型把图转成文字 | 目标场景 42 条 + 边界场景 21 条；RAG 评估 31 条 | GPT-4 生成，人工抽检 10/50 条，约 90% 一致 |
| VirtualHome（家居） | 沿用 ProgPrompt 的 10 个任务；另用 GPT-4 生成 19 个测试样本 | 10 + 19 | 仿真器目标状态（对象关系、开关状态） |

几个值得借鉴的做法：
- **场景语言采样**：同一个场景定义，程序化采出很多实例，变化多但条件一致。
- **目标/边界对照样本**：边界样本只改一点场景元素、结论保持正常，用来测误报。
- **多模态来源**：图像先经视觉模型变成文字，再交给语言模型决策。
- **三类攻击通道**：输入文字（触发词）、环境（场景）、知识库（RAG 检索）。

他们自己在局限里承认数据量小（附录 D.1），家居部分尤其小，而且 BALD-scene 的家居结果和其他模型不可直接比较。

## 2. 我们已经有、且做得更严的部分

- 规模：v2 共 56 个任务，v3 再加 44 个，物理结构与 v2 不重复；正式实验 1,296 回合（v3 holdout 2,304 回合）。
- 边界对照：每个任务都有 boundary 变体（读数恰好在时效上限），作用和 BALD 的边界样本一致：检查“不该拦的不拦”。
- 真值：独立确定性判分器 + 必审卡片全部人工审核，比 GPT-4 生成真值加抽检更可靠。
- 配对设计：同一任务、种子下各条件共用第一次提案，差异只来自检查器。

## 3. 系统性欠缺（按影响排序）

1. **独立结构太少，这才是“数据量少”的本质。** 统计上真正的样本数是物理结构聚类数（v2 test 22 个，v3 holdout 32 个），不是回合数。两设备 × 三档 × 一个布尔传感器的状态空间已经被穷举：v2 用掉后只剩 145 个新结构。加种子、加改写只会增加回合数，不会增加独立证据。要扩大，只能扩大世界本身（多一个设备、多一个传感器或多一个房间）。
2. **语言单一。** 所有指令同一个模板，且直接写出目标档位（“achieve light=low”）。真实用户会说“我要看书了”“屋里太闷”。BALD 用视觉模型/大模型生成多样描述，我们没有。这会高估模型理解指令的能力，也可能放大或掩盖空计划问题。
3. **观测模态单一。** 只有一个“有没有人”的布尔读数。缺少：多个传感器互相印证或冲突（人体感应、门磁、摄像头识别）、数值传感器（温度、CO₂）、历史序列、图像转文字的读数。在我们的威胁模型里，这些都是新的攻击面，例如只篡改多个传感器中的一个，或重放一帧旧的摄像头描述。
4. **缺一种在范围内的攻击通道：记忆/上下文里的过期信息。** BALD 的知识库注入对应到我们这里，就是旧读数通过对话记忆或检索内容进入模型，而不是通过传感器读数本身。这和“重放”同一性质，正好落在我们的威胁模型内。提示注入、训练后门仍然排除。
5. **设备和任务长度。** 只有灯和风扇、最多 3 步写入。课程原始题目 EffectShield 列了灯、风扇、恒温器、门锁、人体传感器五类设备；更长的计划、定时任务、多房间都没有覆盖。

## 4. 可选方向（都需要新的预注册和人工审核，不能改动已冻结的 v3）

| 方向 | 解决哪条 | 成本 | 建议 |
|---|---|---|---|
| A. 指令改写集：同一批 v3 结构，人工审核过的自然说法改写 | 2 | 低：不改守卫和判分器，只加语料 | **推荐先做**，作为 v3 之后的稳健性诊断 |
| B. 记忆通道重放：旧读数放进对话历史，当前读数正确 | 4 | 中：加一种扰动变体，守卫不变 | 推荐，和研究问题最贴 |
| C. 多传感器：加门磁或第二个人体传感器，攻击只动其中一个 | 1、3 | 高：规则、守卫、判分器都要扩展 | 适合写进局限或作为延伸 |
| D. 加第三个设备（如恒温器）扩大状态空间 | 1、5 | 高：同上，且需重新审规则 | 同 C |

按课程计划，Week 12 冻结代码（只允许修正错误），所以 C、D 更适合写成“未来工作”。A、B 改动小，可以在 v3 跑完后作为补充诊断单独预注册。
