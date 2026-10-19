#!/usr/bin/env python3
"""OpenAI-compatible model endpoint on the GPU machine, for the Mac demo and exploratory runs.

Serves the same local Qwen2.5-7B-Instruct weights as the experiments (bf16 on
one CUDA device) behind ``POST /v1/chat/completions`` and ``GET /v1/models``.
Unlike ``scripts/serve_planner.py`` (frozen sampling, seed only), requests may
set temperature, top_p, top_k, max_tokens and seed, so the demo's parameter
controls take effect; the frozen values are the defaults. It also gives
read-only access to finished run traces for the demo's replay tab, with the
same routes as ``serve_planner.py``:

    GET /runs                                   runs that have episodes.jsonl (name, episodes, complete)
    GET /runs/<name>/episodes?task_id=&condition=&variant=&seed=&limit=   NDJSON episode rows

Exposure is limited on purpose:
  * it binds to one address (default: this machine's Tailscale IP), never 0.0.0.0;
  * it answers only clients on loopback or the Tailscale range 100.64.0.0/10;
  * every request except ``/health`` needs ``Authorization: Bearer <token>``.
    The token is read from $EVIBOUND_API_TOKEN, else from
    /mnt/HDD-8T-0/evibound_yanke/planner_token (created with mode 600 on first start;
    the same file scripts/run_planner_server.sh uses).

Generation is serialised (one request at a time) so a demo and a batch cannot
run two copies of the model at once. Outputs from this endpoint are
exploratory; the confirmatory results remain the frozen runs.

    CUDA_VISIBLE_DEVICES=0 python scripts/model_server.py            # Tailscale IP, port 8000
    python scripts/model_server.py --host 127.0.0.1 --port 8001       # local only
"""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import secrets
import subprocess
import threading
import time
import uuid
from pathlib import Path

DEFAULT_MODELS = {"Qwen2.5-7B-Instruct": "/mnt/HDD-8T-0/evibound_yanke/models/Qwen2.5-7B-Instruct"}
RUNS_ROOT = Path("/mnt/HDD-8T-0/evibound_yanke/runs")
TOKEN_FILE = Path("/mnt/HDD-8T-0/evibound_yanke/planner_token")  # shared with run_planner_server.sh
TAILNET = ipaddress.ip_network("100.64.0.0/10")
FROZEN_SAMPLING = {"temperature": 0.2, "top_p": 0.9, "top_k": 20, "max_tokens": 224}
MAX_TOKENS_CAP = 1024


def load_token() -> str:
    if os.environ.get("EVIBOUND_API_TOKEN"):
        return os.environ["EVIBOUND_API_TOKEN"]
    if not TOKEN_FILE.exists():
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(secrets.token_urlsafe(32) + "\n")
        TOKEN_FILE.chmod(0o600)
    return TOKEN_FILE.read_text().strip()


def tailscale_ip() -> str:
    try:
        out = subprocess.run(["tailscale", "ip", "-4"], capture_output=True, text=True, timeout=10).stdout
        return out.split()[0]
    except (OSError, IndexError, subprocess.SubprocessError):
        raise SystemExit("could not read the Tailscale IP; pass --host explicitly")


def client_allowed(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return False
    return address.is_loopback or address in TAILNET


class ModelPool:
    """Lazy-loaded models; one generation at a time."""

    def __init__(self, paths: dict[str, str]):
        self.paths, self.loaded, self.lock = paths, {}, threading.Lock()

    def get(self, name: str):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if name not in self.paths:
            raise KeyError(name)
        if name not in self.loaded:
            path = self.paths[name]
            tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, padding_side="left")
            tokenizer.pad_token = tokenizer.eos_token
            model = AutoModelForCausalLM.from_pretrained(
                path, local_files_only=True, dtype=torch.bfloat16, attn_implementation="sdpa",
                device_map={"": "cuda:0"})
            model.eval()
            self.loaded[name] = (tokenizer, model)
        return self.loaded[name]

    def chat(self, name: str, messages: list[dict], sampling: dict) -> dict:
        import torch
        with self.lock:
            tokenizer, model = self.get(name)
            text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
            batch = tokenizer([text], return_tensors="pt").to("cuda:0")
            if sampling.get("seed") is not None:
                torch.manual_seed(int(sampling["seed"]))
                torch.cuda.manual_seed_all(int(sampling["seed"]))
            start = time.perf_counter()
            temperature = float(sampling["temperature"])
            kwargs = {"max_new_tokens": int(sampling["max_tokens"]), "pad_token_id": tokenizer.pad_token_id,
                      "use_cache": True}
            if temperature > 0:
                kwargs.update(do_sample=True, temperature=temperature, top_p=float(sampling["top_p"]),
                              top_k=int(sampling["top_k"]))
            else:
                kwargs.update(do_sample=False)
            with torch.inference_mode():
                generated = model.generate(**batch, **kwargs)
            seq = generated[0, batch["input_ids"].shape[1]:].tolist()
            finish = "length"
            if tokenizer.eos_token_id in seq:
                seq, finish = seq[:seq.index(tokenizer.eos_token_id)], "stop"
            content = tokenizer.decode(seq, skip_special_tokens=True).strip()
            return {"content": content, "prompt_tokens": int(batch["input_ids"].shape[1]),
                    "completion_tokens": len(seq), "finish_reason": finish,
                    "latency_s": round(time.perf_counter() - start, 3)}


