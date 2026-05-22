# TravelProductIntelligence

Price tracking and markdown analysis pipeline for Australian travel luggage brands — Samsonite, Rimowa, Antler, and Tumi.

## Overview

Automated scrapers crawl product pages for four premium AU luggage brands, extract structured data (price, availability, colour, product type), and load it into BigQuery for time-series price analysis and markdown detection.

## Architecture

```
config/brands.py
      |
   main.py  ──►  scrapers/jsonld.py  ──►  pipelines/  ──►  BigQuery
      |                                                         |
  utils/sitemap.py                                    alerts/discord.py
```

**Discovery**: Brand sitemaps are parsed to find all product URLs, which are upserted into `products_index`.

**Scraping**: JSON-LD structured data is extracted from each product page and normalised into a flat schema.

**Storage**: Raw rows land in `products_raw_v2`; the index tracks `first_seen_ts`, `last_seen_ts`, and `last_scraped_ts`.

**Alerts**: Discord webhooks notify on run completion or failure.

## Tech stack

| Layer | Technology |
|---|---|
| Scraping | Python 3.12, Requests, BeautifulSoup |
| Storage | Google BigQuery |
| Container | Docker |
| Scheduling | GitHub Actions |
| Proxy | SmartProxy (residential, for bot-protected pages) |
| Alerting | Discord webhooks |

## Brands covered

| Brand | Domain | Discovery method | AU locale |
|---|---|---|---|
| Samsonite | samsonite.com.au | Sitemap index | `au/en` |
| Rimowa | rimowa.com | Seed URLs | `au/en` |
| Antler | antler.com.au | Sitemap index | `au/en` |
| Tumi | tumi.com.au | Sitemap index | `au/en` |

## What you can analyse

- **Price over time** — track price changes per product, brand, and colour variant
- **Markdown detection** — when did a product go on sale and by how much?
- **Stock trends** — in-stock vs out-of-stock over time
- **Range changes** — new product introductions (`first_seen_ts`) and discontinuations
- **Cross-brand comparison** — compare equivalent luggage types across brands

## Structure

```
main.py                  CLI entry point (--brand <key> / --all)
config/brands.py         Brand configurations (sitemap, URL patterns, parser)
scrapers/jsonld.py       JSON-LD product data extractor
scrapers/sfcc.py         SFCC platform parser (legacy fallback)
pipelines/index.py       BigQuery products_index upsert logic
pipelines/raw.py         BigQuery products_raw_v2 insert logic
alerts/discord.py        Discord webhook alerts
utils/sitemap.py         Sitemap discovery and URL filtering
utils/classify.py        Product type classification
utils/helpers.py         Shared utilities (parse_price, classify_product_type)
utils/http.py            HTTP client with proxy and retry support
legacy/                  Archived prototype scripts
tests/                   Unit tests
```

## Environment variables

| Variable | Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to BigQuery service account JSON |
| `SMARTPROXY_HOST` | SmartProxy hostname (default: `proxy.smartproxy.net`) |
| `SMARTPROXY_PORT` | SmartProxy port (default: `3120`) |
| `SMARTPROXY_USER` | SmartProxy username |
| `SMARTPROXY_PASS` | SmartProxy password |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL for run alerts |

## Running locally

```bash
pip install -r requirements.txt

export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
export SMARTPROXY_USER=your-user
export SMARTPROXY_PASS=your-pass
export DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Run a single brand
python main.py --brand samsonite

# Run all enabled brands
python main.py --all
```

## Docker

```bash
docker build -t travel-product-intelligence .
docker run --env-file .env travel-product-intelligence python main.py --all
```
