"""Thumbnail generation.

Extracts key frames from video or generates AI thumbnails.
Uses Stable Diffusion/FLUX when available, ffmpeg frame extraction as fallback.
"""

import subprocess
import os
import json
from pathlib import Path


def extract_thumbnail(video_path: str, output_path: str,
                      time: float = None) -> dict:
    """Extract a single frame from video as a thumbnail.

    If time not specified, picks the frame at 10% of duration (avoids black intros).
    """
    from .ffmpeg_service import get_video_params

    if time is None:
        params = get_video_params(video_path)
        time = params["duration"] * 0.1

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(time),
        "-i", video_path,
        "-vframes", "1",
        "-q:v", "2",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg thumbnail failed: {result.stderr}")

    return {"output": output_path, "time": time, "method": "frame_extract"}


def extract_best_thumbnails(video_path: str, output_dir: str,
                            count: int = 5) -> list:
    """Extract multiple candidate thumbnails at evenly-spaced intervals.

    Picks frames across the video and returns them for the user to choose.
    """
    from .ffmpeg_service import get_video_params

    params = get_video_params(video_path)
    duration = params["duration"]

    os.makedirs(output_dir, exist_ok=True)
    thumbnails = []

    for i in range(count):
        # Skip first and last 5% of video
        t = duration * (0.05 + 0.9 * (i / (count - 1))) if count > 1 else duration * 0.5
        output_path = os.path.join(output_dir, f"thumb_{i:02d}.jpg")
        extract_thumbnail(video_path, output_path, time=t)
        thumbnails.append({
            "path": output_path,
            "filename": f"thumb_{i:02d}.jpg",
            "time": round(t, 2),
        })

    return thumbnails


def generate_ai_thumbnail(prompt: str, output_path: str,
                          width: int = 1280, height: int = 720,
                          on_progress=None) -> dict:
    """Generate a thumbnail using AI image generation.

    Tries Stable Diffusion via diffusers.
    """
    from .tool_availability import check_tool

    if not check_tool("diffusers"):
        raise RuntimeError(
            "AI thumbnail generation requires diffusers. "
            "Install with: pip install diffusers transformers accelerate"
        )

    if on_progress:
        on_progress(10, "Loading image generation model...")

    import torch
    from diffusers import StableDiffusionPipeline

    pipe = StableDiffusionPipeline.from_pretrained(
        "stabilityai/stable-diffusion-2-1",
        torch_dtype=torch.float16,
    )
    pipe.to("cuda")

    if on_progress:
        on_progress(30, "Generating thumbnail...")

    image = pipe(
        prompt,
        width=width,
        height=height,
        num_inference_steps=25,
    ).images[0]

    if on_progress:
        on_progress(90, "Saving thumbnail...")

    image.save(output_path, quality=95)

    return {
        "output": output_path,
        "method": "stable_diffusion",
        "prompt": prompt,
        "resolution": f"{width}x{height}",
    }


def generate_project_thumbnails(video_path: str, project_dir: str,
                                count: int = 5,
                                on_progress=None) -> dict:
    """Generate thumbnail candidates for a project.

    Extracts frames + optionally generates AI thumbnails.
    Saves to exports/thumbnails/.
    """
    thumb_dir = os.path.join(project_dir, "exports", "thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)

    if on_progress:
        on_progress(10, f"Extracting {count} candidate frames...")

    thumbnails = extract_best_thumbnails(video_path, thumb_dir, count=count)

    return {
        "thumbnails": thumbnails,
        "count": len(thumbnails),
    }
