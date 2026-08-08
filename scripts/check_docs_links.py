"""Validate local inline Markdown links in tracked documentation."""

from __future__ import annotations

import argparse
import re
import string
import subprocess
import sys
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

FENCE_PATTERN = re.compile(r"^( {0,3})(`{3,}|~{3,})")


@dataclass(frozen=True)
class BrokenLink:
    markdown_file: Path
    line_number: int
    target: str
    resolved_path: Path
    reason: str


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
        value = value[1 : value.index(">")]
    else:
        value = value.split(maxsplit=1)[0] if value else ""

    unescaped: list[str] = []
    index = 0
    while index < len(value):
        if (
            value[index] == "\\"
            and index + 1 < len(value)
            and value[index + 1] in string.punctuation
        ):
            unescaped.append(value[index + 1])
            index += 2
            continue
        unescaped.append(value[index])
        index += 1
    return "".join(unescaped)


def is_escaped(text: str, index: int) -> bool:
    backslashes = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        backslashes += 1
        cursor -= 1
    return backslashes % 2 == 1


def backtick_run(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and text[cursor] == "`":
        cursor += 1
    return cursor - index


def code_span_end(text: str, opening_index: int, delimiter_length: int) -> int | None:
    cursor = opening_index + delimiter_length
    while cursor < len(text):
        next_tick = text.find("`", cursor)
        if next_tick == -1:
            return None
        run_length = backtick_run(text, next_tick)
        if run_length == delimiter_length:
            return next_tick + run_length
        cursor = next_tick + run_length
    return None


def masked_fenced_code(text: str) -> str:
    active_fence: tuple[str, int] | None = None
    output: list[str] = []

    for line in text.splitlines(keepends=True):
        fence_match = FENCE_PATTERN.match(line)
        should_mask = active_fence is not None

        if active_fence is None and fence_match:
            marker = fence_match.group(2)
            info = line[fence_match.end() :]
            if marker[0] == "~" or "`" not in info:
                active_fence = (marker[0], len(marker))
                should_mask = True
        elif active_fence is not None and fence_match:
            marker = fence_match.group(2)
            trailing = line[fence_match.end() :].strip()
            if marker[0] == active_fence[0] and len(marker) >= active_fence[1] and not trailing:
                active_fence = None

        if should_mask:
            output.append("".join(character if character in "\r\n" else " " for character in line))
        else:
            output.append(line)

    return "".join(output)


def link_destination_end(text: str, opening_parenthesis: int) -> int | None:
    cursor = opening_parenthesis + 1
    nested_parentheses = 0
    destination_started = False
    destination_done = False
    angle_destination = False
    title_closer: str | None = None

    while cursor < len(text):
        character = text[cursor]
        if character == "\\" and cursor + 1 < len(text):
            cursor += 2
            continue
        if title_closer is not None:
            if character == title_closer:
                title_closer = None
            cursor += 1
            continue
        if angle_destination:
            if character == ">":
                angle_destination = False
                destination_done = True
            cursor += 1
            continue
        if not destination_started:
            if character.isspace():
                cursor += 1
                continue
            destination_started = True
            if character == "<":
                angle_destination = True
                cursor += 1
                continue
        if destination_done:
            if character in {'"', "'"}:
                title_closer = character
            elif character == "(":
                title_closer = ")"
            elif character == ")":
                return cursor
            cursor += 1
            continue
        if character.isspace() and nested_parentheses == 0:
            destination_done = True
        elif character == "(":
            nested_parentheses += 1
        elif character == ")":
            if nested_parentheses == 0:
                return cursor
            nested_parentheses -= 1
        cursor += 1

    return None


def inline_link_destinations(markdown: str) -> list[tuple[int, str]]:
    text = masked_fenced_code(markdown)
    line_starts = [0, *(match.end() for match in re.finditer("\n", text))]
    bracket_stack: list[int] = []
    links: list[tuple[int, str]] = []
    cursor = 0

    while cursor < len(text):
        character = text[cursor]
        if character == "`" and not is_escaped(text, cursor):
            delimiter_length = backtick_run(text, cursor)
            span_end = code_span_end(text, cursor, delimiter_length)
            cursor = span_end if span_end is not None else cursor + delimiter_length
            continue
        if character == "[" and not is_escaped(text, cursor):
            bracket_stack.append(cursor)
        elif character == "]" and not is_escaped(text, cursor) and bracket_stack:
            label_start = bracket_stack.pop()
            if cursor + 1 < len(text) and text[cursor + 1] == "(":
                closing_parenthesis = link_destination_end(text, cursor + 1)
                if closing_parenthesis is not None:
                    raw_destination = text[cursor + 2 : closing_parenthesis]
                    links.append((bisect_right(line_starts, label_start), raw_destination))
                    cursor = closing_parenthesis + 1
                    continue
        cursor += 1

    return links


def is_ignored(target: str) -> bool:
    lowered = target.lower()
    return (
        not target
        or target.startswith("#")
        or lowered.startswith(("http://", "https://", "mailto:"))
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
    resolved_root = root.resolve()

    for markdown_file in files:
        relative_file = markdown_file.resolve().relative_to(resolved_root)
        markdown = markdown_file.read_text(encoding="utf-8")

        for line_number, raw_destination in inline_link_destinations(markdown):
            target = destination(raw_destination)
            if is_ignored(target):
                continue
            resolved_path = local_target_path(root, markdown_file, target)
            if resolved_path is None:
                continue
            checked += 1
            if not resolved_path.is_relative_to(resolved_root):
                broken.append(
                    BrokenLink(
                        markdown_file=relative_file,
                        line_number=line_number,
                        target=target,
                        resolved_path=resolved_path,
                        reason="link target escapes repository root",
                    )
                )
            elif not resolved_path.exists():
                broken.append(
                    BrokenLink(
                        markdown_file=relative_file,
                        line_number=line_number,
                        target=target,
                        resolved_path=resolved_path,
                        reason="missing local link",
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
    parser.add_argument(
        "paths",
        nargs="*",
        help="Markdown files to check; defaults to all tracked *.md files.",
    )
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
                f"{link.markdown_file}:{link.line_number}: {link.reason} "
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
