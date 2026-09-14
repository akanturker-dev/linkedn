"""LinkedIn kisi aramasi icin sorgu kurar ve arama sonucu kartlarini kisi bilgisine cevirir.
Tarayici kullanmaz; tarayici tarafi linkedin_bot.kisi_ara icindedir."""

import re
from urllib.parse import quote

from .kampanyalar import ROL_GRUPLARI, rol_ifadeleri
from .metin import sade_metin
from .tazelik import uye_no

ARAMA_ADRESI = "https://www.linkedin.com/search/results/people/"
TURKIYE_GEO = "102105699"
SAYFA_BASINA_SONUC = 10
SORGU_BASINA_ROL = 4
# Kelimesi cok olan sektorlerde cumle uzayip LinkedIn'de kirpilmasin diye sektor kelimeleri de gruplanir
SORGU_BASINA_SEKTOR = 6
VARSAYILAN_ROLLER = ROL_GRUPLARI["kurucu"][:3] + ROL_GRUPLARI["genel_mudur"][:1]

_DUGME_METINLERI = {
    "baglanti kur", "connect", "takip et", "follow", "mesaj", "message", "mesaj gonder",
    "beklemede", "pending", "dogrulandi", "verified", "premium",
}
_DERECE = re.compile(r"^(1st|2nd|3rd\+?|[123]\.)$|derece baglanti|degree connection")
_SIMDIKI = re.compile(r"^\s*(şu anda|su anda|current)\s*:\s*", re.IGNORECASE)
_TURKCE_EK = re.compile(r"^(.+?)['’](de|da|te|ta|nde|nda)\s", re.IGNORECASE)
_SIRKET_AYRACLARI = (" at ", " @ ")
_BOLUCULER = (" | ", " – ", " — ", " - ", ", ", " / ")


def _veya(ifadeler: list) -> str:
    parcalar = [f'"{i}"' if " " in i else i for i in ifadeler]
    return parcalar[0] if len(parcalar) == 1 else "(" + " OR ".join(parcalar) + ")"


def _liste(degerler) -> list:
    return [str(d).strip() for d in (degerler or []) if str(d).strip()]


def kampanya_sorgulari(sektor_kelimeleri: list, roller: list, sehirler=None, ilceler=None) -> list:
    """Rolleri, oncelik sirasini bozmadan kucuk gruplara bolup her grup icin bir LinkedIn arama cumlesi kurar.
    Sehirler ve ilceler ayri birer VEYA grubu olur; gruplar arasinda VE vardir (sehir grubu VE ilce grubu).
    Cok uzun cumleler LinkedIn'de kirpilabildigi icin tek sorguya sigdirilmaz: kelimesi cok olan sektorlerde
    sektor kelimeleri de gruplara bolunur ve her rol grubu her sektor grubuyla eslesir."""
    roller = roller or VARSAYILAN_ROLLER
    kelimeler = _liste(sektor_kelimeleri)
    sektor_gruplari = [kelimeler[i:i + SORGU_BASINA_SEKTOR] for i in range(0, len(kelimeler), SORGU_BASINA_SEKTOR)] \
        or [[]]
    konum = "".join(f" {_veya(liste)}" for liste in (_liste(sehirler), _liste(ilceler)) if liste)
    sorgular = []
    for sektor_grubu in sektor_gruplari:
        sektor = f" {_veya(sektor_grubu)}" if sektor_grubu else ""
        for i in range(0, len(roller), SORGU_BASINA_ROL):
            grup = roller[i:i + SORGU_BASINA_ROL]
            sorgular.append(f"{_veya([ifade for rol in grup for ifade in rol_ifadeleri(rol)])}{sektor}{konum}")
    return sorgular


def arama_adresi(anahtar_kelime: str, sayfa: int = 1) -> str:
    """Konum filtresi Turkiye'dir (Turkiye sarti zorunlu)."""
    adres = (f"{ARAMA_ADRESI}?keywords={quote(anahtar_kelime)}"
             f"&geoUrn=%5B%22{TURKIYE_GEO}%22%5D&origin=FACETED_SEARCH")
    return adres + (f"&page={sayfa}" if sayfa > 1 else "")


def _atlanir_mi(satir: str) -> bool:
    sade = sade_metin(satir).strip(" •·\t")
    if not sade or sade in _DUGME_METINLERI or _DERECE.search(sade):
        return True
    if sade.startswith(("gecmis:", "past:")):
        return True
    if ("profilini" in sade and "goruntule" in sade) or (sade.startswith("view ") and "profile" in sade):
        return True
    return any(p in sade for p in ("ortak baglanti", "mutual connection", "status is", "sponsorlu", "promoted"))


