import subprocess
import json
import os
import shutil
from pathlib import Path


def get_video_info(video_path: str) -> dict:
    """Get video metadata using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-print_format", "json",
        "-show_format", "-show_streams",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr}")
    return json.loads(result.stdout)


def get_video_params(video_path: str) -> dict:
    """Extract resolution, fps, codec info from video."""
    info = get_video_info(video_path)
    video_stream = None
    for s in info.get("streams", []):
        if s.get("codec_type") == "video":
            video_stream = s
            break
    if not video_stream:
        raise RuntimeError("No video stream found")

    fps_parts = video_stream.get("r_frame_rate", "30/1").split("/")
    fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) != 0 else 30.0

    return {
        "width": int(video_stream.get("width", 1920)),
        "height": int(video_stream.get("height", 1080)),
        "fps": fps,
        "codec": video_stream.get("codec_name", "h264"),
        "duration": float(info.get("format", {}).get("duration", 0)),
    }


def convert_to_match(input_path: str, output_path: str, target_params: dict):
    """Convert a video to match target resolution, fps, and codec."""
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"scale={target_params['width']}:{target_params['height']}:force_original_aspect_ratio=decrease,pad={target_params['width']}:{target_params['height']}:(ow-iw)/2:(oh-ih)/2",
        "-r", str(target_params["fps"]),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg convert failed: {result.stderr}")


def assemble_videos(parts: list[str], output_path: str, main_params: dict):
    """Concatenate video parts using ffmpeg concat demuxer."""
    processing_dir = os.path.dirname(output_path)
    prepared_parts = []

    for i, part in enumerate(parts):
        part_params = get_video_params(part)
        needs_convert = (
            part_params["width"] != main_params["width"] or
            part_params["height"] != main_params["height"] or
            abs(part_params["fps"] - main_params["fps"]) > 0.5
        )

        if needs_convert:
            converted = os.path.join(processing_dir, f"converted_part_{i}.mp4")
            convert_to_match(part, converted, main_params)
            prepared_parts.append(converted)
        else:
            # Re-encode to ensure compatible streams for concat
            reencoded = os.path.join(processing_dir, f"reencoded_part_{i}.mp4")
            cmd = [
                "ffmpeg", "-y", "-i", part,
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
                "-pix_fmt", "yuv420p",
                "-r", str(main_params["fps"]),
                reencoded
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg re-encode failed: {result.stderr}")
            prepared_parts.append(reencoded)

    # Create concat file
    concat_file = os.path.join(processing_dir, "concat_list.txt")
    with open(concat_file, "w") as f:
        for part in prepared_parts:
            f.write(f"file '{part}'\n")

    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_file,
        "-c", "copy",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed: {result.stderr}")

    # Cleanup temp files
    for part in prepared_parts:
        if "converted_part_" in part or "reencoded_part_" in part:
            os.remove(part)
    os.remove(concat_file)


def extract_audio(video_path: str, audio_path: str):
    """Extract audio from video as WAV."""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        audio_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg audio extraction failed: {result.stderr}")


def burn_captions(video_path: str, ass_path: str, output_path: str, style_name: str = "classic"):
    """Burn captions into video using Pillow-rendered PNG overlays.

    Supports multiple caption styles including outlines, backgrounds,
    uppercase, and word-by-word highlighting.
    """
    import tempfile
    from PIL import Image, ImageDraw, ImageFont
    from .caption_gen import get_style

    captions_json = os.path.join(os.path.dirname(ass_path), "captions.json")
    with open(captions_json) as f:
        captions = json.load(f)

    if not captions:
        shutil.copy2(video_path, output_path)
        return

    style = get_style(style_name)
    params = get_video_params(video_path)
    width, height = params["width"], params["height"]

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

    with tempfile.TemporaryDirectory() as tmpdir:
        render_items = []  # list of (png_path, start, end)

        for i, cap in enumerate(captions):
            cap_text = cap["text"].upper() if uppercase else cap["text"]

            if word_highlight and "word_timing" in cap and cap["word_timing"]:
                # Render one PNG per word with that word highlighted
                for wi, wt in enumerate(cap["word_timing"]):
                    words_display = []
                    for wt2 in cap["word_timing"]:
                        w = wt2["word"].upper() if uppercase else wt2["word"]
                        words_display.append(w)

                    png_path = os.path.join(tmpdir, f"cap_{i:05d}_w{wi:02d}.png")
                    _render_highlight_caption(
                        png_path, width, height, font, words_display, wi,
                        text_color, highlight_color, outline_color, outline_width,
                        margin_bottom,
                    )
                    render_items.append((png_path, wt["start"], wt["end"]))
            else:
                # Standard single-image caption
                png_path = os.path.join(tmpdir, f"cap_{i:05d}.png")
                _render_caption(
                    png_path, width, height, font, cap_text,
                    text_color, outline_color, outline_width,
                    bg_color, margin_bottom, pad_x, pad_y, corner_radius,
                )
                render_items.append((png_path, cap["start"], cap["end"]))

        # Process in batches
        BATCH_SIZE = 50
        current_input = video_path

        for batch_start in range(0, len(render_items), BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, len(render_items))
            batch = render_items[batch_start:batch_end]
            is_last_batch = batch_end >= len(render_items)

            batch_output = output_path if is_last_batch else os.path.join(tmpdir, f"pass_{batch_start}.mp4")

            cmd = ["ffmpeg", "-y", "-i", current_input]
            for png_path, _, _ in batch:
                cmd.extend(["-i", png_path])

            filters = []
            prev = "0:v"
            for j, (_, start, end) in enumerate(batch):
                input_idx = j + 1
                out_label = f"v{j + 1}"
                filters.append(
                    f"[{prev}][{input_idx}:v]overlay=0:0:enable='between(t,{start:.3f},{end:.3f})'[{out_label}]"
                )
                prev = out_label

            filter_str = ";".join(filters)

            cmd.extend([
                "-filter_complex", filter_str,
                "-map", f"[{prev}]",
                "-map", "0:a?",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "copy",
                "-pix_fmt", "yuv420p",
                batch_output,
            ])

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise RuntimeError(f"ffmpeg caption burn failed: {result.stderr}")

            if current_input != video_path and os.path.exists(current_input):
                os.remove(current_input)
            current_input = batch_output


def _render_caption(png_path, width, height, font, text,
                    text_color, outline_color, outline_width,
                    bg_color, margin_bottom, pad_x, pad_y, corner_radius):
    """Render a single caption as a transparent PNG."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    # Position: centered horizontally, offset from bottom
    if bg_color:
        box_w = tw + pad_x * 2
        box_h = th + pad_y * 2
        box_x = (width - box_w) // 2
        box_y = height - margin_bottom - box_h
        text_x = box_x + pad_x
        text_y = box_y + pad_y

        draw.rounded_rectangle(
            [box_x, box_y, box_x + box_w, box_y + box_h],
            radius=corner_radius, fill=bg_color,
        )
    else:
        text_x = (width - tw) // 2
        text_y = height - margin_bottom - th

    # Draw outline by rendering text at offsets
    if outline_color and outline_width > 0:
        _draw_text_outline(draw, text_x, text_y, text, font, outline_color, outline_width)

    # Draw main text
    draw.text((text_x, text_y), text, font=font, fill=text_color)
    img.save(png_path)


