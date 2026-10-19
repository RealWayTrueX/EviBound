# Mac demo, Linux model: the planner service / Mac 演示、Linux 跑模型

The Mac only shows the demo; every model call and every experiment runs on
the GPU machine. `scripts/serve_planner.py` exposes the frozen planner and the
experiment traces over HTTP, and the demo on the Mac talks to it. No SSH is
involved anywhere: the two machines are already on the same Tailscale
network, which uses outbound WireGuard/HTTPS only.

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
