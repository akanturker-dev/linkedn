"""Haftalik temizlik: yazdigimiz kisilerin takibi ve listeden cikarma isleri.

Iki tur is var:
  istek_geri_cek  — kabul edilmemis baglanti istegi geri cekilir. LinkedIn'in bakligi sinyal budur:
                    bekleyen ve kabul edilmeyen istek yigilmasi hesabi riske atar.
  baglanti_kaldir — kabul edip cevap vermeyen ya da "is cikmadi" denen kisinin baglantisi kaldirilir.
                    Hesap riskini azaltmaz ama listeyi ve agi temiz tutar.

Motor da bu dosyayi kullanir (servis'i kullanamaz: servis zaten motoru cagiriyor).
"""
from datetime import datetime

from . import db

TIP_ADLARI = {"istek_geri_cek": "İsteği geri çek", "baglanti_kaldir": "Bağlantıyı kaldır"}
# Bu durumdakiler asla temizlige alinmaz
DOKUNULMAZ = ("gorusme", "musteri")
CEVAP_DURUMLARI = ("cevap_verdi", "gorusme", "musteri")
# Ekrandaki toplu dugmeler
TURLER = {
    "cevapsiz": "Mesaja cevap vermeyenler",
    "kabul_yok": "İsteği kabul etmeyenler",
    "is_yok": "Cevap verdi ama iş çıkmadı",
}


def _gun_farki(zaman: str, simdi: datetime):
    if not zaman:
        return None
    try:
        return (simdi - datetime.fromisoformat(zaman)).days
    except ValueError:
        return None


def oneri(lead: dict, istek_gun, mesaj_gun, cevap: bool) -> dict:
    """Bu kisi icin ne yapmali: metin ve renk (iyi / uyari / hata / bos)."""
    temizlik = lead.get("temizlik")
    if temizlik == "sirada":
        return {"oneri": "sirada", "metin": f"Sırada: {TIP_ADLARI.get(lead.get('temizlik_tipi'), 'temizlenecek')}",
                "renk": "uyari"}
    if temizlik == "yapildi":
        return {"oneri": "yapildi", "metin": "Temizlendi, listeden çıkarıldı", "renk": ""}
    if temizlik == "hata":
        return {"oneri": "hata", "metin": "Temizlenemedi, elle bak", "renk": "hata"}
    if lead["durum"] in DOKUNULMAZ:
        return {"oneri": "dokunma", "metin": "Görüşme/müşteri — dokunma", "renk": "iyi"}
    if lead["durum"] == "ilgilenmiyor":
        return {"oneri": "is_yok", "metin": "İş çıkmadı — çıkarılabilir", "renk": "uyari"}
    if cevap:
        return {"oneri": "cevap", "metin": "Cevap verdi — sen ilgilen", "renk": "iyi"}
    if mesaj_gun is not None:
        if mesaj_gun >= 7:
            return {"oneri": "cevapsiz", "metin": f"{mesaj_gun} gündür cevap yok — çıkarılabilir", "renk": "hata"}
        if mesaj_gun >= 3:
            return {"oneri": "cevapsiz", "metin": f"{mesaj_gun} gündür cevap yok", "renk": "uyari"}
        return {"oneri": "bekle", "metin": f"Mesaj {mesaj_gun} gün önce gitti — bekle", "renk": ""}
    if lead["durum"] == "baglanti_kabul":
        return {"oneri": "mesaj_sirasi", "metin": "Kabul etti, mesaj sırasını bekliyor", "renk": ""}
    if istek_gun is not None and istek_gun >= 14:
        return {"oneri": "kabul_yok", "metin": f"{istek_gun} gündür kabul etmedi — istek geri çekilebilir",
                "renk": "hata"}
    return {"oneri": "kabul_bekleniyor", "metin": f"İstek {istek_gun} gün önce gitti, kabul bekleniyor", "renk": ""}


def tablo(leadler: list = None) -> list:
    """Yazdigimiz herkesin takip satiri: istek/mesaj kac gun once gitti, cevap geldi mi, ne yapmali."""
    leadler = db.leads_getir() if leadler is None else leadler
    istekler = db.gonderim_zamanlari("baglanti_istegi")
    mesajlar = db.gonderim_zamanlari("mesaj")
    simdi = datetime.now()
    satirlar = []
    for lead in leadler:
        if lead["id"] not in istekler:
            continue  # kendisine hic yazilmamis kisi bu listede yok
        mesaj_gun = _gun_farki(mesajlar.get(lead["id"]), simdi)
        cevap = lead["durum"] in CEVAP_DURUMLARI or (lead["durum"] == "ilgilenmiyor" and lead["id"] in mesajlar)
        satir = {
            "lead": lead,
            "istek_gun": _gun_farki(istekler.get(lead["id"]), simdi),
            "mesaj_gun": mesaj_gun,
            "cevap": cevap,
        }
        satir.update(oneri(lead, satir["istek_gun"], mesaj_gun, cevap))
        satirlar.append(satir)
    return satirlar


