"""Image/text API client using only Python's standard library; owner: guardsynth-coc."""
import argparse
import base64
import json
import mimetypes
import os
from pathlib import Path
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt")
    parser.add_argument("--image", type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--key-file", type=Path)
    parser.add_argument("--max-tokens", type=int, default=512)
    args = parser.parse_args()
    key = args.key_file.read_text().strip() if args.key_file else os.environ.get("QWEN_API_KEY", "")
    if not key:
        parser.error("Provide --key-file or QWEN_API_KEY")
    content = [{"type": "text", "text": args.prompt}]
    if args.image:
        mime = mimetypes.guess_type(args.image.name)[0]
        if mime not in ("image/png", "image/jpeg", "image/webp"):
            parser.error("Image must be PNG, JPEG, or WebP")
        encoded = base64.b64encode(args.image.read_bytes()).decode()
        content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}})
    payload = {"model": "qwen3-vl-8b", "messages": [{"role": "user", "content": content}],
               "max_tokens": args.max_tokens, "temperature": 0}
    request = urllib.request.Request(args.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(), headers={"Content-Type": "application/json",
                                                   "Authorization": "Bearer " + key})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=180) as response:
        result = json.load(response)
    print(result["choices"][0]["message"]["content"])
    print(json.dumps({"finish_reason": result["choices"][0]["finish_reason"], "usage": result["usage"]}))


if __name__ == "__main__":
    main()
