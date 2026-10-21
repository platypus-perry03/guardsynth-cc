"""Check a real request or an explicitly synthetic workload; owner: guardsynth-coc."""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
import urllib.error
import urllib.request

from apps.qwen_vlm.run import MODEL


def synthetic_request():
    from PIL import Image, ImageDraw
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    text = "Synthetic capacity test, not an official driving prompt. Context:" + " road" * 12000
    text = tokenizer.decode(tokenizer.encode(text, add_special_tokens=False)[:10800])
    assert len(tokenizer.encode(text, add_special_tokens=False)) == 10800
    content = [{"type": "text", "text": text}]
    for frame in range(16):
        image = Image.new("RGB", (640, 360), (40 + frame * 3, 70, 90))
        ImageDraw.Draw(image).text((20, 20), f"Synthetic frame {frame}, time {-2 + frame * .5:.1f} s", fill="white")
        stream = io.BytesIO()
        image.save(stream, "PNG")
        encoded = base64.b64encode(stream.getvalue()).decode()
        content.extend([{"type": "text", "text": f"Frame timestamp: {-2 + frame * .5:.1f} s"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + encoded}}])
    content.append({"type": "text", "text": "For this capacity test, output the consecutive integers 1 through 2000 separated by spaces. Continue until the output limit; do not summarize."})
    return {"model": "qwen3-vl-8b", "messages": [{"role": "user", "content": content}],
            "temperature": 0, "max_tokens": 1024}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--request-json", type=Path)
    group.add_argument("--synthetic", action="store_true")
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--base-url", default="http://SERVER_IP:8000/v1")
    args = parser.parse_args()
    payload = synthetic_request() if args.synthetic else json.loads(args.request_json.read_text())
    if args.request_json and payload.get("max_tokens") == 1024:
        data = args.request_json.read_bytes()
    else:
        payload["max_tokens"] = 1024
        data = json.dumps(payload).encode()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    manifest = {"project_id": "guardsynth-coc", "task_id": "qwen-vlm-capacity",
        "run_id": args.output_dir.name, "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "RUNNING", "mode": "synthetic" if args.synthetic else "supplied_request",
        "inputs": [str(Path(__file__).relative_to(Path.cwd()))] + ([str(args.request_json)] if args.request_json else []),
        "request_sha256": hashlib.sha256(data).hexdigest(), "request_bytes": len(data),
        "requested_output_tokens": 1024,
        "scope": "Synthetic 10800-token text and 16 authored 640x360 frames; not the official prompt or CARLA video" if args.synthetic else "Supplied request with max_tokens set to 1024"}
    manifest["input_sha256"] = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest()
                                for path in manifest["inputs"]}
    (args.output_dir / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    log_path = args.key_file.parent / "server.log"
    log_offset = log_path.stat().st_size
    request = urllib.request.Request(args.base_url.rstrip("/") + "/chat/completions", data=data,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + args.key_file.read_text().strip()})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    started = time.monotonic()
    try:
        response = opener.open(request, timeout=900)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        body = json.load(response)
        result = {"project_id": "guardsynth-coc", "task_id": "qwen-vlm-capacity",
            "mode": manifest["mode"], "status": "COMPLETED" if response.status == 200 else "FAILED",
            "http_status": response.status, "elapsed_seconds": round(time.monotonic() - started, 3),
            "response": body, "scope": manifest["scope"]}
    with log_path.open("rb") as log:
        log.seek(log_offset)
        for line in log.read().decode(errors="replace").splitlines():
            if line.startswith('{"event": "inference_memory"'):
                result["gpu_memory"] = json.loads(line)
    (args.output_dir / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
    manifest["status"] = result["status"]
    (args.output_dir / "RUN_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "response"}, indent=2), flush=True)
    print("Usage:", body.get("usage"), flush=True)
    if response.status != 200:
        print(json.dumps(body), flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
