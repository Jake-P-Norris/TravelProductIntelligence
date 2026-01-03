from datetime import datetime, timezone
from typing import Optional

import requests


def send_alert(
    webhook_url: str,
    *,
    title: str,
    message: str,
    is_error: bool,
    brand: str,
) -> None:
    if not webhook_url:
        return

    color = 0xFF0000 if is_error else 0x00FF00
    payload = {
        "embeds": [{
            "title": title,
            "description": message[:3900],
            "color": color,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "footer": {"text": f"Mentzer Scraper | {brand}"}
        }]
    }

    try:
        r = requests.post(webhook_url, json=payload, timeout=10)
        if r.status_code == 429:
            try:
                data = r.json()
                retry_after = float(data.get("retry_after", 1.5))
            except Exception:
                retry_after = 1.5
            import time
            time.sleep(retry_after)
            r = requests.post(webhook_url, json=payload, timeout=10)
        r.raise_for_status()
    except Exception:
        pass
