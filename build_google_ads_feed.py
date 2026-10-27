"""DiKa Meta catalogue CSV -> Google Ads custom feed (Business data > Dynamic display ad feeds, no Merchant Center).
The Meta feed has one row per size; Google Ads gets one row per product (item_group_id), because the product page
and price are shared by all sizes. Columns follow the Google Ads Custom feed template:
  ID                  item_group_id without hyphens (letters and digits only, lowercase), e.g. 61137826790000000001
  Item title          the product name shortened to 25 characters ("de damă" / "femme" dropped, cut at a word)
  Item description    the rest of the name, 25 characters max
  Final URL, Item category, Price / Sale price (e.g. "409.00 RON"), Formatted price / Formatted sale price
  Image URL           images/<ID>.jpg in this repo: the first product photo, WebP converted to an 800x800 sRGB JPG
                      (Google Ads takes PNG/JPG/GIF only and DiKa's CDN serves WebP only)
Sale price is left empty unless it is lower than Price.
Usage: python3 build_google_ads_feed.py <market> <meta.csv> <out.csv>     market = ro | fr"""
import csv, io, json, pathlib, re, sys, urllib.parse, urllib.request
from PIL import Image, ImageCms

MARKETS = {
    "ro": dict(currency="RON", fmt=lambda v: f"{v:,.0f}".replace(",", ".") + " lei" if v == int(v) else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " lei",
               min_rows=300, gender=r"\b(de damă|de dama|pentru femei|pentru damă|de femei|damă|femei|feminin[ăa]?)\b",
               stop={"cu", "din", "de", "și", "si", "în", "in", "o", "un", "la", "pe", "tip", "a", "al", "ale", "cu o", "pentru"},
               tail={"fără", "culoare", "culoarea", "nuanța", "nuanță", "mânecă", "mâneci", "model", "efect"}),
    "fr": dict(currency="EUR", fmt=lambda v: (f"{v:,.0f}" if v == int(v) else f"{v:,.2f}").replace(",", " ").replace(".", ",") + " €",
               min_rows=150, gender=r"\b(pour femmes?|de femmes?|femmes?|féminine?)\b",
               stop={"avec", "en", "à", "de", "du", "des", "la", "le", "les", "et", "au", "aux", "pour", "d'", "l'", "d’", "l’", "un", "une"},
               tail={"sans", "couleur", "teinte", "nuance", "manches", "manche", "style", "motif", "effet"}),
}
CATEGORIES = [  # first keyword found (earliest in the name) wins; RO + FR
    ("Paltoane", "Manteaux", r"palton|pardesi|trench|manteau|caban|cape\b"),
    ("Rochii", "Robes", r"rochi|robe"),
    ("Fuste", "Jupes", r"fust|jupe"),
    ("Pantaloni", "Pantalons", r"pantalon|blugi|jean"),
    ("Sacouri", "Blazers", r"sacou|blazer"),
    ("Jachete", "Vestes", r"jachet|geac|bolero|veste\b"),
    ("Veste", "Gilets sans manches", r"\bvest[ăa]\b|sans manches"),
    ("Salopete", "Combinaisons", r"salopet|combinaison"),
    ("Costume", "Tailleurs", r"costum|compleu|tailleur|ensemble"),
    ("Tricotaje", "Mailles", r"pulover|cardigan|helanc|tricot|pull|gilet|maille|col roulé"),
    ("Cămăși și bluze", "Chemises et blouses", r"cămaș|camas|bluz|chemise|blouse"),
    ("Topuri", "Tops", r"\btop|tricou|t-shirt|body|débardeur"),
    ("Accesorii", "Accessoires", r"curea|ceintur|geant|poșet|sac\b|eșarf|esarf|fular|foulard|écharpe|pălări|chapeau|voucher|carte cadeau"),
]
IMG_SIZE = 800
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
RAW = "https://raw.githubusercontent.com/martingalabov-jpg/dika-google-ads-feed/main/images/"


def money(s):
    n, cur = s.split()
    return float(n), cur


def shorten(words, drop, limit=25):
    out = []
    for w in words:
        if len(" ".join(out + [w])) > limit:
            break
        out.append(w)
    while out and (out[-1].lower().strip(",") in drop or len(out[-1]) == 1):  # never end on "cu", "à", "couleur"...
        out.pop()
    return " ".join(out).strip(" ,;-"), len(out)


