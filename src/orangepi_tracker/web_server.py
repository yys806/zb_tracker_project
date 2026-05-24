from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape as html_escape
import json
import socket
import threading
import time
from urllib.parse import urlparse

import cv2


WEB_CONSOLE_VERSION = "v27-status-reset-smooth"


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>OrangePi 云台控制台</title>
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
    main { width: min(1320px, calc(100vw - 28px)); margin: 0 auto; padding: 24px 0 32px; }
    header { display: flex; justify-content: space-between; align-items: end; gap: 16px; margin-bottom: 18px; }
    h1 { margin: 0; font-size: clamp(1.9rem, 4vw, 3.4rem); letter-spacing: -0.05em; }
    p { margin: 8px 0 0; color: var(--muted); line-height: 1.65; }
    .badge { border: 1px solid rgba(242, 184, 75, 0.45); border-radius: 999px; color: var(--accent); padding: 8px 14px; white-space: nowrap; background: rgba(242, 184, 75, 0.08); }
    .grid { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(330px, 0.85fr); gap: 16px; align-items: start; }
    .frame, .panel { border: 1px solid var(--line); border-radius: 24px; background: var(--panel); box-shadow: 0 24px 70px rgba(0, 0, 0, 0.32); overflow: hidden; }
    .frame img { display: block; width: 100%; height: auto; background: #050807; }
    .panel { padding: 16px; }
    .panel h2 { margin: 0 0 12px; font-size: 1rem; color: var(--accent); }
    .stats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 14px; }
    .stat { border-radius: 16px; background: var(--panel-2); padding: 12px; min-height: 68px; }
    .stat span { display: block; color: var(--muted); font-size: 0.78rem; }
    .stat strong { display: block; margin-top: 6px; font-size: 1.16rem; overflow-wrap: anywhere; }
    .row { display: flex; gap: 8px; flex-wrap: wrap; margin: 10px 0; }
    .button-strip { display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 12px; }
    .button-strip form { margin: 0; flex: 1 1 120px; min-width: 0; }
    .button-strip button { width: 100%; min-height: 40px; }
    button { border: 1px solid var(--line); border-radius: 12px; background: rgba(255,255,255,0.08); color: var(--text); padding: 8px 10px; font: inherit; cursor: pointer; transition: transform 0.12s ease, border-color 0.12s ease, background 0.12s ease; }
    button:hover { transform: translateY(-1px); border-color: rgba(242,184,75,0.55); }
    button:disabled { cursor: wait; opacity: 0.58; transform: none; }
    button.primary { background: rgba(242,184,75,0.16); color: var(--accent); }
    button.danger { background: rgba(255,107,95,0.15); color: var(--danger); }
    button.safe { background: rgba(94,230,168,0.12); color: var(--ok); }
    .hsv-readout { border-radius: 16px; background: var(--panel-2); padding: 12px; margin: 10px 0 14px; color: var(--muted); white-space: pre-wrap; overflow-wrap: anywhere; font-family: Consolas, "Courier New", monospace; font-size: 0.86rem; line-height: 1.55; }
    .message { color: var(--muted); min-height: 1.4em; margin-top: 12px; overflow-wrap: anywhere; }
    .tips { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 16px; }
    .tip { border-radius: 18px; background: rgba(255, 255, 255, 0.06); padding: 14px 16px; color: var(--muted); }
    code { color: var(--accent); }
    @media (max-width: 960px) { .grid { grid-template-columns: 1fr; } header { align-items: start; flex-direction: column; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>OrangePi 云台控制台</h1>
        <p>把目标卡片放在画面中心，点击中心自动标定。标定成功后再开始跟踪；启动后默认不会自动动舵机。</p>
      </div>
      <div class="badge">Auto HSV + MJPEG · v27-status-reset-smooth</div>
    </header>
    <section class="grid">
      <div class="frame"><img src="/stream.mjpg" alt="OrangePi tracking stream" /></div>
      <aside class="panel">
        <h2>实时状态</h2>
        <div class="stats">
          <div class="stat"><span>状态 / 跟踪</span><strong id="state">-</strong></div>
          <div class="stat"><span>FPS</span><strong id="fps">-</strong></div>
          <div class="stat"><span>目标</span><strong id="target">-</strong></div>
          <div class="stat"><span>pan / tilt</span><strong id="angles">-</strong></div>
          <div class="stat"><span>面积 / 置信度</span><strong id="quality">-</strong></div>
          <div class="stat"><span>后端 / 自适应</span><strong id="mode">-</strong></div>
        </div>

        <h2>自动标定</h2>
        <p>只需要中心自动标定。系统会显示当前追踪 HSV，不需要手动调 HSV。</p>
        <div class="button-strip">
          <form action="/ui/calibrate" method="get">
            <button class="safe" id="calibrate" type="submit">中心自动标定</button>
          </form>
        </div>
        <div class="hsv-readout" id="hsvReadout">HSV: -</div>

        <h2>云台安全</h2>
        <div class="button-strip">
          <form action="/ui/start" method="get">
            <button class="safe" id="startTracking" type="submit">开始跟踪</button>
          </form>
          <form action="/ui/stop" method="get">
            <button class="danger" id="stop" type="submit">急停</button>
          </form>
          <form action="/ui/reset" method="get">
            <button class="primary" id="reset" type="submit">复位</button>
          </form>
        </div>
        <div class="message" id="message">表单控制已可用；如果实时状态不刷新，按钮仍然可以直接控制云台。</div>
      </aside>
    </section>
    <section class="tips">
      <div class="tip">程序启动后不会自动追踪，也不会自动回中。必须先中心自动标定，再点击开始跟踪。</div>
      <div class="tip">如果目标短暂丢失，默认保持当前姿态，不再自动搜索乱扫。</div>
      <div class="tip">如果网页卡顿，优先使用 USB 网口，或降低 <code>--jpeg</code> 参数。</div>
    </section>
  </main>
  <script>
    function $(id) {
      return document.getElementById(id);
    }

    var messageEl = $("message");
    messageEl.textContent = "控制台脚本已加载，正在读取状态...";

    function requestUrl(path) {
      var sep = path.indexOf("?") >= 0 ? "&" : "?";
      return path + sep + "_ts=" + new Date().getTime();
    }

    function api(path, body, onSuccess, onError) {
      var xhr = new XMLHttpRequest();
      var done = false;
      xhr.timeout = 3500;
      var timer = window.setTimeout(function () {
        if (done) return;
        done = true;
        try { xhr.abort(); } catch (err) {}
        onError(new Error("request timeout: " + path));
      }, 3500);

      xhr.ontimeout = function () {
        if (done) return;
        done = true;
        window.clearTimeout(timer);
        onError(new Error("request timeout: " + path));
      };

      xhr.onerror = function () {
        if (done) return;
        done = true;
        window.clearTimeout(timer);
        onError(new Error("network error: " + path));
      };

      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4 || done) return;
        done = true;
        window.clearTimeout(timer);
        try {
          var data = JSON.parse(xhr.responseText || "{}");
          if (xhr.status < 200 || xhr.status >= 300 || data.ok === false) {
            onError(new Error(data.error || ("request failed: " + path)));
            return;
          }
          onSuccess(data);
        } catch (err) {
          onError(err);
        }
      };

      xhr.open(body === null ? "GET" : "POST", requestUrl(path), true);
      xhr.setRequestHeader("Cache-Control", "no-store");
      xhr.setRequestHeader("Pragma", "no-cache");
      if (body !== null) {
        xhr.setRequestHeader("Content-Type", "application/json");
        xhr.send(JSON.stringify(body || {}));
      } else {
        xhr.send();
      }
    }

    function formatHsv(ranges) {
      if (!ranges || ranges.length === 0) return "HSV: 未标定";
      var lines = [];
      for (var index = 0; index < ranges.length; index += 1) {
        var range = ranges[index];
        lines.push("范围 " + (index + 1) + ": lower=[" + range.lower.join(", ") + "]  upper=[" + range.upper.join(", ") + "]");
      }
      return lines.join("\\n");
    }

    function updateStatus(data) {
      var runState = data.emergency_stop ? "STOP" : (data.tracking_enabled ? "RUNNING" : (data.color_ready ? "READY" : "NEED_CALIBRATE"));
      $("state").textContent = String(data.state || "-") + " / " + runState;
      $("fps").textContent = String(data.fps == null ? "-" : data.fps);
      $("target").textContent = data.target_found ? "FOUND" : "LOST";
      $("target").style.color = data.target_found ? "var(--ok)" : "var(--danger)";
      $("angles").textContent = String(data.pan == null ? "-" : data.pan) + " / " + String(data.tilt == null ? "-" : data.tilt);
      $("quality").textContent = String(data.area == null ? "-" : data.area) + " / " + String(data.confidence == null ? "-" : data.confidence);
      $("mode").textContent = String(data.backend || "-") + " / " + (data.adaptive_hsv_enabled ? "AUTO" : "FIXED") + (data.stale ? " / STALE" : "");
      $("hsvReadout").textContent = formatHsv(data.hsv_ranges);
      $("message").textContent = data.message || "";
    }

    function refreshStatus() {
      api("/api/status", null, updateStatus, function (err) {
        messageEl.textContent = "状态刷新失败：" + err.message + "。请确认网页地址、端口和后端进程。";
      });
    }

    function postAndRefresh(path, body, button) {
      var oldText = button ? button.textContent : "";
      if (button) {
        button.disabled = true;
        button.textContent = "执行中...";
      }
      api(path, body || {}, function (data) {
        if (button) {
          button.disabled = false;
          button.textContent = oldText;
        }
        updateStatus(data.status || data);
      }, function (err) {
        if (button) {
          button.disabled = false;
          button.textContent = oldText;
        }
        messageEl.textContent = err.message;
      });
    }

    $("calibrate").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/calibrate", {}, $("calibrate")); return false; };
    $("startTracking").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/start", {}, $("startTracking")); return false; };
    $("stop").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/stop", {}, $("stop")); return false; };
    $("reset").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/reset", {}, $("reset")); return false; };

    window.setTimeout(refreshStatus, 0);
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
        if parsed.path == "/ui/calibrate":
            self._handle_ui_action(self.server.app.calibrate_color)
            return
        if parsed.path == "/ui/start":
            self._handle_ui_action(self.server.app.start_tracking)
            return
        if parsed.path == "/ui/stop":
            self._handle_ui_action(self.server.app.stop_motion, return_status=True)
            return
        if parsed.path == "/ui/reset":
            self._handle_ui_action(self.server.app.reset_gimbal)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            body = self._read_json()
            app = self.server.app
            if parsed.path == "/api/calibrate":
                status = app.calibrate_color()
            elif parsed.path == "/api/start":
                status = app.start_tracking()
            elif parsed.path == "/api/stop":
                app.stop_motion()
                status = app.get_console_status()
            elif parsed.path == "/api/reset":
                status = app.reset_gimbal()
            else:
                self.send_error(404)
                return
            self._send_json({"ok": True, "status": status})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)

    def _handle_ui_action(self, action, return_status: bool = False) -> None:
        try:
            result = action()
            if return_status:
                status = self.server.app.get_console_status()
            else:
                status = result
            self._send_redirect("/", status)
        except Exception as exc:
            self._send_html(f"<pre>{html_escape(str(exc))}</pre>", status=400)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _send_index(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
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
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_redirect(self, location: str, status_payload: dict | None = None) -> None:
        self.send_response(303)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.end_headers()

    def _send_html(self, html: str, status: int = 200) -> None:
        data = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
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
