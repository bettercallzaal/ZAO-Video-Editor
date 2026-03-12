"""Audio enhancement and denoising.

Uses Meta's Denoiser (denoiser/facebook) when available,
falls back to ffmpeg audio filters.
"""

import subprocess
import os
from pathlib import Path


def enhance_audio(input_path: str, output_path: str,
                  on_progress=None) -> dict:
    """Enhance audio — remove noise and improve clarity.

    Tries Meta denoiser first, falls back to ffmpeg filters.
    """
    from .tool_availability import check_tool

    if check_tool("denoiser"):
        return _enhance_denoiser(input_path, output_path, on_progress)
    else:
        return _enhance_ffmpeg(input_path, output_path, on_progress)


def enhance_video_audio(video_path: str, output_path: str,
                        on_progress=None) -> dict:
    """Extract audio from video, enhance it, then remux.

    Original video stream is copied (no re-encode).
    """
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        audio_in = os.path.join(tmpdir, "audio_in.wav")
        audio_out = os.path.join(tmpdir, "audio_out.wav")

        if on_progress:
            on_progress(10, "Extracting audio...")

        # Extract audio
        subprocess.run([
            "ffmpeg", "-y", "-i", video_path,
            "-vn", "-acodec", "pcm_s16le", "-ar", "16000", "-ac", "1",
            audio_in,
        ], capture_output=True)

        if on_progress:
            on_progress(20, "Enhancing audio...")

        result = enhance_audio(audio_in, audio_out, on_progress)

        if on_progress:
            on_progress(80, "Remuxing enhanced audio...")

        # Remux: copy video, replace audio
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_out,
            "-map", "0:v", "-map", "1:a",
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"ffmpeg remux failed: {res.stderr}")

    return {
        "method": result["method"],
        "output": output_path,
    }


def _enhance_denoiser(input_path: str, output_path: str,
                      on_progress=None) -> dict:
    """Use Meta's Denoiser for speech enhancement."""
    if on_progress:
        on_progress(30, "Running Meta Denoiser...")

    import torch
    import torchaudio
    from denoiser import pretrained
    from denoiser.dsp import convert_audio

    model = pretrained.dns64()
    model.eval()

    wav, sr = torchaudio.load(input_path)
    wav = convert_audio(wav, sr, model.sample_rate, model.chin)

    with torch.no_grad():
        denoised = model(wav.unsqueeze(0))[0]

    if on_progress:
        on_progress(70, "Saving enhanced audio...")

    torchaudio.save(output_path, denoised.squeeze(0).cpu(), model.sample_rate)

    return {"method": "meta_denoiser", "output": output_path}


def _enhance_ffmpeg(input_path: str, output_path: str,
                    on_progress=None) -> dict:
    """Fallback: ffmpeg audio filters for basic noise reduction."""
    if on_progress:
        on_progress(30, "Applying noise reduction (ffmpeg)...")

    # afftdn = FFT-based denoiser, highpass removes rumble, loudnorm normalizes
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-af", "afftdn=nf=-25,highpass=f=80,loudnorm=I=-16:TP=-1.5:LRA=11",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio enhance failed: {result.stderr}")

    return {"method": "ffmpeg_afftdn", "output": output_path}
