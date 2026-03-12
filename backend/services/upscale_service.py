"""Video/image upscaling via Real-ESRGAN.

Upscales video frame-by-frame or images for thumbnails.
Falls back to ffmpeg lanczos scaling if Real-ESRGAN not installed.
"""

import subprocess
import os
import json
from pathlib import Path


def upscale_video(input_path: str, output_path: str, scale: int = 2,
                  on_progress=None) -> dict:
    """Upscale video using Real-ESRGAN or ffmpeg fallback.

    Args:
        scale: 2 or 4 (upscale factor)
    Returns:
        dict with output path, method used, and resolution info
    """
    from .tool_availability import check_tool

    if check_tool("realesrgan"):
        return _upscale_realesrgan(input_path, output_path, scale, on_progress)
    else:
        return _upscale_ffmpeg(input_path, output_path, scale, on_progress)


def upscale_image(input_path: str, output_path: str, scale: int = 2) -> dict:
    """Upscale a single image."""
    from .tool_availability import check_tool

    if check_tool("realesrgan"):
        cmd = [
            "realesrgan-ncnn-vulkan",
            "-i", input_path,
            "-o", output_path,
            "-s", str(scale),
            "-n", "realesrgan-x4plus",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Real-ESRGAN failed: {result.stderr}")
        return {"method": "realesrgan", "output": output_path}
    else:
        # PIL fallback
        from PIL import Image
        img = Image.open(input_path)
        new_size = (img.width * scale, img.height * scale)
        img = img.resize(new_size, Image.LANCZOS)
        img.save(output_path, quality=95)
        return {"method": "pillow_lanczos", "output": output_path}


def _upscale_realesrgan(input_path: str, output_path: str, scale: int,
                        on_progress=None) -> dict:
    """Upscale video using realesrgan-ncnn-vulkan frame extraction."""
    import tempfile
    from .ffmpeg_service import get_video_params

    params = get_video_params(input_path)
    new_w = params["width"] * scale
    new_h = params["height"] * scale

    with tempfile.TemporaryDirectory() as tmpdir:
        frames_in = os.path.join(tmpdir, "frames_in")
        frames_out = os.path.join(tmpdir, "frames_out")
        os.makedirs(frames_in)
        os.makedirs(frames_out)

        if on_progress:
            on_progress(10, "Extracting frames...")

        # Extract frames
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            os.path.join(frames_in, "frame_%06d.png"),
        ], capture_output=True)

        if on_progress:
            on_progress(25, "Upscaling frames with Real-ESRGAN...")

        # Upscale all frames
        cmd = [
            "realesrgan-ncnn-vulkan",
            "-i", frames_in,
            "-o", frames_out,
            "-s", str(scale),
            "-n", "realesrgan-x4plus",
            "-f", "png",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Real-ESRGAN failed: {result.stderr}")

        if on_progress:
            on_progress(75, "Reassembling video...")

        # Extract audio
        audio_path = os.path.join(tmpdir, "audio.aac")
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            "-vn", "-c:a", "aac", "-b:a", "192k", audio_path,
        ], capture_output=True)

        # Reassemble
        cmd = [
            "ffmpeg", "-y",
            "-framerate", str(params["fps"]),
            "-i", os.path.join(frames_out, "frame_%06d.png"),
        ]
        if os.path.exists(audio_path):
            cmd.extend(["-i", audio_path, "-c:a", "copy"])

        cmd.extend([
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p",
            output_path,
        ])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg reassemble failed: {result.stderr}")

    return {
        "method": "realesrgan",
        "output": output_path,
        "original_resolution": f"{params['width']}x{params['height']}",
        "upscaled_resolution": f"{new_w}x{new_h}",
        "scale": scale,
    }


def _upscale_ffmpeg(input_path: str, output_path: str, scale: int,
                    on_progress=None) -> dict:
    """Upscale video using ffmpeg lanczos filter (no AI, but always available)."""
    from .ffmpeg_service import get_video_params

    params = get_video_params(input_path)
    new_w = params["width"] * scale
    new_h = params["height"] * scale

    if on_progress:
        on_progress(20, f"Upscaling to {new_w}x{new_h} (lanczos)...")

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={new_w}:{new_h}:flags=lanczos",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "copy", "-pix_fmt", "yuv420p",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg upscale failed: {result.stderr}")

    return {
        "method": "ffmpeg_lanczos",
        "output": output_path,
        "original_resolution": f"{params['width']}x{params['height']}",
        "upscaled_resolution": f"{new_w}x{new_h}",
        "scale": scale,
    }
