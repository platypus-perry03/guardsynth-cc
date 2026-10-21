# Qwen VLM API

- owner_project: `guardsynth-coc`
- Model: locally cached `Qwen3-VL-8B-Instruct`, revision
  `0c351dd01ed87e9c1b53cbc748cba10e6187ff3b`; no LoRA adapter.
- Runtime: existing `runtime/alpamayo/ar1_venv`; no dependency installation or
  change to the experiment environment.

From the repository root, start the service on physical GPU 1:

```bash
mkdir -p projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-service-2026-10-21-001
runtime/alpamayo/ar1_venv/bin/python -u -m apps.qwen_vlm.run \
  --host SERVER_IP --port 8000 --gpu 1 \
  --key-file projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-service-2026-10-21-001/api_key.token
```

The key is generated on first start with owner-only file permissions. Share it
with intended clients through a private channel, for example by copying the
file over SSH. Do not put it in source, a URL, or a chat message. Runtime logs,
PID, and service metadata belong in the same restricted run directory.

For the running instance, the PID is in
`projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-service-2026-10-21-001/server.pid`.
It runs as a detached process, not a boot-time system service; after a reboot,
restart it with the command above. Stop only this instance by sending SIGTERM
to the PID in that file after confirming its command is `apps.qwen_vlm.run`.

On another computer, copy `client.py` and the key file, then use Python 3:

```bash
scp jinhyun@SERVER_IP:apps/qwen_vlm/client.py .
scp jinhyun@SERVER_IP:projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-service-2026-10-21-001/api_key.token .
chmod 600 api_key.token
```

```bash
python3 client.py "Describe this image." --image scene.jpg \
  --base-url http://SERVER_IP:8000/v1 --key-file api_key.token
```

The client uses the standard library and sends the image bytes as base64;
the server does not need the client's local file path. The key can also be
supplied through `QWEN_API_KEY`. The server never fetches image URLs or files
named in a request. PNG, JPEG, and WebP are supported, with up to 16 images
and a 16 MiB request limit. Images are resized by the model processor to at
most 802816 pixels per image. Each message supports up to 64 content parts,
including interleaved frame timestamps and images. Inputs plus requested output
are limited to 32768 tokens, and output to 1024 tokens per call. The context
check counts the processor's actual text and image tokens. Authenticated
`GET /health` reports these limits. A GPU memory failure returns HTTP 503
with CUDA memory details so the client can reduce frame count or resolution;
peak allocated/reserved GPU memory and token counts are logged without
request text or images.

Endpoints (all require `Authorization: Bearer <key>`):

- `GET /health`
- `GET /v1/models`
- `POST /v1/chat/completions`: `model: qwen3-vl-8b`, `messages`,
  `max_tokens` (default 512), and `temperature: 0`.

This is a minimal non-streaming chat-completions API, not a complete OpenAI
implementation. One inference runs at a time; concurrent calls receive 429.
`response_format` does not enable constrained JSON decoding; clients should
parse and validate generated JSON themselves.
Request text, images, and authentication headers are not logged. The direct
HTTP endpoint is intended for the agreed lab network, without router port
forwarding. Use an SSH tunnel if accessing across an untrusted network.
Serving uses a bounded image size and context, so it is not a reproduction of
the paper's frozen 12-token evaluation protocol.

The host-side smoke check exercises authentication and real text/image
inference through `SERVER_IP:8000`. Reachability from another computer
depends on lab routing and firewall rules and must be checked there; the
setup does not change firewall rules.

## CoC labeling capacity checks

The service accepts 16 separate 640x360 frames with interleaved timestamps;
32,768 tokens include both the encoded input and the requested output budget.
An official prompt's token count under a different model's tokenizer may
differ from Qwen's count. The API reports the actual encoded input count in
`usage.prompt_tokens`, and memory telemetry is in `server.log`.

To test the actual client request (with output budget set to 1024):

```bash
runtime/alpamayo/ar1_venv/bin/python -u -m apps.qwen_vlm.check_capacity \
  --request-json request.json \
  --key-file projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-service-2026-10-21-001/api_key.token \
  --output-dir projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-capacity-2026-10-21-003
```

The output directory must be new. The check saves request hashes, status,
response, elapsed time, and peak GPU allocation/reservation; it does not save
the key or duplicate the input frames. `--synthetic` instead creates an
explicitly synthetic workload with 10,800 text tokens and 16 authored 640x360
images. This is a capacity probe, not a validation of the official NVIDIA
prompt, actual CARLA frames, or CoC labeling quality.

Completed checks on physical GPU 1 (A100 80GB), with a 1024-token output budget:

| Request | Input tokens including images | Actual output tokens | Time | Peak allocated / reserved GPU memory |
|---|---:|---:|---:|---:|
| Supplied full CoC request and 16 original CARLA PNGs | 14,499 | 32 | 3.105 s | 20455.7 / 21518.0 MiB |
| Synthetic 10,800-token text and 16 authored frames | 14,519 | 1,024 | 30.993 s | 20460.8 / 21518.0 MiB |

The [actual-request record](../../projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-capacity-2026-10-21-002/RESULT.json)
returns HTTP 200, `finish_reason: stop`, and a parseable JSON object with
`ego_behavior_schema.effect_on_ego_behavior`. All 20 supplied checksums pass;
the request was sent byte-for-byte unchanged, and its 16 embedded images match
the original 640x360 PNGs. The human-readable `prompt.txt` includes message
headers; every substantive line is present in the request. Official-source
provenance is recorded in the supplied manifest; the run tests serving, not
independently the accuracy of the driving explanation.
The [synthetic control](../../projects/04-guardsynth-coc/artifacts/restricted/qwen-vlm-service-001/qwen-vlm-capacity-2026-10-21-001/RESULT.json)
reaches the full 1024-token output limit without an out-of-memory error.

Run the HTTP tests without loading model weights:

```bash
runtime/alpamayo/ar1_venv/bin/python -m unittest discover -s apps/qwen_vlm/tests -v
```
