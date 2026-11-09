"""Summarize lung audit rows against a copied Stage 0 feature CSV."""
import argparse
import csv
from collections import Counter
from io import BytesIO
from pathlib import Path
import posixpath
import re
from urllib.request import Request, urlopen
from zipfile import ZipFile
from xml.etree import ElementTree as ET

LUNG_IDS = {15, 16}
LOW, HIGH = 0.0005, 0.01
NS = {
    "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "p": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def parse_xlsx(data):
    """Read worksheet cell values without requiring an XLSX plugin."""
    with ZipFile(BytesIO(data)) as book:
        workbook = ET.fromstring(book.read("xl/workbook.xml"))
        rels = ET.fromstring(book.read("xl/_rels/workbook.xml.rels"))
        targets = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
        strings = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in si.findall(".//m:t", NS))
                       for si in root.findall("m:si", NS)]
        sheet = workbook.find("m:sheets/m:sheet", NS)
        if sheet is None:
            return [], []
        target = targets[sheet.attrib["{" + NS["r"] + "}id"]]
        path = (target.lstrip("/") if target.startswith("/") else
                posixpath.normpath(posixpath.join("xl", target)))
        root = ET.fromstring(book.read(path))
        rows = []
        for row in root.findall(".//m:sheetData/m:row", NS):
            vals = {}
            for cell in row.findall("m:c", NS):
                ref = cell.attrib.get("r", "")
                col = re.match(r"[A-Z]+", ref)
                if not col:
                    continue
                idx = 0
                for char in col.group():
                    idx = idx * 26 + ord(char) - 64
                idx -= 1
                v = cell.find("m:v", NS)
                value = v.text if v is not None else ""
                if cell.attrib.get("t") == "s" and value:
                    value = strings[int(value)]
                elif cell.attrib.get("t") == "inlineStr":
                    value = "".join(t.text or "" for t in cell.findall(".//m:t", NS))
                vals[idx] = value
            rows.append(vals)
        if not rows:
            return [], []
        headers = [rows[0].get(i, "").strip() for i in range(max(rows[0]) + 1)]
        records = []
        for raw in rows[1:]:
            records.append({h: raw.get(i, "") for i, h in enumerate(headers) if h})
        return headers, records


def metadata_bytes(path=None):
    if path and Path(path).is_file():
        return Path(path).read_bytes()
    from huggingface_hub import hf_hub_url
    url = hf_hub_url(repo_id="BodyMaps/PanTSMini", filename="metadata.xlsx",
                     repo_type="dataset")
    with urlopen(Request(url, headers={"User-Agent": "PanTS-lung-audit/1.0"}),
                 timeout=90) as response:
        return response.read()


def overlap_fraction(row):
    total = 0.0
    for slot in (1, 2):
        try:
            label = int(float(row.get(f"overlap_top{slot}_label") or 0))
            fraction = float(row.get(f"overlap_top{slot}_fraction") or 0)
        except (ValueError, TypeError):
            continue
        if label in LUNG_IDS:
            total += fraction
    return total


def case_number(case_id):
    match = re.search(r"(\d+)$", str(case_id))
    return int(match.group(1)) if match else None


def case_id(value):
    number = case_number(value)
    return f"PanTS_{number:08d}" if number is not None else str(value)


def truth(value):
    return str(value).strip().lower() in {"true", "1", "yes"}


