from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import threading
import time
from urllib.parse import urlparse

import cv2


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OrangePi 云台远程控制台</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #08110f;
      --panel: rgba(18, 34, 29, 0.92);
      --panel-2: rgba(255, 255, 255, 0.06);
      --line: rgba(255, 255, 255, 0.12);
      --text: #eef7ef;
      --muted: #9bb3aa;
      --accent: #f2b84b;
      --danger: #ff6b5f;
      --ok: #5ee6a8;
      --blue: #5db7ff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", "Noto Sans SC", sans-serif;
      background:
        radial-gradient(circle at 12% 6%, rgba(242, 184, 75, 0.20), transparent 28rem),
        radial-gradient(circle at 88% 10%, rgba(93, 183, 255, 0.16), transparent 24rem),
        linear-gradient(135deg, #060b0a, var(--bg));
      color: var(--text);
    }
    main {
      width: min(1320px, calc(100vw - 28px));
      margin: 0 auto;
      padding: 24px 0 32px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: end;
      gap: 16px;
      margin-bottom: 18px;
    }
    h1 {
      margin: 0;
      font-size: clamp(1.9rem, 4vw, 3.4rem);
      letter-spacing: -0.05em;
    }
    p { margin: 8px 0 0; color: var(--muted); line-height: 1.65; }
    .badge {
      border: 1px solid rgba(242, 184, 75, 0.45);
      border-radius: 999px;
      color: var(--accent);
      padding: 8px 14px;
      white-space: nowrap;
      background: rgba(242, 184, 75, 0.08);
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(330px, 0.85fr);
      gap: 16px;
      align-items: start;
    }
    .frame, .panel {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: 0 24px 70px rgba(0, 0, 0, 0.32);
      overflow: hidden;
    }
    .frame img {
      display: block;
      width: 100%;
      height: auto;
      background: #050807;
    }
    .panel {
      padding: 16px;
    }
    .panel h2 {
      margin: 0 0 12px;
      font-size: 1rem;
      color: var(--accent);
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 14px;
    }
    .stat {
      border-radius: 16px;
      background: var(--panel-2);
      padding: 12px;
      min-height: 68px;
    }
    .stat span {
      display: block;
      color: var(--muted);
      font-size: 0.78rem;
    }
    .stat strong {
      display: block;
      margin-top: 6px;
      font-size: 1.16rem;
      overflow-wrap: anywhere;
    }
    .row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 10px 0;
    }
    button, select, input {
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(255,255,255,0.08);
      color: var(--text);
      padding: 9px 11px;
      font: inherit;
    }
    select { min-width: 140px; }
    button {
      cursor: pointer;
      transition: transform 0.12s ease, border-color 0.12s ease, background 0.12s ease;
    }
    button:hover { transform: translateY(-1px); border-color: rgba(242,184,75,0.55); }
    button.primary { background: rgba(242,184,75,0.16); color: var(--accent); }
    button.danger { background: rgba(255,107,95,0.15); color: var(--danger); }
    button.safe { background: rgba(94,230,168,0.12); color: var(--ok); }
    .hsv-card {
      border-radius: 16px;
      background: var(--panel-2);
      padding: 12px;
      margin-top: 10px;
    }
    .hsv-title {
      color: var(--muted);
      font-size: 0.86rem;
      margin-bottom: 8px;
    }
    .hsv-grid {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    label {
      display: grid;
      gap: 5px;
      color: var(--muted);
      font-size: 0.78rem;
    }
    input[type="number"] {
      width: 100%;
      padding: 8px 9px;
    }
    .message {
      color: var(--muted);
      min-height: 1.4em;
      margin-top: 12px;
      overflow-wrap: anywhere;
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
    @media (max-width: 960px) {
      .grid { grid-template-columns: 1fr; }
      header { align-items: start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>OrangePi 云台控制台</h1>
        <p>实时监控、颜色切换、HSV 调参、中心自动标定、急停和回中都在这里完成。</p>
      </div>
      <div class="badge">MJPEG + Control API</div>
    </header>
    <section class="grid">
      <div class="frame">
        <img src="/stream.mjpg" alt="OrangePi tracking stream" />
      </div>
      <aside class="panel">
        <h2>实时状态</h2>
        <div class="stats">
          <div class="stat"><span>状态</span><strong id="state">-</strong></div>
          <div class="stat"><span>FPS</span><strong id="fps">-</strong></div>
          <div class="stat"><span>目标</span><strong id="target">-</strong></div>
          <div class="stat"><span>pan / tilt</span><strong id="angles">-</strong></div>
          <div class="stat"><span>面积 / 置信度</span><strong id="quality">-</strong></div>
          <div class="stat"><span>颜色 / 后端</span><strong id="mode">-</strong></div>
        </div>

        <h2>颜色与 HSV</h2>
        <div class="row">
          <select id="colorSelect"></select>
          <button class="primary" id="applyColor">切换颜色</button>
          <button class="safe" id="calibrate">中心自动标定</button>
        </div>
        <div id="hsvEditor"></div>
        <div class="row">
          <button class="primary" id="applyHsv">应用 HSV</button>
          <button id="saveConfig">保存配置</button>
        </div>

        <h2>云台安全</h2>
        <div class="row">
          <button class="danger" id="stop">急停</button>
          <button class="safe" id="resume">恢复跟踪</button>
          <button class="primary" id="center">回中</button>
        </div>
        <div class="message" id="message">正在连接控制台...</div>
      </aside>
    </section>
    <section class="tips">
      <div class="tip">真实模式下急停会暂停舵机动作；恢复后继续根据目标偏差跟踪。</div>
      <div class="tip">自动标定前，把目标放在画面中心十字线附近，再点击按钮。</div>
      <div class="tip">如果网页打不开，先跑 <code>bash scripts/run/10_network_check.sh</code>。</div>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    let statusCache = null;
    let hsvTouched = false;

    async function api(path, body = null) {
      const init = body === null
        ? {}
        : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
      const res = await fetch(path, init);
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        throw new Error(data.error || `request failed: ${path}`);
      }
      return data;
    }

    function rangeInput(rangeIndex, side, axis, value, max) {
      return `<label>${side}.${axis}<input type="number" min="0" max="${max}" data-range="${rangeIndex}" data-side="${side}" data-axis="${axis}" value="${value}"></label>`;
    }

    function renderHsvEditor(ranges) {
      if (hsvTouched) return;
      const cards = ranges.map((range, index) => {
        const lower = range.lower;
        const upper = range.upper;
        return `<div class="hsv-card">
          <div class="hsv-title">HSV 范围 ${index + 1}</div>
          <div class="hsv-grid">
            ${rangeInput(index, "lower", "h", lower[0], 180)}
            ${rangeInput(index, "lower", "s", lower[1], 255)}
            ${rangeInput(index, "lower", "v", lower[2], 255)}
            ${rangeInput(index, "upper", "h", upper[0], 180)}
            ${rangeInput(index, "upper", "s", upper[1], 255)}
            ${rangeInput(index, "upper", "v", upper[2], 255)}
          </div>
        </div>`;
      }).join("");
      $("hsvEditor").innerHTML = cards;
      document.querySelectorAll("#hsvEditor input").forEach((input) => {
        input.addEventListener("input", () => { hsvTouched = true; });
      });
    }

    function readHsvEditor() {
      const ranges = [];
      document.querySelectorAll("#hsvEditor input").forEach((input) => {
        const index = Number(input.dataset.range);
        const side = input.dataset.side;
        const axis = input.dataset.axis;
        const axisIndex = {h: 0, s: 1, v: 2}[axis];
        if (!ranges[index]) ranges[index] = { lower: [0, 0, 0], upper: [0, 0, 0] };
        ranges[index][side][axisIndex] = Number(input.value);
      });
      return ranges;
    }

    function updateStatus(data) {
      statusCache = data;
      $("state").textContent = data.emergency_stop ? `${data.state} / STOP` : data.state;
      $("fps").textContent = `${data.fps}`;
      $("target").textContent = data.target_found ? "FOUND" : "LOST";
      $("target").style.color = data.target_found ? "var(--ok)" : "var(--danger)";
      $("angles").textContent = `${data.pan} / ${data.tilt}`;
      $("quality").textContent = `${data.area} / ${data.confidence}`;
      $("mode").textContent = `${data.color_name} / ${data.backend}`;
      $("message").textContent = data.message || "";

      const select = $("colorSelect");
      if (select.options.length === 0) {
        data.available_colors.forEach((color) => {
          const opt = document.createElement("option");
          opt.value = color;
          opt.textContent = color;
          select.appendChild(opt);
        });
      }
      select.value = data.color_name;
      renderHsvEditor(data.hsv_ranges);
    }

    async function refreshStatus() {
      try {
        const data = await api("/api/status");
        updateStatus(data);
      } catch (err) {
        $("message").textContent = err.message;
      }
    }

    async function postAndRefresh(path, body = {}) {
      try {
        const data = await api(path, body);
        hsvTouched = false;
        updateStatus(data.status || data);
      } catch (err) {
        $("message").textContent = err.message;
      }
    }

    $("applyColor").onclick = () => postAndRefresh("/api/color", { color: $("colorSelect").value });
    $("applyHsv").onclick = () => postAndRefresh("/api/hsv", { ranges: readHsvEditor() });
    $("calibrate").onclick = () => postAndRefresh("/api/calibrate");
    $("saveConfig").onclick = () => postAndRefresh("/api/save-config");
    $("stop").onclick = () => postAndRefresh("/api/stop");
    $("resume").onclick = () => postAndRefresh("/api/resume");
    $("center").onclick = () => postAndRefresh("/api/center");

    refreshStatus();
    setInterval(refreshStatus, 1000);
  </script>
</body>
</html>
""".encode("utf-8")


class MjpegServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self, server_address, request_handler_class, app, jpeg_quality: int, stream_fps: float):
        super().__init__(server_address, request_handler_class)
        self.app = app
        self.jpeg_quality = max(30, min(95, int(jpeg_quality)))
        self.stream_fps = max(1.0, min(30.0, float(stream_fps)))
        self.frame_condition = threading.Condition()
        self.latest_jpeg: bytes | None = None
        self.latest_frame_id = 0
        self.stop_event = threading.Event()
        self.producer_thread = threading.Thread(target=self._produce_frames, name="mjpeg-producer", daemon=True)

    def start_stream(self) -> None:
        self.producer_thread.start()

    def stop_stream(self) -> None:
        self.stop_event.set()
        with self.frame_condition:
            self.frame_condition.notify_all()
        self.producer_thread.join(timeout=2.0)

    def _produce_frames(self) -> None:
        interval = 1.0 / self.stream_fps
        while not self.stop_event.is_set():
            started = time.perf_counter()
            ok, frame = self.app.read_web_frame()
            if ok and frame is not None:
                encoded_ok, encoded = cv2.imencode(
                    ".jpg",
                    frame,
                    [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality],
                )
                if encoded_ok:
                    with self.frame_condition:
                        self.latest_jpeg = encoded.tobytes()
                        self.latest_frame_id += 1
                        self.frame_condition.notify_all()

            elapsed = time.perf_counter() - started
            remaining = interval - elapsed
            if remaining > 0:
                self.stop_event.wait(remaining)


class MjpegHandler(BaseHTTPRequestHandler):
    server: MjpegServer

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in {"/", "/index.html"}:
            self._send_index()
            return
        if parsed.path == "/stream.mjpg":
            self._send_stream()
            return
        if parsed.path == "/health":
            self._send_text("ok\n", "text/plain; charset=utf-8")
            return
        if parsed.path == "/api/status":
            self._send_json(self.server.app.get_console_status())
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
            app = self.server.app
            if parsed.path == "/api/color":
                status = app.set_color(str(body.get("color", "")))
            elif parsed.path == "/api/hsv":
                status = app.set_hsv_ranges(body.get("ranges", []))
            elif parsed.path == "/api/calibrate":
                status = app.calibrate_color()
            elif parsed.path == "/api/save-config":
                status = app.save_runtime_config()
            elif parsed.path == "/api/stop":
                app.stop_motion()
                status = app.get_console_status()
            elif parsed.path == "/api/resume":
                app.resume_motion()
                status = app.get_console_status()
            elif parsed.path == "/api/center":
                app.center_gimbal()
                status = app.get_console_status()
            else:
                self.send_error(404)
                return
            self._send_json({"ok": True, "status": status})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

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

    def _send_json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
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

        last_frame_id = 0
        while True:
            with self.server.frame_condition:
                self.server.frame_condition.wait_for(
                    lambda: self.server.stop_event.is_set() or self.server.latest_frame_id != last_frame_id,
                    timeout=5.0,
                )
                if self.server.stop_event.is_set():
                    break
                if self.server.latest_jpeg is None or self.server.latest_frame_id == last_frame_id:
                    continue
                data = self.server.latest_jpeg
                last_frame_id = self.server.latest_frame_id

            try:
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
                self.wfile.write(data)
                self.wfile.write(b"\r\n")
            except (BrokenPipeError, ConnectionResetError, TimeoutError):
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


def run_mjpeg_server(app, host: str = "0.0.0.0", port: int = 5000, jpeg_quality: int = 70, stream_fps: float = 12.0) -> int:
    server = MjpegServer((host, port), MjpegHandler, app=app, jpeg_quality=jpeg_quality, stream_fps=stream_fps)
    display_host = _guess_lan_ip() if host in {"0.0.0.0", ""} else host
    print(f"网页控制台已启动: http://{display_host}:{port}")
    print(f"推流参数: jpeg_quality={server.jpeg_quality}, stream_fps={server.stream_fps:g}")
    print("按 Ctrl+C 停止。")
    try:
        server.start_stream()
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n网页控制台已停止。")
    finally:
        server.stop_stream()
        server.server_close()
    return 0
