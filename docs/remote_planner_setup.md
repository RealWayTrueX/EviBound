# Mac demo, Linux model: the planner service / Mac 演示、Linux 跑模型

The Mac only shows the demo; every model call and every experiment runs on
the GPU machine. `scripts/serve_planner.py` exposes the frozen planner and the
experiment traces over HTTP, and the demo on the Mac talks to it. The demo
itself needs no SSH: the two machines are already on the same Tailscale
network, which uses outbound WireGuard/HTTPS only. Since 2026-11-03 the
planner is off by default and the one-click launcher in section 5 starts and
stops it over SSH.

Mac 只做演示，模型调用和实验都在 GPU 机上跑。`scripts/serve_planner.py` 把冻结的
规划器和数据盘上的运行记录以 HTTP 方式提供，Mac 上的 demo 直接调用。全程不用 SSH：
两台机器已经在同一个 Tailscale 网络里，Tailscale 只用出站的 WireGuard/HTTPS。

```
Mac  demo/index.html ──► demo/serve.py (127.0.0.1:8765)
                              │  /api/generate        → POST /v1/chat/completions
                              │  /api/remote/runs     → GET  /runs
                              │  /api/remote/episodes → GET  /runs/<name>/episodes
                              ▼
Tailscale (100.72.39.67:8000, bearer token)
                              ▼
Linux  scripts/serve_planner.py ── evibound.planner.LocalPlanner (bf16, one GPU)
                                └─ /mnt/HDD-8T-0/evibound_yanke/runs/*/episodes.jsonl
```

Any OpenAI-compatible server with a bearer token works for the model calls
(the demo only needs `POST /v1/chat/completions`); `/runs` and
`/runs/<name>/episodes` are optional extras for the replay tab, and without
them episode files are imported by hand. `scripts/serve_planner.py` provides
all three with the frozen planner.

## 1. On the Linux machine (once) / Linux 端

```bash
cd /home/yanke/EviBound && git pull origin main
tmux new-session -d -s evibound_planner 'bash scripts/run_planner_server.sh 1'   # 1 = GPU index; "cpu" or "none" also work
tmux capture-pane -p -t evibound_planner | tail -5     # shows the token file path and the listen address
cat /mnt/HDD-8T-0/evibound_yanke/planner_token         # the bearer token the Mac needs
```

- `run_planner_server.sh` creates the token once (`$EVIBOUND_DATA/planner_token`,
  mode 600), binds to the machine's Tailscale address (`tailscale ip -4`) and
  logs to `$EVIBOUND_DATA/runs/planner_server.log`. `PLANNER_HOST=0.0.0.0`
  would also accept LAN traffic; the token is required either way.
- The service needs about 18 GB on the chosen GPU. Pick a free one with
  `nvidia-smi`; `none` serves only the traces and needs no GPU.
- Sampling is the frozen planner's (temperature 0.2, top-p 0.9, top-k 20,
  224 tokens); a request can only choose `seed`. Replies are exploratory.

### 1b. Adjustable sampling: `scripts/model_server.py` / 可调采样参数

`serve_planner.py` fixes temperature, top-p, top-k and length to the frozen
values. When the demo's parameter controls should take effect, run
`scripts/model_server.py` instead on the same port: same weights (bf16, one
GPU), same routes (`/health`, `/v1/models`, `/v1/chat/completions`, `/runs`,
`/runs/<name>/episodes`), same token file, Tailscale-only binding, but each
request may set `temperature`, `top_p`, `top_k`, `max_tokens` and `seed`
(frozen values are the defaults; the reply's `evibound.sampling` echoes what
was used). Run only one of the two servers on port 8000.

`serve_planner.py` 把采样参数固定为冻结值；如果希望演示页面里调的温度等参数生效，
改用 `scripts/model_server.py`：同样的权重、路由、口令文件和只绑 Tailscale 地址，
但每个请求可以设置 `temperature`、`top_p`、`top_k`、`max_tokens`、`seed`，默认就是
冻结值。同一端口只开其中一个。

```bash
tmux new-session -d -s evibound_model_server 'cd /home/yanke/EviBound && source scripts/env.sh && CUDA_VISIBLE_DEVICES=1 python scripts/model_server.py --preload'
```

## 2. On the Mac / Mac 端

```bash
mkdir -p ~/.config/evibound && printf '%s' '<token>' > ~/.config/evibound/planner_token && chmod 600 ~/.config/evibound/planner_token
cd ~/CyberSercurity/EviBound && python3 demo/serve.py        # http://127.0.0.1:8765/
```

