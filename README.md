# TravelProductIntelligence

Retail product & pricing data pipeline — Python scrapers → BigQuery.

## What it does
Scrapes product and pricing data from retail brand websites and loads it into BigQuery for analysis and price tracking.

## Architecture
scrapers/ → pipelines/ → BigQuery → alerts/

## Tech stack
- Python
- Google BigQuery
- Docker
- GitHub Actions (scrape.yml)

## Structure
- `scrapers/` — brand-specific web scrapers (JSON-LD, SFCC, sitemap-based)
- `pipelines/` — BigQuery load logic
- `alerts/` — alerting on price changes or anomalies
- `config/` — brand configs and credentials
- `utils/` — shared utilities (classification, sitemap discovery)
- `main.py` — entry point

## Running locally
```bash
pip install -r requirements.txt
python main.py
```

## Docker
```bash
docker build -t TravelProductIntelligence .
docker run TravelProductIntelligence
```

## Environment variables
- `GOOGLE_APPLICATION_CREDENTIALS` — path to BigQuery service account JSON
- Configure brands in `config/brands.py`

## Background
Personal retail analytics project built to track competitor pricing and product availability across fashion and luggage brands.
