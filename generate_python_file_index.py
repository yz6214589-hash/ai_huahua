from __future__ import annotations

import ast
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class PythonFileEntry:
    file_name: str
    purpose: str
    simplified_path: str


def _is_excluded(rel_posix_lower: str) -> bool:
    excluded_prefixes = (
        "week4/课程代码-20260307/openclaw/",
        "week4/课程代码-20260307/.openclaw/",
        "week5/课程代码-20260314/chan.py/",
        "week5/课程代码-20260318/chan.py/",
    )
    return rel_posix_lower.startswith(excluded_prefixes)


def _simplify_path(rel_path: Path) -> str:
    parts = rel_path.parts
    if not parts:
        return rel_path.name

    week_part = parts[0]
    return f"{week_part}\\{rel_path.name}"


def _extract_docstring(file_path: Path) -> str:
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "未说明"

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=SyntaxWarning)
            module = ast.parse(content)
            doc = ast.get_docstring(module)
        if doc:
            return " ".join(doc.strip().split())
        return "未说明"
    except SyntaxError:
        return _extract_docstring_fallback(content)


def _extract_docstring_fallback(content: str) -> str:
    lines = content.splitlines()
    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if line.startswith("#!"):
            idx += 1
            continue
        if line.lower().startswith("# -*- coding:") or line.lower().startswith("# coding:"):
            idx += 1
            continue
        if line.startswith("#"):
            idx += 1
            continue
        break

    if idx >= len(lines):
        return "未说明"

    first = lines[idx].lstrip()
    if first.startswith('"""') or first.startswith("'''"):
        quote = first[:3]
        remainder = first[3:]
        if quote in remainder:
            doc = remainder.split(quote, 1)[0]
            doc = doc.strip()
            return " ".join(doc.split()) if doc else "未说明"

        collected: list[str] = []
        if remainder:
            collected.append(remainder)
        idx += 1
        while idx < len(lines):
            current = lines[idx]
            if quote in current:
                before, _ = current.split(quote, 1)
                collected.append(before)
                break
            collected.append(current)
            idx += 1

        doc = "\n".join(collected).strip()
        return " ".join(doc.split()) if doc else "未说明"

    return "未说明"


def _escape_md_cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\r\n", "\n").replace("\r", "\n").replace("\n", "<br>")


def _iter_python_files(root: Path, week_dirs: Iterable[Path]) -> list[PythonFileEntry]:
    entries: list[PythonFileEntry] = []
    for week_dir in week_dirs:
        if not week_dir.exists() or not week_dir.is_dir():
            continue

        for file_path in week_dir.rglob("*.py"):
            if not file_path.is_file():
                continue

            rel = file_path.relative_to(root)
            rel_posix_lower = rel.as_posix().lower()
            if _is_excluded(rel_posix_lower):
                continue

            entries.append(
                PythonFileEntry(
                    file_name=file_path.name,
                    purpose=_extract_docstring(file_path),
                    simplified_path=_simplify_path(rel),
                )
            )
    entries.sort(key=lambda e: (e.simplified_path.lower(), e.file_name.lower(), e.purpose.lower()))
    return entries


def _write_markdown(output_path: Path, entries: list[PythonFileEntry]) -> None:
    lines = [
        "| 文件名 | 用途 | 路径 |",
        "|---|---|---|",
    ]
    for entry in entries:
        lines.append(
            "| "
            + " | ".join(
                [
                    _escape_md_cell(entry.file_name),
                    _escape_md_cell(entry.purpose),
                    _escape_md_cell(entry.simplified_path),
                ]
            )
            + " |"
        )
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parent
    week_dirs = [root / f"week{i}" for i in range(1, 7)]

    entries = _iter_python_files(root=root, week_dirs=week_dirs)
    output_path = root / "python_file_index.md"
    _write_markdown(output_path=output_path, entries=entries)

    print(f"共收录 {len(entries)} 个 Python 文件，已生成 python_file_index.md")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    main()
