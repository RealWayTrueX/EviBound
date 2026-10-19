#!/usr/bin/env python3
"""Serve the frozen EviBound planner over HTTP so a laptop demo can call the GPU machine.

Runs on the experiment machine (one GPU, the pinned Qwen2.5-7B-Instruct weights)
and exposes, with the same chat template and sampling as the experiments:

  GET  /health                       model, device, whether the planner is loaded
  GET  /v1/models                    OpenAI-style model list (fixed sampling is listed)
  POST /v1/chat/completions          OpenAI-style chat completion; body may carry "seed"
  GET  /runs                         experiment runs under --runs-dir with an episodes.jsonl
  GET  /runs/<name>/episodes         NDJSON stream of episodes, filtered by task_id,
                                     condition, variant, seed; limit (default 200, max 2000)

The Mac demo (demo/serve.py, demo/backends.json) talks to this directly, no
SSH involved: reach it over the LAN, a Tailscale address or a tunnel, see
docs/remote_planner_setup.md. Anything other than loopback requires a bearer
token (EVIBOUND_API_TOKEN); the server refuses to start otherwise.

Usage on the GPU machine (see scripts/run_planner_server.sh for the tmux form):
  EVIBOUND_API_TOKEN=... CUDA_VISIBLE_DEVICES=1 python scripts/serve_planner.py \\
      --host 0.0.0.0 --port 8000 --runs-dir /mnt/HDD-8T-0/evibound_yanke/runs

Temperature, top-p, top-k and the 224-token limit are the frozen planner's and
cannot be changed per request; a request may only choose the sampling seed.
Outputs from this service are exploratory, never confirmatory results.
"""

from __future__ import annotations

import argparse
import hmac
import json
import os
import re
import sys
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

DEFAULT_MODEL = "/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct"
DEFAULT_RUNS = "/mnt/HDD-8T-0/evibound_yanke/runs"
MODEL_NAME = "Qwen2.5-7B-Instruct"
FIXED_SAMPLING = {"temperature": 0.2, "top_p": 0.9, "top_k": 20, "max_new_tokens": 224}
ROLES = ("system", "user", "assistant")
MAX_BODY = 1 << 20
MAX_MESSAGES = 8
MAX_CHARS = 40_000
MAX_EPISODES = 2000
LOOPBACK = ("127.0.0.1", "localhost", "::1")
RUN_NAME = re.compile(r"^[\w.-]{1,80}$")
FILTERS = ("task_id", "condition", "variant", "seed")


