from dataclasses import dataclass
from typing import Dict, Optional, List


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

    parser: str  # "jsonld" or "sfcc"

    # Proxy behavior
    sitemap_use_proxy: bool
    product_use_proxy: bool

    # SFCC only (Jil Sander): ajax URL template that includes {pid}
    sfcc_ajax_template: Optional[str] = None

    # Optional: non-sitemap discovery (e.g., Prada category pages)
    seed_urls: Optional[List[str]] = None


BRANDS: Dict[str, BrandConfig] = {
    "acne": BrandConfig(
        enabled=True,  # flip to True when you want it live
        key="acne",
        name="ACNE STUDIOS",
        source="acnestudios.com",
        locale="au/en",
        sitemap_index="https://www.acnestudios.com/sitemap_index.xml",
        sitemap_filter=None,
        product_url_pattern=r"^https://www\.acnestudios\.com/au/en/.+/([A-Z]{2}\d{4}-[A-Z0-9]{2,})\.html$",
        parser="jsonld",
        sitemap_use_proxy=True,
        product_use_proxy=True,
        sfcc_ajax_template=None,
        seed_urls=None,
    ),
    "jilsander": BrandConfig(
        enabled=True,
        key="jilsander",
        name="JIL SANDER",
        source="jilsander.com",
        locale="en-au",
        sitemap_index="https://www.jilsander.com/en-au/sitemap_index.xml",
        sitemap_filter=r"sitemap-en-au\.xml(\.gz)?$",
        product_url_pattern=r"^https://www\.jilsander\.com/en-au/.+/([A-Z0-9]+)\.html$",
        parser="sfcc",
        sitemap_use_proxy=False,     # your critical fix
        product_use_proxy=True,      # product pages via proxy worked for you
        sfcc_ajax_template=(
            "https://www.jilsander.com/on/demandware.store/"
            "Sites-JilSanderAPAC-Site/en_AU/Product-Show?pid={pid}&format=ajax"
        ),
        seed_urls=None,
    ),
    "driesvannoten": BrandConfig(
        enabled=True,
        key="driesvannoten",
        name="DRIES VAN NOTEN",
        source="driesvannoten.com",
        locale="global",
        sitemap_index="https://www.driesvannoten.com/sitemap.xml",
        # only root product sitemap (not /fr/, /en-sn/, etc) — keeps discovery sane
        sitemap_filter=r"^https://www\.driesvannoten\.com/sitemap_products_\d+\.xml(\?.*)?$",
        # IMPORTANT: canonical products only (no /en-xx/ or /fr-fr/)
        product_url_pattern=r"^https://www\.driesvannoten\.com/products/([^/?#]+)$",
        parser="jsonld",
        sitemap_use_proxy=False,
        product_use_proxy=True,
        sfcc_ajax_template=None,
        seed_urls=None,
    ),
    "prada": BrandConfig(
        enabled=True,
        key="prada",
        name="PRADA",
        source="prada.com",
        locale="au/en",

        # NOTE: Prada AU sitemap is mostly pradasphere/store-locator (no products).
        # We keep this filled for completeness, but discovery should use seed_urls.
        sitemap_index="https://www.prada.com/au/en/sitemap.xml",
        sitemap_filter=None,

        # Product pages:
        # https://www.prada.com/au/en/p/<slug>/<SKU>
        # Example SKU: 1BG600_2HFQ_F0002_V_OOO
        product_url_pattern=r"^https://www\.prada\.com/au/en/p/[^/]+/([A-Z0-9]+(?:_[A-Z0-9]+)+)$",

        parser="jsonld",

        # You successfully fetched category + product HTML without proxy
        sitemap_use_proxy=False,
        product_use_proxy=False,

        sfcc_ajax_template=None,

        # Category seeds (start small; add more once stable)
        seed_urls=[
            "https://www.prada.com/au/en/womens/bags/c/10062AU",
            # "https://www.prada.com/au/en/mens/bags/c/10143AU",
            # "https://www.prada.com/au/en/womens/shoes/c/10070AU",
            # "https://www.prada.com/au/en/mens/shoes/c/10149AU",
        ],
    ),
}
