"""Background music generation via Meta's MusicGen.

Generates royalty-free music from text descriptions.
Requires GPU for reasonable speed.
"""

import os
from pathlib import Path


def generate_music(prompt: str, output_path: str,
                   duration: float = 30.0,
                   model_size: str = "small",
                   on_progress=None) -> dict:
    """Generate music from a text prompt.

    Args:
        prompt: Description of desired music (e.g. "upbeat corporate background music")
        duration: Duration in seconds (max ~30s per generation)
        model_size: "small" (300M), "medium" (1.5B), or "large" (3.3B)

    Returns dict with output path and generation info.
    """
    from .tool_availability import check_tool

    if check_tool("musicgen"):
        return _generate_musicgen(prompt, output_path, duration, model_size,
                                  on_progress)
    else:
        raise RuntimeError(
            "MusicGen not installed. Install with: pip install audiocraft"
        )


def generate_background_music(prompt: str, project_dir: str,
                              duration: float = 30.0,
                              on_progress=None) -> dict:
    """Generate background music and save to project."""
    processing_dir = Path(project_dir) / "processing"
    processing_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(processing_dir / "background_music.wav")

    result = generate_music(prompt, output_path, duration,
                           on_progress=on_progress)

    return result


def mix_audio_with_music(video_path: str, music_path: str,
                         output_path: str,
                         music_volume: float = 0.15,
                         on_progress=None) -> dict:
    """Mix background music with video audio.

    Args:
        music_volume: 0.0 to 1.0 — how loud the music is relative to speech
    """
    import subprocess

    if on_progress:
        on_progress(30, "Mixing audio with background music...")

    # Use ffmpeg to mix: original audio + music at reduced volume
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", music_path,
        "-filter_complex",
        f"[0:a][1:a]amix=inputs=2:duration=first:weights=1 {music_volume}[aout]",
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio mix failed: {result.stderr}")

    return {
        "output": output_path,
        "music_volume": music_volume,
    }


def _generate_musicgen(prompt, output_path, duration, model_size, on_progress):
    """Generate using Meta's AudioCraft MusicGen."""
    if on_progress:
        on_progress(10, f"Loading MusicGen ({model_size})...")

    from audiocraft.models import MusicGen
    import torchaudio

    model = MusicGen.get_pretrained(f"facebook/musicgen-{model_size}")
    model.set_generation_params(duration=duration)

    if on_progress:
        on_progress(30, "Generating music...")

    wav = model.generate([prompt])

    if on_progress:
        on_progress(85, "Saving audio...")

    # wav shape: [batch, channels, samples]
    audio = wav[0].cpu()
    torchaudio.save(output_path, audio, sample_rate=32000)

    return {
        "output": output_path,
        "method": f"musicgen_{model_size}",
        "prompt": prompt,
        "duration": duration,
    }