def karti_coz(satirlar: list):
    """Arama sonucu kartinin metin satirlarindan ad, unvan, konum ve 'Su anda' bilgisini cikarir."""
    temiz = [s.strip() for s in satirlar if s and s.strip() and not _atlanir_mi(s)]
    if not temiz:
        return None
    ad = temiz[0].split(" • ")[0].strip()
    if sade_metin(ad).startswith(("linkedin uyesi", "linkedin member")):
        return None  # ag disindaki gizli profil: adi yok, baglanti kurulamaz
    simdiki = next((s for s in temiz[1:] if _SIMDIKI.match(s)), None)
    digerleri = [s for s in temiz[1:] if s is not simdiki]
    return {
        "ad": ad,
        "unvan": digerleri[0] if digerleri else "",
        "konum": digerleri[1] if len(digerleri) > 1 else "",
        "simdiki": _SIMDIKI.sub("", simdiki).strip() if simdiki else "",
    }


def rol_bul(metin: str, roller: list):
    """Metinde gecen en oncelikli rolu dondurur: (oncelik, rol) ya da None."""
    sade = sade_metin(metin)
    for oncelik, rol in enumerate(roller):
        if any(sade_metin(ifade) in sade for ifade in rol_ifadeleri(rol)):
            return oncelik, rol
    return None


def _sirket_temizle(metin: str) -> str:
    return re.split(r"\s[|•·–—-]\s", metin)[0].strip(" .,;:")


def sirket_cikar(unvan: str, simdiki: str, rol: str) -> str:
    """'General Manager at ABC Hotels', 'ABC Hotels'de Genel Müdür', 'Genel Müdür - ABC Otel',
    'ABC Otel Genel Müdürü' gibi unvanlardan sirket adini cikarir; bulamazsa bos dondurur."""
    rol_sade = [sade_metin(i) for i in rol_ifadeleri(rol)] if rol else []
    for kaynak in (simdiki, unvan):
        if not kaynak:
            continue
        sade = sade_metin(kaynak)  # Turkce harfleri tek karakterle degistirir, indeksler kaynakla ayni kalir
        for ayrac in _SIRKET_AYRACLARI:
            yer = sade.find(ayrac)
            if yer != -1:
                return _sirket_temizle(kaynak[yer + len(ayrac):])
        ek = _TURKCE_EK.match(kaynak)
        if ek:
            return _sirket_temizle(ek.group(1))
        for bolucu in _BOLUCULER:
            if bolucu in kaynak:
                parcalar = [p.strip() for p in kaynak.split(bolucu) if p.strip()]
                adaylar = [p for p in parcalar if not any(r in sade_metin(p) for r in rol_sade)]
                if len(parcalar) > 1 and adaylar:
                    return _sirket_temizle(adaylar[0])
        for r in rol_sade:
            yer = sade.find(r)
            if yer > 1:
                return _sirket_temizle(kaynak[:yer])
    return ""


def _konum_uygun(konum: str, sehirler=None) -> bool:
    """Turkiye zorunlu; sehir secildiyse kisinin konumu o sehirlerden biri olmali. Ilce burada aranmaz:
    LinkedIn profilinde konum sehir duzeyinde yazilir, ilce arama cumlesinde kullanilir.
    Konum okunamadiysa arama filtresine guvenilir."""
    if not konum:
        return True
    sade = sade_metin(konum)
    secili = _liste(sehirler)
    if secili:
        return any(sade_metin(s) in sade for s in secili)
    return "turkiye" in sade or "turkey" in sade


def adaylari_cikar(kartlar: list, roller: list, sehirler=None) -> list:
    """Kartlardan sadece secilen rollerdeki ve Turkiye'deki (sehir secildiyse o sehirlerdeki) kisileri aday yapar."""
    roller = roller or VARSAYILAN_ROLLER
    adaylar = []
    for kart in kartlar:
        kisi = karti_coz(kart.get("satirlar", []))
        if not kisi:
            continue
        eslesme = rol_bul(f"{kisi['unvan']} {kisi['simdiki']}", roller)
        if not eslesme or not _konum_uygun(kisi["konum"], sehirler):
            continue
        oncelik, rol = eslesme
        adaylar.append(
            {
                "linkedin_url": kart["url"].split("?")[0].rstrip("/"),
                "linkedin_ad": kisi["ad"],
                "linkedin_unvan": kisi["unvan"],
                "konum": kisi["konum"],
                "linkedin_rol": rol,
                "oncelik": oncelik,
                "isletme_adi": sirket_cikar(kisi["unvan"], kisi["simdiki"], rol),
                # Kartin icindeki LinkedIn kimliginden uye numarasi: buyukse sonra katilmis demektir
                "uye_no": uye_no(kart.get("kimlik")),
            }
        )
    return adaylar