def metadata_summary(records, features, colon_high):
    headers = records[0].keys() if records else ()
    lookup = {re.sub(r"[^a-z0-9]", "", h.lower()): h for h in headers}
    id_col = lookup.get("p existing") or lookup.get("p antsid") or lookup.get("pantsid")
    # The published workbook column is "PanTS ID".
    id_col = id_col or next((h for h in headers if h.lower().replace(" ", "") in
                             {"pantsid", "pantsid"}), None)
    attrs = {
        "site": lookup.get("site"),
        "manufacturer": lookup.get("manufacturer"),
        "ct phase": lookup.get("ctphase"),
    }
    if not id_col:
        print("Metadata join skipped: no PanTS ID column found.")
        return
    md = {case_id(r.get(id_col, "")): r for r in records if r.get(id_col)}
    feature_ids = {case_id(r.get("case_id", "")) for r in features}
    all_ids = set(md)
    flag_ids = colon_high & all_ids
    print(f"Metadata cases available: {len(all_ids)}; feature-copy cases joined: "
          f"{len(feature_ids & all_ids)}; flagged colon-high: {len(flag_ids)}")
    for label, group in (("all metadata cases", all_ids),
                         ("flagged colon-high cases", flag_ids)):
        print(f"Metadata counts for {label}:")
        for attr, col in attrs.items():
            if not col:
                print(f"  {attr}: column unavailable")
                continue
            counts = Counter(str(md[c].get(col, "")).strip() or "(blank)" for c in group)
            print(f"  {attr}:")
            for value, n in sorted(counts.items(), key=lambda item: (-item[1], item[0])):
                print(f"    {value}: {n}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", default=str(Path(__file__).with_name("lung_audit.csv")))
    parser.add_argument("--features-copy", default=r"D:\PanTS_data\features_partial.csv",
                        help="Use a copied features CSV; never point this at the live file.")
    parser.add_argument("--metadata", help="Optional local metadata.xlsx; otherwise fetch in memory.")
    parser.add_argument("--flags-dir", default=r"D:\PanTS_data")
    args = parser.parse_args()
    audit_path, feature_path = Path(args.audit), Path(args.features_copy)
    if feature_path.name.lower() == "features_all.csv":
        parser.error("--features-copy must name a copy, not the live file")
    with audit_path.open(newline="", encoding="utf-8") as stream:
        audit = list(csv.DictReader(stream))
    with feature_path.open(newline="", encoding="utf-8") as stream:
        features = list(csv.DictReader(stream))
    case_rows = {}
    for row in features:
        case_rows.setdefault(case_id(row.get("case_id", "")), {})[row.get("organ", "")] = row
    colon_fraction = {c: overlap_fraction(organs.get("colon", {}))
                      for c, organs in case_rows.items()}
    stomach_fraction = {c: overlap_fraction(organs.get("stomach", {}))
                        for c, organs in case_rows.items()}
    colon_high = {c for c, x in colon_fraction.items() if x > HIGH}
    colon_above_low = {c for c, x in colon_fraction.items() if x > LOW}
    colon_low_only = colon_above_low - colon_high
    stomach_high = {c for c, x in stomach_fraction.items() if x > HIGH}
    stomach_above_low = {c for c, x in stomach_fraction.items() if x > LOW}

    print(f"Cases in lung_audit.csv: {len({r.get('case_id') for r in audit})}")
    print(f"Cases in feature copy: {len(case_rows)}")
    print(f"Colon lung overlap > 0.01: {len(colon_high)}")
    print(f"Colon lung overlap > 0.0005: {len(colon_above_low)}")
    print(f"Stomach lung overlap > 0.01: {len(stomach_high)}")
    print(f"Stomach lung overlap > 0.0005: {len(stomach_above_low)}")
    below = {case_id(r.get("case_id", "")) for r in audit
             if truth(r.get("lung_left_centroid_below_liver"))
             or truth(r.get("lung_right_centroid_below_liver"))}
    empty = {case_id(r.get("case_id", "")) for r in audit
             if int(float(r.get("n_lungs_empty") or 0)) > 0}
    print(f"Audit cases with a lung centroid below liver: {len(below)}")
    print(f"Audit cases with an empty lung: {len(empty)}")
    audit_ids = {case_id(r.get("case_id", "")) for r in audit}
    print("Group combinations in audited cases (high, low-only, below-liver, empty):")
    combos = Counter((c in colon_high, c in colon_low_only, c in below, c in empty)
                     for c in audit_ids)
    for combo, n in sorted(combos.items()):
        print(f"  {combo}: {n}")

    blocks = {}
    for c in case_rows:
        num = case_number(c)
        if num is None:
            continue
        start = ((num - 1) // 500) * 500 + 1
        blocks.setdefault(start, set()).add(c)
    print("Counts per 500-case ID block (feature-copy cases, colon high, colon low-only, stomach high):")
    for start, ids in sorted(blocks.items()):
        print(f"  {start}-{start+499}: {len(ids)}, {len(ids & colon_high)}, "
              f"{len(ids & colon_low_only)}, {len(ids & stomach_high)}")

    flags_dir = Path(args.flags_dir)
    flags_dir.mkdir(parents=True, exist_ok=True)
    flag_sets = {
        "colon_high": colon_high,
        "colon_above_low": colon_above_low,
        "stomach_high": stomach_high,
        "stomach_above_low": stomach_above_low,
    }
    for name, ids in flag_sets.items():
        path = flags_dir / f"lung_flags_{name}.txt"
        path.write_text("".join(f"{c}\n" for c in sorted(ids)), encoding="utf-8")
        print(f"Wrote {len(ids)} IDs: {path}")

    try:
        data = metadata_bytes(args.metadata)
        headers, records = parse_xlsx(data)
        print(f"Metadata workbook loaded ({len(data)} bytes); columns: {headers}")
        metadata_summary(records, features, colon_high)
    except Exception as exc:
        print(f"Metadata unavailable; skipped site/manufacturer/phase join ({type(exc).__name__}).")


if __name__ == "__main__":
    main()
