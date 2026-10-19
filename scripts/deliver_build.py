#!/usr/bin/env python3
"""Verify and optionally deliver one successful Analysis build, without rebuilding.

Default mode only reads. Delivery backs up existing selected-volume outputs, then
writes their PDFs, relinked editor SyncTeX and one current delivery identity JSON.
Reassess when the official build manifest, source exclusions, audit/inventory
schemas, TeX diagnostics or project layout change; this is not mathematical review.
"""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import stat
import sys

sys.dont_write_bytecode = True
from make_inventory import make_inventory
from audit_bookmarks import canonical_title, expected_pdf_title

ROOT = Path(__file__).resolve().parent.parent
READ_HASHES = {}
EXCLUDED = re.compile(r"\.(aux|log|toc|out|bcf|bbl|blg|run\.xml|idx|ind|ilg|fls|fdb_latexmk|synctex(\.gz)?|xdv|nav|snm|vrb|lof|lot)$", re.I)
BAD_LOG = re.compile(
    r"There were undefined (?:references|citations)|There were multiply-defined labels|"
    r"(?:Reference|Citation) .+ undefined|LaTeX Warning: Label .+ multiply defined|"
    r"^! |LaTeX Error:|Package \S+ Error:|Missing character:|Overfull \\[hv]box|"
    r"Rerun to get|Please \(re\)run|Please rerun|Label\(s\) may have changed|"
    r"rerunfilecheck Warning|Token not allowed in a PDF string|Float too large|"
    r"Too many unprocessed floats|Float\(s\) lost", re.M | re.I)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inside(path, parent):
    return path == parent or parent in path.parents


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read_json(path):
    return json.loads(read_bytes(path).decode("utf-8-sig"))


def read_bytes(path):
    data = path.read_bytes()
    READ_HASHES[path.resolve()] = hashlib.sha256(data).hexdigest().upper()
    return data


def rel(path):
    return path.relative_to(ROOT).as_posix()


