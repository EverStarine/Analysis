#!/usr/bin/env python3
"""Read-only, stdlib TeX reference candidates for the three-volume Analysis book."""
import argparse
import bisect
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


EXCLUDED = {"tmp", ".git", ".agents", ".codex", "__pycache__"}
LABEL_MACROS = {"BookPart": 2, "OptionalChapter": 2, "OptionalSection": 2,
                "OptionalSubsection": 2, "BookAppendixPart": 1}
TOKEN = re.compile(
    r"\\(?P<cmd>BookPart|OptionalChapter|OptionalSection|OptionalSubsection|BookAppendixPart|"
    r"input|include|label|begin|end|crefrange|Crefrange|"
    r"cpagerefrange|Cpagerefrange|ref|cref|Cref|eqref|pageref|"
    r"autoref|nameref|itemref|vref|Vref|hyperref)\b\*?\s*"
    r"(?:\[(?P<opt>[^\]]*)\]\s*)?(?:\{(?P<arg>[^{}]*)\})?"
)
TEXT_POINTER = re.compile(r"第[一二三四五六七八九十百千万零〇两\d]+(?:卷|章|节)|"
                          r"前文|后文|后面.*(?:定理|公式)|上述(?:定理|引理|命题)|下述(?:定理|引理|命题)")


def blank(text):
    return "".join("\n" if c == "\n" else " " for c in text)


def braced_argument(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "{":
        return None, pos
    start, depth = pos + 1, 1
    pos += 1
    while pos < len(text):
        if text[pos] == "\\" and pos + 1 < len(text) and text[pos + 1] in "{}\\":
            pos += 2
            continue
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos], pos + 1
        pos += 1
    return None, pos


def scrub(text):
    """Keep offsets/line numbers; ignore comments and common verbatim constructs."""
    text = re.sub(r"\\begin\{(verbatim\*?|lstlisting|minted|comment)\}.*?\\end\{\1\}",
                  lambda m: blank(m.group()), text, flags=re.S)
    text = re.sub(r"\\verb\*?([^\w\s]).*?\1", lambda m: blank(m.group()), text)
    chars = list(text)
    for match in re.finditer("%", text):
        backslashes, pos = 0, match.start() - 1
        while pos >= 0 and text[pos] == "\\":
            backslashes += 1
            pos -= 1
        if backslashes % 2 == 0:
            end = text.find("\n", match.start())
            end = len(text) if end < 0 else end
            chars[match.start():end] = " " * (end - match.start())
    return "".join(chars)


def is_root(path):
    return (path / "Shared").is_dir() and all(
        (path / f"Book{n}" / f"Book{n}.tex").is_file() for n in (1, 2, 3)
    ) and (path / "工作流程说明.md").is_file()


def resolve_root(value):
    if value:
        root = Path(value).resolve()
        if is_root(root):
            return root
        raise ValueError("--root 必须是含三卷入口、Shared 和工作流程说明.md 的《分析学》项目根")
    for parent in Path(__file__).resolve().parents:
        if is_root(parent):
            return parent
    raise ValueError("未从脚本安装位置找到《分析学》项目，请传 --root")


def allowed(path, root):
    return path.is_relative_to(root) and not any(
        part in EXCLUDED for part in path.relative_to(root).parts
    )


def inventory(root):
    definitions, references = {}, {}
    input_issues, files, textual, parsed = [], set(), {}, {}

    def parse(path):
        if path not in parsed:
            raw = path.read_text(encoding="utf-8-sig")
            clean = scrub(raw)
            starts = [0] + [m.end() for m in re.finditer("\n", clean)]
            lines = raw.splitlines()
            parsed[path] = (clean, starts, lines, list(TOKEN.finditer(clean)))
        return parsed[path]

    for book in ("Book1", "Book2", "Book3"):
        sequence, seen, active, environments = 0, set(), set(), []
        book_dir = root / book

        def visit(path):
            nonlocal sequence
            if path in active:
                input_issues.append({"book": book, "file": path.relative_to(root).as_posix(),
                                     "issue": "input_cycle"})
                return
            if path in seen:
                input_issues.append({"book": book, "file": path.relative_to(root).as_posix(),
                                     "issue": "repeated_input_not_expanded"})
                return
            seen.add(path)
            active.add(path)
            files.add(path)
            clean, starts, lines, tokens = parse(path)
            relative = path.relative_to(root).as_posix()
            nearest_label = None
            for lineno, line in enumerate(clean.splitlines(), 1):
                if TEXT_POINTER.search(line):
                    textual[(relative, lineno)] = {"file": relative, "line": lineno,
                                                  "text": line.strip()[:400]}
            for match in tokens:
                sequence += 1
                command, arg = match["cmd"], match["arg"]
                line = bisect.bisect_right(starts, match.start())
                location = {"file": relative, "line": line}
                if command in ("input", "include"):
                    if not arg or any(c in arg for c in "#\\{}"): 
                        input_issues.append(dict(location, book=book, issue="dynamic_or_unbraced_input", target=arg))
                        continue
                    name = Path(arg.strip())
                    if not name.suffix:
                        name = name.with_suffix(".tex")
                    candidates = [(book_dir / name).resolve(), (path.parent / name).resolve()]
                    target = next((p for p in candidates if allowed(p, root) and p.is_file()), None)
                    if target is None:
                        input_issues.append(dict(location, book=book, issue="missing_or_outside_input", target=arg))
                    else:
                        visit(target)
                    continue
                if command == "begin" and arg:
                    environments.append(arg)
                    continue
                if command == "end" and arg:
                    if arg in environments:
                        del environments[len(environments) - 1 - environments[::-1].index(arg):]
                    continue
                values = match["opt"] if command == "hyperref" else arg
                if command in LABEL_MACROS:
                    pos = match.start() + len(command) + 1
                    for _ in range(LABEL_MACROS[command]):
                        values, pos = braced_argument(clean, pos)
                        if values is None:
                            break
                is_definition = command == "label" or command in LABEL_MACROS
                if not values:
                    continue
                if command.endswith("range"):
                    second = re.match(r"\s*\{([^{}]+)\}", clean[match.end():])
                    if second:
                        values += "," + second[1]
                snippet = " ".join(lines[max(0, line - 2):line + 2]).strip()[:500]
                for label in (x.strip() for x in values.split(",")):
                    if not label or any(c in label for c in "#\\{}\n"):
                        continue
                    key = (relative, match.start(), label)
                    store = definitions if is_definition else references
                    record = store.setdefault(key, dict(location, label=label, command=command,
                        context=snippet, nearest_label_hint=nearest_label,
                        environments=list(environments), source_order={}))
                    record["source_order"][book] = sequence
                    if is_definition:
                        nearest_label = label
            active.remove(path)

        visit((book_dir / f"{book}.tex").resolve())
    return list(definitions.values()), list(references.values()), input_issues, files, list(textual.values())