def split_title(title, m):
    t = re.sub(m["gender"], "", title, flags=re.I)
    t = re.sub(r"\s+,", ",", re.sub(r"\s+", " ", t)).strip(" ,")
    t = re.sub(r"(\d)\s+%", r"\1%", t)  # keep "100 %" as one word
    words = t.split()
    drop = m["stop"] | m["tail"]
    head, n = shorten(words, drop)
    if not head:  # one very long word: hard cut
        head, n = t[:25].rstrip(), len(words)
    rest = words[n:]
    while rest and rest[0].lower().strip(",") in m["stop"]:
        rest = rest[1:]
    desc, _ = shorten(rest, drop)
    return head[0].upper() + head[1:], desc


def category(title, mkt):
    s, best = title.lower(), None
    for ro, fr, rx in CATEGORIES:
        hit = re.search(rx, s)
        if hit and (best is None or hit.start() < best[0]):
            best = (hit.start(), ro if mkt == "ro" else fr)
    return best[1] if best else ("Îmbrăcăminte" if mkt == "ro" else "Vêtements")


def ensure_image(pid, src_url, img_dir, manifest):
    """Convert the product's WebP to a square white-padded sRGB JPG once; redo only if the source URL changed."""
    dst = img_dir / f"{pid}.jpg"
    if dst.exists() and manifest.get(pid) == src_url:
        return True
    try:
        req = urllib.request.Request(urllib.parse.quote(src_url, safe=":/%?=&'"), headers={"User-Agent": "Mozilla/5.0"})
        im = Image.open(io.BytesIO(urllib.request.urlopen(req, timeout=30).read())).convert("RGB")
    except Exception as e:  # keep the last good image if there is one
        print(f"image failed {pid}: {e}")
        return dst.exists()
    im.thumbnail((IMG_SIZE, IMG_SIZE), Image.LANCZOS)
    sq = Image.new("RGB", (IMG_SIZE, IMG_SIZE), "white")
    sq.paste(im, ((IMG_SIZE - im.width) // 2, (IMG_SIZE - im.height) // 2))
    sq.save(dst, quality=85, optimize=True, progressive=True, icc_profile=SRGB)
    manifest[pid] = src_url
    return True


def main():
    mkt, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    m = MARKETS[mkt]
    img_dir = pathlib.Path("images"); img_dir.mkdir(exist_ok=True)
    man_path = img_dir / "manifest.json"
    manifest = json.loads(man_path.read_text()) if man_path.exists() else {}

    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    products = {}
    for r in rows:
        if r["availability"].strip().lower() != "in stock":
            continue
        products.setdefault(r["item_group_id"], r)

    header = ["ID", "Item title", "Item description", "Final URL", "Image URL", "Item category",
              "Price", "Sale price", "Formatted price", "Formatted sale price"]
    outrows, no_img = [], 0
    for gid, r in products.items():
        pid = re.sub(r"[^0-9a-z]", "", gid.lower())
        p, cur = money(r["price"])
        if cur != m["currency"]:
            raise SystemExit(f"Unexpected currency {cur} for {gid} - output NOT written")
        s = money(r["sale_price"])[0] if r["sale_price"].strip() else 0
        on_sale = 0 < s < p
        if not ensure_image(pid, r["image_link"], img_dir, manifest):
            no_img += 1
            continue
        title, desc = split_title(r["title"], m)
        outrows.append([pid, title, desc, r["link"], RAW + f"{pid}.jpg", category(r["title"], mkt),
                        f"{p:.2f} {cur}", f"{s:.2f} {cur}" if on_sale else "",
                        m["fmt"](p), m["fmt"](s) if on_sale else ""])

    man_path.write_text(json.dumps(manifest, indent=0, sort_keys=True))
    if len(outrows) < m["min_rows"]:
        raise SystemExit(f"Only {len(outrows)} products - output NOT written")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(sorted(outrows))
    print(f"{mkt}: {len(rows)} size rows -> {len(products)} products -> {len(outrows)} written ({no_img} without image)")


if __name__ == "__main__":
    main()
