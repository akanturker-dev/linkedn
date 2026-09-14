import requests

SEARCH_URL = "https://google.serper.dev/search"


class SerperHatasi(Exception):
    pass


def _post(url: str, api_key: str, payload: dict) -> dict:
    if not api_key:
        raise SerperHatasi("Serper API anahtarı ayarlanmamış. Ayarlar sekmesinden ekle.")
    headers = {"X-API-KEY": api_key, "Content-Type": "application/json"}
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    if resp.status_code == 401:
        raise SerperHatasi("Serper API anahtarı geçersiz.")
    if resp.status_code == 429:
        raise SerperHatasi("Serper API kullanım limiti aşıldı (429).")
    resp.raise_for_status()
    return resp.json()


def google_ara(query: str, api_key: str, sayfa: int = 1) -> dict:
    return _post(SEARCH_URL, api_key, {"q": query, "gl": "tr", "hl": "tr", "page": sayfa})
