#!/usr/bin/env python3
"""Read-only literal LaTeX term/index inventory; not a TeX interpreter."""

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import sys


MACROS = {"term", "termidx", "foreignidx", "symidx"}
EXCLUDED = {".git", ".agents", ".codex", "tmp", "work", "outputs"}
VERBATIM_ENV = re.compile(r"\\begin\{(verbatim\*?|Verbatim|lstlisting|minted|comment)\}")
DECLARATIONS = {
    "newcommand", "renewcommand", "providecommand", "DeclareRobustCommand",
    "NewDocumentCommand", "RenewDocumentCommand", "ProvideDocumentCommand",
    "DeclareDocumentCommand",
}


def control(text, pos):
    """Return a control sequence name and the first position after it."""
    match = re.match(r"\\([A-Za-z@]+|.)", text[pos:], re.DOTALL)
    return (match.group(1), pos + len(match.group(0))) if match else ("", pos + 1)


def blank_span(chars, start, end):
    for pos in range(start, end):
        if chars[pos] not in "\r\n":
            chars[pos] = " "


def mask_noncode(text):
    """Preserve source offsets while masking comments and common literal areas."""
    chars = list(text)
    pos = 0
    while pos < len(text):
        if text[pos] == "%":
            end = text.find("\n", pos)
            end = len(text) if end < 0 else end
            blank_span(chars, pos, end)
            pos = end
        elif text[pos] == "\\":
            name, end = control(text, pos)
            env = VERBATIM_ENV.match(text, pos)
            if env:
                close = "\\end{" + env.group(1) + "}"
                found = text.find(close, env.end())
                end = len(text) if found < 0 else found + len(close)
                blank_span(chars, pos, end)
            elif name == "verb":
                if end < len(text) and text[end] == "*":
                    end += 1
                if end < len(text) and not text[end].isspace():
                    found = text.find(text[end], end + 1)
                    newline = text.find("\n", end)
                    if found >= 0 and (newline < 0 or found < newline):
                        end = found + 1
                    else:
                        end = len(text) if newline < 0 else newline
                    blank_span(chars, pos, end)
            pos = end
        else:
            pos += 1
    return "".join(chars)


