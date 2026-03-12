"""stable-ts timestamp refinement — post-processes transcripts for better timing."""


def refine_timestamps(audio_path: str, segments: list, on_progress=None) -> list:
    """Refine word-level timestamps using stable-ts forced alignment.

    Takes existing segments and returns them with improved start/end values.
    """
    import stable_whisper

    if on_progress:
        on_progress(0, "Loading stable-ts alignment model...")

    model = stable_whisper.load_faster_whisper("base")

    if on_progress:
        on_progress(20, "Preparing transcript for alignment...")

    # Build the full text for alignment
    full_text = " ".join(seg["text"] for seg in segments)

    if on_progress:
        on_progress(30, "Aligning timestamps with audio...")

    # Use stable-ts to align existing text to audio
    result = model.align(audio_path, full_text, language="en")

    if on_progress:
        on_progress(80, "Mapping refined timestamps to segments...")

    # Extract refined word-level data from stable-ts result
    refined_words = []
    for seg in result.segments:
        for word in seg.words:
            refined_words.append({
                "word": word.word.strip(),
                "start": word.start,
                "end": word.end,
                "probability": getattr(word, "probability", 0.9),
            })

    if not refined_words:
        if on_progress:
            on_progress(100, "No refinement possible, keeping original timestamps")
        return segments

    # Map refined words back onto original segments
    word_idx = 0
    refined_segments = []

    for seg in segments:
        new_seg = dict(seg)
        seg_words = seg.get("words", [])

        if seg_words and word_idx < len(refined_words):
            new_words = []
            seg_start = None
            seg_end = None

            for _ in seg_words:
                if word_idx < len(refined_words):
                    rw = refined_words[word_idx]
                    new_words.append(rw)
                    if seg_start is None:
                        seg_start = rw["start"]
                    seg_end = rw["end"]
                    word_idx += 1

            if new_words:
                new_seg["words"] = new_words
                if seg_start is not None:
                    new_seg["start"] = seg_start
                if seg_end is not None:
                    new_seg["end"] = seg_end

        refined_segments.append(new_seg)

    if on_progress:
        on_progress(100, f"Refined timestamps for {len(refined_segments)} segments")

    return refined_segments
