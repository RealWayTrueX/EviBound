# Threat Model in the Real World / 威胁模型的现实对应

Companion to [`threat-model.md`](threat-model.md). That file is part of the
Week-8 frozen protocol (its SHA-256 is sealed in
`artifacts/week8_protocol_freeze.json`), so it is left byte-identical. This
page adds no new claim. It explains, for readers outside the project, how the
simulated attacks correspond to things that can happen in a real smart home,
and which real-world cases EviBound does **not** cover.

本文是 [`threat-model.md`](threat-model.md) 的配套说明。该文件属于 Week-8
冻结协议（哈希记录在 `artifacts/week8_protocol_freeze.json`），因此保持原样
不改。本文不增加新的研究结论，只向项目外的读者解释：模拟中的攻击在真实
智能家居里对应什么，以及哪些现实情况 EviBound **不**覆盖。

---

## English

### Where the agent's sensor reading comes from

In a real home the reading travels a chain before the AI agent sees it:

```
presence sensor -> radio/network protocol -> hub or gateway (keeps the record)
               -> integrations / cloud APIs / plugins -> agent tool call -> LLM context
```

EviBound's threat model splits this chain in two:

- **Trusted:** the hub-side record store ("collector"). It keeps each reading
  with an ID, timestamp and epoch, and nobody can rewrite it.
- **Untrusted:** everything between that store and the model, and the model's
  own output. The agent must *cite* the record it relied on, and EviBound checks
  the citation against the trusted store before each device write.

The simulator does not model radios or networks. It models only the outcome
that matters for the agent: **the reading the agent sees can be wrong, while
the trusted record stays correct.** "Tamper" and "replay" are two ways that can
happen.

### A1 Tamper: the agent sees a value the trusted record does not contain

Real-world ways this happens:

- A compromised or buggy third-party integration, cloud bridge or plugin
  returns a false "occupied / not occupied" state to the agent.
- A device on an unauthenticated local channel (some legacy 433 MHz sensors,
  MQTT deployments without authentication) can be impersonated, so the
  agent-facing feed accepts a forged message.
- Non-malicious: a mapping bug inverts the value somewhere between hub and agent.

How EviBound catches it: the cited record ID exists, but its value does not
match the trusted store (**provenance check**).

In the simulator: the first observation keeps the authentic record's ID and
timestamp but flips its presence value.

### A2 Replay: the agent sees an authentic reading that is out of date

Real-world ways this happens:

- An old radio message is captured and sent again. Devices without message
  counters or timestamps accept it. Modern protocols include replay protection
  (Zigbee frame counters, Z-Wave S2, Matter message counters), but older or
  home-made integrations often do not.
- More commonly, non-malicious staleness: a sensor's battery dies or it drops
  off the network, and the hub keeps showing its last value; an integration
  serves a cached state; the agent reuses a reading from earlier in its
  conversation memory.

How EviBound catches it: the record is genuine, but older than the allowed age
(2 simulated time units) (**freshness check**). This is why the
`M_no_freshness` ablation exists: provenance alone accepts a genuine old record.

In the simulator: the first observation is an authentic historical record from
time 0 with the opposite presence value, served unchanged.

### A3 Unauthorized action: the agent writes a device it is not allowed to control

This is not an outside attacker. A user asks for an outcome that would need a
device the agent was not granted (for example, a lighting assistant asked for
"lights low and fan high"), and the model tries to complete the request anyway.
Real analogues are permission scopes: a guest account limited to lights, an
assistant integration granted only some entities. This is the classic
*confused deputy* problem.

How EviBound catches it: every write is checked against the task's authorized
device list.

### Not covered (stated as limitations)

| Real-world case | Why EviBound cannot stop it |
|---|---|
| Physically fooling the sensor (blocking or triggering a motion sensor) | The record is authentic and fresh; only the physical world disagrees |
| Compromised hub / record store | It is in the trusted base by assumption |
| Commands sent straight to devices, bypassing the agent | EviBound only mediates the agent's writes |
| Prompt injection via device names, notes or tool text | Deferred attack family (threat-model.md §7) |
| Jamming or denial of service | Availability is out of scope |
| Adaptive attackers who change strategy based on the defense | Attacks are fixed by design |

### What a real deployment would need for the same check

1. Authenticated sensor pairing and hub-side records with IDs, sequence
   numbers or timestamps (the simulator's exact-match lookup stands in for
   cryptographic verification).
2. An enforcement point between the agent and the device API, so no write
   bypasses the check.
3. The agent cites record IDs instead of copying values, and the hub's clock
   is trusted for the age check.

### Mapping table

