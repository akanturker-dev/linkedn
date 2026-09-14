"""LinkedIn profil, sirket ve paylasim sayfalarindan okunan metni bilgiye ceviren saf fonksiyonlar.
Tarayici kullanmaz; sinif adlarina degil etiket ve metin sirasina dayanir (LinkedIn tasarim degistirince daha az bozulur)."""

import re

from .metin import sade_metin

_ETIKETLER = {
    "website": ("web sitesi", "website"),
    "sektor": ("sektor", "industry"),
    "boyut": ("sirket buyuklugu", "company size"),
}
_ZAMAN = re.compile(r"(?<![\w])(\d+)\s*(dk|sa|gun|g|hf|hafta|ay|yil|y|mo|yr|min|h|d|w|m)(?![\w])")
_GUN_KATSAYISI = {
    "dk": 0, "min": 0, "m": 0, "sa": 0, "h": 0,
    "g": 1, "gun": 1, "d": 1,
    "hf": 7, "hafta": 7, "w": 7,
    "ay": 30, "mo": 30,
    "y": 365, "yil": 365, "yr": 365,
}
_PAYLASIM_YOK = ("henuz paylasim", "hasn't posted", "has not posted", "no posts yet", "paylasim yapmadi")


def sirket_slugu(href: str) -> str:
    """'https://www.linkedin.com/company/abc-otel/?x=1' -> 'abc-otel'"""
    eslesme = re.search(r"/company/([^/?#]+)", href or "")
    return eslesme.group(1) if eslesme else ""


def boyut_bandi(metin: str):
    """'11-50 çalışan', '2-10 employees', '1.001-5.000 çalışan', '10.001+ employees' -> LinkedIn dilimi."""
    sayilar = re.findall(r"\d[\d.,]*", metin or "")
    if not sayilar:
        return None
    alt = int(re.sub(r"[.,]", "", sayilar[0]))
    if alt <= 10:
        return "1-10"
    if alt <= 50:
        return "11-50"
    if alt <= 200:
        return "51-200"
    if alt <= 500:
        return "201-500"
    if alt <= 1000:
        return "501-1000"
    return "1001+"


def sirket_hakkinda_coz(satirlar: list) -> dict:
    """Sirket 'Hakkinda' sayfasindaki 'Etiket / deger' satir ciftlerinden site, sektor ve buyuklugu cikarir."""
    temiz = [s.strip() for s in satirlar if s and s.strip()]
    sonuc = {"website": None, "sektor": None, "boyut": None}
    for i, satir in enumerate(temiz[:-1]):
        sade = sade_metin(satir).rstrip(":")
        for alan, etiketler in _ETIKETLER.items():
            if sonuc[alan] is None and sade in etiketler:
                sonuc[alan] = temiz[i + 1]
    if sonuc["boyut"]:
        sonuc["boyut"] = boyut_bandi(sonuc["boyut"])
    if sonuc["website"] and not sonuc["website"].lower().startswith(("http", "www.")) and "." not in sonuc["website"]:
        sonuc["website"] = None
    return sonuc


def son_paylasim_gunu(metin: str):
    """Paylasimlar sayfasindaki '2 hf •', '3d •', '1 ay •' gibi zamanlardan en yenisini gun olarak dondurur.
    Hic paylasim yoksa -1, okunamazsa None."""
    sade = sade_metin(metin or "")
    if any(ifade in sade for ifade in _PAYLASIM_YOK):
        return -1
    gunler = []
    for satir in sade.splitlines():
        if "•" not in satir and "·" not in satir:
            continue
        for sayi, birim in _ZAMAN.findall(satir):
            gunler.append(int(sayi) * _GUN_KATSAYISI[birim])
            break
    return min(gunler) if gunler else None
