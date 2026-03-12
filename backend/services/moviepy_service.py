"""MoviePy v2 integration — programmatic video editing for captions and clips."""

import os
import json


def burn_captions_moviepy(video_path: str, captions_json_path: str,
                          output_path: str, style_name: str = "classic",
                          on_progress=None) -> None:
    """Burn captions using MoviePy CompositeVideoClip.

    Eliminates the fragile batched ffmpeg filter_complex approach.
    Uses existing Pillow rendering for caption images, then composes
    them onto the video in a single pass via MoviePy.
    """
    import tempfile
    from moviepy import VideoFileClip, ImageClip, CompositeVideoClip
    from PIL import Image, ImageDraw, ImageFont
    from .caption_gen import get_style
    from .ffmpeg_service import (
        _find_font, _hex_to_rgba, _render_caption,
        _render_highlight_caption,
    )

    with open(captions_json_path) as f:
        captions = json.load(f)

    if not captions:
        import shutil
        shutil.copy2(video_path, output_path)
        return

    if on_progress:
        on_progress(5, "Loading video...")

    video = VideoFileClip(video_path)
    width, height = video.size
    style = get_style(style_name)

    font_path = _find_font(bold=style.get("font_weight") == "bold")
    font_size = max(28, int(height * style["font_size_ratio"]))

    try:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    text_color = _hex_to_rgba(style["text_color"])
    outline_color = _hex_to_rgba(style["outline_color"]) if style.get("outline_color") else None
    outline_width = style.get("outline_width", 0)
    bg_color = _hex_to_rgba(style["bg_color"], style.get("bg_opacity", 255)) if style.get("bg_color") else None
    highlight_color = _hex_to_rgba(style.get("highlight_color", "#FFFFFF")) if style.get("word_highlight") else None
    uppercase = style.get("uppercase", False)
    margin_bottom = max(30, int(height * style["margin_bottom_pct"]))
    pad_x = style.get("padding_x", 0)
    pad_y = style.get("padding_y", 0)
    corner_radius = style.get("corner_radius", 0)
    word_highlight = style.get("word_highlight", False)

    if on_progress:
        on_progress(15, f"Rendering {len(captions)} caption images...")

    with tempfile.TemporaryDirectory() as tmpdir:
        caption_clips = []
        total = len(captions)

        for i, cap in enumerate(captions):
            cap_text = cap["text"].upper() if uppercase else cap["text"]

            if word_highlight and "word_timing" in cap and cap["word_timing"]:
                # Word-by-word highlight: one clip per word
                for wi, wt in enumerate(cap["word_timing"]):
                    words_display = [
                        (wt2["word"].upper() if uppercase else wt2["word"])
                        for wt2 in cap["word_timing"]
                    ]

                    png_path = os.path.join(tmpdir, f"cap_{i:05d}_w{wi:02d}.png")
                    _render_highlight_caption(
                        png_path, width, height, font, words_display, wi,
                        text_color, highlight_color, outline_color, outline_width,
                        margin_bottom,
                    )

                    duration = wt["end"] - wt["start"]
                    if duration > 0:
                        clip = (ImageClip(png_path)
                                .with_start(wt["start"])
                                .with_duration(duration))
                        caption_clips.append(clip)
            else:
                # Standard caption
                png_path = os.path.join(tmpdir, f"cap_{i:05d}.png")
                _render_caption(
                    png_path, width, height, font, cap_text,
                    text_color, outline_color, outline_width,
                    bg_color, margin_bottom, pad_x, pad_y, corner_radius,
                )

                duration = cap["end"] - cap["start"]
                if duration > 0:
                    clip = (ImageClip(png_path)
                            .with_start(cap["start"])
                            .with_duration(duration))
                    caption_clips.append(clip)

            if on_progress and i % 20 == 0:
                pct = 15 + int((i / total) * 50)
                on_progress(pct, f"Rendered {i}/{total} captions...")

        if on_progress:
            on_progress(70, f"Compositing {len(caption_clips)} overlays...")

        # Compose all caption clips onto the video in one pass
        final = CompositeVideoClip([video] + caption_clips)

        if on_progress:
            on_progress(75, "Writing output video...")

        final.write_videofile(
            output_path,
            codec="libx264",
            preset="medium",
            ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p"],
            audio_codec="aac",
            logger=None,
        )

        if on_progress:
            on_progress(100, "Caption burn complete (MoviePy)")

        video.close()
        final.close()


def assemble_with_transitions(parts: list, output_path: str,
                               transition: str = "crossfade",
                               transition_duration: float = 0.5,
                               on_progress=None) -> None:
    """Concatenate videos with crossfade transitions using MoviePy."""
    from moviepy import VideoFileClip, concatenate_videoclips

    if on_progress:
        on_progress(10, f"Loading {len(parts)} video parts...")

    clips = [VideoFileClip(p) for p in parts]

    if on_progress:
        on_progress(40, "Applying transitions...")

    if transition == "crossfade" and len(clips) > 1:
        final = concatenate_videoclips(clips, method="compose",
                                        padding=-transition_duration)
    else:
        final = concatenate_videoclips(clips, method="compose")

    if on_progress:
        on_progress(60, "Writing assembled video...")

    final.write_videofile(
        output_path,
        codec="libx264",
        preset="medium",
        ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p"],
        audio_codec="aac",
        logger=None,
    )

    for clip in clips:
        clip.close()
    final.close()

    if on_progress:
        on_progress(100, "Assembly with transitions complete")


def export_clip_moviepy(video_path: str, output_path: str,
                         start: float, end: float,
                         vertical: bool = False,
                         on_progress=None) -> None:
    """Export a clip with optional vertical 9:16 crop using MoviePy."""
    from moviepy import VideoFileClip

    if on_progress:
        on_progress(10, "Loading video...")

    video = VideoFileClip(video_path).subclipped(start, end)

    if vertical:
        if on_progress:
            on_progress(30, "Cropping to vertical 9:16...")

        w, h = video.size
        target_w = int(h * 9 / 16)
        if target_w > w:
            target_w = w

        x_center = w // 2
        x1 = x_center - target_w // 2
        video = video.cropped(x1=x1, width=target_w)

    if on_progress:
        on_progress(50, "Writing clip...")

    video.write_videofile(
        output_path,
        codec="libx264",
        preset="medium",
        ffmpeg_params=["-crf", "18", "-pix_fmt", "yuv420p"],
        audio_codec="aac",
        logger=None,
    )
    video.close()

    if on_progress:
        on_progress(100, "Clip exported (MoviePy)")