def sayilar(satirlar: list) -> dict:
    """Sayfanin ustundeki ozet sayilari."""
    ozet = {"toplam": len(satirlar), "cevap": 0, "bekleyen_mesaj": 0, "cevapsiz": 0, "kabul_yok": 0,
            "is_yok": 0, "sirada": 0, "yapildi": 0}
    for satir in satirlar:
        kod = satir["oneri"]
        if kod in ("cevap", "dokunma"):
            ozet["cevap"] += 1
        elif kod in ("bekle", "mesaj_sirasi"):
            ozet["bekleyen_mesaj"] += 1
        elif kod == "cevapsiz":
            ozet["cevapsiz"] += 1
        elif kod in ("kabul_yok", "kabul_bekleniyor"):
            ozet["kabul_yok"] += 1
        elif kod == "is_yok":
            ozet["is_yok"] += 1
        elif kod == "sirada":
            ozet["sirada"] += 1
        elif kod == "yapildi":
            ozet["yapildi"] += 1
    return ozet


def _tip_sec(lead: dict) -> str:
    """Kabul etmemisse istek geri cekilir, bagliysa baglanti kaldirilir."""
    return "istek_geri_cek" if lead["durum"] == "istek_gonderildi" else "baglanti_kaldir"


def hedefler(tur: str, gun: int = 0, satirlar: list = None) -> list:
    """Toplu dugmenin dokunacagi kisiler: [(lead id, temizlik tipi), ...]."""
    secilenler = []
    for satir in satirlar if satirlar is not None else tablo():
        lead = satir["lead"]
        if lead.get("temizlik") == "sirada" or lead.get("temizlik") == "yapildi" or lead["durum"] in DOKUNULMAZ:
            continue
        if tur == "cevapsiz" and satir["oneri"] == "cevapsiz" and (satir["mesaj_gun"] or 0) >= gun:
            secilenler.append((lead["id"], "baglanti_kaldir"))
        elif tur == "kabul_yok" and satir["oneri"] in ("kabul_yok", "kabul_bekleniyor") \
                and (satir["istek_gun"] or 0) >= gun:
            secilenler.append((lead["id"], "istek_geri_cek"))
        elif tur == "is_yok" and satir["oneri"] == "is_yok":
            secilenler.append((lead["id"], "baglanti_kaldir"))
    return secilenler


def siraya_al(lead_idleri: list, tip: str = None) -> int:
    """Elle secilenleri siraya alir; tip verilmezse kisinin durumuna gore secilir."""
    gruplar = {}
    for lead_id in lead_idleri:
        lead = db.lead_getir(lead_id)
        if not lead or lead["durum"] in DOKUNULMAZ or lead.get("temizlik") == "sirada":
            continue
        gruplar.setdefault(tip or _tip_sec(lead), []).append(lead_id)
    sayi = sum(db.temizlige_al(idler, secilen_tip) for secilen_tip, idler in gruplar.items())
    if sayi:
        db.log(f"{sayi} kişi temizlik sırasına alındı; bot günlük sınıra uyarak tek tek çıkaracak.")
    return sayi


def siradan_cikar(lead_idleri: list) -> int:
    sayi = db.temizlikten_cikar(lead_idleri)
    if sayi:
        db.log(f"{sayi} kişi temizlik sırasından çıkarıldı, listede kalmaya devam ediyor.")
    return sayi


def toplu_siraya_al(tur: str, gun: int = 0, sessiz: bool = False) -> int:
    """Ekrandaki toplu dugme ve otomatik kural bunu kullanir."""
    gruplar = {}
    for lead_id, tip in hedefler(tur, gun):
        gruplar.setdefault(tip, []).append(lead_id)
    sayi = sum(db.temizlige_al(idler, tip) for tip, idler in gruplar.items())
    if sayi and not sessiz:
        db.log(f"{TURLER.get(tur, tur)}: {sayi} kişi temizlik sırasına alındı (en az {gun} gün).")
    return sayi


def otomatik_sirala(ayarlar: dict) -> int:
    """Ayarlardaki kurallara gore kendiliginden siraya alir (0 = o kural kapali)."""
    kural = ayarlar.get("temizlik") or {}
    sayi = 0
    if kural.get("cevapsiz_gun"):
        sayi += toplu_siraya_al("cevapsiz", kural["cevapsiz_gun"], sessiz=True)
    if kural.get("bekleyen_istek_gun"):
        sayi += toplu_siraya_al("kabul_yok", kural["bekleyen_istek_gun"], sessiz=True)
    if kural.get("is_cikmayan"):
        sayi += toplu_siraya_al("is_yok", 0, sessiz=True)
    if sayi:
        db.log(f"Otomatik temizlik kuralı: {sayi} kişi sıraya alındı (Ayarlar'dan kapatabilirsin).")
    return sayi
