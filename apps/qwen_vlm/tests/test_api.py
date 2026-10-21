"""HTTP contract checks without model downloads or GPU allocation."""
import base64
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import urllib.error
import urllib.request

from PIL import Image
from apps.qwen_vlm.run import Backend as ModelBackend, InferenceMemoryError, load_key, make_server


class Backend:
    def __init__(self):
        self.calls = []

    def generate(self, messages, max_tokens):
        self.calls.append((messages, max_tokens))
        return "test answer", 12, 3, "stop"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.server = make_server(self.backend, "test-key", "127.0.0.1", 0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def request(self, path, payload=None, key="test-key", headers=None):
        h = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
        h.update(headers or {})
        req = urllib.request.Request(self.url + path, headers=h,
            data=json.dumps(payload).encode() if payload is not None else None)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            return response.status, json.load(response)

    def payload(self):
        return {"model": "qwen3-vl-8b", "messages": [{"role": "user", "content": "Hello"}]}

    def test_authentication_precedes_inference(self):
        status, _ = self.request("/v1/chat/completions", self.payload(), key="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(self.backend.calls, [])

    def test_key_creation_is_private_and_stable(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "api_key.token"
            key = load_key(path)
            self.assertGreaterEqual(len(key), 24)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(load_key(path), key)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                load_key(path)

    def test_health_and_model_name(self):
        self.assertEqual(self.request("/health")[1]["status"], "ready")
        self.assertEqual(self.request("/v1/models")[1]["data"][0]["id"], "qwen3-vl-8b")

    def test_local_image_round_trip(self):
        image = Image.new("RGB", (8, 6), (255, 0, 0))
        stream = io.BytesIO()
        image.save(stream, "PNG")
        data = base64.b64encode(stream.getvalue()).decode()
        payload = self.payload()
        payload["messages"][0]["content"] = [
            {"type": "text", "text": "What color?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + data}}]
        status, response = self.request("/v1/chat/completions", payload)
        self.assertEqual(status, 200)
        self.assertEqual(response["choices"][0]["message"]["content"], "test answer")
        self.assertEqual(response["usage"]["total_tokens"], 15)
        decoded = self.backend.calls[0][0][0]["content"][1]["image"]
        self.assertEqual(decoded.size, (8, 6))
        self.assertEqual(decoded.getpixel((0, 0)), (255, 0, 0))

    def test_remote_image_and_invalid_output_budget_rejected(self):
        payload = self.payload()
        payload["messages"][0]["content"] = [
            {"type": "image_url", "image_url": {"url": "http://127.0.0.1/private"}}]
        self.assertEqual(self.request("/v1/chat/completions", payload)[0], 400)
        payload = self.payload()
        payload["max_tokens"] = 100000
        self.assertEqual(self.request("/v1/chat/completions", payload)[0], 400)
        self.assertEqual(self.backend.calls, [])

    def test_sixteen_frames_and_sixty_four_parts_are_accepted(self):
        stream = io.BytesIO()
        Image.new("RGB", (8, 6), (255, 0, 0)).save(stream, "PNG")
        url = "data:image/png;base64," + base64.b64encode(stream.getvalue()).decode()
        parts = []
        for frame in range(16):
            parts.extend([{"type": "text", "text": f"Frame at {frame * .5} seconds"},
                          {"type": "image_url", "image_url": {"url": url}}])
        parts.extend([{"type": "text", "text": "Additional context"}] * 32)
        payload = self.payload()
        payload["messages"][0]["content"] = parts
        payload["max_tokens"] = 1024
        self.assertEqual(self.request("/v1/chat/completions", payload)[0], 200)
        self.assertEqual(len(self.backend.calls[0][0][0]["content"]), 64)
        self.assertEqual(self.backend.calls[0][1], 1024)
        parts.append({"type": "text", "text": "One too many"})
        self.assertEqual(self.request("/v1/chat/completions", payload)[0], 400)
        payload["messages"] = [{"role": "user", "content": parts[:32]},
                               {"role": "user", "content": [parts[1]]}]
        self.assertEqual(self.request("/v1/chat/completions", payload)[0], 400)
        self.assertEqual(len(self.backend.calls), 1)

    def test_context_limit_counts_requested_output(self):
        backend = ModelBackend.__new__(ModelBackend)
        backend.processor = SimpleNamespace(apply_chat_template=Mock(
            return_value={"input_ids": SimpleNamespace(shape=(1, 31745))}))
        with self.assertRaisesRegex(ValueError, "32768-token"):
            backend.generate([], 1024)

    def test_gpu_memory_error_is_reported_and_service_recovers(self):
        self.backend.torch = SimpleNamespace(cuda=SimpleNamespace(empty_cache=Mock()))
        original = self.backend.generate
        self.backend.generate = Mock(side_effect=InferenceMemoryError("GPU memory insufficient: test CUDA detail"))
        status, body = self.request("/v1/chat/completions", self.payload())
        self.assertEqual(status, 503)
        self.assertIn("test CUDA detail", body["error"]["message"])
        self.backend.torch.cuda.empty_cache.assert_called_once()
        self.backend.generate = original
        self.assertEqual(self.request("/v1/chat/completions", self.payload())[0], 200)

    def test_busy_returns_429(self):
        started, release = threading.Event(), threading.Event()
        def blocking(_messages, _max_tokens):
            started.set()
            release.wait(5)
            return "done", 1, 1, "stop"
        self.backend.generate = blocking
        thread = threading.Thread(target=lambda: self.request("/v1/chat/completions", self.payload()))
        thread.start()
        try:
            self.assertTrue(started.wait(2))
            self.assertEqual(self.request("/v1/chat/completions", self.payload())[0], 429)
        finally:
            release.set()
            thread.join()


if __name__ == "__main__":
    unittest.main()
