"""DiKa Meta catalogue CSV -> Google Merchant Center product feed (TSV, Google attribute names).
Separate from the Google Ads custom feed (build_google_ads_feed.py), which stays as it is.

One row per size, id = the Meta size id (the same id the sites' Google tag sends), grouped by item_group_id.
  title / description   the catalogue's full product name and description (Merchant Center allows 150 / 5000)
  image_link            the catalogue's own WebP (800x1000); Merchant Center accepts WebP, so no conversion
  price / sale_price    "409.00 RON"; sale_price only when it is lower than price
  gender / age_group    female / adult (DiKa sells womenswear only); required for apparel in FR and RO
  color / size          from the catalogue; size_system FR (dika.com/fr) or EU (dikastore.ro) on numeric sizes
  identifier_exists     no: DiKa is the manufacturer and has no GTINs
  google_product_category  numeric id from Google's taxonomy, picked from the product name
  product_type          the same local category as the Google Ads feed (Manteaux / Paltoane, ...)
  custom_label_0 / _1   collection (e.g. I26) / onSale|notOnSale, as in the catalogue
Gift cards are left out (not a physical product).
Usage: python3 build_merchant_feed.py <market> <meta.csv> <out.tsv>     market = ro | fr"""
import csv, re, sys, urllib.parse
from build_google_ads_feed import MARKETS, category, money

SIZE_SYSTEM = {"fr": "FR", "ro": "EU"}
GIFT = r"carte cadeau|voucher|card cadou|gift card"
# (regex on the lower-cased name, Google taxonomy id); the keyword found earliest in the name wins,
# on a tie the earlier entry wins (so "gilet sans manches" is a vest, not knitwear)
GPC = [
    (r"ceintur|curea|centur", 169),                                       # Clothing Accessories > Belts
    (r"foulard|écharpe|echarpe|eșarf|esarf|fular|\bșal\b|\bsal\b", 177),  # Scarves & Shawls
    (r"chapeau|bonnet|pălări|palari|căciul|caciul", 173),            # Hats
    (r"sac à dos|sac a dos|rucsac", 100),                           # Luggage & Bags > Backpacks
    (r"\bsac\b|geant|poșet|poset", 3032),                           # Handbags
    (r"chouchou|scrunchie|elastic\w* de p", 171),                     # Hair Accessories
    (r"chaussure|botte|bottine|escarpin|sandale|mocassin|pantof|cizm|botin|balerin", 187),  # Shoes
    (r"gilet sans manches|\bvest[ăa]\b", 1831),                     # Outerwear > Vests
    (r"palton|pardesi|trench|hain[ăa]|manteau|caban|doudoune|parka|geac|jachet|veste\b|blazer|sacou|bol[ée]ro|blouson", 5598),  # Coats & Jackets
    (r"\brobe|rochi", 2271),                                        # Dresses
    (r"skort|jupe|fust", 1581),                                     # Skirts
    (r"\bshort|pantaloni scur", 207),                               # Shorts
    (r"pantalon|\bjean|blugi|legging|colan", 204),                  # Pants
    (r"combinaison|salopet", 5250),                                 # Jumpsuits & Rompers
    (r"tailleur|costum|compleu|ensemble", 1594),                    # Suits
    (r"chemis|blouse|cămaș|camas|bluz|\btop\b|tricou|t-shirt|\bbody|\bpolo|débardeur|caraco|pull|pulover|cardigan|gilet|maille|col roulé|helanc|tricot", 212),  # Shirts & Tops
]
HEADER = ["id", "item_group_id", "title", "description", "link", "image_link", "availability", "condition",
          "price", "sale_price", "brand", "gender", "age_group", "color", "size", "size_system",
          "identifier_exists", "google_product_category", "product_type", "custom_label_0", "custom_label_1"]


def gpc(name):
    s, best = name.lower(), None
    for rx, gid in GPC:
        hit = re.search(rx, s)
        if hit and (best is None or hit.start() < best[0]):
            best = (hit.start(), gid)
    return best[1] if best else 1604  # Apparel & Accessories > Clothing


def clean(s):
    return re.sub(r"\s+", " ", s or "").strip()


def main():
    mkt, src, out = sys.argv[1], sys.argv[2], sys.argv[3]
    m = MARKETS[mkt]
    with open(src, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    outrows, groups, gifts = [], set(), 0
    for r in rows:
        name = clean(r["title"])
        if re.search(GIFT, name, re.I):
            gifts += 1
            continue
        p, cur = money(r["price"])
        if cur != m["currency"]:
            raise SystemExit(f"Unexpected currency {cur} for {r['id']} - output NOT written")
        s = money(r["sale_price"])[0] if r["sale_price"].strip() else 0
        size = clean(r["size"])
        numeric = re.fullmatch(r"\d{2}", size) and 30 <= int(size) <= 56
        avail = r["availability"].strip().lower().replace(" ", "_")
        outrows.append([
            re.sub(r"[^0-9a-z]", "", r["id"].lower()), r["item_group_id"], name[:150],
            clean(r["description"])[:5000] or name, r["link"].strip(),
            urllib.parse.quote(r["image_link"].strip(), safe=":/%?=&'"),
            avail if avail in ("in_stock", "out_of_stock", "preorder", "backorder") else "out_of_stock",
            r["condition"].strip().lower() or "new",
            f"{p:.2f} {cur}", f"{s:.2f} {cur}" if 0 < s < p else "",
            r["brand"].strip() or "DiKa", "female", "adult",
            clean(r["color"]).capitalize(), size, SIZE_SYSTEM[mkt] if numeric else "",
            "no", gpc(name), category(name, mkt),
            clean(r.get("custom_label_0")), clean(r.get("custom_label_1")),
        ])
        groups.add(r["item_group_id"])

    if len(groups) < m["min_rows"]:
        raise SystemExit(f"Only {len(groups)} products - output NOT written")
    if len({r[0] for r in outrows}) != len(outrows):
        raise SystemExit("Duplicate size IDs - output NOT written")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", quoting=csv.QUOTE_MINIMAL, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(sorted(outrows))
    print(f"{mkt}: {len(rows)} size rows -> {len(groups)} products -> {len(outrows)} rows written ({gifts} gift cards left out)")


if __name__ == "__main__":
    main()
