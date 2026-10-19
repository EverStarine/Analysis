#!/usr/bin/env python3
"""Audit Analysis PDF outlines against the active heading inventory.

Purpose: check numbering, hierarchy, titles, optional marks and destinations;
write current JSON/TSV/Markdown evidence only to the explicit --out-dir.
Reassess the parser when project layout, heading macros or PDF drivers change.
The PDF directory may contain BookN.pdf or BookN/BookN.pdf (isolated builds).
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import hashlib
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader
from pypdf.generic import Destination, NullObject


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def chinese_number(n: int) -> str:
    digits = "零一二三四五六七八九"
    if n < 10:
        return digits[n]
    if n < 20:
        return "十" + (digits[n % 10] if n % 10 else "")
    if n < 100:
        return digits[n // 10] + "十" + (digits[n % 10] if n % 10 else "")
    raise ValueError(f"Unsupported chapter number {n}")


def expected_prefix(dest_name: str | None) -> str | None:
    if not dest_name:
        return None
    m = re.fullmatch(r"chapter\.(\d+)", dest_name)
    if m:
        return f"第{chinese_number(int(m[1]))}章"
    m = re.fullmatch(r"appendix\.([A-Z]+)", dest_name)
    if m:
        return f"附录 {m[1]}"
    m = re.fullmatch(r"(?:section|subsection|subsubsection)\.([A-Z]|\d+)((?:\.\d+)+)", dest_name)
    if m:
        return m[1] + m[2]
    return None


def prefix_ok(title: str, prefix: str) -> bool:
    return bool(prefix_match(title, prefix))


def prefix_match(title: str, prefix: str):
    # The optional-reading star belongs to the number, not to the heading text.
    # A boundary after the complete prefix prevents 3.5 from matching 3.50.
    return re.match(r"^" + re.escape(prefix) + r"(?P<star>\*)?(?:\s|$)", title)


def content_title(title: str, prefix: str | None) -> str:
    match = prefix_match(title, prefix) if prefix else None
    if match:
        return title[match.end():].strip()
    return title.strip()


def group(text: str, pos: int):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos >= len(text) or text[pos] != "{":
        raise ValueError(f"Expected braced argument at {pos}: {text!r}")
    start, depth = pos + 1, 1
    pos += 1
    while pos < len(text):
        if text[pos] == "\\":
            pos += 2
            continue
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos], pos + 1
        pos += 1
    raise ValueError(f"Unclosed braced argument: {text!r}")


def pdf_branches(text: str) -> str:
    pattern = re.compile(r"\\texorpdfstring\s*")
    while match := pattern.search(text):
        _, pos = group(text, match.end())
        pdf, end = group(text, pos)
        # Retain an argument boundary so a control word inside the PDF branch
        # cannot consume a following space outside that argument.
        text = text[:match.start()] + "{" + pdf_branches(pdf) + "}" + text[end:]
    return text


def canonical_title(text: str) -> str:
    return unicodedata.normalize("NFC", re.sub(r"\s+", " ", text).strip())


def expected_pdf_title(heading: dict, dest_name: str | None) -> str:
    # Compare the PDF branch rather than make_inventory.py's printed TeX branch.
    # The mapping follows the live Shared/Preamble.tex definitions.
    text = pdf_branches(heading.get("raw_title", heading["title"]))
    macros = {
        "AnalysisPdfAlpha": "α", "AnalysisPdfGamma": "Γ",
        "AnalysisPdfLambda": "λ", "AnalysisPdfMu": "μ",
        "AnalysisPdfPi": "π", "AnalysisPdfSigma": "σ",
        "AnalysisPdfTheta": "θ", "AnalysisPdfXi": "ξ", "AnalysisPdfZeta": "ζ",
        "AnalysisPdfCapitalLambda": "Λ", "AnalysisPdfVarPhi": "φ",
        "AnalysisPdfVarTheta": "ϑ", "AnalysisPdfPsi": "ψ", "AnalysisPdfWeierstrassP": "℘",
        "WeakStar": "弱∗", "WeakStarJoin": "", "AnalysisOptionalMark": "*",
        "alpha": "α", "Gamma": "Γ", "lambda": "λ", "mu": "μ",
        "pi": "π", "sigma": "σ", "theta": "θ", "xi": "ξ", "zeta": "ζ",
    }
    for name, value in sorted(macros.items(), key=lambda item: -len(item[0])):
        text = re.sub(r"\\" + re.escape(name) + r"(?![A-Za-z])(?:\{\}|[ \t\r\n]*)", lambda _: value, text)
    accents = {"'": "\u0301", "`": "\u0300", '"': "\u0308", "^": "\u0302", "~": "\u0303", "=": "\u0304", ".": "\u0307"}
    text = re.sub(r"\\(['`\"^~=.])(?:\{([A-Za-z])\}|([A-Za-z]))", lambda m: unicodedata.normalize("NFC", (m[2] or m[3]) + accents[m[1]]), text)
    wrappers = re.compile(r"\\(?:textnormal|textup|textrm|textbf|textit|emph|mathrm|mathit|mbox|ensuremath)\s*")
    while match := wrappers.search(text):
        body, end = group(text, match.end())
        text = text[:match.start()] + body + text[end:]
    # Hyperref drops TeX sub/superscript tokens in unprotected math titles.
    text = re.sub(r"\\\((.*?)\\\)", lambda m: m[1].replace("^", "").replace("_", ""), text, flags=re.S)
    text = re.sub(r"\$([^$]*)\$", lambda m: m[1].replace("^", "").replace("_", ""), text)
    text = text.replace("\\\\", "")
    text = text.replace("\\ ", " ").replace("\\,", " ").replace("\\;", " ")
    text = text.replace("\\&", "&").replace("\\%", "%").replace("\\_", "_")
    remaining = re.findall(r"\\[A-Za-z]+|\\[^\s]", text)
    if remaining:
        raise ValueError(f"Unresolved PDF-title macros: {sorted(set(remaining))}")
    text = text.replace("---", "—").replace("--", "–")
    text = text.replace("~", " ").replace("{", "").replace("}", "").replace("$", "")
    part = re.fullmatch(r"part\.(\d+)", dest_name or "")
    if heading["level"] == "part" and part:
        text = f"第{chinese_number(int(part[1]))}编 " + text
    return canonical_title(text)


def number_or_null(value):
    if value is None or isinstance(value, NullObject):
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return str(value)


def extract(pdf: Path, book: int, headings: list[dict], check_titles: bool = False) -> dict:
    reader = PdfReader(pdf)
    named = reader.named_destinations
    labels = reader.page_labels
    nodes = []
    traversal_errors = []
    visited = set()

    def walk(ref, level, parent_index):
        while ref:
            node = ref.get_object()
            ir = node.indirect_reference
            obj_id = f"{ir.idnum} {ir.generation} R" if ir else None
            if obj_id in visited:
                traversal_errors.append(f"Outline cycle at {obj_id}")
                return
            visited.add(obj_id)
            title = str(node.get("/Title", ""))
            action = node.get("/A", {})
            dest_raw = action.get("/D", node.get("/Dest"))
            dest_name = str(dest_raw) if isinstance(dest_raw, str) else None
            dest = named.get(dest_name) if dest_name else None
            target_error = None
            if dest is None and isinstance(dest_raw, (list, tuple)):
                try:
                    dest = Destination(title, dest_raw[0], dest_raw[1], *dest_raw[2:])
                except Exception as exc:
                    target_error = str(exc)
            page = None
            if dest is not None:
                try:
                    page0 = reader.get_destination_page_number(dest)
                    if page0 is not None and 0 <= page0 < len(reader.pages):
                        page = page0 + 1
                    else:
                        target_error = f"Destination has invalid page {page0}"
                except Exception as exc:
                    target_error = str(exc)
            else:
                target_error = target_error or f"Unresolved destination {dest_raw!s}"
            prefix = expected_prefix(dest_name)
            index = len(nodes)
            record = {
                "index": index,
                "level": level,
                "parent_index": parent_index,
                "title": title,
                "content_title": content_title(title, prefix),
                "expected_prefix": prefix,
                "numbered_prefix_present": prefix_ok(title, prefix) if prefix else None,
                "optional_mark_present": bool(prefix_match(title, prefix).group("star")) if prefix and prefix_match(title, prefix) else False,
                "destination_name": dest_name,
                "page": page,
                "page_label": labels[page - 1] if page else None,
                "target_type": str(dest.get("/Type")) if dest else None,
                "left": number_or_null(dest.get("/Left")) if dest else None,
                "top": number_or_null(dest.get("/Top")) if dest else None,
                "zoom": number_or_null(dest.get("/Zoom")) if dest else None,
                "outline_object": obj_id,
                "count": int(node["/Count"]) if "/Count" in node else None,
                "action_type": str(action.get("/S")) if action else None,
                "target_error": target_error,
            }
            nodes.append(record)
            if node.get("/First"):
                walk(node.raw_get("/First"), level + 1, index)
            ref = node.raw_get("/Next") if node.get("/Next") else None

    outlines = reader.trailer["/Root"].get("/Outlines")
    if outlines and outlines.get("/First"):
        walk(outlines.raw_get("/First"), 0, None)

    source = sorted((h for h in headings if h["book"] == book), key=lambda h: h["order"])
    source_map = {h["id"]: i for i, h in enumerate(source)}
    source_errors = []
    source_title_errors = []
    if len(source) != len(nodes):
        source_errors.append(f"Source headings {len(source)} != PDF outline entries {len(nodes)}")
    for i, (record, h) in enumerate(zip(nodes, source)):
        record["source_id"] = h["id"]
        record["source_level"] = h["level"]
        record["source_file"] = h["file"]
        record["source_line"] = h["line"]
        record["source_title"] = h["title"]
        record["source_starred"] = h["starred"]
        record["source_optional"] = h["optional"]
        try:
            record["source_pdf_title"] = expected_pdf_title(h, record["destination_name"])
            record["source_pdf_title_error"] = None
            record["source_title_matches"] = canonical_title(record["content_title"]) == record["source_pdf_title"]
        except ValueError as exc:
            record["source_pdf_title"] = None
            record["source_pdf_title_error"] = str(exc)
            record["source_title_matches"] = False
        if check_titles:
            if record["source_pdf_title_error"]:
                source_title_errors.append(f"Entry {i} {h['id']}: {record['source_pdf_title_error']}")
            elif not record["source_title_matches"]:
                source_title_errors.append(f"Entry {i} {h['id']}: PDF heading {record['content_title']!r} != inventory PDF branch {record['source_pdf_title']!r}")
            if record["expected_prefix"] and record["optional_mark_present"] != h["optional"]:
                source_title_errors.append(f"Entry {i} {h['id']}: optional star {record['optional_mark_present']} != inventory optional {h['optional']}")
        parent = source_map.get(h["parent_id"])
        if parent == 0 and source[0]["level"] == "volume":
            parent = None
        if record["parent_index"] != parent:
            source_errors.append(f"Entry {i} ({record['title']}): PDF parent {record['parent_index']} != source parent {parent}")

    grouped_dest = collections.defaultdict(list)
    grouped_sibling_title = collections.defaultdict(list)
    grouped_exact = collections.defaultdict(list)
    for n in nodes:
        if n["destination_name"]:
            grouped_dest[n["destination_name"]].append(n["index"])
        grouped_sibling_title[(n["parent_index"], n["title"])].append(n["index"])
        grouped_exact[(n["parent_index"], n["title"], n["page"], n["destination_name"])].append(n["index"])
    duplicate_dest = {k: v for k, v in grouped_dest.items() if len(v) > 1}
    sibling_repeats = [{"parent_index": k[0], "title": k[1], "indices": v} for k, v in grouped_sibling_title.items() if len(v) > 1]
    exact_repeats = [{"parent_index": k[0], "title": k[1], "page": k[2], "destination_name": k[3], "indices": v} for k, v in grouped_exact.items() if len(v) > 1]
    page_backtracks = []
    for a, b in zip(nodes, nodes[1:]):
        if a["page"] and b["page"] and b["page"] < a["page"]:
            page_backtracks.append({"from_index": a["index"], "from_page": a["page"], "to_index": b["index"], "to_page": b["page"]})
    prefixes = [n for n in nodes if n["expected_prefix"]]
    return {
        "book": book,
        "pdf": str(pdf.resolve()),
        "size_bytes": pdf.stat().st_size,
        "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
        "pages": len(reader.pages),
        "outline_entries": len(nodes),
        "source_headings": len(source),
        "counts_by_depth": dict(sorted(collections.Counter(n["level"] for n in nodes).items())),
        "counts_by_source_level": dict(collections.Counter(n.get("source_level") for n in nodes)),
        "numbered_entries": len(prefixes),
        "missing_number_prefix_count": sum(not n["numbered_prefix_present"] for n in prefixes),
        "missing_number_prefix_indices": [n["index"] for n in prefixes if not n["numbered_prefix_present"]],
        "target_error_indices": [n["index"] for n in nodes if n["target_error"]],
        "traversal_errors": traversal_errors,
        "source_hierarchy_errors": source_errors,
        "source_title_errors": source_title_errors,
        "source_title_mismatch_count": sum(not n.get("source_title_matches", False) for n in nodes),
        "source_title_checks_required": check_titles,
        "duplicate_destinations": duplicate_dest,
        "duplicate_sibling_titles": sibling_repeats,
        "duplicate_exact_entries": exact_repeats,
        "page_backtracks": page_backtracks,
        "nodes": nodes,
    }


def compare(current, baseline):
    errors = []
    page_moves = []
    title_changes = []
    old = {b["book"]: b for b in baseline["books"]}
    for book in current["books"]:
        prev = old[book["book"]]
        if len(book["nodes"]) != len(prev["nodes"]):
            errors.append(f"Book{book['book']} outline count changed: {len(prev['nodes'])} -> {len(book['nodes'])}")
        for a, b in zip(prev["nodes"], book["nodes"]):
            for key in ["level", "parent_index", "destination_name"]:
                if a[key] != b[key]:
                    errors.append(f"Book{book['book']} entry {b['index']} {key}: {a[key]!r} -> {b[key]!r}")
            old_title = content_title(a["title"], a["expected_prefix"])
            if canonical_title(old_title) != canonical_title(b["content_title"]):
                title_changes.append({"book": book["book"], "index": b["index"], "source_id": b.get("source_id"), "old_title": old_title, "new_title": b["content_title"], "new_inventory_matches": b.get("source_title_matches")})
            if a["page"] != b["page"] or a["top"] != b["top"]:
                page_moves.append({"book": book["book"], "index": b["index"], "title": b["title"], "old_page": a["page"], "new_page": b["page"], "old_top": a["top"], "new_top": b["top"]})
    return {"errors": errors, "title_changes": title_changes, "page_or_vertical_target_moves": page_moves}


def write_outputs(report, out, tag):
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{tag}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["book", "index", "level", "parent_index", "title", "expected_prefix", "numbered_prefix_present", "optional_mark_present", "destination_name", "page", "page_label", "target_type", "left", "top", "zoom", "source_id", "source_file", "source_line", "source_pdf_title", "source_title_matches"]
    with (out / f"{tag}-outlines.tsv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for book in report["books"]:
            for n in book["nodes"]:
                writer.writerow({"book": book["book"], **n})
    lines = [f"# PDF 书签检查：{tag}", "",
             "> **总则**：所有规则都必须写明设立的原因；当规则的原因失效时，规则也应同步失效并删除或修订。所有工作记录都必须服务于后续工作效率的提升；仅记录流水账、对后续工作无意义的内容没有保留必要，评估为无用时应清理。", "",
             "**用途与有效性**：本记录保存当前 PDF 的身份、书签与源码标题对应关系，帮助后续定位导航问题及判断既有核验是否仍可沿用。对应源码、标题清单或 PDF 改变后，本次通过结论不再自动适用，应按实际影响重新核验；旧记录不再支持当前身份或未决问题时，合并必要信息后清理。", "",
             f"提取时间：{report['generated_at']}。PDF 页码以 1 为起点，page_label 是 PDF 页标签。", "", "| 卷 | 页数 | 书签数 | 须编号条目 | 缺编号 | 无效目标 | 层级异常 | 精确重复 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for b in report["books"]:
        lines.append(f"| {b['book']} | {b['pages']} | {b['outline_entries']} | {b['numbered_entries']} | {b['missing_number_prefix_count']} | {len(b['target_error_indices'])} | {len(b['source_hierarchy_errors'])} | {len(b['duplicate_exact_entries'])} |")
    lines += ["", "## 各卷结构及首末编号样例", ""]
    for b in report["books"]:
        lines += [f"### 第 {b['book']} 卷", "", f"SHA-256：`{b['sha256']}`", "", f"深度数量：`{b['counts_by_depth']}`；源层级数量：`{b['counts_by_source_level']}`。", ""]
        numbered = [n for n in b["nodes"] if n["expected_prefix"]]
        samples = numbered[:4] + [n for n in numbered if (n["destination_name"] or "").startswith("appendix.")] + numbered[-3:]
        for n in samples:
            lines.append(f"- 深度 {n['level']}：`{n['title']}`；应有前缀 `{n['expected_prefix']}`；PDF 页 {n['page']}，页标签 {n['page_label']}；目标 `{n['destination_name']}`。")
        lines += ["", "附录与后附材料：", ""]
        for n in b["nodes"]:
            if n["title"] == "附录" or (n["destination_name"] or "").startswith("appendix.") or n["title"] in ["后记", "参考文献", "中文索引", "外文索引", "符号索引"]:
                p = b["nodes"][n["parent_index"]]["title"] if n["parent_index"] is not None else "PDF 根层"
                lines.append(f"- `{n['title']}`：深度 {n['level']}，父项 `{p}`，PDF 页 {n['page']}，目标 `{n['destination_name']}`。")
        lines += ["", f"重复目标：{len(b['duplicate_destinations'])}；同父同名条目：{len(b['duplicate_sibling_titles'])}；精确重复：{len(b['duplicate_exact_entries'])}；目标页倒退：{len(b['page_backtracks'])}。", ""]
        if b["source_hierarchy_errors"]:
            lines.extend(f"- {e}" for e in b["source_hierarchy_errors"])
        if b["source_title_checks_required"]:
            lines += [f"题名与指定新清单不符：{b['source_title_mismatch_count']}；题名/选读星号错误：{len(b['source_title_errors'])}。", ""]
            lines.extend(f"- {e}" for e in b["source_title_errors"])
    if report.get("comparison"):
        c = report["comparison"]
        lines += ["## 与基线比较", "", f"树结构/目的地差异：{len(c['errors'])}；有记录的题名变化：{len(c['title_changes'])}；页码或纵向目标移动：{len(c['page_or_vertical_target_moves'])}。题名变化与指定新清单核对，不要求与旧基线相同。", ""]
        lines.extend(f"- {e}" for e in c["errors"])
    lines += ["## 验证结论", "", f"结构验证：{'通过' if not report['errors'] else '未通过'}。", ""]
    lines.extend(f"- {e}" for e in report["errors"])
    lines += ["完整树及坐标见同名 JSON/TSV。复用时显式指定 `--out-dir` 与 `--heading-inventory`，并以 `--pdf-dir` 选择成品或隔离构建目录；只有需要比较固定结构时才传入 `--baseline`。", ""]
    (out / f"{tag}-report.md").write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="current")
    parser.add_argument("--volumes", type=int, nargs="+", choices=[1, 2, 3], default=[1, 2, 3])
    parser.add_argument("--pdf-dir", type=Path, default=ROOT)
    parser.add_argument("--out-dir", type=Path, required=True, help="Explicit directory for current audit outputs")
    parser.add_argument("--inventory", type=Path, help="Source heading inventory; use --heading-inventory for strict title checks")
    parser.add_argument("--heading-inventory", type=Path, help="Use the final source inventory and strictly match all PDF-branch titles and optional stars")
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--require-numbered", action="store_true")
    args = parser.parse_args()
    inventory = args.heading_inventory or args.inventory
    if inventory is None:
        parser.error("Supply --heading-inventory or --inventory.")
    headings = json.loads(inventory.read_text(encoding="utf-8"))["headings"]
    books = []
    for book in sorted(set(args.volumes)):
        flat = args.pdf_dir / f"Book{book}.pdf"
        isolated = args.pdf_dir / f"Book{book}" / f"Book{book}.pdf"
        pdf = flat if flat.is_file() else isolated
        if not pdf.is_file():
            parser.error(f"Missing PDF: {flat} or {isolated}")
        books.append(extract(pdf, book, headings, bool(args.heading_inventory)))
    report = {"generated_at": datetime.datetime.now().astimezone().isoformat(), "inventory": str(inventory.resolve()), "source_title_checks_required": bool(args.heading_inventory), "books": books, "errors": []}
    for b in report["books"]:
        if b["target_error_indices"]:
            report["errors"].append(f"Book{b['book']}: {len(b['target_error_indices'])} unresolved destinations")
        report["errors"].extend(b["source_hierarchy_errors"])
        report["errors"].extend(b["source_title_errors"])
        report["errors"].extend(b["traversal_errors"])
        if b["duplicate_exact_entries"] or b["duplicate_destinations"]:
            report["errors"].append(f"Book{b['book']}: duplicate outline destination or exact entry")
        if b["page_backtracks"]:
            report["errors"].append(f"Book{b['book']}: outline destinations move backward in page order")
        if args.require_numbered and b["missing_number_prefix_count"]:
            report["errors"].append(f"Book{b['book']}: {b['missing_number_prefix_count']} missing number prefixes")
    if args.baseline:
        baseline_path = args.baseline.resolve()
        report["comparison"] = compare(report, json.loads(baseline_path.read_text(encoding="utf-8")))
        report["errors"].extend(report["comparison"]["errors"])
    write_outputs(report, args.out_dir, args.tag)
    summary = [{k: b[k] for k in ["book", "pages", "outline_entries", "numbered_entries", "missing_number_prefix_count", "counts_by_depth"]} for b in report["books"]]
    print(json.dumps({"summary": summary, "errors": report["errors"], "report": str(args.out_dir / f"{args.tag}-report.md")}, ensure_ascii=False, indent=2))
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
