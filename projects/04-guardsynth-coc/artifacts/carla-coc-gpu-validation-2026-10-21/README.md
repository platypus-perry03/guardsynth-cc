# Full official CoC GPU-memory validation bundle

request.json is self-contained: the full official prompt plus 16 individual original 640x360 PNG frames encoded as data URLs. No API key is included. max_tokens=1024. The video message has 32 content parts (16 timestamp texts + 16 images). prompt.txt contains all textual messages, manifest.json gives chronological frame mapping and source hashes, frames/ contains original PNGs.

Run from this directory: `sha256sum -c SHA256SUMS`. Feed request.json through the service parser and Backend.generate(messages, 1024), or POST it after raising request limits. Record prompt/completion tokens, peak allocated/reserved GPU memory, inference time, and normal completion/OOM. Do not log Authorization headers. This is the full-prompt test, not the earlier compact-prompt success.
