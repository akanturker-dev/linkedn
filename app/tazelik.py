"""LinkedIn'e ne zaman katildigini tahmin etme.

OLCULEN GERCEK (13 Eylul 2026, gercek LinkedIn hesabinda dogrulandi):
  * LinkedIn aramasinin TUM filtre listesi soyle: Baglantilar, Konumlar, Mevcut sirketler,
    su uyenin baglantilari/takipcileri, Onceki sirketler, Okullar, Sektorler, Profil Dilleri,
    Hizmet kategorileri, Anahtar Sozcukler, Ad, Soyadi, Unvan, Sirket, Okul.
    ** Kayit/katilim tarihi diye bir filtre YOK. ** Profilde de yazmiyor (iletisim bilgileri dahil).
  * Ama her arama sonucu kartinin icinde kisinin LinkedIn uye kimligi var (ACoAA... ile baslayan urn).
    Bunun icinde 4 baytlik UYE NUMARASI duruyor ve bu numara sirayla dagitiliyor:
    ** buyuk numara = LinkedIn'e sonra katilmis. ** Bu siralama kesindir, tahmin degildir.
    Ornek olcum: 113.218.637 (eski) ... 1.820.231.225 (yeni) araligi tek arama sayfasinda goruldu.

Bu yuzden:
  - "En yeni katilanlari getir" islemi KESIN calisir (numaraya gore siralama).
  - "3 gun once katildi" gibi tarih etiketi TAHMINDIR: numarayi tarihe cevirmek icin
    asistan gordugu en buyuk numarayi gun gun kaydeder ve zamanla gercek hizi kendisi olcer
    (olcum_ekle / _hiz). Yeterli olcum birikene kadar TOHUM_HIZ kullanilir ve bu ekranda
    "kaba tahmin" diye yazar.
"""
import base64
import re
from datetime import date, datetime, timedelta

from . import db

URN_DESENI = re.compile(r"ACoAA[A-Za-z0-9_-]{15,40}")

# "Sadece en yeni" modu: tarihe hic bakmaz. Simdiye kadar bulunmus en yeni EN_YENI_KOTA kisiden
# daha yeni olmayani almaz; yani cita her yeni bulusla kendiliginden yukselir. Tahmin icermez,
# sadece uye numarasi siralamasina dayanir - bu yuzden en guvenilir secenek budur.
EN_YENI = "enyeni"
EN_YENI_KOTA = 100

# Ekrandaki tazelik secenekleri: (kod, ad, gun). gun=None ise tarih penceresi yoktur.
PENCERELER = [
    (EN_YENI, "Sadece en yeni katılanlar (tarihe bakma)", None),
    ("3g", "Son 3 gün içinde katılanlar", 3),
    ("1h", "Son 1 hafta içinde katılanlar", 7),
    ("1a", "Son 1 ay içinde katılanlar", 30),
    ("3a", "Son 3 ay içinde katılanlar", 90),
    ("6a", "Son 6 ay içinde katılanlar", 180),
    ("12a", "Son 12 ay içinde katılanlar", 365),
]
PENCERE_GUNU = {kod: gun for kod, _, gun in PENCERELER if gun}
PENCERE_ADI = {kod: ad for kod, ad, _ in PENCERELER}
VARSAYILAN_PENCERE = "3a"

# Gunde dagitilan uye numarasi (tohum). Gercek hiz olculunce bu deger kullanilmaz.
TOHUM_HIZ = 900_000
# Kendi hizimizi olcmek icin en az bu kadar gun arayla iki olcum gerekir
EN_AZ_OLCUM_ARALIGI = 5


def uye_no(kaynak: str):
    """Kart HTML'inden ya da urn metninden uye numarasini cikarir. Bulamazsa None."""
    if not kaynak:
        return None
    eslesme = URN_DESENI.search(kaynak)
    if not eslesme:
        return None
    try:
        baytlar = base64.urlsafe_b64decode(eslesme.group(0)[:12] + "==")
    except Exception:
        return None
    if len(baytlar) < 8:
        return None
    numara = int.from_bytes(baytlar[4:8], "big")
    return numara or None


