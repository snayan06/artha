#!/usr/bin/env python3
"""Validate local inline Markdown links in tracked documentation."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote


LINK_PATTERN = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
FENCE_PATTERN = re.compile(r"^\s*(`{3,}|~{3,})")
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")


@dataclass(frozen=True)
class BrokenLink:
    markdown_file: Path
    line_number: int
    target: str
    resolved_path: Path


def tracked_markdown_files(root: Path) -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", "*.md"],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        message = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"could not list tracked Markdown files: {message}")
    return [root / entry.decode("utf-8") for entry in result.stdout.split(b"\0") if entry]


def markdown_files(root: Path, requested: list[str]) -> list[Path]:
    if not requested:
        return tracked_markdown_files(root)

    files: list[Path] = []
    for requested_path in requested:
        path = Path(requested_path)
        path = path if path.is_absolute() else root / path
        if not path.is_file():
            raise RuntimeError(f"Markdown file does not exist: {requested_path}")
        files.append(path)
    return files


def destination(raw_destination: str) -> str:
    value = raw_destination.strip()
    if value.startswith("<") and ">" in value:
        return value[1 : value.index(">")]
    return value.split(maxsplit=1)[0] if value else ""


def is_ignored(target: str) -> bool:
    lowered = target.lower()
    return (
        not target
        or target.startswith("#")
        or lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
    )


def local_target_path(root: Path, markdown_file: Path, target: str) -> Path | None:
    target_without_suffix = target.split("#", 1)[0].split("?", 1)[0]
    if not target_without_suffix:
        return None
    decoded = unquote(target_without_suffix)
    if decoded.startswith("/"):
        return (root / decoded.lstrip("/")).resolve()
    return (markdown_file.parent / decoded).resolve()


def check_links(root: Path, files: list[Path]) -> tuple[int, list[BrokenLink]]:
    checked = 0
    broken: list[BrokenLink] = []

    for markdown_file in files:
        relative_file = markdown_file.resolve().relative_to(root.resolve())
        active_fence: tuple[str, int] | None = None

        for line_number, line in enumerate(markdown_file.read_text(encoding="utf-8").splitlines(), 1):
            fence_match = FENCE_PATTERN.match(line)
            if fence_match:
                marker = fence_match.group(1)
                marker_kind = marker[0]
                if active_fence is None:
                    active_fence = (marker_kind, len(marker))
                elif marker_kind == active_fence[0] and len(marker) >= active_fence[1]:
                    active_fence = None
                continue
            if active_fence is not None:
                continue

            searchable_line = INLINE_CODE_PATTERN.sub("", line)
            for match in LINK_PATTERN.finditer(searchable_line):
                target = destination(match.group(1))
                if is_ignored(target):
                    continue
                resolved_path = local_target_path(root, markdown_file, target)
                if resolved_path is None:
                    continue
                checked += 1
                if not resolved_path.exists():
                    broken.append(
                        BrokenLink(
                            markdown_file=relative_file,
                            line_number=line_number,
                            target=target,
                            resolved_path=resolved_path,
                        )
                    )

    return checked, broken


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (defaults to the parent of scripts/).",
    )
    parser.add_argument("paths", nargs="*", help="Markdown files to check; defaults to all tracked *.md files.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    try:
        files = markdown_files(root, args.paths)
        checked, broken = check_links(root, files)
    except (OSError, RuntimeError, UnicodeError, ValueError) as error:
        print(f"Markdown link check failed: {error}", file=sys.stderr)
        return 2

    if broken:
        for link in broken:
            print(
                f"{link.markdown_file}:{link.line_number}: missing local link "
                f"{link.target!r} -> {link.resolved_path}",
                file=sys.stderr,
            )
        print(
            f"Markdown link check failed: {len(broken)} missing local link(s) "
            f"across {len(files)} Markdown file(s).",
            file=sys.stderr,
        )
        return 1

    noun = "link" if checked == 1 else "links"
    print(f"Markdown links valid: {checked} local {noun} checked across {len(files)} file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
