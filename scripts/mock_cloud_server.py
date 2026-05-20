from __future__ import annotations

import argparse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="本地 mock 云端服务：接收 OrangePi 上传的跟踪统计数据")
    parser.add_argument("--host", default="0.0.0.0", help="绑定地址，默认允许局域网访问")
    parser.add_argument("--port", type=int, default=9000, help="服务端口")
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "cloud_uploads"),
        help="接收到的 JSON 保存目录",
    )
    return parser.parse_args()


class CloudStore:
    def __init__(self, output_dir: str) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save(self, payload: dict) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_name = str(payload.get("run_name") or "tracking_run").replace(os.sep, "_")
        path = self.output_dir / f"{timestamp}_{run_name}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def list_uploads(self) -> list[str]:
        return [path.name for path in sorted(self.output_dir.glob("*.json"))]


class MockCloudServer(ThreadingHTTPServer):
    def __init__(self, server_address, handler_class, store: CloudStore):
        super().__init__(server_address, handler_class)
        self.store = store


class MockCloudHandler(BaseHTTPRequestHandler):
    server: MockCloudServer

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json({"ok": True})
            return
        if path in {"/", "/uploads"}:
            self._send_json({"uploads": self.server.store.list_uploads()})
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/tracking-runs":
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "invalid JSON")
            return

        saved_path = self.server.store.save(payload)
        print(f"收到上传数据，已保存: {saved_path}")
        self._send_json({"ok": True, "saved": str(saved_path)})

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> int:
    args = parse_args()
    store = CloudStore(args.output_dir)
    server = MockCloudServer((args.host, args.port), MockCloudHandler, store)
    print(f"mock 云端服务已启动: http://{args.host}:{args.port}")
    print("上传接口: POST /api/tracking-runs")
    print("按 Ctrl+C 停止。")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nmock 云端服务已停止。")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