| Real home | Simulator |
|---|---|
| Hub's authenticated sensor record | Immutable `obs-current` record |
| Out-of-date but genuine reading | `obs-old` (time 0, opposite value) |
| Agent-facing feed or tool output | The observation copy placed in the prompt |
| Permission scope of the assistant | Task `authorized` list |
| Enforcement middleware | EviBound guard (condition M) |
| Ground truth checked afterwards | Independent trajectory oracle |

---

## 中文

### 智能体看到的传感器读数从哪里来

真实家庭里，读数要经过一条链才到 AI 智能体：

```
人体存在传感器 → 无线/网络协议 → 网关或中枢（保存记录）
             → 第三方集成 / 云端 API / 插件 → 智能体的工具调用 → 模型上下文
```

EviBound 的威胁模型把这条链分成两段：

- **可信：** 网关一侧的记录库（collector）。每条读数带有 ID、时间戳和
  epoch，任何人都改不了。
- **不可信：** 记录库到模型之间的所有环节，以及模型自己的输出。智能体必须
  *引用*它依据的那条记录，EviBound 在每次写设备前拿引用去和可信记录核对。

模拟器不模拟无线或网络细节，只模拟对智能体有影响的结果：**智能体看到的
读数可能是错的，而可信记录始终正确。** 篡改和重放是造成这种情况的两种方式。

### A1 篡改：智能体看到的值，可信记录里并没有

现实中的来源：

- 第三方集成、云端桥接或插件被攻破或有缺陷，给智能体回传了错误的
  “有人/无人”状态。
- 本地通信没有认证（部分老式 433MHz 传感器、未开认证的 MQTT），设备可以
  被冒充，智能体那一侧的数据流就收下了伪造的消息。
- 非恶意情况：网关到智能体之间的映射写错，把值弄反了。

EviBound 怎么拦：引用的记录 ID 存在，但值和可信记录对不上（**来源校验**）。

模拟方式：第一次观测保留真实记录的 ID 和时间戳，只把“有没有人”的值翻转。

### A2 重放：智能体看到的读数是真的，但已经过时

现实中的来源：

- 截获一条旧的无线消息再发一次。没有计数器或时间戳的设备会照单全收。
  较新的协议有防重放机制（Zigbee 帧计数器、Z-Wave S2、Matter 消息计数器），
  但老设备和自制集成常常没有。
- 更常见的是非恶意的过期：传感器没电或掉线后，网关仍显示最后一次的值；
  集成返回的是缓存状态；智能体沿用了对话记忆里更早的读数。

EviBound 怎么拦：记录是真的，但超过允许的时效（模拟时间 2 个单位）
（**时效校验**）。这也是设置 `M_no_freshness` 消融的原因：只查来源的话，
真实但过期的旧记录会被放行。

模拟方式：第一次观测换成时间 0 的一条真实历史记录，内容和现在相反，原样提供。

### A3 越权操作：智能体写了它无权控制的设备

这不是外部攻击者。用户要的结果需要一个智能体没有被授权的设备（比如只管灯
的助手被要求“灯开 1 档、风扇开 2 档”），模型仍然试图把事情做完。现实中对应
权限范围：访客账号只能控制灯，某个助手集成只被授权部分设备。这就是经典的
“混淆代理人”（confused deputy）问题。

EviBound 怎么拦：每次写入都对照任务的授权设备列表。

### 不覆盖的情况（作为局限写明）

| 现实情况 | EviBound 为什么拦不住 |
|---|---|
| 物理上骗传感器（挡住或故意触发人体感应） | 记录本身真实且新鲜，只是现实世界不同 |
| 网关或记录库本身被攻破 | 按假设它属于可信基 |
| 绕过智能体直接给设备发命令 | EviBound 只管智能体发出的写操作 |
| 通过设备名、备注或工具文本做提示注入 | 延后处理的攻击类型（threat-model.md 第 7 节） |
| 干扰信号或拒绝服务 | 可用性不在范围内 |
| 会根据防御调整策略的自适应攻击者 | 攻击方式按设计固定 |

### 真实部署要实现同样的检查需要什么

1. 传感器配对经过认证，网关记录带 ID、序号或时间戳（模拟器用“精确匹配
   查表”代替密码学验证）。
2. 在智能体和设备 API 之间有强制检查点，任何写操作都绕不过去。
3. 智能体引用记录 ID 而不是自己抄数值；时效检查以网关的可信时钟为准。

### 对应关系表

| 真实家庭 | 模拟器 |
|---|---|
| 网关里经过认证的传感器记录 | 不可变记录 `obs-current` |
| 真实但过时的读数 | `obs-old`（时间 0，值相反） |
| 给智能体看的数据流或工具输出 | 放进提示词里的那份观测副本 |
| 助手的权限范围 | 任务的 `authorized` 列表 |
| 强制检查中间件 | EviBound 守卫（条件 M） |
| 事后核对的真实结果 | 独立轨迹判分器（oracle） |