In the page choose 智能体 → "UQ Linux GPU 机 …", press 检查连接, then run
steps as usual: each 模型生成 sends the exact messages shown to the Linux
machine. In 回放真实轨迹, 列出运行 and 拉取 … 的回合 fetch real holdout
episodes straight from the data disk. Moving the token without SSH:
read it on the Linux terminal, or `tailscale file cp
/mnt/HDD-8T-0/evibound_yanke/planner_token xins-macbook-pro:` (Taildrop).

`demo/backends.json` holds the address (`http://100.72.39.67:8000/v1`); the
token comes from `EVIBOUND_API_TOKEN` or `~/.config/evibound/planner_token`,
never from the page. Small exploratory batches can also be driven from the
Mac while computing on Linux:
`python3 scripts/run_v3_local.py --split dev --planner openai --base-url http://100.72.39.67:8000/v1 --model Qwen2.5-7B-Instruct --api-key-env EVIBOUND_API_TOKEN --seeds 11 --output /tmp/v3_remote_dev`
(the Mac only orchestrates; large runs belong on the Linux machine itself).

## 3. If Tailscale is unavailable / 没有 Tailscale 时

| Route | Needs | Notes |
|---|---|---|
| LAN direct | both on one network, Linux port open (`sudo ufw allow 8000`), `PLANNER_HOST=0.0.0.0` | campus Wi-Fi often isolates clients; test with `curl http://<ip>:8000/health` |
| Cloudflare quick tunnel | `cloudflared tunnel --url http://127.0.0.1:8000` on Linux (outbound HTTPS only) | gives a public `*.trycloudflare.com` URL; the bearer token is the only protection, so rotate it afterwards |
| ngrok / zrok / bore | an account or a relay | same caveat as above |

All of these use outbound connections from the Linux machine, so a blocked
SSH port does not matter. Tailscale is preferred because the service is then
reachable only from Xin's own devices.

## 4. Security notes / 安全说明

- `serve_planner.py` refuses to listen beyond loopback without a token, checks
  the token in constant time, caps request size, message count and length,
  and resolves run names strictly inside the runs directory.
- The demo's local server never sends the token to the browser (`/api/info`
  only reports whether one is configured) and accepts API calls only from
  its own page on a loopback host.
- Traces served over `/runs` are synthetic experiment data; no personal data
  is involved.

## 5. One-click start and stop from the Mac / Mac 一键启动、关闭

The GPU planner is **off by default** (stopped 2026-11-03 so both GPUs are free
for experiments). For a demo, double-click on the Mac:

| File | What it does |
|---|---|
| `demo/launch/EviBound-Demo-Start.command` | SSH to `yanke@100.72.39.67`, start `scripts/model_server.py --preload` in tmux `evibound_model_server` on the GPU with the most free memory (refuses if none has ≥ 19,000 MiB free), wait for `/health` over Tailscale, then start `demo/serve.py` and open `http://127.0.0.1:8765/` |
| `demo/launch/EviBound-Demo-Stop.command` | kill the tmux session on the server (frees the GPU) and stop the local demo page |

Copies of both files also sit in `~/CyberSercurity/` on Xin's Mac, outside
the git clone, so they work before the clone is updated. They assume the clone
at `~/CyberSercurity/EviBound` (override with `EVIBOUND_MAC_REPO`) and the
token file `~/.config/evibound/planner_token` from section 2.

The Mac has no key login to the server yet, so each start or stop asks for the
server password once. To make it truly one click, the owner can set up key
login once (a deliberate security choice, so it is not automated):

```bash
ls ~/.ssh/id_ed25519.pub || ssh-keygen -t ed25519      # on the Mac, only if no key exists
ssh-copy-id yanke@100.72.39.67                         # asks for the server password one last time
```

GPU 规划器默认关闭（2026-11-03 关掉，两张卡都留给实验）。演示时在 Mac 上双击
`EviBound-Demo-Start.command`：它通过 SSH 在空闲显存最多的 GPU 上启动
`model_server.py`（tmux 会话 `evibound_model_server`），等 Tailscale 上的 `/health`
就绪后启动本机演示页并打开浏览器。用完双击 `EviBound-Demo-Stop.command` 释放 GPU。
目前 Mac 没有免密登录，每次会问一次服务器密码；需要真正"一键"时由负责人自己运行上面
两行配置免密（安全设置，不自动改）。
