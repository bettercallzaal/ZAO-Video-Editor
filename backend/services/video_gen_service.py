"""Video generation via LTX-2 (Lightricks).

Generates B-roll clips, transitions, and fill content from text prompts.
Requires NVIDIA GPU with 32GB+ VRAM.
"""

import os
import subprocess
from pathlib import Path


def generate_video(prompt: str, output_path: str,
                   duration: float = 6.0,
                   width: int = 768, height: int = 512,
                   seed: int = -1,
                   on_progress=None) -> dict:
    """Generate a video clip from a text prompt using LTX-2.

    Args:
        prompt: Text description of desired video
        duration: Duration in seconds (6, 8, 10, 12, 14, 16, 18, 20)
        width/height: Output resolution (will be adjusted to model constraints)
        seed: Random seed (-1 for random)

    Returns dict with output path and generation info.
    """
    if on_progress:
        on_progress(10, "Loading LTX-2 model...")

    try:
        from ltx_pipelines.text_to_video import TextToVideoPipeline
        return _generate_ltx_native(prompt, output_path, duration, width, height,
                                    seed, on_progress)
    except ImportError:
        pass

    # Try diffusers fallback
    try:
        return _generate_diffusers(prompt, output_path, duration, width, height,
                                   seed, on_progress)
    except ImportError:
        raise RuntimeError(
            "LTX-2 not installed. Install with: pip install ltx-pipelines\n"
            "Or: pip install diffusers transformers accelerate"
        )


def generate_broll(prompt: str, project_dir: str,
                   duration: float = 6.0, count: int = 1,
                   on_progress=None) -> list:
    """Generate B-roll clips and save to project's processing directory.

    Returns list of generated clip paths.
    """
    processing_dir = Path(project_dir) / "processing" / "broll"
    processing_dir.mkdir(parents=True, exist_ok=True)

    clips = []
    for i in range(count):
        output_path = str(processing_dir / f"broll_{i:03d}.mp4")
        if on_progress:
            on_progress(
                10 + int(80 * i / count),
                f"Generating B-roll {i+1}/{count}..."
            )
        result = generate_video(prompt, output_path, duration=duration)
        clips.append(result)

    return clips


def generate_transition(prompt: str, output_path: str,
                        duration: float = 2.0,
                        on_progress=None) -> dict:
    """Generate a short transition clip."""
    if not prompt:
        prompt = "smooth cinematic transition, abstract motion, elegant"
    return generate_video(prompt, output_path, duration=duration,
                         on_progress=on_progress)


def image_to_video(image_path: str, output_path: str,
                   prompt: str = "",
                   duration: float = 6.0,
                   on_progress=None) -> dict:
    """Generate video from a starting image (image-to-video).

    Uses the image as the first frame and generates motion.
    """
    if on_progress:
        on_progress(10, "Loading model for image-to-video...")

    try:
        import torch
        from diffusers import LTXImageToVideoPipeline
        from diffusers.utils import load_image

        pipe = LTXImageToVideoPipeline.from_pretrained(
            "Lightricks/LTX-Video",
            torch_dtype=torch.float16,
        )
        pipe.to("cuda")

        image = load_image(image_path)

        if on_progress:
            on_progress(30, "Generating video from image...")

        num_frames = max(24, int(duration * 24))

        result = pipe(
            prompt=prompt or "cinematic motion, smooth camera movement",
            image=image,
            num_frames=num_frames,
            num_inference_steps=30,
        )

        if on_progress:
            on_progress(85, "Encoding video...")

        from diffusers.utils import export_to_video
        export_to_video(result.frames[0], output_path, fps=24)

        return {"output": output_path, "method": "ltx_i2v", "duration": duration}
    except Exception as e:
        raise RuntimeError(f"Image-to-video generation failed: {e}")


def _generate_ltx_native(prompt, output_path, duration, width, height,
                         seed, on_progress):
    """Generate using native LTX pipeline."""
    from ltx_pipelines.text_to_video import TextToVideoPipeline

    if on_progress:
        on_progress(20, "Initializing LTX-2 pipeline...")

    pipeline = TextToVideoPipeline()

    if on_progress:
        on_progress(40, "Generating video...")

    result = pipeline(
        prompt=prompt,
        width=width,
        height=height,
        num_frames=int(duration * 24),
        seed=seed if seed >= 0 else None,
    )

    if on_progress:
        on_progress(90, "Saving video...")

    result.save(output_path)

    return {
        "output": output_path,
        "method": "ltx_native",
        "prompt": prompt,
        "duration": duration,
        "resolution": f"{width}x{height}",
    }


def _generate_diffusers(prompt, output_path, duration, width, height,
                        seed, on_progress):
    """Generate using HuggingFace diffusers LTX pipeline."""
    import torch
    from diffusers import LTXPipeline
    from diffusers.utils import export_to_video

    if on_progress:
        on_progress(20, "Loading LTX-2 via diffusers...")

    pipe = LTXPipeline.from_pretrained(
        "Lightricks/LTX-Video",
        torch_dtype=torch.float16,
    )
    pipe.to("cuda")

    if on_progress:
        on_progress(40, "Generating video...")

    generator = torch.Generator("cuda").manual_seed(seed) if seed >= 0 else None
    num_frames = max(24, int(duration * 24))

    result = pipe(
        prompt=prompt,
        width=width,
        height=height,
        num_frames=num_frames,
        num_inference_steps=30,
        generator=generator,
    )

    if on_progress:
        on_progress(85, "Encoding video...")

    export_to_video(result.frames[0], output_path, fps=24)

    return {
        "output": output_path,
        "method": "ltx_diffusers",
        "prompt": prompt,
        "duration": duration,
        "resolution": f"{width}x{height}",
    }