def parse_sampling(body: dict) -> dict:
    sampling = dict(FROZEN_SAMPLING)
    for key in ("temperature", "top_p", "top_k", "max_tokens", "seed"):
        if body.get(key) is not None:
            sampling[key] = body[key]
    if body.get("max_new_tokens") is not None:  # the demo's own name for max_tokens
        sampling["max_tokens"] = body["max_new_tokens"]
    try:
        sampling["temperature"] = min(max(float(sampling["temperature"]), 0.0), 2.0)
        sampling["top_p"] = min(max(float(sampling["top_p"]), 0.01), 1.0)
        sampling["top_k"] = max(int(sampling["top_k"]), 1)
        sampling["max_tokens"] = min(max(int(sampling["max_tokens"]), 1), MAX_TOKENS_CAP)
        if sampling.get("seed") is not None:
            sampling["seed"] = int(sampling["seed"])
    except (TypeError, ValueError):
        raise ValueError("sampling parameters must be numbers")
    return sampling


def clean_messages(messages) -> list[dict]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    out = []
    for item in messages:
        if (not isinstance(item, dict) or item.get("role") not in ("system", "user", "assistant")
                or not isinstance(item.get("content"), str)):
            raise ValueError("each message needs role system/user/assistant and string content")
        out.append({"role": item["role"], "content": item["content"]})
    return out


def run_names() -> list[str]:
    if not RUNS_ROOT.is_dir():
        return []
    return sorted(p.name for p in RUNS_ROOT.iterdir() if (p / "episodes.jsonl").is_file())


def build_app(pool: ModelPool, token: str):
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse, PlainTextResponse

    app = FastAPI(title="EviBound model endpoint", docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        if not client_allowed(request.client.host if request.client else ""):
            return JSONResponse({"error": "client not on loopback or the Tailscale network"}, status_code=403)
        if request.url.path != "/health":
            supplied = request.headers.get("authorization", "")
            if not secrets.compare_digest(supplied, "Bearer " + token):
                return JSONResponse({"error": "missing or wrong bearer token"}, status_code=401)
        return await call_next(request)

    @app.get("/health")
    def health():
        return {"ok": True, "models": list(pool.paths), "loaded": list(pool.loaded)}

    @app.get("/v1/models")
    def models():
        return {"object": "list", "data": [{"id": name, "object": "model", "owned_by": "local"}
                                           for name in pool.paths]}

    @app.post("/v1/chat/completions")
    def chat(body: dict):
        if body.get("stream"):
            raise HTTPException(400, "streaming is not supported")
        name = body.get("model") or next(iter(pool.paths))
        try:
            messages, sampling = clean_messages(body.get("messages")), parse_sampling(body)
            result = pool.chat(name, messages, sampling)
        except KeyError:
            raise HTTPException(404, f"unknown model {name!r}; see /v1/models")
        except ValueError as exc:
            raise HTTPException(400, str(exc))
        return {
            "id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion", "created": int(time.time()),
            "model": name,
            "choices": [{"index": 0, "finish_reason": result["finish_reason"],
                         "message": {"role": "assistant", "content": result["content"]}}],
            "usage": {"prompt_tokens": result["prompt_tokens"], "completion_tokens": result["completion_tokens"],
                      "total_tokens": result["prompt_tokens"] + result["completion_tokens"]},
            "evibound": {"sampling": sampling, "latency_s": result["latency_s"], "precision": "bfloat16 on CUDA"},
        }

    @app.get("/runs")
    def runs():
        out = []
        for name in run_names():
            path = RUNS_ROOT / name / "episodes.jsonl"
            with path.open() as stream:
                count = sum(1 for _ in stream)
            out.append({"name": name, "episodes": count, "complete": (RUNS_ROOT / name / "COMPLETE").exists(),
                        "modified_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(path.stat().st_mtime))})
        return {"runs": out}

    @app.get("/runs/{name}/episodes")
    def run_episodes(name: str, task_id: str | None = None, condition: str | None = None,
                     variant: str | None = None, seed: int | None = None, limit: int = 200):
        if name not in run_names():
            raise HTTPException(404, "unknown run")
        wanted = {k: v for k, v in (("task_id", task_id), ("condition", condition), ("variant", variant),
                                    ("seed", seed)) if v is not None}
        limit, lines = min(max(limit, 1), 2000), []
        with (RUNS_ROOT / name / "episodes.jsonl").open() as stream:
            for line in stream:
                if wanted:
                    row = json.loads(line)
                    if any(row.get(k) != v for k, v in wanted.items()):
                        continue
                lines.append(line.rstrip("\n"))
                if len(lines) >= limit:
                    break
        return PlainTextResponse("\n".join(lines) + ("\n" if lines else ""), media_type="application/x-ndjson")

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--host", help="bind address (default: Tailscale IPv4)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--model", action="append", metavar="NAME=PATH",
                        help="extra or replacement model; default serves the experiment's Qwen2.5-7B-Instruct")
    parser.add_argument("--preload", action="store_true", help="load the default model before serving")
    args = parser.parse_args()
    paths = dict(DEFAULT_MODELS)
    for item in args.model or []:
        name, _, path = item.partition("=")
        if not name or not path:
            parser.error("--model needs NAME=PATH")
        paths[name] = path
    host = args.host or tailscale_ip()
    if host in ("0.0.0.0", "::"):
        parser.error("refusing to bind every interface; pass a specific address")
    pool = ModelPool(paths)
    if args.preload:
        pool.get(next(iter(paths)))
    token = load_token()
    import uvicorn
    print(json.dumps({"listening": f"http://{host}:{args.port}/v1", "models": list(paths),
                      "token_file": None if os.environ.get("EVIBOUND_API_TOKEN") else str(TOKEN_FILE)}),
          flush=True)
    uvicorn.run(build_app(pool, token), host=host, port=args.port, log_level="info", access_log=True)


if __name__ == "__main__":
    main()
