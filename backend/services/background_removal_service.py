"""Background removal via rembg.

Removes backgrounds from video frames or images.
Useful for green-screen effects and compositing.
"""

import subprocess
import os
from pathlib import Path


def remove_background_image(input_path: str, output_path: str,
                            model: str = "u2net") -> dict:
    """Remove background from a single image.

    Models: u2net, u2netp (lightweight), u2net_human_seg, isnet-general-use
    """
    from rembg import remove
    from PIL import Image

    img = Image.open(input_path)
    result = remove(img, model_name=model)
    result.save(output_path)

    return {"output": output_path, "model": model}


def remove_background_video(input_path: str, output_path: str,
                            model: str = "u2net",
                            bg_color: str = "#00FF00",
                            on_progress=None) -> dict:
    """Remove background from video, replacing with solid color or transparency.

    Processes frame-by-frame: extract → remove bg → reassemble.
    """
    import tempfile
    from rembg import remove, new_session
    from PIL import Image
    from .ffmpeg_service import get_video_params

    params = get_video_params(input_path)
    session = new_session(model)

    with tempfile.TemporaryDirectory() as tmpdir:
        frames_in = os.path.join(tmpdir, "frames_in")
        frames_out = os.path.join(tmpdir, "frames_out")
        os.makedirs(frames_in)
        os.makedirs(frames_out)

        if on_progress:
            on_progress(5, "Extracting frames...")

        # Extract frames
        subprocess.run([
            "ffmpeg", "-y", "-i", input_path,
            os.path.join(frames_in, "frame_%06d.png"),
        ], capture_output=True)

        frame_files = sorted(Path(frames_in).glob("*.png"))
        total = len(frame_files)

        if on_progress:
            on_progress(10, f"Removing background from {total} frames...")

        # Parse bg color
        hex_color = bg_color.lstrip("#")
        bg_rgb = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

        for i, frame_path in enumerate(frame_files):
            img = Image.open(frame_path)
            result = remove(img, session=session)

            # Composite onto solid background
            bg = Image.new("RGB", result.size, bg_rgb)
            bg.paste(result, mask=result.split()[3] if result.mode == "RGBA" else None)
            bg.save(os.path.join(frames_out, frame_path.name))

            if on_progress and i % 30 == 0:
                pct = 10 + int(70 * i / total)
                on_progress(pct, f"Processing frame {i+1}/{total}...")

        if on_progress:
            on_progress(85, "Reassembling video...")

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
            "-pix_fmt", "yuv420p", output_path,
        ])
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg reassemble failed: {result.stderr}")

    return {
        "output": output_path,
        "model": model,
        "frames_processed": total,
        "bg_color": bg_color,
    }


def extract_subject(input_path: str, output_path: str,
                    model: str = "u2net") -> dict:
    """Extract subject with transparent background (PNG output)."""
    from rembg import remove
    from PIL import Image

    img = Image.open(input_path)
    result = remove(img, model_name=model)
    result.save(output_path, format="PNG")

    return {"output": output_path, "model": model}