def report(args):
    root = resolve_root(args.root)
    scopes = []
    for value in args.scope:
        path = (root / value).resolve()
        if not allowed(path, root) or not path.exists():
            raise ValueError(f"范围必须是项目内存在且未排除的文件/目录: {value}")
        scopes.append(path)
    defs, refs, issues, files, text_candidates = inventory(root)

    def in_scope(relative):
        path = root / relative
        return any(path == s or path.is_relative_to(s) for s in scopes)

    for scope in scopes:
        if not any(p == scope or p.is_relative_to(scope) for p in files):
            raise ValueError(f"范围没有出现在三卷有效输入链中: {scope.relative_to(root)}")
    by_label = defaultdict(list)
    for record in defs:
        by_label[record["label"]].append(record)
    all_keys = set(by_label) | {r["label"] for r in refs}
    missing_request = set(args.label) - all_keys
    if missing_request:
        raise ValueError("指定标签在定义和引用中均不存在: " + ", ".join(sorted(missing_request)))
    selected = set(args.label) | {d["label"] for d in defs if in_scope(d["file"])}
    if args.all:
        selected = all_keys
    chosen_refs = [r for r in refs if args.all or in_scope(r["file"]) or r["label"] in selected]
    for ref in chosen_refs:
        targets = by_label.get(ref["label"], [])
        ref["targets"] = [dict(file=t["file"], line=t["line"], context=t["context"],
                                environments=t["environments"]) for t in targets]
        relations = {}
        for book, order in ref["source_order"].items():
            same_book = [t for t in targets if book in t["source_order"]]
            if not targets:
                relations[book] = "unresolved_candidate"
            elif not same_book:
                relations[book] = "other_volume_only_internal_reference"
            elif len(same_book) > 1:
                relations[book] = "ambiguous_duplicate_label"
            else:
                relations[book] = "target_later_in_source" if same_book[0]["source_order"][book] > order else "target_earlier_in_source"
        ref["syntactic_relation"] = relations
        ref["selection_reason"] = "direct_reverse_reference" if ref["label"] in selected and not in_scope(ref["file"]) else "source_scope"
    relevant_keys = selected | {r["label"] for r in chosen_refs}
    duplicate_labels = []
    for label in sorted(relevant_keys):
        targets = by_label.get(label, [])
        for book in ("Book1", "Book2", "Book3"):
            locations = [{"file": t["file"], "line": t["line"]} for t in targets if book in t["source_order"]]
            if len(locations) > 1:
                duplicate_labels.append({"label": label, "book": book, "locations": locations})
    selected_files = {d["file"] for d in defs if d["label"] in selected}
    textual = [t for t in text_candidates if args.all or in_scope(t["file"]) or t["file"] in selected_files]
    return {
        "project_root": str(root),
        "scope": {"paths": args.scope, "labels": args.label, "all": args.all},
        "limitations": ["语法候选不等于语义证明依赖；同卷源码顺序不判定逻辑循环", "不展开宏、条件、动态输入或外部辅助标签；文字指向可能漏检", "最近标签仅作上下文提示；输入链异常可能导致覆盖不完整"],
        "inventory_counts": {"active_tex_files": len(files), "label_definitions": len(defs), "reference_occurrences": len(refs)},
        "active_input_files": sorted(p.relative_to(root).as_posix() for p in files),
        "input_issues": issues,
        "definitions": [d for d in defs if d["label"] in relevant_keys],
        "references": chosen_refs,
        "duplicate_label_candidates": duplicate_labels,
        "unresolved_candidates": [r for r in chosen_refs if "unresolved_candidate" in r["syntactic_relation"].values()],
        "cross_volume_internal_reference_candidates": [r for r in chosen_refs if "other_volume_only_internal_reference" in r["syntactic_relation"].values()],
        "textual_pointer_candidates": textual[:args.max_text_candidates],
        "textual_pointer_candidates_omitted": max(0, len(textual) - args.max_text_candidates),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", help="Explicit Analysis project root, otherwise infer from installation")
    parser.add_argument("--scope", action="append", default=[], help="Project-relative file or directory; repeatable")
    parser.add_argument("--label", action="append", default=[], help="Stable label whose direct callers are needed; repeatable")
    parser.add_argument("--all", action="store_true", help="Explicit whole-book static inventory")
    parser.add_argument("--max-text-candidates", type=int, default=100)
    args = parser.parse_args()
    if not (args.scope or args.label or args.all):
        parser.error("请选择 --scope、--label 或 --all")
    if args.max_text_candidates < 0:
        parser.error("--max-text-candidates 不能为负数")
    try:
        result = report(args)
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(2, f"error: {error}\n")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
