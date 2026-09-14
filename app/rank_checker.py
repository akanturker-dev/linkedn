import re
from urllib.parse import urlparse

from .metin import sade_metin
from .serper_client import google_ara

# Sirketin kendi sitesi sayilmayacak rehber, sosyal medya ve rezervasyon siteleri
DIZIN_SITELERI = (
    "linkedin.", "facebook.", "instagram.", "twitter.", "x.com", "youtube.", "tiktok.", "tripadvisor.",
    "booking.", "yelp.", "wikipedia.", "google.", "foursquare.", "sahibinden.", "hepsiburada.", "trendyol.",
    "yandex.", "yemeksepeti.", "etstur.", "jollytur.", "tatilsepeti.", "otelz.", "expedia.", "hotels.com",
    "agoda.", "trivago.", "kariyer.net", "armut.com", "doktortakvimi.", "emlakjet.", "hurriyetemlak.",
    "arabam.com", "zomato.", "bloomberght.", "haberturk.", "hurriyet.", "milliyet.", "sabah.",
)


def _domain_normalize(url_or_domain: str) -> str:
    if not url_or_domain:
        return ""
    value = url_or_domain.strip().lower()
    if "://" not in value:
        value = "http://" + value
    netloc = urlparse(value).netloc
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def domain_eslesiyor(website: str, sonuc_linki: str) -> bool:
    hedef = _domain_normalize(website)
    aday = _domain_normalize(sonuc_linki)
    if not hedef or not aday:
        return False
    return hedef == aday or aday.endswith("." + hedef) or hedef.endswith("." + aday)


def _alan_adi_sirkete_benziyor(sirket: str, link: str) -> bool:
    alan = re.sub(r"[^a-z0-9]", "", _domain_normalize(link).split(".")[0])
    kelimeler = [re.sub(r"[^a-z0-9]", "", k) for k in sade_metin(sirket).split()]
    return any(len(k) >= 3 and k in alan for k in kelimeler)


def site_bul(sirket: str, sehir: str, api_key: str):
    """Sirketin kendi web sitesini Google'dan bulur. Google'in isletme kutusundaki site onceliklidir;
    yoksa ilk sonuclardan, rehber/sosyal medya olmayan ve alan adi sirket adina benzeyen alinir."""
    sonuc = google_ara(f'"{sirket}" {sehir}', api_key, sayfa=1)
    kutu_sitesi = (sonuc.get("knowledgeGraph") or {}).get("website")
    if kutu_sitesi:
        return kutu_sitesi
    for item in sonuc.get("organic", [])[:6]:
        link = item.get("link", "")
        alan = _domain_normalize(link)
        if alan and not any(d in alan for d in DIZIN_SITELERI) and _alan_adi_sirkete_benziyor(sirket, link):
            return link
    return None


def sira_kontrol_et(website: str, arama_terimi: str, api_key: str, max_sayfa: int = 3):
    """Google'da arama_terimi icin website kacinci sirada/sayfada cikiyor bulur.
    Donus: (mutlak_sira, sayfa) bulunursa, (None, None) ilk max_sayfa*10 sonucta yoksa."""
    for sayfa in range(1, max_sayfa + 1):
        sonuc = google_ara(arama_terimi, api_key, sayfa=sayfa)
        organik = sonuc.get("organic", [])
        for i, item in enumerate(organik):
            if domain_eslesiyor(website, item.get("link", "")):
                mutlak_sira = (sayfa - 1) * 10 + (i + 1)
                return mutlak_sira, sayfa
        if not organik:
            break
    return None, None
