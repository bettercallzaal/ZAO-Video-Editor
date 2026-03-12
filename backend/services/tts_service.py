"""Text-to-speech and voice cloning via Coqui XTTS-v2.

Generate voiceovers from text, optionally cloning a speaker's voice
from a 6-second audio sample.
"""

import os
from pathlib import Path


def text_to_speech(text: str, output_path: str,
                   language: str = "en",
                   speaker_wav: str = None,
                   on_progress=None) -> dict:
    """Generate speech from text.

    Args:
        text: Text to speak
        output_path: Where to save the audio
        language: Language code (en, es, fr, de, it, pt, etc.)
        speaker_wav: Optional path to a voice sample for cloning

    Returns dict with output path and info.
    """
    from .tool_availability import check_tool

    if check_tool("coqui_tts"):
        return _generate_coqui(text, output_path, language, speaker_wav, on_progress)
    else:
        raise RuntimeError(
            "Coqui TTS not installed. Install with: pip install TTS"
        )


def clone_voice_preview(speaker_wav: str, text: str,
                        output_path: str, language: str = "en") -> dict:
    """Quick voice clone preview — generate a short sample."""
    return text_to_speech(text, output_path, language, speaker_wav)


def generate_voiceover(script: str, project_dir: str,
                       speaker_wav: str = None,
                       language: str = "en",
                       on_progress=None) -> dict:
    """Generate a full voiceover from a script and save to project.

    Splits long scripts into chunks for better quality.
    """
    processing_dir = Path(project_dir) / "processing"
    processing_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(processing_dir / "voiceover.wav")

    # For long text, split into sentences and concatenate
    sentences = _split_into_chunks(script, max_chars=250)

    if len(sentences) <= 1:
        return text_to_speech(script, output_path, language, speaker_wav, on_progress)

    import tempfile
    import subprocess

    with tempfile.TemporaryDirectory() as tmpdir:
        chunk_paths = []
        for i, sentence in enumerate(sentences):
            if on_progress:
                pct = 10 + int(80 * i / len(sentences))
                on_progress(pct, f"Generating chunk {i+1}/{len(sentences)}...")

            chunk_path = os.path.join(tmpdir, f"chunk_{i:03d}.wav")
            text_to_speech(sentence, chunk_path, language, speaker_wav)
            chunk_paths.append(chunk_path)

        if on_progress:
            on_progress(90, "Joining audio chunks...")

        # Concatenate chunks
        concat_file = os.path.join(tmpdir, "concat.txt")
        with open(concat_file, "w") as f:
            for p in chunk_paths:
                f.write(f"file '{p}'\n")

        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:a", "pcm_s16le",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")

    return {
        "output": output_path,
        "chunks": len(sentences),
        "language": language,
        "cloned": speaker_wav is not None,
    }


def _generate_coqui(text, output_path, language, speaker_wav, on_progress):
    """Generate speech using Coqui XTTS-v2."""
    if on_progress:
        on_progress(15, "Loading XTTS-v2 model...")

    from TTS.api import TTS

    model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts = TTS(model_name)

    if on_progress:
        on_progress(40, "Generating speech...")

    if speaker_wav:
        tts.tts_to_file(
            text=text,
            file_path=output_path,
            speaker_wav=speaker_wav,
            language=language,
        )
    else:
        tts.tts_to_file(
            text=text,
            file_path=output_path,
            language=language,
        )

    return {
        "output": output_path,
        "method": "coqui_xtts_v2",
        "language": language,
        "cloned": speaker_wav is not None,
    }


def _split_into_chunks(text: str, max_chars: int = 250) -> list:
    """Split text into sentence-boundary chunks for TTS."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    chunks = []
    current = ""
    for sentence in sentences:
        if len(current) + len(sentence) > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = current + " " + sentence if current else sentence
    if current.strip():
        chunks.append(current.strip())
    return chunks if chunks else [text]