def identity(sources):
    text = "\n".join(f"{p}:{h}" for p, h in sorted(sources.items()))
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def source_files(base, volumes):
    files = {}
    for folder in ["Shared"] + [f"Book{v}" for v in volumes]:
        directory = base / folder
        require(directory.is_dir(), f"Missing source directory: {directory}")
        for p in [directory, *directory.rglob("*")]:
            require(not (p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                    f"Source link/junction needs scope review: {p}")
            if p.is_file() and not EXCLUDED.search(p.name) and not (folder.startswith("Book") and p.name == f"{folder}.pdf"):
                files[p.relative_to(base).as_posix()] = sha(p)
    return files


def check_sources(run, volumes, expected):
    for base in (ROOT, run / "source"):
        actual = source_files(base, volumes)
        require(actual == expected, f"Source set/hash mismatch: {base}; "
                f"missing={sorted(expected.keys() - actual.keys())[:5]}, "
                f"added={sorted(actual.keys() - expected.keys())[:5]}, "
                f"changed={[p for p in actual.keys() & expected.keys() if actual[p] != expected[p]][:5]}")


def prepare_synctex(run, book, source_hashes):
    """Resolve .. before classifying inputs; only actual snapshot sources map live."""
    cwd, snapshot, build = run / "source" / book, run / "source", run / "build"
    original = build / book / f"{book}.synctex.gz"
    lines, counts = [], {"source": 0, "auxiliary": 0, "external": 0}

    def project_input(raw):
        p = Path(raw)
        p = (p if p.is_absolute() else cwd / p).resolve()
        if inside(p, snapshot):
            name = p.relative_to(snapshot).as_posix()
            require(name in source_hashes, f"Unmanifested SyncTeX/FLS source: {p}")
            target, kind = ROOT / name, "source"
        elif inside(p, build):
            target, kind = p, "auxiliary"
        else:
            require(not inside(p, ROOT), f"Input outside this run (possibly old build): {p}")
            return None, "external"
        require(p.is_file() and target.is_file(), f"Missing project input: {p} -> {target}")
        return target, kind

    for line in gzip.decompress(read_bytes(original)).decode("utf-8").splitlines(keepends=True):
        if line.startswith("Input:"):
            parts = line.rstrip("\r\n").split(":", 2)
            require(len(parts) == 3 and parts[1].isdigit(), "Malformed SyncTeX Input line")
            target, kind = project_input(parts[2])
            counts[kind] += 1
            if target is not None:
                ending = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
                line = f"Input:{parts[1]}:{target.as_posix()}{ending}"
        lines.append(line)
    require(counts["source"] > 0, f"SyncTeX contains no project sources: {original}")
    for line in read_bytes(build / book / f"{book}.fls").decode("utf-8", errors="replace").splitlines():
        if line.startswith("INPUT "):
            project_input(line[6:])
    return gzip.compress("".join(lines).encode("utf-8"), mtime=0), counts


def check_book(run, result, sources, allow_overfull_vbox=0):
    v = result["volume"]
    book, build = f"Book{v}", run / "build" / f"Book{v}"
    pdf = (run / result["pdf"]).resolve()
    require(pdf == build / f"{book}.pdf", f"Unexpected PDF path: {pdf}")
    require(sha(pdf) == result["pdfSha256"].upper(), f"Build PDF hash mismatch: {book}")
    READ_HASHES[pdf] = result["pdfSha256"].upper()
    require(3 <= result["passes"], f"Insufficient stable passes: {book}")
    log_path = build / f"{book}.log"
    log = read_bytes(log_path).decode("utf-8", errors="replace")
    # Writing-stage delivery may explicitly defer small vertical layout warnings.
    # Keep the original log and actual warning count in the delivery evidence.
    # Horizontal overflow, missing glyphs and all reference/build errors still fail.
    allowed = []
    def allow_vbox(match):
        if float(match.group(1)) <= allow_overfull_vbox:
            allowed.append(match.group(0))
            return ""
        return match.group(0)
    checked_log = re.sub(r"Overfull \\vbox \(([\d.]+)pt too high\)[^\r\n]*", allow_vbox, log)
    bad = BAD_LOG.search(checked_log)
    require(not bad, f"Final log diagnostic in {book}: {bad.group(0) if bad else ''}")
    require("Output written on" in log, f"Incomplete final log: {book}")
    require(result["layoutWarningCount"] == len(allowed), f"Unaccepted manifest layout warnings: {book}")
    indexes, evidence = {}, [pdf, log_path, build / f"{book}.synctex.gz", build / f"{book}.fls"]
    for index in ("chinese", "foreign", "symbols"):
        idx, ind, ilg = [build / f"{index}.{suffix}" for suffix in ("idx", "ind", "ilg")]
        text = read_bytes(ilg).decode("utf-8", errors="replace")
        require(idx.stat().st_size and ind.stat().st_size and f"{index}.ind" in log,
                f"Missing/empty/unread index: {book}/{index}")
        for word in ("rejected", "warnings"):
            values = re.findall(rf"\b(\d+) {word}\b", text)
            require(values and all(int(n) == 0 for n in values), f"Index {word}: {book}/{index}")
        indexes[index] = {"rejected": 0, "warnings": 0, "ind_sha256": sha(ind), "ilg_sha256": sha(ilg)}
        READ_HASHES[ind] = indexes[index]["ind_sha256"]
        evidence += [idx, ind, ilg]
    bbl = build / f"{book}.bbl"
    require(bbl.is_file() and bbl.stat().st_size and f"{book}.bbl" in log, f"Missing/unread bibliography: {book}")
    evidence.append(bbl)
    sync, counts = prepare_synctex(run, book, sources)
    selected = {p: h for p, h in sources.items() if p.startswith((book + "/", "Shared/"))}
    record = {"book": v, "build_pdf": rel(pdf), "pdf_sha256": sha(pdf),
              "source_files_checked": len(selected), "source_identity_sha256": identity(selected),
              "sources_current": True, "passes": result["passes"], "indexes": indexes,
              "final_log": rel(log_path), "final_log_sha256": sha(log_path),
              "underfull": len(re.findall(r"Underfull \\[hv]box", log)),
              "overfull": len(allowed), "deferred_layout_warnings": allowed,
              "allowed_overfull_vbox_pt": allow_overfull_vbox,
              "missing_characters": 0, "pdf_string_warnings": 0,
              "build_synctex": rel(build / f"{book}.synctex.gz"),
              "build_synctex_sha256": sha(build / f"{book}.synctex.gz"),
              "synctex_sha256": hashlib.sha256(sync).hexdigest().upper(), "synctex_inputs": counts,
              "output_pdf": f"{book}.pdf", "editor_pdf": f"{book}/{book}.pdf",
              "editor_synctex": f"{book}/{book}.synctex.gz"}
    return record, sync, evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "audit", "backup-dir"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--extra-audit", type=Path)
    parser.add_argument("--allow-overfull-vbox", type=float, default=0, metavar="PT",
                        help="Explicitly defer vertical overflow up to PT; retain warnings in delivery evidence")
    parser.add_argument("--deliver", action="store_true", help="Back up and replace selected-volume outputs after all checks")
    args = parser.parse_args()
    require(0 <= args.allow_overfull_vbox < float("inf"), "Vertical overflow limit must be finite and nonnegative")
    run, audit_path, backup = args.run.resolve(), args.audit.resolve(), args.backup_dir.resolve()
    require(inside(run, ROOT / "tmp" / "build") and run != ROOT / "tmp" / "build", "--run must be a project tmp/build run")
    require(inside(backup, ROOT / "tmp") and backup != ROOT / "tmp" and not inside(backup, run)
            and not inside(run, backup), "--backup-dir must be a separate explicit project tmp location")
    manifest_path = run / "manifest.json"
    manifest = read_json(manifest_path)
    require(manifest["schema"] == 1 and manifest["status"] == "success" and not manifest["error"], "Not a successful official manifest")
    require(Path(manifest["projectRoot"]).resolve() == ROOT, "Manifest belongs to another project")
    volumes = sorted(manifest["volumes"])
    require(volumes and len(volumes) == len(set(volumes)) and set(volumes) <= {1, 2, 3}, "Invalid manifest volumes")
    sources = {item["path"]: item["sha256"].upper() for item in manifest["sources"]}
    require(len(sources) == len(manifest["sources"]), "Duplicate manifest source paths")
    check_sources(run, volumes, sources)
    results = {item["volume"]: item for item in manifest["results"]}
    require(len(results) == len(manifest["results"]) and sorted(results) == volumes, "Manifest result scope mismatch")
    require(manifest["commands"] and all(c["exitCode"] == 0 for c in manifest["commands"]), "Failed/missing build commands")
    for v in volumes:
        passes = [c for c in manifest["commands"] if Path(c["executable"]).stem.lower() == "xelatex"
                  and Path(c["cwd"]).resolve() == run / "source" / f"Book{v}"]
        require(len(passes) == results[v]["passes"] <= manifest["maxPasses"], f"Pass record mismatch: Book{v}")
    audit = read_json(audit_path)
    require(inside(audit_path, run), "--audit must be saved inside this run")
    require(audit["errors"] == [] and audit["source_title_checks_required"] is True, "Strict title audit required, with errors=[]")
    books = {b["book"]: b for b in audit["books"]}
    require(len(books) == len(audit["books"]) and sorted(books) == volumes, "Audit must contain exactly the selected volumes")
    inventory_path = Path(audit["inventory"]).resolve()
    require(inside(inventory_path, run), "Heading inventory must be saved inside this run")
    inventory = read_json(inventory_path)
    fresh = make_inventory(run / "source", volumes)
    for key in ("volumes", "headings", "active_files", "source_hashes", "counts", "functional_counts"):
        require(inventory[key] == fresh[key], f"Stale/incompatible heading inventory: {key}")
    evidence = [manifest_path, audit_path, inventory_path]
    extra_path = args.extra_audit.resolve() if args.extra_audit else None
    if extra_path:
        require(inside(extra_path, run), "--extra-audit must be saved inside this run")
        extra = read_json(extra_path)
        require(extra["errors"] == [] and extra.get("passed", True) is True, "Extra audit has errors")
        extra_books = {b.get("book", b.get("volume")): b for b in extra["books"]}
        require(len(extra_books) == len(extra["books"]) and sorted(extra_books) == volumes, "Extra audit scope mismatch")
        for v in volumes:
            require(extra_books[v].get("sha256", extra_books[v].get("pdf_sha256", "")).upper()
                    == results[v]["pdfSha256"].upper(), f"Extra audit PDF hash mismatch: Book{v}")
        evidence.append(extra_path)
    records, prepared, targets = [], {}, []
    for v in volumes:
        b = books[v]
        require(Path(b["pdf"]).resolve() == run / "build" / f"Book{v}" / f"Book{v}.pdf"
                and b["sha256"].upper() == results[v]["pdfSha256"].upper(), f"Audit PDF identity mismatch: Book{v}")
        for key in ("missing_number_prefix_count", "source_title_mismatch_count", "target_error_indices",
                    "traversal_errors", "source_hierarchy_errors", "source_title_errors",
                    "duplicate_destinations", "duplicate_exact_entries", "page_backtracks"):
            require(not b[key], f"Book{v} audit failure: {key}")
        require(b["source_title_checks_required"] is True and b["outline_entries"] == b["source_headings"]
                == len(b["nodes"]) == sum(h["book"] == v for h in inventory["headings"]), f"Incomplete strict audit: Book{v}")
        headings = sorted((h for h in inventory["headings"] if h["book"] == v), key=lambda h: h["order"])
        parents = {h["id"]: i for i, h in enumerate(headings)}
        for node, heading in zip(b["nodes"], headings):
            parent = parents.get(heading["parent_id"])
            if parent == 0 and headings[0]["level"] == "volume":
                parent = None
            require(node["source_id"] == heading["id"] and node["source_file"] == heading["file"]
                    and node["source_line"] == heading["line"] and node["parent_index"] == parent
                    and node["source_title_matches"] is True and not node["target_error"]
                    and canonical_title(node["content_title"]) == expected_pdf_title(heading, node["destination_name"])
                    and (not node["expected_prefix"] or node["numbered_prefix_present"]
                         and node["optional_mark_present"] == heading["optional"]), f"Stale/incomplete audit node: {heading['id']}")
        record, sync, inputs = check_book(run, results[v], sources, args.allow_overfull_vbox)
        record.update({"pages": b["pages"], "bookmarks": b["outline_entries"], "numbered_bookmarks": b["numbered_entries"]})
        records.append(record); prepared[v] = sync; evidence += inputs
        targets += [(ROOT / record[k], backup / record[k]) for k in ("output_pdf", "editor_pdf", "editor_synctex")]
    hashes = {p: sha(p) for p in evidence}
    require(all(hashes[p] == h for p, h in READ_HASHES.items()), "Inputs changed after being read")
    for target, saved in targets:
        require(saved.resolve() == saved and inside(saved, backup) and not saved.exists(),
                f"Backup conflict or redirected path; refusing overwrite: {saved}")
        require(target.resolve() == target and (not target.exists() or target.is_file() and target.stat().st_nlink == 1), f"Unsafe output target: {target}")
    delivery_path = run / "current-audit" / "delivery.json"
    if args.deliver:
        require(not delivery_path.exists(), f"Delivery identity already exists: {delivery_path}")
        check_sources(run, volumes, sources)
        require(all(sha(p) == h for p, h in hashes.items()), "Build/audit inputs changed during verification")
        for target, saved in targets:
            require(saved.resolve() == saved and not saved.exists(), f"Backup path changed: {saved}")
            if target.exists():
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, saved)
                require(sha(target) == sha(saved), f"Backup verification failed: {target}")
        for record in records:
            for key in ("output_pdf", "editor_pdf"):
                shutil.copy2(ROOT / record["build_pdf"], ROOT / record[key])
            (ROOT / record["editor_synctex"]).write_bytes(prepared[record["book"]])
        check_sources(run, volumes, sources)
        require(all(sha(p) == h for p, h in hashes.items()), "Build/audit inputs changed during delivery")
        for record in records:
            require(all(sha(ROOT / record[k]) == record["pdf_sha256"] for k in ("output_pdf", "editor_pdf")), "Delivered PDF mismatch")
            require(sha(ROOT / record["editor_synctex"]) == record["synctex_sha256"], "Delivered SyncTeX mismatch")
        delivery = {"schema": 1, "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "scope": "Selected-volume source/PDF/editor identity; replace after source/output changes; not mathematical review.",
                    "run": rel(run), "volumes": volumes, "manifest": rel(manifest_path), "manifest_sha256": hashes[manifest_path],
                    "navigation_audit": rel(audit_path), "navigation_audit_sha256": hashes[audit_path],
                    "source_inventory": rel(inventory_path), "source_inventory_sha256": hashes[inventory_path],
                    "source_identity_sha256": identity(sources), "books": records}
        if extra_path:
            delivery.update(extra_audit=rel(extra_path), extra_audit_sha256=hashes[extra_path])
        delivery_path.parent.mkdir(parents=True, exist_ok=True)
        delivery_path.write_text(json.dumps(delivery, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"mode": "delivered" if args.deliver else "verified", "volumes": volumes,
                      "books": records, "delivery": rel(delivery_path) if args.deliver else None, "errors": []}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({"errors": [str(exc)]}, ensure_ascii=False), file=sys.stderr)
        sys.exit(1)