def _render_highlight_caption(png_path, width, height, font, words, active_idx,
                              inactive_color, active_color, outline_color,
                              outline_width, margin_bottom):
    """Render a caption with one word highlighted in a different color."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    full_text = " ".join(words)
    bbox = draw.textbbox((0, 0), full_text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    start_x = (width - tw) // 2
    text_y = height - margin_bottom - th

    # Draw outline for full text first
    if outline_color and outline_width > 0:
        _draw_text_outline(draw, start_x, text_y, full_text, font, outline_color, outline_width)

    # Draw each word individually with appropriate color
    x = start_x
    for i, word in enumerate(words):
        color = active_color if i == active_idx else inactive_color
        draw.text((x, text_y), word, font=font, fill=color)
        word_w = draw.textbbox((0, 0), word + " ", font=font)[2]
        x += word_w

    img.save(png_path)


def _draw_text_outline(draw, x, y, text, font, color, width):
    """Draw text outline by rendering at offsets around the position."""
    for dx in range(-width, width + 1):
        for dy in range(-width, width + 1):
            if dx * dx + dy * dy <= width * width:
                draw.text((x + dx, y + dy), text, font=font, fill=color)


def _hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    """Convert hex color to RGBA tuple."""
    if not hex_color:
        return (255, 255, 255, alpha)
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16)
    g = int(hex_color[2:4], 16)
    b = int(hex_color[4:6], 16)
    return (r, g, b, alpha)


def _find_font(bold: bool = True) -> str:
    """Find a suitable font for caption rendering. Prefers bold fonts."""
    if bold:
        bold_candidates = [
            # Montserrat (if user installed it)
            os.path.expanduser("~/Library/Fonts/Montserrat-Bold.ttf"),
            os.path.expanduser("~/Library/Fonts/Montserrat-ExtraBold.ttf"),
            os.path.expanduser("~/Library/Fonts/Montserrat-Black.ttf"),
            "/Library/Fonts/Montserrat-Bold.ttf",
            "/Library/Fonts/Montserrat-ExtraBold.ttf",
            # Arial Bold
            "/Library/Fonts/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            # Helvetica Bold
            "/System/Library/Fonts/Helvetica Bold.ttc",
            "/System/Library/Fonts/HelveticaNeue.ttc",
            # SF Pro Bold
            "/System/Library/Fonts/SFNS.ttf",
            "/System/Library/Fonts/SFNSText.ttf",
        ]
        for path in bold_candidates:
            if os.path.exists(path):
                return path

    # Regular fallbacks
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


def copy_without_reencode(input_path: str, output_path: str):
    """Copy video without re-encoding."""
    shutil.copy2(input_path, output_path)
