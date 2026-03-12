"""Storage management — disk usage tracking, cleanup, and file integrity."""

import os
import json
from pathlib import Path


PROJECTS_DIR = Path(__file__).parent.parent.parent / "projects"


def get_dir_size(path: Path) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    if not path.exists():
        return 0
    for entry in path.rglob("*"):
        if entry.is_file():
            try:
                total += entry.stat().st_size
            except (OSError, FileNotFoundError):
                pass
    return total


def get_project_storage(project_name: str) -> dict:
    """Get detailed storage breakdown for a project."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        return {"total": 0, "breakdown": {}}

    subdirs = ["input", "processing", "transcripts", "captions", "metadata", "exports", "clips"]
    breakdown = {}
    total = 0

    for subdir in subdirs:
        size = get_dir_size(project_dir / subdir)
        if size > 0:
            breakdown[subdir] = size
        total += size

    # Add project.json and any root files
    for f in project_dir.iterdir():
        if f.is_file():
            total += f.stat().st_size

    return {
        "total": total,
        "total_human": _human_size(total),
        "breakdown": {k: {"bytes": v, "human": _human_size(v)} for k, v in breakdown.items()},
    }


def get_all_projects_storage() -> dict:
    """Get storage for all projects plus total."""
    if not PROJECTS_DIR.exists():
        return {"projects": {}, "total": 0, "total_human": "0 B"}

    projects = {}
    total = 0
    for d in PROJECTS_DIR.iterdir():
        if d.is_dir() and (d / "project.json").exists():
            info = get_project_storage(d.name)
            projects[d.name] = {
                "total": info["total"],
                "total_human": info["total_human"],
            }
            total += info["total"]

    return {
        "projects": projects,
        "total": total,
        "total_human": _human_size(total),
    }


def get_cleanable_files(project_name: str) -> list:
    """Identify intermediate files that can be safely cleaned up."""
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        return []

    cleanable = []
    processing = project_dir / "processing"

    # audio.wav can be cleaned if transcription is done
    audio = processing / "audio.wav"
    raw_transcript = project_dir / "transcripts" / "raw.json"
    if audio.exists() and raw_transcript.exists():
        cleanable.append({
            "path": str(audio.relative_to(project_dir)),
            "size": audio.stat().st_size,
            "size_human": _human_size(audio.stat().st_size),
            "reason": "Transcription complete — audio no longer needed",
        })

    # assembled.mp4 can be cleaned if captioned.mp4 exists
    assembled = processing / "assembled.mp4"
    captioned = processing / "captioned.mp4"
    if assembled.exists() and captioned.exists():
        cleanable.append({
            "path": str(assembled.relative_to(project_dir)),
            "size": assembled.stat().st_size,
            "size_human": _human_size(assembled.stat().st_size),
            "reason": "Captioned video exists — assembled version is redundant",
        })

    # trimmed.mp4 can be cleaned if captioned.mp4 exists
    trimmed = processing / "trimmed.mp4"
    if trimmed.exists() and captioned.exists():
        cleanable.append({
            "path": str(trimmed.relative_to(project_dir)),
            "size": trimmed.stat().st_size,
            "size_human": _human_size(trimmed.stat().st_size),
            "reason": "Captioned video exists — trimmed version is redundant",
        })

    # Old transcript versions if edited exists
    edited = project_dir / "transcripts" / "edited.json"
    if edited.exists():
        for name in ["raw.json", "corrected.json", "cleaned.json"]:
            f = project_dir / "transcripts" / name
            if f.exists():
                cleanable.append({
                    "path": str(f.relative_to(project_dir)),
                    "size": f.stat().st_size,
                    "size_human": _human_size(f.stat().st_size),
                    "reason": "Edited transcript exists — earlier versions are redundant",
                })

    # exports/ files that are just copies
    exports = project_dir / "exports"
    if exports.exists():
        source_in_exports = exports / "source.mp4"
        if source_in_exports.exists():
            cleanable.append({
                "path": str(source_in_exports.relative_to(project_dir)),
                "size": source_in_exports.stat().st_size,
                "size_human": _human_size(source_in_exports.stat().st_size),
                "reason": "Source video copy in exports — original still in input/processing",
            })

    return cleanable


def cleanup_project(project_name: str, remove_paths: list = None) -> dict:
    """Remove specified intermediate files, or all cleanable files if none specified.

    Returns summary of what was cleaned.
    """
    project_dir = PROJECTS_DIR / project_name
    if not project_dir.exists():
        return {"cleaned": 0, "freed": 0}

    if remove_paths is None:
        cleanable = get_cleanable_files(project_name)
        remove_paths = [c["path"] for c in cleanable]

    cleaned = 0
    freed = 0

    for rel_path in remove_paths:
        full_path = project_dir / rel_path
        if full_path.exists() and full_path.is_file():
            size = full_path.stat().st_size
            full_path.unlink()
            cleaned += 1
            freed += size

    return {
        "cleaned": cleaned,
        "freed": freed,
        "freed_human": _human_size(freed),
    }


def verify_file_integrity(file_path: Path, min_size: int = 100) -> bool:
    """Basic integrity check — file exists, is not empty/truncated."""
    if not file_path.exists():
        return False
    try:
        size = file_path.stat().st_size
        if size < min_size:
            return False

        # For JSON files, verify parseable
        if file_path.suffix == ".json":
            with open(file_path) as f:
                json.load(f)

        # For video files, verify has reasonable size (at least 10KB)
        if file_path.suffix in (".mp4", ".mov", ".mkv", ".webm", ".wav"):
            if size < 10_000:
                return False

        return True
    except Exception:
        return False


def _human_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size string."""
    if size_bytes == 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    while size >= 1024 and i < len(units) - 1:
        size /= 1024
        i += 1
    return f"{size:.1f} {units[i]}"
