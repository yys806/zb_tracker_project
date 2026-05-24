from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import socket
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="上传最新跟踪日志摘要到云端 HTTP 接口")
    parser.add_argument(
        "--endpoint",
        default="http://127.0.0.1:9000/api/tracking-runs",
        help="云端接收地址，例如 http://电脑IP:9000/api/tracking-runs",
    )
    parser.add_argument("--logs-dir", default=str(PROJECT_ROOT / "logs"), help="日志根目录")
    parser.add_argument("--run-dir", default=None, help="指定 logs/<timestamp> 目录；不指定则自动选择最新一次")
    parser.add_argument(
        "--benchmark-json",
        default=str(PROJECT_ROOT / "benchmark_results" / "morphology_benchmark.json"),
        help="可选的形态学 benchmark JSON 路径",
    )
    parser.add_argument("--timeout", type=float, default=5.0, help="上传超时时间，单位秒")
    parser.add_argument("--dry-run", action="store_true", help="只打印将要上传的 JSON，不真正发送")
    return parser.parse_args()


def find_latest_run(logs_dir: Path) -> Path:
    candidates = [
        path
        for path in logs_dir.iterdir()
        if path.is_dir() and (path / "summary.json").exists()
    ]
    if not candidates:
        raise FileNotFoundError(f"没有在 {logs_dir} 下找到包含 summary.json 的日志目录")
    return sorted(candidates)[-1]


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(run_dir: Path, benchmark_json: Path | None) -> dict:
    summary = read_json(run_dir / "summary.json") or {}
    analysis = read_json(run_dir / "analysis" / "tracking_analysis.json")
    benchmark = read_json(benchmark_json) if benchmark_json is not None else None
    frames_csv = run_dir / "frames.csv"

    payload = {
        "project": "OrangePi 两自由度云台目标跟踪系统",
        "device": socket.gethostname(),
        "uploaded_at": datetime.now().isoformat(timespec="seconds"),
        "run_name": run_dir.name,
        "run_dir": str(run_dir),
        "summary": summary,
        "analysis": analysis,
        "benchmark": benchmark,
        "artifacts": {
            "frames_csv": str(frames_csv) if frames_csv.exists() else None,
            "summary_json": str(run_dir / "summary.json"),
            "analysis_dir": str(run_dir / "analysis") if (run_dir / "analysis").exists() else None,
        },
    }
    return payload


def upload(endpoint: str, payload: dict, timeout: float) -> tuple[int, str]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8", errors="replace")


def main() -> int:
    args = parse_args()
    run_dir = Path(args.run_dir) if args.run_dir else find_latest_run(Path(args.logs_dir))
    benchmark_json = Path(args.benchmark_json) if args.benchmark_json else None
    payload = build_payload(run_dir, benchmark_json)
    output_dir = run_dir / "analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    payload_path = output_dir / "cloud_upload_payload.json"
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.dry_run:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print(f"payload saved: {payload_path}")
        return 0

    try:
        status, body = upload(args.endpoint, payload, args.timeout)
    except HTTPError as exc:
        print(f"上传失败，HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 2
    except URLError as exc:
        print(f"上传失败，无法连接云端接口: {exc}", file=sys.stderr)
        return 2

    print(f"上传成功，HTTP {status}")
    print(body)
    print(f"payload saved: {payload_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
