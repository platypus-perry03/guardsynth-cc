"""Authenticated image/text chat API using the existing Transformers runtime.

Owner: guardsynth-coc. Implements non-streaming /v1/chat/completions only.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[2]
MODEL = ROOT / "runtime/alpamayo/hf_cache/models--Qwen--Qwen3-VL-8B-Instruct/snapshots/0c351dd01ed87e9c1b53cbc748cba10e6187ff3b"
MAX_BODY = 16 * 1024 * 1024
MAX_IMAGE_PIXELS = 16_000_000
MAX_CONTEXT_TOKENS = 32768
MAX_IMAGES = 16
MAX_CONTENT_PARTS = 64
MAX_OUTPUT_TOKENS = 1024


class InferenceMemoryError(RuntimeError):
    """GPU allocation failure that can be reported without exposing request data."""


def load_key(path):
    if not path.exists():
        with open(path, "x", opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
            stream.write(secrets.token_urlsafe(32) + "\n")
    if path.stat().st_mode & 0o077:
        raise ValueError("Key file must be readable only by its owner (chmod 600)")
    key = path.read_text().strip()
    if len(key) < 24:
        raise ValueError("Key must contain at least 24 characters")
    return key


def parse_messages(messages):
    from PIL import Image

    if not isinstance(messages, list) or not 1 <= len(messages) <= 32:
        raise ValueError("Provide between 1 and 32 messages")
    result, image_count = [], 0
    for message in messages:
        if not isinstance(message, dict) or message.get("role") not in ("system", "user", "assistant"):
            raise ValueError("Supported roles: system, user, assistant")
        content = message.get("content")
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if not isinstance(content, list) or not 1 <= len(content) <= MAX_CONTENT_PARTS:
            raise ValueError(f"Provide text or between 1 and {MAX_CONTENT_PARTS} text/image_url parts per message")
        parts = []
        for part in content:
            if not isinstance(part, dict):
                raise ValueError("Invalid message part")
            if part.get("type") == "text" and isinstance(part.get("text"), str):
                parts.append({"type": "text", "text": part["text"]})
            elif part.get("type") == "image_url":
                item = part.get("image_url")
                url = item.get("url", "") if isinstance(item, dict) else ""
                if not isinstance(url, str) or not url.startswith(("data:image/png;base64,", "data:image/jpeg;base64,", "data:image/webp;base64,")):
                    raise ValueError("Send PNG/JPEG/WebP as a base64 data URL; remote URLs and file paths are unsupported")
                image_count += 1
                if image_count > MAX_IMAGES:
                    raise ValueError(f"At most {MAX_IMAGES} images per request")
                try:
                    raw = base64.b64decode(url.split(",", 1)[1], validate=True)
                    with Image.open(io.BytesIO(raw)) as image:
                        if image.width * image.height > MAX_IMAGE_PIXELS:
                            raise ValueError("Image exceeds 16 megapixels")
                        rgb = image.convert("RGB")
                except (OSError, binascii.Error, Image.DecompressionBombError) as exc:
                    raise ValueError("Invalid image") from exc
                parts.append({"type": "image", "image": rgb})
            else:
                raise ValueError("Supported content types: text and image_url")
        result.append({"role": message["role"], "content": parts})
    return result


class Backend:
    def __init__(self, model_path):
        import torch
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        if not torch.cuda.is_available():
            raise RuntimeError("CUDA GPU is unavailable in this execution environment")
        torch.set_num_threads(4)
        self.torch = torch
        self.processor = AutoProcessor.from_pretrained(model_path, local_files_only=True,
                                                       max_pixels=1024 * 28 * 28)
        self.model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path, local_files_only=True, dtype=torch.bfloat16,
            attn_implementation="sdpa").to("cuda:0").eval()

    def generate(self, messages, max_tokens):
        inputs = self.processor.apply_chat_template(messages, tokenize=True,
            add_generation_prompt=True, return_dict=True, return_tensors="pt")
        prompt_tokens = inputs["input_ids"].shape[1]
        if prompt_tokens + max_tokens > MAX_CONTEXT_TOKENS:
            raise ValueError(f"Input has {prompt_tokens} tokens; adding {max_tokens} output tokens exceeds the {MAX_CONTEXT_TOKENS}-token service limit")
        self.torch.cuda.reset_peak_memory_stats()
        status = "error"
        try:
            inputs = inputs.to("cuda:0")
            with self.torch.inference_mode():
                output = self.model.generate(**inputs, max_new_tokens=max_tokens, do_sample=False)
            generated = output[0, prompt_tokens:]
            text = self.processor.decode(generated, skip_special_tokens=True)
            eos = self.model.generation_config.eos_token_id
            eos = [eos] if isinstance(eos, int) else (eos or [])
            finish = "stop" if generated[-1].item() in eos else "length"
            status = "ok"
            return text, prompt_tokens, len(generated), finish
        except self.torch.OutOfMemoryError as exc:
            status = "out_of_memory"
            raise InferenceMemoryError(f"GPU memory insufficient; reduce frame count, resolution, or output length. CUDA detail: {exc}") from None
        finally:
            print(json.dumps({"event": "inference_memory", "status": status,
                "prompt_tokens": prompt_tokens, "max_output_tokens": max_tokens,
                "peak_allocated_mib": round(self.torch.cuda.max_memory_allocated() / 2**20, 1),
                "peak_reserved_mib": round(self.torch.cuda.max_memory_reserved() / 2**20, 1)}), flush=True)


def make_server(backend, key, host, port, model_name="qwen3-vl-8b"):
    gate = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # Do not record request text, images, or credentials.

        def respond(self, status, value):
            body = json.dumps(value, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def error(self, status, message):
            self.respond(status, {"error": {"message": message, "type": "request_error"}})

        def authorized(self):
            if not hmac.compare_digest(self.headers.get("Authorization", "").encode(), ("Bearer " + key).encode()):
                self.error(401, "Valid bearer token required")
                return False
            return True

        def do_GET(self):
            if not self.authorized():
                return
            if self.path == "/health":
                self.respond(200, {"status": "ready", "model": model_name,
                    "limits": {"context_tokens": MAX_CONTEXT_TOKENS,
                        "images_per_request": MAX_IMAGES,
                        "content_parts_per_message": MAX_CONTENT_PARTS,
                        "max_output_tokens": MAX_OUTPUT_TOKENS}})
            elif self.path == "/v1/models":
                self.respond(200, {"object": "list", "data": [
                    {"id": model_name, "object": "model", "owned_by": "local"}]})
            else:
                self.error(404, "Unknown endpoint")

        def do_POST(self):
            if not self.authorized():
                return
            if self.path != "/v1/chat/completions":
                return self.error(404, "Unknown endpoint")
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= MAX_BODY or self.headers.get("Transfer-Encoding"):
                    return self.error(413, "Request body must be between 1 byte and 16 MiB")
                self.connection.settimeout(30)
                raw = self.rfile.read(size)
                if len(raw) != size:
                    raise ValueError("Incomplete body")
                request = json.loads(raw)
                if not isinstance(request, dict):
                    raise ValueError("Expected a JSON object")
                if request.get("model") != model_name:
                    return self.error(404, "Unknown model; consult /v1/models")
                if request.get("stream") or request.get("tools"):
                    raise ValueError("Streaming and tool calls are unsupported")
                if request.get("temperature", 0) != 0:
                    raise ValueError("This service uses greedy decoding; use temperature=0")
                cap = request.get("max_tokens", 512)
                if type(cap) is not int or not 1 <= cap <= MAX_OUTPUT_TOKENS:
                    raise ValueError(f"max_tokens must be an integer between 1 and {MAX_OUTPUT_TOKENS}")
                messages = parse_messages(request.get("messages"))
            except (ValueError, TypeError, TimeoutError) as exc:
                return self.error(400, str(exc))
            if not gate.acquire(blocking=False):
                return self.error(429, "Model is busy; retry after the current request completes")
            out_of_memory = False
            try:
                text, prompt, completion, finish = backend.generate(messages, cap)
                self.respond(200, {"id": "chatcmpl-" + uuid.uuid4().hex,
                    "object": "chat.completion", "created": int(time.time()), "model": model_name,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": text},
                                 "finish_reason": finish}],
                    "usage": {"prompt_tokens": prompt, "completion_tokens": completion,
                              "total_tokens": prompt + completion}})
            except ValueError as exc:
                self.error(400, str(exc))
            except InferenceMemoryError as exc:
                out_of_memory = True
                self.error(503, str(exc))
            except Exception as exc:
                print(f"Inference failed: {type(exc).__name__}", flush=True)
                self.error(500, "Inference failed; see the server log")
            finally:
                try:
                    if out_of_memory:
                        backend.torch.cuda.empty_cache()
                finally:
                    gate.release()

    return ThreadingHTTPServer((host, port), Handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, default=MODEL)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--gpu", default="1")
    parser.add_argument("--key-file", type=Path, required=True)
    args = parser.parse_args()
    os.environ["CUDA_VISIBLE_DEVICES"] = args.gpu
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        key = load_key(args.key_file)
    except ValueError as exc:
        parser.error(str(exc))
    print(f"Loading local model on GPU {args.gpu}: {args.model_path}", flush=True)
    backend = Backend(args.model_path)
    server = make_server(backend, key, args.host, args.port)
    print(f"READY http://{args.host}:{server.server_port}/v1 (bearer authentication required)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
