import gzip
import random
import time
from dataclasses import dataclass
from typing import Optional, Tuple

import requests


# Global HTTP tuning
REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
BASE_RETRY_DELAY = 2.0


@dataclass(frozen=True)
class ProxyConfig:
    host: str
    port: str
    user: str
    password: str

    @property
    def proxies(self) -> dict:
        proxy_url = f"http://{self.user}:{self.password}@{self.host}:{self.port}"
        return {"http": proxy_url, "https": proxy_url}


def jitter_sleep(rng: Tuple[float, float]) -> None:
    time.sleep(random.uniform(rng[0], rng[1]))


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-AU,en;q=0.8,en-US;q=0.6",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    })
    return s


def _decompress_if_gz(url: str, content: bytes) -> str:
    if url.lower().endswith(".gz"):
        return gzip.decompress(content).decode("utf-8", errors="replace")
    return content.decode("utf-8", errors="replace")


def get_text(
    session: requests.Session,
    url: str,
    *,
    use_proxy: bool,
    proxy: Optional[ProxyConfig],
    fallback_no_proxy: bool = False,
) -> str:
    """
    Fetch URL with retries.
    If fallback_no_proxy=True, and we hit SSL/403/429-type pain, retry WITHOUT proxy once.
    """
    last_error: Optional[Exception] = None
    tried_no_proxy = False

    for attempt in range(1, MAX_RETRIES + 1):
        proxies = proxy.proxies if (use_proxy and proxy) else None

        try:
            r = session.get(url, timeout=REQUEST_TIMEOUT, proxies=proxies)

            # Proxy sometimes triggers 403 on sitemaps; fallback to direct
            if r.status_code == 403 and fallback_no_proxy and use_proxy and not tried_no_proxy:
                use_proxy = False
                tried_no_proxy = True
                continue

            if r.status_code == 429:
                ra = r.headers.get("Retry-After")
                delay = float(ra) if ra and ra.isdigit() else (BASE_RETRY_DELAY * attempt)
                time.sleep(delay)

                if fallback_no_proxy and use_proxy and not tried_no_proxy:
                    use_proxy = False
                    tried_no_proxy = True
                continue

            if r.status_code in (500, 502, 503, 504):
                delay = BASE_RETRY_DELAY * attempt + random.uniform(0.0, 1.2)
                time.sleep(delay)
                continue

            r.raise_for_status()

            if url.lower().endswith(".gz"):
                return _decompress_if_gz(url, r.content)

            return r.text

        except (requests.exceptions.SSLError,
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError) as e:
            last_error = e
            delay = BASE_RETRY_DELAY * attempt + random.uniform(0.0, 1.2)
            time.sleep(delay)

            if fallback_no_proxy and use_proxy and not tried_no_proxy:
                use_proxy = False
                tried_no_proxy = True

        except requests.exceptions.HTTPError as e:
            last_error = e
            code = getattr(e.response, "status_code", None)

            if code in (400, 404):
                raise

            if code == 403 and fallback_no_proxy and use_proxy and not tried_no_proxy:
                use_proxy = False
                tried_no_proxy = True
                continue

            delay = BASE_RETRY_DELAY * attempt + random.uniform(0.0, 1.2)
            time.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError("Unknown error in get_text()")
