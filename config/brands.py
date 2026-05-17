from dataclasses import dataclass
from typing import Dict, Optional, List

@dataclass(frozen=True)
class BrandConfig:
    enabled: bool; key: str; name: str; source: str; locale: str
    sitemap_index: str; sitemap_filter: Optional[str]; product_url_pattern: str
    parser: str; sitemap_use_proxy: bool; product_use_proxy: bool
    sfcc_ajax_template: Optional[str] = None
    seed_urls: Optional[List[str]] = None

LEGACY_BRANDS: Dict[str, BrandConfig] = {}

BRANDS: Dict[str, BrandConfig] = {
    "samsonite": BrandConfig(True,"samsonite","SAMSONITE","samsonite.com.au","au/en","https://www.samsonite.com.au/sitemap_index.xml",r"sitemap_0-product\.xml$",r"^https://www\.samsonite\.com\.au/.+?/([a-z0-9\-]+)\.html$","jsonld",False,False),
    "americantourister": BrandConfig(True,"americantourister","AMERICAN TOURISTER","americantourister.com.au","au/en","https://www.americantourister.com.au/sitemap_index.xml",r"sitemap_0-product\.xml$",r"^https://www\.americantourister\.com\.au/.+?/([a-z0-9\-]+(?:/[a-z0-9\-]+)?(?:/at-[a-z0-9\-]+)?)\.html$","jsonld",False,False),
    "antler": BrandConfig(True,"antler","ANTLER","antler.com.au","au/en","https://www.antler.com.au/sitemap.xml",r"sitemap_products_\d+\.xml",r"^https://www\.antler\.com\.au/products/([^/?#]+)$","jsonld",False,False),
    "tosca": BrandConfig(False,"tosca","TOSCA","toscaluggage.com.au","au/en","https://www.toscaluggage.com.au/sitemap.xml",None,r"^https://www\.toscaluggage\.com\.au/.+","jsonld",False,False),
    "highsierra": BrandConfig(True,"highsierra","HIGH SIERRA","highsierra.com.au","au/en","https://www.highsierra.com.au/sitemap_index.xml",r"sitemap_0-product\.xml$",r"^https://www\.highsierra\.com\.au/.+?/([a-z0-9\-]+)\.html$","jsonld",False,False),
    "delsey": BrandConfig(True,"delsey","DELSEY","int.delsey.com","en","https://int.delsey.com/sitemap.xml",None,r"^https://int\.delsey\.com/(?:collections/[^/]+/)?products/([^/?#]+)/?$","jsonld",False,False,seed_urls=["https://int.delsey.com/collections/luggages"]),
    "victorinox": BrandConfig(True,"victorinox","VICTORINOX","victorinox.com","en","https://www.victorinox.com/sitemap/en.xml",r"/sitemap/dynamic/en\.xml$",r"^https://www\.victorinox\.com/en/Products/Travel-Gear/.+/p/([^/?#]+)$","jsonld",False,False,seed_urls=["https://www.victorinox.com/en/Products/Travel-Gear/c/TRG/"]),
    "july": BrandConfig(False,"july","JULY","july.com","au/en","https://july.com/sitemap.xml",None,r"^https://july\.com/(?:au/)?products/((?!gift-card)[^/?#]+)/?$","jsonld",False,False,seed_urls=["https://july.com/au/luggage/"]),
    "rimowa": BrandConfig(False,"rimowa","RIMOWA","rimowa.com","au/en","https://www.rimowa.com/sitemap.xml",None,r"^https://www\.rimowa\.com/.+","jsonld",False,False,seed_urls=["https://www.rimowa.com/au/en/luggage/"]),
    "lojel": BrandConfig(True,"lojel","LOJEL","lojel.com","global","https://www.lojel.com/sitemap_index.xml",r"product-sitemap\.xml$",r"^https://(?:www|us)\.lojel\.com/product/([^/?#]+)/?$","jsonld",False,False),
}
