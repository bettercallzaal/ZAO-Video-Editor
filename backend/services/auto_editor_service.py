"""auto-editor integration — automatic silence/dead-air removal from video."""

import subprocess
import json
import os
from pathlib import Path


def preview_silence_cuts(video_path: str, margin: float = 0.1,
                         threshold: float = 0.04) -> dict:
    """Preview what auto-editor would cut without applying changes.

    Returns cut info including original/edited duration and cut list.
    """
    from .ffmpeg_service import get_video_params
    params = get_video_params(video_path)
    original_duration = params["duration"]

    # Export the edit timeline as JSON
    tmpfile = video_path + ".cuts.json"
    cmd = [
        "auto-editor", video_path,
        "--margin", f"{margin}s",
        "--edit", f"audio:threshold={threshold * 100:.0f}%",
        "--export", "json",
        "-o", tmpfile,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"auto-editor preview failed: {result.stderr}")

    cuts = []
    edited_duration = original_duration

    if os.path.exists(tmpfile):
        try:
            with open(tmpfile) as f:
                timeline = json.load(f)

            # Parse the timeline to find removed sections
            # auto-editor JSON format has chunks with speed values
            chunks = timeline.get("chunks", timeline.get("v", []))
            removed_time = 0
            for chunk in chunks:
                if isinstance(chunk, list) and len(chunk) >= 3:
                    start, end, speed = chunk[0], chunk[1], chunk[2]
                    if speed == 0:  # silence (cut)
                        cuts.append({
                            "start": round(start, 2),
                            "end": round(end, 2),
                            "duration": round(end - start, 2),
                        })
                        removed_time += (end - start)
                elif isinstance(chunk, dict):
                    if chunk.get("speed", 1) == 0:
                        s = chunk.get("start", 0)
                        e = chunk.get("end", 0)
                        cuts.append({
                            "start": round(s, 2),
                            "end": round(e, 2),
                            "duration": round(e - s, 2),
                        })
                        removed_time += (e - s)

            edited_duration = original_duration - removed_time
        finally:
            os.remove(tmpfile)

    return {
        "original_duration": round(original_duration, 2),
        "edited_duration": round(edited_duration, 2),
        "removed_seconds": round(original_duration - edited_duration, 2),
        "cut_count": len(cuts),
        "cuts": cuts,
    }


def remove_silence(video_path: str, output_path: str,
                   margin: float = 0.1, threshold: float = 0.04,
                   on_progress=None) -> dict:
    """Remove silence from video using auto-editor.

    Args:
        video_path: Input video path
        output_path: Output video path
        margin: Seconds of padding to keep around speech
        threshold: Audio level threshold (0.0-1.0, lower = more aggressive)
        on_progress: Callback (progress_pct, message)

    Returns dict with duration info.
    """
    from .ffmpeg_service import get_video_params
    params = get_video_params(video_path)
    original_duration = params["duration"]

    if on_progress:
        on_progress(10, "Analyzing audio for silence...")

    cmd = [
        "auto-editor", video_path,
        "--margin", f"{margin}s",
        "--edit", f"audio:threshold={threshold * 100:.0f}%",
        "--video-codec", "libx264",
        "--video-quality", "18",
        "-o", output_path,
        "--no-open",
    ]

    if on_progress:
        on_progress(30, "Removing silent sections...")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise RuntimeError(f"auto-editor failed: {result.stderr}")

    if on_progress:
        on_progress(90, "Calculating results...")

    # Get the output duration
    edited_params = get_video_params(output_path)
    edited_duration = edited_params["duration"]
    removed = original_duration - edited_duration

    if on_progress:
        on_progress(100, f"Removed {removed:.1f}s of silence ({removed/original_duration*100:.0f}% of video)")

    return {
        "original_duration": round(original_duration, 2),
        "edited_duration": round(edited_duration, 2),
        "removed_seconds": round(removed, 2),
        "removed_percent": round(removed / original_duration * 100, 1) if original_duration > 0 else 0,
    }