# ---------------- Numarayi tarihe cevirme (kendi kendini ayarlar) ----------------

def olcum_ekle(en_buyuk_numara: int) -> None:
    """Her aramada gorulen en buyuk numara gunluk olarak kaydedilir; tarih egrisi bundan cikar."""
    if en_buyuk_numara:
        db.tavan_olcumu_kaydet(date.today().isoformat(), int(en_buyuk_numara))


def _olcumler() -> list:
    return [(datetime.fromisoformat(g).date(), n) for g, n in db.tavan_olcumleri()]


def _hiz_ve_tavan():
    """(gunluk hiz, bugunku tavan numara, olculdu mu) dondurur."""
    olcumler = _olcumler()
    if not olcumler:
        return TOHUM_HIZ, None, False
    son_gun, son_no = olcumler[-1]
    ilk_gun, ilk_no = olcumler[0]
    fark_gun = (son_gun - ilk_gun).days
    if fark_gun >= EN_AZ_OLCUM_ARALIGI and son_no > ilk_no:
        hiz, olculdu = (son_no - ilk_no) / fark_gun, True
    else:
        hiz, olculdu = TOHUM_HIZ, False
    # Son olcumden bu yana gecen gunler icin tavan ileri tasinir
    tavan = son_no + hiz * max((date.today() - son_gun).days, 0)
    return hiz, tavan, olculdu


def olculdu_mu() -> bool:
    return _hiz_ve_tavan()[2]


def esik(pencere_kodu: str):
    """Secilen tazelik penceresine karsilik gelen uye numarasi esigi; bu numaradan buyukse 'taze'.
    "Sadece en yeni" modunda esik tarihten degil, simdiye kadar bulunanlarin en yenilerinden gelir."""
    if pencere_kodu == EN_YENI:
        return db.en_yeni_uye_no_bari(EN_YENI_KOTA)
    hiz, tavan, _ = _hiz_ve_tavan()
    if not tavan:
        return None
    return tavan - hiz * PENCERE_GUNU.get(pencere_kodu, PENCERE_GUNU[VARSAYILAN_PENCERE])


def tahmini_gun(numara) -> int:
    """Bu uye numarasi kac gun once katilmis olabilir (tahmin). Bilinmiyorsa None."""
    if not numara:
        return None
    hiz, tavan, _ = _hiz_ve_tavan()
    if not tavan or hiz <= 0:
        return None
    return max(int((tavan - numara) / hiz), 0)


def tahmini_tarih(numara):
    gun = tahmini_gun(numara)
    return (date.today() - timedelta(days=gun)) if gun is not None else None


def etiket(numara) -> str:
    """Ekranda kisinin yaninda gorunecek tazelik yazisi."""
    gun = tahmini_gun(numara)
    if gun is None:
        return "Katılma zamanı okunamadı"
    kaba = "" if olculdu_mu() else " (kaba tahmin)"
    if gun < 1:
        return f"Bugün katılmış olabilir{kaba}"
    if gun < 7:
        return f"~{gun} gün önce katılmış{kaba}"
    if gun < 30:
        return f"~{gun // 7} hafta önce katılmış{kaba}"
    if gun < 365:
        return f"~{gun // 30} ay önce katılmış{kaba}"
    return f"~{gun // 365} yıl önce katılmış{kaba}"


def taze_mi(numara, pencere_kodu: str) -> bool:
    if not numara:
        return False
    sinir = esik(pencere_kodu)
    if sinir is None:
        # "Sadece en yeni" modunda kota dolana kadar sinir yoktur: ilk kisiler alinir, cita sonra yukselir.
        # Tarih pencerelerinde ise sinir hesaplanamiyorsa (hic olcum yok) kimse alinmaz.
        return pencere_kodu == EN_YENI
    return numara >= sinir


def sirala(adaylar: list) -> list:
    """En yeni katilan en uste. Numarasi okunamayanlar en alta."""
    return sorted(adaylar, key=lambda a: a.get("uye_no") or 0, reverse=True)
