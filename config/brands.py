from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class BrandConfig:
    enabled: bool
    key: str
    name: str
    source: str
    locale: str
    sitemap_index: str
    sitemap_filter: Optional[str]
    product_url_pattern: str
    parser: str
    sitemap_use_proxy: bool
    product_use_proxy: bool
    sfcc_ajax_template: Optional[str] = None
    seed_urls: Optional[List[str]] = None


BRANDS: Dict[str, BrandConfig] = {
    "samsonite": BrandConfig(
        enabled=True,
        key="samsonite",
        name="SAMSONITE",
        source="samsonite.com.au",
        locale="au/en",
        sitemap_index="https://www.samsonite.com.au/sitemap_index.xml",
        sitemap_filter=r"sitemap_0-product\.xml$",
        product_url_pattern=r"^https://www\.samsonite\.com\.au/[^/]+/([a-z0-9\-]+)\.html$",
        parser="jsonld",
        sitemap_use_proxy=False,
        product_use_proxy=False,
    ),
    "rimowa": BrandConfig(
        enabled=True,
        key="rimowa",
        name="RIMOWA",
        source="rimowa.com",
        locale="au/en",
        sitemap_index="https://www.rimowa.com/sitemap.xml",
        sitemap_filter=None,
        product_url_pattern=r"^https://www\.rimowa\.com/au/en/.+/(\d+)\.html$",
        parser="jsonld",
        sitemap_use_proxy=True,
        product_use_proxy=True,
        seed_urls=[
            "https://www.rimowa.com/au/en/luggage/",
            "https://www.rimowa.com/au/en/all-products/",
        ],
    ),
    "antler": BrandConfig(
        enabled=True,
        key="antler",
        name="ANTLER",
        source="antler.com.au",
        locale="au/en",
        sitemap_index="https://www.antler.com.au/sitemap.xml",
        sitemap_filter=r"sitemap_products_\d+\.xml",
        product_url_pattern=r"^https://www\.antler\.com\.au/products/([^/?#]+)$",
        parser="jsonld",
        sitemap_use_proxy=False,
        product_use_proxy=False,
    ),
    "tumi": BrandConfig(
        enabled=True,
        key="tumi",
        name="TUMI",
        source="tumi.com.au",
        locale="au/en",
        sitemap_index="https://www.tumi.com.au/sitemap_index.xml",
        sitemap_filter=r"sitemap_0-product\.xml$",
        product_url_pattern=r"^https://www\.tumi\.com\.au/.+/(tu-[a-z0-9]+-\d+)\.html$",
        parser="jsonld",
        sitemap_use_proxy=False,
        product_use_proxy=False,
    ),
}
