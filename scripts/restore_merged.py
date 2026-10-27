"""Restore the exact uploaded merged CSV and generate matching review exports."""
import base64, csv, gzip, hashlib, io, json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "gsat-vocabulary-merged-toeic-toefl-ielts-wordup.csv"
EXPECTED_SHA256 = "2abe788f4411f33f2e16ba4bca42fd31908031a6d8370423e5e2633f65023c31"

def main():
    parts = sorted((ROOT / "data" / "merged-parts").glob("part-*.b64"))
    assert len(parts) == 13, "Missing merged CSV parts"
    raw = gzip.decompress(base64.b64decode("".join(p.read_text().strip() for p in parts), validate=True))
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA256, "Merged CSV checksum mismatch"
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    fields = reader.fieldnames
    rows = list(reader)
    assert len(rows) == 10219
    assert all(r.get("headword") for r in rows)
    out = ROOT / "public" / "data"
    out.mkdir(parents=True, exist_ok=True)
    (out / NAME).write_bytes(raw)
    confidence = Counter(r.get("analysis_confidence", "") for r in rows)
    qa = {"records": len(rows), "source": NAME, "sha256": EXPECTED_SHA256,
          "confidence": dict(confidence),
          "source_kinds": dict(Counter(r.get("source_kind", "") for r in rows))}
    (out / "root-analysis-qa.json").write_text(json.dumps(qa, ensure_ascii=False, indent=2), encoding="utf-8")
    for name, status in [("root-manual-review.csv", "MANUAL_REVIEW"),
                         ("root-discarded-candidates.csv", "DISCARD"),
                         ("unmatched-review.csv", "UNMATCHED")]:
        with (out / name).open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(r for r in rows if r.get("analysis_confidence") == status)
    with (out / "unmatched-word-family.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(r for r in rows if r.get("unmatched_class") in {"WORD_FAMILY", "INFLECTION", "COMPOUND"})
    print(json.dumps(qa, ensure_ascii=False))

if __name__ == "__main__":
    main()
