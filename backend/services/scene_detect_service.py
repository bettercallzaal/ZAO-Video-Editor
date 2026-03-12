"""Scene detection via PySceneDetect.

Detects shot boundaries and generates automatic chapter markers.
CPU-only, no GPU required.
"""

import json
from pathlib import Path


def detect_scenes(video_path: str, threshold: float = 27.0,
                  min_scene_len: float = 2.0) -> list:
    """Detect scene boundaries in a video.

    Args:
        threshold: ContentDetector threshold (lower = more sensitive, default 27)
        min_scene_len: Minimum scene length in seconds

    Returns:
        List of scenes with start/end times
    """
    from scenedetect import detect, ContentDetector, open_video

    video = open_video(video_path)
    fps = video.frame_rate

    min_frames = int(min_scene_len * fps)
    scene_list = detect(
        video_path,
        ContentDetector(threshold=threshold, min_scene_len=min_frames),
    )

    scenes = []
    for i, (start, end) in enumerate(scene_list):
        scenes.append({
            "id": i,
            "start": start.get_seconds(),
            "end": end.get_seconds(),
            "duration": (end - start).get_seconds(),
        })

    return scenes


def scenes_to_chapters(scenes: list, video_duration: float = 0) -> str:
    """Convert scene list to YouTube-style chapter format.

    Generates timestamp markers like:
    0:00 Intro
    1:23 Scene 2
    3:45 Scene 3
    """
    lines = []
    for i, scene in enumerate(scenes):
        start = scene["start"]
        h = int(start // 3600)
        m = int((start % 3600) // 60)
        s = int(start % 60)

        if h > 0:
            timestamp = f"{h}:{m:02d}:{s:02d}"
        else:
            timestamp = f"{m}:{s:02d}"

        if i == 0 and start < 1.0:
            label = "Intro"
        else:
            label = f"Scene {i + 1}"

        lines.append(f"{timestamp} {label}")

    return "\n".join(lines)


def detect_and_generate_chapters(video_path: str, project_dir: str,
                                 threshold: float = 27.0,
                                 on_progress=None) -> dict:
    """Full pipeline: detect scenes → generate chapters → save.

    Saves:
    - metadata/scenes.json (raw scene data)
    - metadata/chapters.txt (YouTube format, editable)
    """
    if on_progress:
        on_progress(10, "Detecting scene boundaries...")

    scenes = detect_scenes(video_path, threshold=threshold)

    if on_progress:
        on_progress(70, f"Found {len(scenes)} scenes, generating chapters...")

    from .ffmpeg_service import get_video_params
    params = get_video_params(video_path)
    duration = params.get("duration", 0)

    chapters = scenes_to_chapters(scenes, duration)

    # Save
    project_path = Path(project_dir)
    metadata_dir = project_path / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)

    with open(metadata_dir / "scenes.json", "w") as f:
        json.dump(scenes, f, indent=2)

    with open(metadata_dir / "chapters.txt", "w") as f:
        f.write(chapters)

    return {
        "scene_count": len(scenes),
        "chapters": chapters,
        "scenes": scenes,
    }
