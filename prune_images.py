"""Delete images/<ID>.jpg (and manifest entries) that no market feed references any more.
Usage: python3 prune_images.py <feed.csv> [<feed.csv> ...]"""
import csv, json, pathlib, sys

used = set()
for f in sys.argv[1:]:
    with open(f, encoding="utf-8") as fh:
        used |= {r["ID"] for r in csv.DictReader(fh)}
if len(used) < 100:
    raise SystemExit(f"Only {len(used)} IDs in use - nothing pruned")
img = pathlib.Path("images")
gone = [p for p in img.glob("*.jpg") if p.stem not in used]
for p in gone:
    p.unlink()
man = img / "manifest.json"
m = json.loads(man.read_text())
man.write_text(json.dumps({k: v for k, v in m.items() if k in used}, indent=0, sort_keys=True))
print(f"{len(used)} IDs in use, {len(gone)} images pruned")
