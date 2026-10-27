# DiKa - Google Ads custom feeds (RO + FR)

Google Ads custom feeds (Business data > Dynamic display ad feeds > Custom), built from DiKa's Meta catalogues.
No Merchant Center is involved.

| Market | Source (Meta catalogue) | Google Ads feed (raw URL for the scheduled upload) |
|---|---|---|
| RO, dikastore.ro, RON | `https://images.dika.com/catalogues/3000/meta-pixel/general-ro.csv` | `https://raw.githubusercontent.com/martingalabov-jpg/dika-google-ads-feed/main/dika-ro-google-ads-feed.csv` |
| FR, dika.com/fr, EUR | `https://images.dika.com/catalogues/5000/meta-pixel/general-fr.csv` | `https://raw.githubusercontent.com/martingalabov-jpg/dika-google-ads-feed/main/dika-fr-google-ads-feed.csv` |

The catalogue number is the store: 1000 = BG, 3000 = RO, 5000 = FR (5000 also has `general-en.csv`).

## What `build_google_ads_feed.py` does

    python3 build_google_ads_feed.py <ro|fr> <meta.csv> <out.csv>

- **One row per product.** The Meta feed has one row per size. All sizes share the product page and price, so rows are grouped on `item_group_id`.
- **ID** is `item_group_id` lowercased, with the hyphens removed. Google Ads IDs are letters and digits only. For example, `61137-82679-00000-000-1` becomes `61137826790000000001`. **The Google tag must send exactly this value** as `items[].id` on `view_item`, `add_to_cart` and `purchase`. In GTM, take the last five hyphen-separated parts of the product URL slug and join them.
- **Item title / Item description**: Google allows 25 characters each. The product name loses "de damă" / "femme", is cut at a word boundary, and never ends on a preposition or a word like "culoare" / "couleur". The rest of the name goes into Item description.
- **Item category**: derived from the product name (Paltoane / Manteaux, Rochii / Robes, ...). The Meta `custom_label_2` is "Unknown" for most rows.
- **Price / Sale price**: `409.00 RON`. Sale price is filled only when it is lower than Price. **Formatted price** is `409 lei` / `1.039 lei` (RO) and `90 €` (FR).
- **Image URL**: `images/<ID>.jpg` in this repo. Google Ads accepts only PNG, JPG and GIF, and DiKa's CDN serves WebP only. So the first product photo is converted to an 800x800 white-padded JPG with an sRGB ICC profile. It is converted once and redone only when the source image URL changes (`images/manifest.json`). RO and FR share the images.
- A feed is not written if its currency is wrong or it has too few products (RO under 300, FR under 150).

`prune_images.py` deletes images that no feed uses any more.

## Refresh

The GitHub Actions workflow `.github/workflows/refresh-feed.yml` runs every 6 hours at :15 UTC, and can also be started by hand. A download that is not the catalogue CSV, or a build below the product floor, stops the run without publishing.

## Google Ads setup

1. Tools > Business data > + > Dynamic display ad feed > **Custom**. Create one feed per market: `DiKa RO custom feed` and `DiKa FR custom feed`.
2. Upload > Schedule > source **HTTPS**, URL = the raw URL above, every 6 hours, no login.
3. Attach the feed to the market's Display campaign (Settings > Dynamic ads). Without a Google tag that sends these IDs, the ads can only show generic, non-personalised products.
