from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from html import escape as html_escape
import json
import socket
import threading
import time
from urllib.parse import urlparse

import cv2


WEB_CONSOLE_VERSION = "v33-gesture-only"


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
    .grid { display: flex; flex-direction: column; gap: 16px; align-items: stretch; }
    .frame, .panel { border: 1px solid var(--line); border-radius: 24px; background: var(--panel); box-shadow: 0 24px 70px rgba(0, 0, 0, 0.32); overflow: hidden; }
    .frame img { display: block; width: 100%; height: auto; background: #050807; }
    .left-column { display: contents; }
    .frame { order: 1; }
    .panel { order: 2; padding: 16px; }
    .insight-grid { order: 3; }
    .grid > .insight-box, .left-column > .insight-box { order: 4; }
    .panel h2 { margin: 18px 0 12px; font-size: 1rem; color: var(--accent); }
    .panel h2:first-child { margin-top: 0; }
    .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 10px; margin-bottom: 14px; }
    .stat { border-radius: 16px; background: var(--panel-2); padding: 12px; min-height: 68px; }
    .stat span { display: block; color: var(--muted); font-size: 0.78rem; }
    .stat strong { display: block; margin-top: 6px; font-size: 1.16rem; overflow-wrap: anywhere; }
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
    .metric-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; margin: 10px 0 14px; }
    .metric-box { border-radius: 16px; background: var(--panel-2); padding: 12px; }
    .metric-box h3 { margin: 0 0 10px; font-size: 0.92rem; color: var(--blue); }
    .metric-line { display: flex; justify-content: space-between; gap: 12px; padding: 4px 0; color: var(--muted); font-size: 0.88rem; }
    .metric-line strong { color: var(--text); font-weight: 600; text-align: right; overflow-wrap: anywhere; }
    .mini-canvas { width: 100%; height: 180px; display: block; border-radius: 12px; background: rgba(0,0,0,0.18); border: 1px solid rgba(255,255,255,0.08); }
    .insight-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
    .insight-box { border: 1px solid var(--line); border-radius: 18px; background: var(--panel); padding: 14px; min-height: 176px; }
    .insight-box h3 { margin: 0 0 10px; color: var(--blue); font-size: 0.96rem; }
    .event-log { max-height: 126px; overflow: hidden; display: grid; gap: 6px; }
    .event-item { color: var(--muted); font-size: 0.82rem; display: flex; gap: 8px; justify-content: space-between; border-bottom: 1px solid rgba(255,255,255,0.06); padding-bottom: 5px; }
    .event-item strong { color: var(--text); font-weight: 600; }
    .ai-actions { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin-bottom: 10px; }
    .ai-output { min-height: 118px; white-space: pre-wrap; color: var(--muted); line-height: 1.55; font-size: 0.9rem; }
    .message { color: var(--muted); min-height: 1.4em; margin-top: 12px; overflow-wrap: anywhere; }
    .tips { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-top: 16px; }
    .tip { border-radius: 18px; background: rgba(255, 255, 255, 0.06); padding: 14px 16px; color: var(--muted); }
    code { color: var(--accent); }
    @media (max-width: 960px) { header { align-items: start; flex-direction: column; } .metric-grid { grid-template-columns: 1fr; } }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>OrangePi 云台控制台</h1>
        <p>把目标卡片放在画面中心，点击中心自动标定。标定成功后再开始跟踪；启动后默认不会自动动舵机。</p>
      </div>
        <div class="badge">Auto HSV + Gesture · v33-gesture-only</div>
    </header>
    <section class="grid">
      <div class="left-column">
        <div class="frame"><img src="/stream.mjpg" alt="OrangePi tracking stream" /></div>
        <div class="insight-grid">
          <div class="insight-box">
            <h3>画面质量检测</h3>
            <div class="metric-line"><span>曝光</span><strong id="qualityExposure">-</strong></div>
            <div class="metric-line"><span>亮度</span><strong id="qualityBrightness">-</strong></div>
            <div class="metric-line"><span>对比度</span><strong id="qualityContrast">-</strong></div>
            <div class="metric-line"><span>清晰度</span><strong id="qualitySharpness">-</strong></div>
            <div class="metric-line"><span>遮挡</span><strong id="qualityOcclusion">-</strong></div>
          </div>
          <div class="insight-box">
            <h3>帧率与延迟</h3>
            <div class="metric-line"><span>实时 FPS</span><strong id="perfFps">-</strong></div>
            <div class="metric-line"><span>检测</span><strong id="perfDetect">-</strong></div>
            <div class="metric-line"><span>控制</span><strong id="perfControl">-</strong></div>
            <div class="metric-line"><span>光流</span><strong id="perfFlow">-</strong></div>
            <div class="metric-line"><span>质量</span><strong id="perfQuality">-</strong></div>
          </div>
          <div class="insight-box">
            <h3>事件日志</h3>
            <div class="event-log" id="eventLog"></div>
          </div>
        </div>
        <div class="insight-box">
          <h3>大模型分析</h3>
          <div class="ai-actions">
            <button class="primary" id="aiStatus" type="button">状态解释</button>
            <button class="primary" id="aiVision" type="button">视觉解释</button>
            <button class="primary" id="aiDiagnosis" type="button">异常诊断</button>
          </div>
          <div class="ai-output" id="aiOutput">DeepSeek API 未配置时不会发起请求。请在后端填入 API Key 后使用。</div>
        </div>
      </div>
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

        <h2>视觉前端</h2>
        <div class="metric-grid">
          <div class="metric-box">
            <h3>HSV 主线</h3>
            <div class="metric-line"><span>检测方式</span><strong>HSV + OpenCV</strong></div>
            <div class="metric-line"><span>后端</span><strong id="visionBackend">-</strong></div>
            <div class="metric-line"><span>目标就绪</span><strong id="visionReady">-</strong></div>
            <div class="metric-line"><span>自适应 HSV</span><strong id="visionAdaptive">-</strong></div>
          </div>
        </div>
        <h2>光流扩展台</h2>
        <div class="metric-grid">
          <div class="metric-box">
            <h3>运动检测</h3>
            <div class="metric-line"><span>状态</span><strong id="flowState">-</strong></div>
            <div class="metric-line"><span>激活点 / 总点</span><strong id="flowPoints">-</strong></div>
            <div class="metric-line"><span>运动比例</span><strong id="flowRatio">-</strong></div>
            <div class="button-strip" style="margin-top:10px;">
              <form action="/ui/flow-toggle" method="get">
                <button class="primary" id="flowToggle" type="button">显示光流箭头</button>
              </form>
            </div>
          </div>
          <div class="metric-box">
            <h3>光流统计</h3>
            <div class="metric-line"><span>平均幅值</span><strong id="flowMean">-</strong></div>
            <div class="metric-line"><span>中位幅值</span><strong id="flowMedian">-</strong></div>
            <div class="metric-line"><span>最大幅值</span><strong id="flowMax">-</strong></div>
            <div class="metric-line"><span>平均位移</span><strong id="flowVector">-</strong></div>
          </div>
          <div class="metric-box">
            <h3>轨迹回放</h3>
            <div class="metric-line"><span>速度</span><strong id="motionSpeed">-</strong></div>
            <div class="metric-line"><span>平滑速度</span><strong id="motionSmooth">-</strong></div>
            <div class="metric-line"><span>方向</span><strong id="motionHeading">-</strong></div>
            <canvas id="trajectoryCanvas" class="mini-canvas" width="480" height="180"></canvas>
          </div>
          <div class="metric-box">
            <h3>区域热力图</h3>
            <canvas id="heatmapCanvas" class="mini-canvas" width="480" height="180"></canvas>
          </div>
        </div>

        <h2>手势识别扩展</h2>
        <div class="metric-grid">
          <div class="metric-box">
            <h3>手势状态</h3>
            <div class="metric-line"><span>开关</span><strong id="gestureEnabled">-</strong></div>
            <div class="metric-line"><span>后端</span><strong id="gestureBackend">-</strong></div>
            <div class="metric-line"><span>识别结果</span><strong id="gestureLabel">-</strong></div>
            <div class="metric-line"><span>手指数</span><strong id="gestureFingers">-</strong></div>
            <div class="metric-line"><span>置信度</span><strong id="gestureConfidence">-</strong></div>
            <div class="button-strip" style="margin-top:10px;">
              <form action="/ui/gesture-toggle" method="get">
                <button class="primary" id="gestureToggle" type="button">开启手势识别</button>
              </form>
            </div>
          </div>
          <div class="metric-box">
            <h3>轮廓信息</h3>
            <div class="metric-line"><span>面积</span><strong id="gestureArea">-</strong></div>
            <div class="metric-line"><span>中心</span><strong id="gestureCenter">-</strong></div>
            <div class="metric-line"><span>缺陷数</span><strong id="gestureDefects">-</strong></div>
            <div class="metric-line"><span>耗时</span><strong id="gestureTime">-</strong></div>
          </div>
        </div>

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

    function api(path, body, onSuccess, onError, timeoutMs, onComplete) {
      var xhr = new XMLHttpRequest();
      var done = false;
      var requestTimeout = timeoutMs || 6000;
      xhr.timeout = requestTimeout;
      function finish() {
        if (onComplete) onComplete();
      }
      var timer = window.setTimeout(function () {
        if (done) return;
        done = true;
        try { xhr.abort(); } catch (err) {}
        onError(new Error("request timeout: " + path));
        finish();
      }, requestTimeout);

      xhr.ontimeout = function () {
        if (done) return;
        done = true;
        window.clearTimeout(timer);
        onError(new Error("request timeout: " + path));
        finish();
      };

      xhr.onerror = function () {
        if (done) return;
        done = true;
        window.clearTimeout(timer);
        onError(new Error("network error: " + path));
        finish();
      };

      xhr.onreadystatechange = function () {
        if (xhr.readyState !== 4 || done) return;
        done = true;
        window.clearTimeout(timer);
        try {
          var data = JSON.parse(xhr.responseText || "{}");
          if (xhr.status < 200 || xhr.status >= 300 || data.ok === false) {
            onError(new Error(data.error || ("request failed: " + path)));
            finish();
            return;
          }
          onSuccess(data);
        } catch (err) {
          onError(err);
        }
        finish();
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

    var statusPending = false;
    var flowPending = false;

    function formatHsv(ranges) {
      if (!ranges || ranges.length === 0) return "HSV: 未标定";
      var lines = [];
      for (var index = 0; index < ranges.length; index += 1) {
        var range = ranges[index];
        lines.push("范围 " + (index + 1) + ": lower=[" + range.lower.join(", ") + "]  upper=[" + range.upper.join(", ") + "]");
      }
      return lines.join("\\n");
    }

    function getCanvasContext(canvasId) {
      var canvas = $(canvasId);
      if (!canvas || !canvas.getContext) return null;
      return canvas.getContext("2d");
    }

    function fitCanvas(canvas, width, height) {
      if (!canvas) return;
      var nextWidth = width > 0 ? width : 480;
      var nextHeight = height > 0 ? height : 180;
      if (canvas.width !== nextWidth) canvas.width = nextWidth;
      if (canvas.height !== nextHeight) canvas.height = nextHeight;
    }

    function paintPanel(ctx, width, height) {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "rgba(0,0,0,0.18)";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "rgba(255,255,255,0.08)";
      ctx.strokeRect(0.5, 0.5, width - 1, height - 1);
    }

    function drawTrajectory(data) {
      var canvas = $("trajectoryCanvas");
      var ctx = getCanvasContext("trajectoryCanvas");
      if (!canvas || !ctx) return;
      var motion = data.motion || {};
      var points = motion.trajectory || [];
      var frameWidth = data.frame_width || 0;
      var frameHeight = data.frame_height || 0;
      fitCanvas(canvas, canvas.clientWidth || canvas.width || 480, 180);
      paintPanel(ctx, canvas.width, canvas.height);
      if (!points.length || frameWidth <= 0 || frameHeight <= 0) {
        ctx.fillStyle = "rgba(238,247,239,0.65)";
        ctx.font = "12px sans-serif";
        ctx.fillText("No trajectory", 14, 24);
        return;
      }

      var scaleX = canvas.width / frameWidth;
      var scaleY = canvas.height / frameHeight;
      ctx.strokeStyle = "rgba(93, 183, 255, 0.95)";
      ctx.fillStyle = "rgba(242, 184, 75, 0.95)";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (var i = 0; i < points.length; i += 1) {
        var p = points[i];
        var x = p.x * scaleX;
        var y = p.y * scaleY;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      for (var j = 0; j < points.length; j += 1) {
        var point = points[j];
        ctx.beginPath();
        ctx.arc(point.x * scaleX, point.y * scaleY, j === points.length - 1 ? 4 : 2, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    function drawHeatmap(data) {
      var canvas = $("heatmapCanvas");
      var ctx = getCanvasContext("heatmapCanvas");
      if (!canvas || !ctx) return;
      var motion = data.motion || {};
      var heatmap = motion.heatmap || [];
      var rows = motion.heatmap_rows || heatmap.length || 0;
      var cols = motion.heatmap_cols || (heatmap[0] ? heatmap[0].length : 0) || 0;
      fitCanvas(canvas, canvas.clientWidth || canvas.width || 480, 180);
      paintPanel(ctx, canvas.width, canvas.height);
      if (!rows || !cols || !heatmap.length) {
        ctx.fillStyle = "rgba(238,247,239,0.65)";
        ctx.font = "12px sans-serif";
        ctx.fillText("No heatmap", 14, 24);
        return;
      }

      var maxValue = 0;
      for (var r = 0; r < heatmap.length; r += 1) {
        for (var c = 0; c < heatmap[r].length; c += 1) {
          if (heatmap[r][c] > maxValue) maxValue = heatmap[r][c];
        }
      }
      if (maxValue <= 0) maxValue = 1;

      var cellWidth = canvas.width / cols;
      var cellHeight = canvas.height / rows;
      for (var row = 0; row < rows; row += 1) {
        for (var col = 0; col < cols; col += 1) {
          var value = (heatmap[row] && heatmap[row][col]) ? heatmap[row][col] : 0;
          var alpha = 0.08 + (value / maxValue) * 0.82;
          ctx.fillStyle = "rgba(255, 107, 95, " + alpha.toFixed(3) + ")";
          ctx.fillRect(col * cellWidth, row * cellHeight, cellWidth + 1, cellHeight + 1);
        }
      }
    }

    function formatMs(value) {
      return String(value == null ? "-" : value) + " ms";
    }

    function updateQuality(data) {
      var quality = data.quality || {};
      $("qualityExposure").textContent = String(quality.exposure_state || "-").toUpperCase();
      $("qualityExposure").style.color = quality.exposure_state === "normal" ? "var(--ok)" : "var(--accent)";
      $("qualityBrightness").textContent = String(quality.brightness == null ? "-" : quality.brightness);
      $("qualityContrast").textContent = String(quality.contrast == null ? "-" : quality.contrast);
      $("qualitySharpness").textContent = String(quality.sharpness == null ? "-" : quality.sharpness);
      $("qualityOcclusion").textContent = String(quality.occlusion_ratio == null ? "-" : quality.occlusion_ratio);
      $("perfFps").textContent = String(data.fps == null ? "-" : data.fps);
      $("perfDetect").textContent = formatMs(data.detect_time_ms);
      $("perfControl").textContent = formatMs(data.control_time_ms);
      $("perfFlow").textContent = formatMs(data.flow_time_ms);
      $("perfQuality").textContent = formatMs(quality.quality_time_ms);
    }

    function formatEventTime(timestamp) {
      if (!timestamp) return "--:--:--";
      var date = new Date(timestamp * 1000);
      return date.toTimeString().slice(0, 8);
    }

    function updateEventLog(events) {
      var log = $("eventLog");
      if (!log) return;
      var items = events || [];
      if (!items.length) {
        log.innerHTML = '<div class="event-item"><span>等待事件</span><strong>-</strong></div>';
        return;
      }
      var html = [];
      var start = Math.max(0, items.length - 6);
      for (var i = items.length - 1; i >= start; i -= 1) {
        var item = items[i];
        html.push('<div class="event-item"><span>' + String(item.message || "-") + '</span><strong>' + formatEventTime(item.timestamp) + '</strong></div>');
      }
      log.innerHTML = html.join("");
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
      updateQuality(data);
      updateEventLog(data.events);
      if (data.flow) {
        $("flowState").textContent = data.flow.motion_detected ? "MOTION" : "STABLE";
        $("flowState").style.color = data.flow.motion_detected ? "var(--accent)" : "var(--ok)";
        $("flowPoints").textContent = String(data.flow.active_points == null ? "-" : data.flow.active_points) + " / " + String(data.flow.total_points == null ? "-" : data.flow.total_points);
        $("flowRatio").textContent = String(data.flow.motion_ratio == null ? "-" : data.flow.motion_ratio);
        $("flowMean").textContent = String(data.flow.mean_magnitude == null ? "-" : data.flow.mean_magnitude);
        $("flowMedian").textContent = String(data.flow.median_magnitude == null ? "-" : data.flow.median_magnitude);
        $("flowMax").textContent = String(data.flow.max_magnitude == null ? "-" : data.flow.max_magnitude);
        $("flowVector").textContent = "(" + String(data.flow.mean_dx == null ? "-" : data.flow.mean_dx) + ", " + String(data.flow.mean_dy == null ? "-" : data.flow.mean_dy) + ")";
        $("flowToggle").textContent = data.flow.draw_vectors ? "隐藏光流箭头" : "显示光流箭头";
      }
      if (data.motion) {
        $("motionSpeed").textContent = String(data.motion.speed_px_s == null ? "-" : data.motion.speed_px_s) + " px/s";
        $("motionSmooth").textContent = String(data.motion.smoothed_speed_px_s == null ? "-" : data.motion.smoothed_speed_px_s) + " px/s";
        $("motionHeading").textContent = String(data.motion.heading_deg == null ? "-" : data.motion.heading_deg) + " deg";
        drawTrajectory(data);
        drawHeatmap(data);
      }
      $("visionBackend").textContent = String(data.backend || "-");
      $("visionReady").textContent = data.color_ready ? "YES" : "NO";
      $("visionReady").style.color = data.color_ready ? "var(--ok)" : "var(--danger)";
      $("visionAdaptive").textContent = data.adaptive_hsv_enabled ? "ON" : "OFF";
      if (data.gesture) {
        $("gestureEnabled").textContent = data.gesture.enabled ? "ON" : "OFF";
        $("gestureEnabled").style.color = data.gesture.enabled ? "var(--ok)" : "var(--muted)";
        $("gestureBackend").textContent = String(data.gesture.backend || "-");
        $("gestureLabel").textContent = data.gesture.enabled ? (data.gesture.found ? String(data.gesture.label || "-") : "NOT_FOUND") : "DISABLED";
        $("gestureLabel").style.color = data.gesture.found ? "var(--accent)" : "var(--muted)";
        $("gestureFingers").textContent = String(data.gesture.finger_count == null ? "-" : data.gesture.finger_count);
        $("gestureConfidence").textContent = String(data.gesture.confidence == null ? "-" : data.gesture.confidence);
        $("gestureArea").textContent = String(data.gesture.area == null ? "-" : data.gesture.area);
        $("gestureCenter").textContent = "(" + String(data.gesture.center_x == null ? "-" : data.gesture.center_x) + ", " + String(data.gesture.center_y == null ? "-" : data.gesture.center_y) + ")";
        $("gestureDefects").textContent = String(data.gesture.defects == null ? "-" : data.gesture.defects);
        $("gestureTime").textContent = formatMs(data.gesture.gesture_time_ms == null ? data.gesture_time_ms : data.gesture.gesture_time_ms);
        $("gestureToggle").textContent = data.gesture.enabled ? "关闭手势识别" : "开启手势识别";
      }
    }

    function refreshStatus() {
      if (statusPending) return;
      statusPending = true;
      api("/api/status", null, updateStatus, function (err) {
        messageEl.textContent = "状态刷新失败：" + err.message + "。请确认网页地址、端口和后端进程。";
      }, 6000, function () {
        statusPending = false;
      });
    }

    function refreshFlow() {
      if (flowPending) return;
      flowPending = true;
      api("/api/flow", null, function (data) {
        updateStatus(data.status || data);
      }, function () {}, 6000, function () {
        flowPending = false;
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

    function requestAi(kind, button) {
      var output = $("aiOutput");
      var oldText = button ? button.textContent : "";
      if (button) {
        button.disabled = true;
        button.textContent = "分析中...";
      }
      if (output) output.textContent = "正在请求 DeepSeek 分析...";
      api("/api/ai/analyze", {kind: kind}, function (data) {
        if (button) {
          button.disabled = false;
          button.textContent = oldText;
        }
        if (output) output.textContent = data.analysis || "DeepSeek 未返回分析内容";
      }, function (err) {
        if (button) {
          button.disabled = false;
          button.textContent = oldText;
        }
        if (output) output.textContent = err.message;
        messageEl.textContent = err.message;
      }, 20000);
    }

    $("calibrate").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/calibrate", {}, $("calibrate")); return false; };
    $("startTracking").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/start", {}, $("startTracking")); return false; };
    $("stop").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/stop", {}, $("stop")); return false; };
    $("reset").onclick = function (event) { if (event && event.preventDefault) event.preventDefault(); postAndRefresh("/api/reset", {}, $("reset")); return false; };
    $("flowToggle").onclick = function (event) {
      if (event && event.preventDefault) event.preventDefault();
      postAndRefresh("/api/flow-toggle", {}, $("flowToggle"));
      return false;
    };
    $("gestureToggle").onclick = function (event) {
      if (event && event.preventDefault) event.preventDefault();
      postAndRefresh("/api/gesture-toggle", {}, $("gestureToggle"));
      return false;
    };
    $("aiStatus").onclick = function () { requestAi("status", $("aiStatus")); };
    $("aiVision").onclick = function () { requestAi("vision", $("aiVision")); };
    $("aiDiagnosis").onclick = function () { requestAi("diagnosis", $("aiDiagnosis")); };

    window.setTimeout(refreshStatus, 0);
    setInterval(refreshStatus, 1000);
    setInterval(refreshFlow, 3000);
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
        failed_reads = 0
        while not self.stop_event.is_set():
            started = time.perf_counter()
            try:
                ok, frame = self.app.read_web_frame()
                if ok and frame is not None:
                    failed_reads = 0
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
                else:
                    failed_reads += 1
                    if failed_reads in {1, 30, 120}:
                        print(f"camera frame read failed; retrying slowly ({failed_reads})")
                    self.stop_event.wait(0.25 if failed_reads < 30 else 1.0)
            except Exception as exc:
                print(f"mjpeg producer error: {exc}")
                self.stop_event.wait(0.2)
                continue

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
        if parsed.path == "/api/flow":
            self._send_json({"ok": True, "flow": self.server.app.get_flow_status(), "status": self.server.app.get_console_status()})
            return
        if parsed.path == "/api/gesture":
            self._send_json({"ok": True, "gesture": self.server.app.get_gesture_status(), "status": self.server.app.get_console_status()})
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
        if parsed.path == "/ui/flow-toggle":
            self._handle_ui_action(self._toggle_flow_vectors)
            return
        if parsed.path == "/ui/gesture-toggle":
            self._handle_ui_action(self._toggle_gesture)
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
            elif parsed.path == "/api/flow-toggle":
                status = app.set_flow_vectors_visible(not app.flow_vectors_visible)
            elif parsed.path == "/api/gesture-toggle":
                status = app.set_gesture_enabled(not app.config.gesture.enabled)
            elif parsed.path == "/api/ai/analyze":
                result = app.run_ai_analysis(str(body.get("kind", "status")))
                self._send_json(result)
                return
            else:
                self.send_error(404)
                return
            self._send_json({"ok": True, "status": status})
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=400)

    def _handle_ui_action(self, action, return_status: bool = False) -> None:
        try:
            result = action()
            status = self.server.app.get_console_status() if return_status else result
            self._send_redirect("/", status)
        except Exception as exc:
            self._send_html(f"<pre>{html_escape(str(exc))}</pre>", status=400)

    def _toggle_flow_vectors(self):
        return self.server.app.set_flow_vectors_visible(not self.server.app.flow_vectors_visible)

    def _toggle_gesture(self):
        app = self.server.app
        return app.set_gesture_enabled(not app.config.gesture.enabled)

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
        try:
            self.send_response(200)
            self.send_header("Age", "0")
            self.send_header("Cache-Control", "no-cache, private")
            self.send_header("Pragma", "no-cache")
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.end_headers()
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

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
            except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
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
