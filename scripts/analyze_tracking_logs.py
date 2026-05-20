from __future__ import annotations

import argparse
import csv
import json
import os
from statistics import mean


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze tracking logs and generate report-ready figures")
    parser.add_argument("--run-dir", default=None, help="Path to one logs/<timestamp> directory")
    parser.add_argument("--logs-dir", default=os.path.join(PROJECT_ROOT, "logs"))
    parser.add_argument("--output-dir", default=None)
    return parser.parse_args()


def find_latest_run(logs_dir: str) -> str:
    candidates = []
    if os.path.isdir(logs_dir):
        for name in os.listdir(logs_dir):
            path = os.path.join(logs_dir, name)
            if os.path.isdir(path) and os.path.exists(os.path.join(path, "frames.csv")):
                candidates.append(path)
    if not candidates:
        raise FileNotFoundError(f"No run directory containing frames.csv found under {logs_dir}")
    return sorted(candidates)[-1]


def read_frames(csv_path: str) -> list[dict]:
    with open(csv_path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def to_float(row: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key, default))
    except (TypeError, ValueError):
        return default


def write_summary_csv(output_dir: str, stats: dict) -> str:
    path = os.path.join(output_dir, "tracking_summary_table.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["metric", "value"])
        for key, value in stats.items():
            writer.writerow([key, value])
    return path


def count_state_entries(states: list[str], state_name: str) -> int:
    count = 0
    previous = None
    for state in states:
        if state == state_name and previous != state_name:
            count += 1
        previous = state
    return count


def try_make_plots(output_dir: str, frames: list[dict]) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except Exception as exc:
        print(f"matplotlib unavailable, skip plots: {exc}")
        return []

    indices = list(range(len(frames)))
    fps = [to_float(row, "fps") for row in frames]
    err_x = [abs(to_float(row, "err_x")) for row in frames]
    err_y = [abs(to_float(row, "err_y")) for row in frames]
    pan = [to_float(row, "pan") for row in frames]
    tilt = [to_float(row, "tilt") for row in frames]
    found = [1 if str(row.get("target_found", "")).lower() == "true" else 0 for row in frames]

    outputs: list[str] = []

    def save_line(name: str, title: str, ylabel: str, series: list[tuple[str, list[float]]]) -> None:
        plt.figure(figsize=(10, 4.8))
        for label, values in series:
            plt.plot(indices, values, label=label, linewidth=1.5)
        plt.title(title)
        plt.xlabel("Frame")
        plt.ylabel(ylabel)
        plt.grid(True, alpha=0.25)
        plt.legend()
        plt.tight_layout()
        path = os.path.join(output_dir, name)
        plt.savefig(path, dpi=160)
        plt.close()
        outputs.append(path)

    save_line("fps_curve.png", "Tracking FPS", "FPS", [("fps", fps)])
    save_line("center_error_curve.png", "Center Error", "Pixels", [("|err_x|", err_x), ("|err_y|", err_y)])
    save_line("gimbal_angle_curve.png", "Gimbal Angles", "Degrees", [("pan", pan), ("tilt", tilt)])
    save_line("target_found_curve.png", "Target Found State", "Found", [("target_found", found)])
    return outputs


def write_markdown(output_dir: str, run_dir: str, stats: dict, plot_paths: list[str]) -> str:
    path = os.path.join(output_dir, "tracking_analysis.md")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# Tracking Log Analysis\n\n")
        fh.write(f"- Run directory: `{run_dir}`\n")
        fh.write(f"- Frames: `{stats['frames']}`\n")
        fh.write(f"- Average FPS: `{stats['avg_fps']:.3f}`\n")
        fh.write(f"- Average |err_x|: `{stats['avg_abs_err_x']:.3f}` px\n")
        fh.write(f"- Average |err_y|: `{stats['avg_abs_err_y']:.3f}` px\n")
        fh.write(f"- Max |err_x|: `{stats['max_abs_err_x']:.3f}` px\n")
        fh.write(f"- Max |err_y|: `{stats['max_abs_err_y']:.3f}` px\n")
        fh.write(f"- Found ratio: `{stats['found_ratio']:.3f}`\n")
        fh.write(f"- Lost events: `{stats['lost_events']}`\n\n")
        if plot_paths:
            fh.write("## Figures\n\n")
            for plot in plot_paths:
                fh.write(f"- `{os.path.basename(plot)}`\n")
    return path


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir or find_latest_run(args.logs_dir)
    frames_path = os.path.join(run_dir, "frames.csv")
    summary_path = os.path.join(run_dir, "summary.json")
    output_dir = args.output_dir or os.path.join(run_dir, "analysis")
    os.makedirs(output_dir, exist_ok=True)

    frames = read_frames(frames_path)
    if not frames:
        raise RuntimeError(f"No frame rows found in {frames_path}")

    fps = [to_float(row, "fps") for row in frames]
    found = [str(row.get("target_found", "")).lower() == "true" for row in frames]
    found_rows = [row for row, is_found in zip(frames, found) if is_found]
    error_rows = found_rows or frames
    err_x = [abs(to_float(row, "err_x")) for row in error_rows]
    err_y = [abs(to_float(row, "err_y")) for row in error_rows]
    states = [row.get("state", "") for row in frames]

    stats = {
        "frames": len(frames),
        "avg_fps": mean(fps),
        "avg_abs_err_x": mean(err_x),
        "avg_abs_err_y": mean(err_y),
        "max_abs_err_x": max(err_x),
        "max_abs_err_y": max(err_y),
        "found_ratio": sum(found) / len(found),
        "lost_events": count_state_entries(states, "LOST_SHORT"),
        "search_events": count_state_entries(states, "SEARCH"),
    }

    if os.path.exists(summary_path):
        with open(summary_path, encoding="utf-8") as fh:
            original_summary = json.load(fh)
        stats["summary_avg_reacquire_time"] = original_summary.get("avg_reacquire_time")

    with open(os.path.join(output_dir, "tracking_analysis.json"), "w", encoding="utf-8") as fh:
        json.dump(stats, fh, ensure_ascii=False, indent=2)

    csv_path = write_summary_csv(output_dir, stats)
    plots = try_make_plots(output_dir, frames)
    md_path = write_markdown(output_dir, run_dir, stats, plots)

    print(f"Analyzed run: {run_dir}")
    print(f"Summary CSV:  {csv_path}")
    print(f"Markdown:     {md_path}")
    for plot in plots:
        print(f"Plot:         {plot}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