class PlannerService:
    """Wraps a planner with LocalPlanner's interface: generate(message_batches, seed) -> [reply]."""

    def __init__(self, planner, *, model_name=MODEL_NAME, device="cuda", runs_dir=None, token=None):
        self.planner = planner
        self.model_name = model_name
        self.device = device
        self.runs_dir = Path(runs_dir).resolve() if runs_dir else None
        self.token = token
        self.lock = threading.Lock()
        self.started = time.time()
        self.calls = 0

    # ---- auth and validation -------------------------------------------------
    def authorized(self, header: str | None) -> bool:
        if not self.token:
            return True
        if not header or not header.startswith("Bearer "):
            return False
        return hmac.compare_digest(header[len("Bearer "):].strip(), self.token)

    @staticmethod
    def clean_messages(messages):
        if not isinstance(messages, list) or not messages or len(messages) > MAX_MESSAGES:
            raise ValueError(f"messages must be a list of 1..{MAX_MESSAGES} items")
        out, chars = [], 0
        for item in messages:
            if not isinstance(item, dict) or item.get("role") not in ROLES or not isinstance(item.get("content"), str):
                raise ValueError("each message needs role in system/user/assistant and a string content")
            chars += len(item["content"])
            out.append({"role": item["role"], "content": item["content"]})
        if chars > MAX_CHARS:
            raise ValueError(f"messages exceed {MAX_CHARS} characters")
        return out

    # ---- model ----------------------------------------------------------------
    def complete(self, messages, seed):
        with self.lock:
            self.calls += 1
            reply = self.planner.generate([messages], seed)[0]
        raw = reply["raw"]
        prompt_tokens = int(reply.get("input_tokens") or 0)
        completion_tokens = int(reply.get("output_tokens") or 0)
        return {
            "id": f"chatcmpl-evibound-{self.calls}", "object": "chat.completion", "created": int(time.time()),
            "model": self.model_name,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": raw}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": prompt_tokens + completion_tokens},
            "evibound": {"seed": seed, "parse_error": reply.get("parse_error"),
                         "latency_s": reply.get("latency_s"), "sampling": FIXED_SAMPLING,
                         "note": "frozen planner; exploratory output, not a confirmatory result"},
        }

    # ---- runs ---------------------------------------------------------------
    def list_runs(self):
        if not self.runs_dir or not self.runs_dir.is_dir():
            return []
        runs = []
        for episodes in sorted(self.runs_dir.glob("*/episodes.jsonl")):
            run_dir = episodes.parent
            with episodes.open("rb") as stream:
                count = sum(1 for _ in stream)
            runs.append({"name": run_dir.name, "episodes": count, "complete": (run_dir / "COMPLETE").exists(),
                         "bytes": episodes.stat().st_size,
                         "modified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(episodes.stat().st_mtime))})
        return runs

    def episodes_path(self, name: str) -> Path | None:
        if not self.runs_dir or not RUN_NAME.match(name):
            return None
        path = (self.runs_dir / name / "episodes.jsonl").resolve()
        if self.runs_dir not in path.parents or not path.is_file():
            return None
        return path

    @staticmethod
    def iter_episodes(path: Path, filters: dict, limit: int):
        sent = 0
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                if filters:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if any(str(row.get(key)) != value for key, value in filters.items()):
                        continue
                yield line if line.endswith("\n") else line + "\n"
                sent += 1
                if sent >= limit:
                    return


def make_handler(service: PlannerService):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"
        server_version = "EviBoundPlanner/1"

        def log_message(self, fmt, *args):
            sys.stderr.write("[planner] %s %s\n" % (self.address_string(), fmt % args))

        def _json(self, status, payload):
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _auth(self) -> bool:
            if service.authorized(self.headers.get("Authorization")):
                return True
            self._json(HTTPStatus.UNAUTHORIZED, {"error": "missing or wrong bearer token (EVIBOUND_API_TOKEN)"})
            return False

        def do_GET(self):
            url = urlsplit(self.path)
            if url.path == "/health":
                return self._json(200, {"ok": True, "model": service.model_name, "device": service.device,
                                        "loaded": service.planner is not None, "calls": service.calls,
                                        "uptime_s": round(time.time() - service.started, 1),
                                        "runs_dir": str(service.runs_dir) if service.runs_dir else None,
                                        "auth_required": bool(service.token)})
            if not self._auth():
                return None
            if url.path == "/v1/models":
                return self._json(200, {"object": "list", "data": [{"id": service.model_name, "object": "model",
                                                                     "owned_by": "evibound", "sampling": FIXED_SAMPLING}]})
            if url.path == "/runs":
                return self._json(200, {"runs": service.list_runs()})
            match = re.fullmatch(r"/runs/([^/]+)/episodes", url.path)
            if match:
                path = service.episodes_path(match.group(1))
                if path is None:
                    return self._json(404, {"error": "unknown run"})
                query = {k: v[0] for k, v in parse_qs(url.query).items() if v}
                filters = {k: query[k] for k in FILTERS if query.get(k)}
                try:
                    limit = max(1, min(MAX_EPISODES, int(query.get("limit", 200))))
                except ValueError:
                    return self._json(400, {"error": "limit must be an integer"})
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Transfer-Encoding", "chunked")
                self.end_headers()
                for line in service.iter_episodes(path, filters, limit):
                    data = line.encode("utf-8")
                    self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
                self.wfile.write(b"0\r\n\r\n")
                return None
            return self._json(404, {"error": "unknown endpoint"})

        def do_POST(self):
            url = urlsplit(self.path)
            if not self._auth():
                return None
            if url.path != "/v1/chat/completions":
                return self._json(404, {"error": "unknown endpoint"})
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY:
                return self._json(413, {"error": "body too large"})
            try:
                data = json.loads(self.rfile.read(length) or b"{}")
                if not isinstance(data, dict):
                    raise ValueError("body must be a JSON object")
                messages = service.clean_messages(data.get("messages"))
                seed = data.get("seed", 11)
                if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**31:
                    raise ValueError("seed must be an integer in [0, 2^31)")
            except (json.JSONDecodeError, ValueError) as exc:
                return self._json(400, {"error": str(exc)})
            if service.planner is None:
                return self._json(503, {"error": "planner not loaded"})
            try:
                return self._json(200, service.complete(messages, seed))
            except Exception as exc:  # surface model errors to the caller instead of a bare 500
                return self._json(500, {"error": f"{type(exc).__name__}: {exc}"})

    return Handler


def make_server(service: PlannerService, host: str, port: int) -> ThreadingHTTPServer:
    if host not in LOOPBACK and not service.token:
        raise SystemExit("refusing to listen beyond loopback without EVIBOUND_API_TOKEN")
    return ThreadingHTTPServer((host, port), make_handler(service))


def load_planner(model_path: str, device: str, cpu_threads: int):
    if device == "cpu":
        from evibound.planner_v3 import CPUPlanner
        return CPUPlanner(model_path, threads=cpu_threads)
    from evibound.planner import LocalPlanner
    return LocalPlanner(model_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", default="127.0.0.1", help="0.0.0.0 to accept LAN/Tailscale/tunnel traffic")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    parser.add_argument("--cpu-threads", type=int, default=12)
    parser.add_argument("--runs-dir", default=DEFAULT_RUNS)
    parser.add_argument("--no-model", action="store_true", help="serve only /runs (no GPU needed)")
    args = parser.parse_args()
    token = os.environ.get("EVIBOUND_API_TOKEN") or None
    planner = None if args.no_model else load_planner(args.model, args.device, args.cpu_threads)
    service = PlannerService(planner, device=args.device, runs_dir=args.runs_dir, token=token)
    server = make_server(service, args.host, args.port)
    print(f"EviBound planner service on http://{args.host}:{args.port}  model={'none' if planner is None else args.model}"
          f"  auth={'token' if token else 'none (loopback only)'}  runs={args.runs_dir}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
