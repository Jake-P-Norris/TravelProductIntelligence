# TravelProductIntelligence

A retail market-intelligence pipeline that tracks competitor pricing, product availability and assortment across Australian travel and luggage brands.

---

## What it does

TravelProductIntelligence scrapes product catalogues from travel brand websites, extracts structured product data (name, price, availability, images, category), and loads it into BigQuery for analysis.

It is designed to support:

- **Pricing intelligence** — monitor retail prices across brands and over time
- **Range tracking** — understand competitor assortment and product mix
- **Availability monitoring** — detect when products go in or out of stock
- **Commercial decision-making** — inform buying, ranging and promotional strategy

---

## Architecture

```
Brand configs (config/brands.py)
        │
        ▼
Sitemap / seed URL discovery (utils/sitemap.py)
        │
        ▼
Product page scraping + JSON-LD parsing (scrapers/jsonld.py)
        │
        ├─► BigQuery: TravelProductIntelligence_raw.products_index
        └─► BigQuery: TravelProductIntelligence_raw.products_raw_v2
                │
                ▼
        Discord run alerts (alerts/discord.py)
```

Discovery supports two strategies:
- **Sitemap index crawl** — follows `sitemap_index.xml` → filtered child sitemaps → product URLs
- **Seed URL crawl** — scrapes a known category page and extracts product links via `<a href>` and regex patterns

Product data is extracted from JSON-LD structured data embedded in each product page.

---

## Tech stack

| Layer | Technology |
|---|---|
| Scraping | Python, `requests`, `BeautifulSoup` |
| Parsing | JSON-LD (`scrapers/jsonld.py`) |
| Storage | Google BigQuery (`google-cloud-bigquery`) |
| Scheduling | GitHub Actions / Docker |
| Alerting | Discord webhooks |
| Config | Per-brand dataclass in `config/brands.py` |

---

## Current working brands

| Brand | Discovery method | Status |
|---|---|---|
| Antler | Sitemap index | Working — 308 URLs discovered |
| Delsey | Seed URL | Working — 46 URLs discovered |
| Lojel | Sitemap index | Working — 65 URLs discovered |
| American Tourister | Sitemap index | Blocked — client challenge from Codespaces |
| High Sierra | Sitemap index | Blocked — client challenge from Codespaces |
| Samsonite | Sitemap index | Blocked — client challenge from Codespaces |
| Victorinox | Sitemap + seed | Discovery returns 0 — under investigation |

Samsonite-family sites (samsonite.com.au, americantourister.com.au, highsierra.com.au) use Cloudflare bot protection that blocks Codespace datacenter IPs. These work correctly from a residential IP or with a residential proxy.

---

## Example successful run

```
python main.py --all
```

```
[
  {'brand': 'ANTLER',  'discovered': 308, 'scraped': 40, 'failed': 0, 'duration': 92,  'error': None},
  {'brand': 'DELSEY',  'discovered': 46,  'scraped': 40, 'failed': 0, 'duration': 118, 'error': None},
  {'brand': 'LOJEL',   'discovered': 65,  'scraped': 40, 'failed': 0, 'duration': 104, 'error': None},
]
```

---

## Setup

**1. Clone and create a virtual environment**

```bash
git clone https://github.com/jakenmntzr/TravelProductIntelligence.git
cd TravelProductIntelligence
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**2. Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` and fill in:

```
SMARTPROXY_HOST=          # optional — only needed for bot-protected sites
SMARTPROXY_PORT=
SMARTPROXY_USER=
SMARTPROXY_PASS=
DISCORD_WEBHOOK_URL=      # optional — alerts are skipped if not set
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

**3. Set up Google Cloud credentials**

Create a GCP service account with BigQuery Data Editor and Job User roles, download the JSON key, and set `GOOGLE_APPLICATION_CREDENTIALS` in `.env`.

**4. Run**

```bash
# Single brand (good for testing)
python main.py --brand antler

# All enabled brands
python main.py --all
```

**5. Run with Docker**

```bash
docker build -t travelproductintelligence .
docker run --env-file .env travelproductintelligence
```

---

## BigQuery schema

Two tables in dataset `TravelProductIntelligence_raw`:

- **`products_index`** — URL discovery index; tracks which URLs have been scraped and when
- **`products_raw_v2`** — scraped product rows: name, price, availability, images, category, product type, brand, locale, scraped timestamp

---

## Portfolio relevance

This project demonstrates skills relevant to retail analytics, commercial analytics, pricing intelligence, and data engineering roles:

- **Data pipeline development** — end-to-end ETL from web scraping to cloud data warehouse
- **Retail pricing intelligence** — automated competitor price and range monitoring
- **BigQuery data modelling** — schema design for product index and raw product fact tables
- **Web scraping at scale** — sitemap crawling, structured data extraction, anti-bot handling
- **Operational reliability** — per-run alerting, error surfacing, proxy fallback logic
- **Clean Python engineering** — typed dataclasses for brand config, modular scrapers, separation of discovery/scraping/storage concerns

---

## Project structure

```
config/brands.py        # Per-brand scraping configuration (sitemap URL, URL patterns, parser)
utils/sitemap.py        # Sitemap index crawl and seed URL discovery
utils/http.py           # HTTP session, retry logic, proxy support
scrapers/jsonld.py      # JSON-LD product data extractor
pipelines/index.py      # BigQuery products_index upsert
pipelines/raw.py        # BigQuery products_raw_v2 insert
alerts/discord.py       # Discord webhook run alerts
main.py                 # Entry point — orchestrates discovery, scraping, storage, alerting
```
