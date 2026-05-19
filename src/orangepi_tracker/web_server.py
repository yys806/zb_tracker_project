from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import threading
import time

import cv2


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OrangePi 云台目标跟踪监控</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0d1714;
      --panel: #14241f;
      --accent: #f2b84b;
      --text: #eef7ef;
      --muted: #9bb3aa;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Noto Sans SC", sans-serif;
      background:
        radial-gradient(circle at 20% 0%, rgba(242, 184, 75, 0.22), transparent 32rem),
        linear-gradient(135deg, #08110f, var(--bg));
      color: var(--text);
    }
    main {
      width: min(1120px, calc(100vw - 32px));
      margin: 0 auto;
      padding: 28px 0 36px;
    }
    header {
      display: flex;
      align-items: end;
      justify-content: space-between;
      gap: 18px;
      margin-bottom: 18px;
    }
    h1 {
      margin: 0;
      font-size: clamp(1.8rem, 4vw, 3.2rem);
      letter-spacing: -0.04em;
    }
    p { color: var(--muted); line-height: 1.7; }
    .badge {
      border: 1px solid rgba(242, 184, 75, 0.5);
      border-radius: 999px;
      color: var(--accent);
      padding: 8px 14px;
      white-space: nowrap;
      background: rgba(242, 184, 75, 0.08);
    }
    .frame {
      overflow: hidden;
      border: 1px solid rgba(255, 255, 255, 0.12);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
    }
    img {
      display: block;
      width: 100%;
      height: auto;
      background: #050807;
    }
    .tips {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .tip {
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.06);
      padding: 14px 16px;
      color: var(--muted);
    }
    code { color: var(--accent); }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>OrangePi 云台监控</h1>
        <p>实时视频流会叠加目标框、中心线、状态、FPS 和 pan/tilt 角度。</p>
      </div>
      <div class="badge">MJPEG Live</div>
    </header>
    <section class="frame">
      <img src="/stream.mjpg" alt="OrangePi tracking stream" />
    </section>
    <section class="tips">
      <div class="tip">退出程序：回到 MobaXterm，按 <code>Ctrl+C</code>。</div>
      <div class="tip">如果画面不刷新：检查摄像头是否被其他程序占用。</div>
      <div class="tip">如果网页打不开：确认电脑和 OrangePi 在同一网络。</div>
    </section>
  </main>
</body>
</html>
""".encode("utf-8")


class MjpegServer(ThreadingHTTPServer):
    def __init__(self, server_address, request_handler_class, app, jpeg_quality: int):
        super().__init__(server_address, request_handler_class)
        self.app = app
        self.jpeg_quality = max(30, min(95, int(jpeg_quality)))
        self.stream_lock = threading.Lock()


class MjpegHandler(BaseHTTPRequestHandler):
    server: MjpegServer

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path in {"/", "/index.html"}:
            self._send_index()
            return
        if self.path == "/stream.mjpg":
            self._send_stream()
            return
        if self.path == "/health":
            self._send_text("ok\n", "text/plain; charset=utf-8")
            return
        self.send_error(404)

    def _send_index(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(INDEX_HTML)))
        self.end_headers()
        self.wfile.write(INDEX_HTML)

    def _send_text(self, text: str, content_type: str) -> None:
        data = text.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_stream(self) -> None:
        self.send_response(200)
        self.send_header("Age", "0")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        with self.server.stream_lock:
            while True:
                ok, frame = self.server.app.read_web_frame()
                if not ok or frame is None:
                    break
                encoded_ok, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.server.jpeg_quality],
                )
                if not encoded_ok:
                    continue
                data = encoded.tobytes()
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(b"Content-Type: image/jpeg\r\n")
                    self.wfile.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
                    self.wfile.write(data)
                    self.wfile.write(b"\r\n")
                    time.sleep(0.001)
                except (BrokenPipeError, ConnectionResetError):
                    break


def _guess_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        return sock.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def run_mjpeg_server(app, host: str = "0.0.0.0", port: int = 5000, jpeg_quality: int = 80) -> int:
    server = MjpegServer((host, port), MjpegHandler, app=app, jpeg_quality=jpeg_quality)
    display_host = _guess_lan_ip() if host in {"0.0.0.0", ""} else host
    print(f"Web monitor running: http://{display_host}:{port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb monitor stopped.")
    finally:
        server.server_close()
    return 0
