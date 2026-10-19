"""Local server for the EviBound attack/defense demo (standard library only).

    python3 demo/serve.py                # http://127.0.0.1:8765
    python3 demo/serve.py --port 9000

What it adds over opening demo/index.html directly:
  * Live model calls. The page sends the exact chat messages it shows; this
    server forwards them to an OpenAI-compatible endpoint (Ollama, LM Studio,
    vLLM on the GPU machine through an SSH tunnel, ...) or to a local
    Hugging Face model loaded with transformers. API keys are read from
    environment variables only, never from the page.
  * Saving edits. "保存修改" writes demo/presets/<name>.json, which can be
    committed so the same prompts and parameters are reused next time.

The server listens on 127.0.0.1 only and never controls a real device. It
refuses requests whose Host is not a loopback name and API calls from any
other origin, and the page can only pick a backend by id (plus base_url/model
for the "custom" entry): paths, key variable names and timeouts come from
backends.json only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEMO = Path(__file__).resolve().parent
PRESETS = DEMO / "presets"
BACKENDS_FILE = DEMO / "backends.json"
_LOCAL_MODELS: dict[str, tuple] = {}
_MODEL_LOCK = threading.Lock()  # one load and one generation at a time (ThreadingHTTPServer)
LOOPBACK_HOSTS = ("127.0.0.1", "localhost", "[::1]")
ROLES = ("system", "user", "assistant")
SAMPLING_KEYS = ("temperature", "top_p", "top_k", "max_new_tokens", "seed")


def _backends() -> list[dict]:
    if BACKENDS_FILE.exists():
        return json.loads(BACKENDS_FILE.read_text())
    return []


def _resolve_backend(data: dict) -> dict:
    """The page names a backend; everything else (paths, key variable names) comes from backends.json."""
    backend_id = data.get("backend_id")
    if backend_id == "custom":
        custom = data.get("custom") if isinstance(data.get("custom"), dict) else {}
        base_url, model = str(custom.get("base_url") or ""), str(custom.get("model") or "")
        if not re.match(r"^https?://", base_url):
            raise ValueError("自定义端点的 base_url 必须以 http:// 或 https:// 开头")
        if not model:
            raise ValueError("自定义端点没有填 model")
        return {"id": "custom", "type": "openai", "base_url": base_url, "model": model}
    for cfg in _backends():
        if cfg.get("id") == backend_id:
            return cfg
    raise ValueError(f"未知的模型端点 {backend_id!r}；请在 demo/backends.json 里配置")


def _clean_messages(messages) -> list[dict]:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a non-empty list")
    out = []
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in ROLES or not isinstance(item.get("content"), str):
            raise ValueError("each message needs role in system/user/assistant and a string content")
        out.append({"role": item["role"], "content": item["content"]})
    return out


def _clean_sampling(sampling) -> dict:
    out = {}
    for key in SAMPLING_KEYS:
        value = (sampling or {}).get(key) if isinstance(sampling, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[key] = value
    return out


def _bearer(cfg: dict) -> str | None:
    """Token from the environment variable or file named in backends.json; never from the page."""
    key_env = cfg.get("api_key_env")
    if key_env and os.environ.get(key_env):
        return os.environ[key_env].strip()
    key_file = cfg.get("api_key_file")
    if key_file:
        path = Path(os.path.expanduser(key_file))
        if path.is_file():
            return path.read_text().strip() or None
    return None


def _service_root(cfg: dict) -> str:
    """scripts/serve_planner.py serves /runs next to /v1; strip the OpenAI prefix."""
    return re.sub(r"/v1/?$", "", cfg["base_url"].rstrip("/"))


def _remote_get(cfg: dict, path: str, timeout_s: float = 60):
    headers = {}
    token = _bearer(cfg)
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(_service_root(cfg) + path, headers=headers)
    return urllib.request.urlopen(request, timeout=timeout_s)


def _call_openai(cfg: dict, messages: list, sampling: dict) -> str:
    url = cfg["base_url"].rstrip("/") + "/chat/completions"
    body = {"model": cfg["model"], "messages": messages,
            "temperature": sampling.get("temperature", 0.2), "top_p": sampling.get("top_p", 0.9),
            "max_tokens": sampling.get("max_new_tokens", 224), "stream": False}
    if "top_k" in sampling:
        body["top_k"] = sampling["top_k"]  # accepted by vLLM / Ollama, ignored by others
    if sampling.get("seed") is not None:
        body["seed"] = sampling["seed"]
    headers = {"Content-Type": "application/json"}
    token = _bearer(cfg)
    if token:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(url, json.dumps(body).encode(), headers)
    with urllib.request.urlopen(request, timeout=cfg.get("timeout_s", 300)) as response:
        data = json.loads(response.read())
    return data["choices"][0]["message"]["content"]


def _call_transformers(cfg: dict, messages: list, sampling: dict) -> str:
    """Same sampling as planner.LocalPlanner; uses Apple MPS, CUDA or CPU, whichever exists."""
    # Some conda builds ship two OpenMP runtimes and abort on `import torch` without this.
    os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    path = os.path.expanduser(cfg["model_path"])
    with _MODEL_LOCK:
        if path not in _LOCAL_MODELS:
            device = "cuda" if torch.cuda.is_available() else "mps" if torch.backends.mps.is_available() else "cpu"
            dtype = torch.float32 if device == "cpu" else torch.bfloat16 if device == "cuda" else torch.float16
            tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True, padding_side="left")
            model = AutoModelForCausalLM.from_pretrained(path, local_files_only=True, dtype=dtype).to(device)
            model.eval()
            _LOCAL_MODELS[path] = (tokenizer, model, device)
        tokenizer, model, device = _LOCAL_MODELS[path]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        batch = tokenizer([text], return_tensors="pt").to(device)
        if sampling.get("seed") is not None:
            torch.manual_seed(int(sampling["seed"]))
        with torch.inference_mode():
            out = model.generate(**batch, max_new_tokens=int(sampling.get("max_new_tokens", 224)), do_sample=True,
                                 temperature=float(sampling.get("temperature", 0.2)),
                                 top_p=float(sampling.get("top_p", 0.9)), top_k=int(sampling.get("top_k", 20)),
                                 pad_token_id=tokenizer.eos_token_id)
        return tokenizer.decode(out[0, batch["input_ids"].shape[1]:], skip_special_tokens=True).strip()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DEMO), **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("[demo] " + fmt % args + "\n")

    def _json(self, status: int, payload) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def _host_ok(self) -> bool:
        """Refuse any request whose Host is not a loopback name: a DNS-rebinding page that resolves
        to 127.0.0.1 still carries its own hostname here and is turned away (page loads included)."""
        host = (self.headers.get("Host") or "").strip().lower()
        port = self.server.server_port
        return host in LOOPBACK_HOSTS or host in {f"{h}:{port}" for h in LOOPBACK_HOSTS}

    def _same_origin(self) -> bool:
        """Only the demo page itself may call the API: a page from any other origin (even
        another local server) gets 403, and preflights are never answered with CORS headers."""
        origin = self.headers.get("Origin")
        if origin is None:  # curl / same-origin GET navigation
            return True
        port = self.server.server_port
        return origin.lower() in {f"http://{h}:{port}" for h in LOOPBACK_HOSTS}

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.FORBIDDEN)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        if not self._host_ok():
            return self._json(403, {"error": "unexpected Host header"})
        return super().do_HEAD()

    def _public_backends(self) -> list[dict]:
        """What the page may see: ids, labels, types, urls; never key names, files or paths."""
        return [{k: v for k, v in cfg.items() if k in ("id", "label", "type", "base_url", "model")}
                | {"has_token": bool(_bearer(cfg))} for cfg in _backends()]

    def _remote(self, query: dict):
        """Resolve the backend named in a /api/remote/* query (custom base_url allowed)."""
        data = {"backend_id": query.get("backend_id", [""])[0]}
        if data["backend_id"] == "custom":
            data["custom"] = {"base_url": query.get("base_url", [""])[0], "model": query.get("model", ["x"])[0] or "x"}
        cfg = _resolve_backend(data)
        if cfg.get("type") != "openai":
            raise ValueError("only OpenAI-compatible backends can serve runs")
        return cfg

    def do_GET(self):
        if not self._host_ok():
            return self._json(403, {"error": "unexpected Host header"})
        if self.path == "/api/info":
            presets = sorted(p.stem for p in PRESETS.glob("*.json"))
            return self._json(200, {"server": True, "backends": self._public_backends(), "presets": presets})
        url = urllib.parse.urlsplit(self.path)
        if url.path in ("/api/remote/health", "/api/remote/runs", "/api/remote/episodes"):
            query = urllib.parse.parse_qs(url.query)
            try:
                cfg = self._remote(query)
                if url.path == "/api/remote/health":
                    with _remote_get(cfg, "/health", 15) as response:
                        return self._json(200, json.loads(response.read()))
                if url.path == "/api/remote/runs":
                    with _remote_get(cfg, "/runs", 60) as response:
                        return self._json(200, json.loads(response.read()))
                run = query.get("run", [""])[0]
                if not re.fullmatch(r"[\w.-]{1,80}", run):
                    return self._json(400, {"error": "bad run name"})
                params = {k: query[k][0] for k in ("task_id", "condition", "variant", "seed", "limit") if query.get(k)}
                with _remote_get(cfg, f"/runs/{run}/episodes?" + urllib.parse.urlencode(params), 600) as response:
                    body = response.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(body)
                return None
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                return self._json(502, {"error": f"模型服务返回 {exc.code}：{detail}"})
            except (urllib.error.URLError, OSError) as exc:
                return self._json(502, {"error": f"模型服务连不上：{exc}. 检查 Tailscale/网络和服务是否在运行。"})
        match = re.fullmatch(r"/api/presets/([\w.-]+)", self.path)
        if match:
            path = PRESETS / f"{match.group(1)}.json"
            if not path.exists():
                return self._json(404, {"error": "preset not found"})
            return self._json(200, json.loads(path.read_text()))
        return super().do_GET()

    def do_POST(self):
        if not self._host_ok():
            return self._json(403, {"error": "unexpected Host header"})
        if not self._same_origin():
            return self._json(403, {"error": "cross-origin requests are not allowed"})
        if not (self.headers.get("Content-Type") or "").lower().startswith("application/json"):
            return self._json(415, {"error": "Content-Type must be application/json"})
        try:
            data = self._body()
        except (json.JSONDecodeError, ValueError):
            return self._json(400, {"error": "request body is not JSON"})
        if not isinstance(data, dict):
            return self._json(400, {"error": "request body must be a JSON object"})
        if self.path == "/api/generate":
            start = time.perf_counter()
            try:
                cfg = _resolve_backend(data)
                messages = _clean_messages(data.get("messages"))
                sampling = _clean_sampling(data.get("sampling"))
            except ValueError as exc:
                return self._json(400, {"error": str(exc)})
            try:
                if cfg.get("type") == "transformers":
                    raw = _call_transformers(cfg, messages, sampling)
                elif cfg.get("type") == "openai":
                    raw = _call_openai(cfg, messages, sampling)
                else:
                    return self._json(400, {"error": "backend type must be openai or transformers (demo/backends.json)"})
            except urllib.error.URLError as exc:
                return self._json(502, {"error": f"模型服务连不上：{exc}. 检查 base_url 和服务是否在运行。"})
            except Exception as exc:  # surface model errors to the page instead of a blank 500
                return self._json(500, {"error": f"{type(exc).__name__}: {exc}"})
            return self._json(200, {"raw": raw, "latency_s": time.perf_counter() - start})
        if self.path == "/api/presets":
            name = re.sub(r"[^\w.-]", "_", str(data.get("name") or "").strip())[:60]
            if not name or name.startswith("."):
                return self._json(400, {"error": "preset name is empty"})
            if not isinstance(data.get("preset"), dict) or data["preset"].get("kind") != "evibound-demo-preset":
                return self._json(400, {"error": "preset must be an evibound-demo-preset object"})
            PRESETS.mkdir(exist_ok=True)
            payload = dict(data["preset"])
            payload["saved_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            (PRESETS / f"{name}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            return self._json(200, {"saved": f"demo/presets/{name}.json"})
        return self._json(404, {"error": "unknown endpoint"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"EviBound demo: http://127.0.0.1:{args.port}/  (Ctrl-C to stop)")
    server.serve_forever()


if __name__ == "__main__":
    main()