def space(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def group(text, pos, opening, required=False, raw=None):
    checkpoint = pos
    pos = space(text, pos)
    if pos >= len(text) or text[pos] != opening:
        if required:
            raise ValueError("expected " + opening + " argument")
        return None, checkpoint
    closing = "}" if opening == "{" else "]"
    start = pos + 1
    pos = start
    braces = 1 if opening == "{" else 0
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            _, pos = control(text, pos)
            continue
        if char == "{":
            braces += 1
        elif char == "}":
            braces -= 1
            if opening == "{" and braces == 0:
                return (raw if raw is not None else text)[start:pos], pos + 1
            if braces < 0:
                raise ValueError("unmatched closing brace in optional argument")
        elif char == closing and braces == 0:
            return (raw if raw is not None else text)[start:pos], pos + 1
        pos += 1
    raise ValueError("unclosed " + opening + " argument")


def skip_declaration(text, pos, name):
    """Skip common command declarations; other dynamic TeX remains out of scope."""
    pos = space(text, pos)
    if pos < len(text) and text[pos] == "*":
        pos = space(text, pos + 1)
    if pos < len(text) and text[pos] == "{":
        _, pos = group(text, pos, "{", True)
    elif pos < len(text) and text[pos] == "\\":
        _, pos = control(text, pos)
    else:
        raise ValueError("unsupported command declaration")
    if "DocumentCommand" in name:
        _, pos = group(text, pos, "{", True)
    else:
        _, pos = group(text, pos, "[")
        _, pos = group(text, pos, "[")
    _, pos = group(text, pos, "{", True)
    return pos


def normalize(value):
    if value is None:
        return None
    parts = []
    pos = 0
    while pos < len(value):
        if value[pos] == "\\":
            _, end = control(value, pos)
            parts.append(value[pos:end])
            pos = end
        elif value[pos] == "%":
            newline = value.find("\n", pos)
            pos = len(value) if newline < 0 else newline + 1
        else:
            parts.append(value[pos])
            pos += 1
    return re.sub(r"\s+", " ", "".join(parts)).strip()


def inventory_file(path, root):
    original = path.read_text(encoding="utf-8-sig")
    text = mask_noncode(original)
    entries, diagnostics = [], []
    pos = 0
    relative = path.relative_to(root).as_posix()
    while pos < len(text):
        if text[pos] != "\\":
            pos += 1
            continue
        start = pos
        name, pos = control(text, pos)
        if name not in MACROS and name not in DECLARATIONS:
            continue
        location = {"file": relative, "line": text.count("\n", 0, start) + 1}
        try:
            if name in DECLARATIONS:
                pos = skip_declaration(text, pos, name)
                continue
            starred = False
            key, foreign = None, None
            pos = space(text, pos)
            if name == "term" and pos < len(text) and text[pos] == "*":
                starred, pos = True, pos + 1
            if name != "symidx":
                key, pos = group(text, pos, "[", raw=original)
            display, pos = group(text, pos, "{", True, raw=original)
            if name == "term":
                foreign, pos = group(text, pos, "[", raw=original)
            entries.append({
                **location, "macro": name, "starred": starred,
                "display": normalize(display), "sort_key": normalize(key),
                "original": normalize(foreign),
                "end_line": text.count("\n", 0, pos) + 1,
                "source": original[start:pos],
            })
        except ValueError as exc:
            diagnostics.append({**location, "macro": name, "reason": str(exc)})
            pos = max(pos, start + 1)
    return entries, diagnostics


def candidates(entries):
    """Lexical leads only; differing concepts and repeated volumes need review."""
    findings = []
    by_display, by_key = defaultdict(list), defaultdict(list)
    for entry in entries:
        volume = entry["file"].split("/")[0]
        macro = entry["macro"]
        kind = "chinese" if macro in {"term", "termidx"} else macro
        by_display[(volume, kind, entry["display"])].append(entry)
        if entry["sort_key"]:
            by_key[(volume, kind, entry["sort_key"])].append(entry)
        if kind == "chinese" and not entry["sort_key"] and re.search(r"[\u3400-\u9fff]", entry["display"]):
            findings.append({"kind": "missing_explicit_chinese_sort_key", "entries": [entry]})
        if any(char in (entry[field] or "") for field in ("display", "sort_key", "original") for char in "|@!"):
            findings.append({"kind": "makeindex_special_character_review", "entries": [entry]})
    for group_entries in by_display.values():
        keys = {entry["sort_key"] or "" for entry in group_entries}
        if len(keys) > 1:
            findings.append({"kind": "same_display_different_sort_keys", "entries": group_entries})
        if sum(entry["macro"] == "term" for entry in group_entries) > 1:
            findings.append({"kind": "repeated_term_introduction", "entries": group_entries})
        if len(group_entries) > 1 and group_entries[0]["macro"] == "symidx":
            findings.append({"kind": "repeated_literal_symbol_entry", "entries": group_entries})
        foreign_forms = {entry["original"] for entry in group_entries if entry["original"]}
        if len(foreign_forms) > 1:
            findings.append({"kind": "same_display_different_originals", "entries": group_entries})
    for group_entries in by_key.values():
        if len({entry["display"] for entry in group_entries}) > 1:
            findings.append({"kind": "shared_sort_key_different_displays", "entries": group_entries})
    return findings


def collect_paths(root, scopes):
    paths = set()
    for scope in scopes:
        candidate = (root / scope).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError("scope must stay inside --root: " + scope)
        if not candidate.exists():
            raise ValueError("scope does not exist: " + scope)
        selected = [candidate] if candidate.is_file() else candidate.rglob("*.tex")
        for path in selected:
            resolved = path.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError("resolved source leaves --root: " + str(path))
            if path.suffix.lower() == ".tex" and not (set(path.relative_to(root).parts) & EXCLUDED):
                paths.add(resolved)
    if not paths:
        raise ValueError("scope contains no eligible .tex files")
    return sorted(paths)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="project root")
    parser.add_argument("--scope", action="append", required=True, help="file or directory relative to root; repeatable")
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        paths = collect_paths(root, args.scope)
        entries, diagnostics = [], []
        for path in paths:
            found, issues = inventory_file(path, root)
            entries.extend(found)
            diagnostics.extend(issues)
    except (ValueError, OSError, UnicodeError) as exc:
        parser.error(str(exc))
    result = {
        "scope": args.scope, "files": [path.relative_to(root).as_posix() for path in paths],
        "limits": "Literal inventory only; lexical file order is not input order. No macro expansion, condition evaluation, definition-order, pinyin, semantic or PDF/index-output validation. Direct index commands are not inventoried.",
        "entry_count": len(entries), "entries": entries,
        "candidates": candidates(entries), "parse_diagnostics": diagnostics,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if diagnostics else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
