"""Paste tables.md (and tables_real.md if present) into REPORT.md between the markers."""
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
for marker, f in (("TABLES", "tables.md"), ("REAL_TABLES", "tables_real.md"), ("DECISION", "tables_decision.md")):
    r = (ROOT / "REPORT.md").read_text()
    a, b = f"<!-- {marker} -->", f"<!-- /{marker} -->"
    if a in r and (ROOT / f).exists():
        i, j = r.index(a) + len(a), r.index(b)
        r = r[:i] + "\n" + (ROOT / f).read_text() + r[j:]
        (ROOT / "REPORT.md").write_text(r)
