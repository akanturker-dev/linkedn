import queue
import random
import threading
from datetime import date, datetime, timedelta

from . import db, tazelik, temizlik
from .config import load_settings
from .degerlendirme import sirket_hakkinda_coz, sirket_slugu, son_paylasim_gunu
from .kampanyalar import GENEL_ILK_MESAJ
from .linkedin_arama import SAYFA_BASINA_SONUC, adaylari_cikar, kampanya_sorgulari
from .linkedin_bot import AramaSiniriDoldu, GuvenlikKontroluGerekli, LinkedInBot
from .metin import sade_metin
from .puanlama import puan_hesapla
from .rank_checker import site_bul, sira_kontrol_et

# Profil ziyaretleri de LinkedIn'de iz birakir; kabul kontrolleri seyrek ve tek tek yapilir
DURUM_KONTROL_ARALIGI_SN = 600
DURUM_KONTROL_GUNLUK = 80
DURUM_KONTROL_TEKRAR_SAAT = 6
OTURUM_TEKRAR_KONTROL_SN = 300
GIRIS_BEKLEME_SN = 600
EN_FAZLA_ARAMA_SAYFASI = 10
# Bu kadar aday sirada bekliyorsa yeni LinkedIn aramasi yapilmaz; arama hakki bosa harcanmaz
ADAY_TAMPONU = 30

_komutlar = queue.Queue()
_bot = None
_guvenlik_kontrolu_bekliyor = False
_giris_baslangici = None
_oturum_tekrar_kontrol = None
_arama_durdurma_gunu = None
_esik_carpanlari = {}
_durum_kilidi = threading.Lock()
_durum = {
    "bot_giris_yapildi": None,
    "guvenlik_kontrolu": False,
    "giris_bekleniyor": False,
    "arama_siniri": False,
    "son_tur_zamani": None,
}


def komut_gonder(komut: str) -> None:
    _komutlar.put(komut)


def anlik_durum() -> dict:
    with _durum_kilidi:
        return dict(_durum)


def _durum_yaz(**alanlar) -> None:
    with _durum_kilidi:
        _durum.update(alanlar)


def _bot_al(headless: bool) -> LinkedInBot:
    global _bot
    if _bot is None:
        _bot = LinkedInBot(headless=headless).baslat()
        db.log(f"LinkedIn için {_bot.tarayici} açıldı (asistana ait ayrı profil).")
    return _bot


def _bot_sifirla() -> None:
    """Kullanici pencereyi kapatirsa tarayici olur; bir sonraki turda yeniden acilsin."""
    global _bot
    if _bot is not None:
        try:
            _bot.durdur()
        except Exception:
            pass
    _bot = None


def _calisma_saatinde_mi(ayarlar: dict) -> bool:
    saat = datetime.now().hour
    return ayarlar["calisma_saatleri"]["baslangic"] <= saat < ayarlar["calisma_saatleri"]["bitis"]


def _hedef_aralik_sn(ayarlar: dict, gunluk_limit: int, saatlik_limit: int = 0) -> float:
    """Gunluk limiti calisma saatlerine esit yayar; saatlik limit bundan hizli gitmeyi de engeller."""
    saatler = ayarlar["calisma_saatleri"]
    pencere_sn = max(1, saatler["bitis"] - saatler["baslangic"]) * 3600
    aralik = pencere_sn / max(1, gunluk_limit)
    if saatlik_limit > 0:
        aralik = max(aralik, 3600 / saatlik_limit)
    return aralik


def _gonderime_hazir_mi(tip: str, aralik_sn: float, gunluk_limit: int) -> bool:
    if gunluk_limit <= 0 or db.son_gun_sayisi(tip) >= gunluk_limit:
        return False
    son = db.son_gonderim_zamani(tip)
    if son is None:
        return True
    # Sapma her gonderimden sonra bir kez secilir; her turda yeniden secilseydi ortalama aralik hedefin altina kayardi
    kayit = _esik_carpanlari.get(tip)
    if kayit is None or kayit[0] != son:
        kayit = (son, random.uniform(0.7, 1.3))
        _esik_carpanlari[tip] = kayit
    gecen_sn = (datetime.now() - datetime.fromisoformat(son)).total_seconds()
    return gecen_sn >= aralik_sn * kayit[1]


def _sehir(konum: str) -> str:
    ilk = (konum or "").split(",")[0].strip()
    return "" if sade_metin(ilk) in ("turkiye", "turkey", "") else ilk


# ---------------- Arama ----------------

def _arama_kampanyasi(ayarlar: dict):
    """Aktif ve hedefine ulasmamis kampanyalardan en az aday bulunmus olani (6 grup esit ilerlesin)."""
    esik = ayarlar["puanlama"]["esik"]
    leadler = db.leads_getir()
    secenekler = []
    for kampanya in db.kampanyalari_getir():
        if kampanya["durum"] != "aktif":
            continue
        if db.kampanya_uygun_sayisi(kampanya["id"], esik) >= kampanya["hedef"]:
            db.kampanya_guncelle(kampanya["id"], {"durum": "tamamlandi"})
            db.log(f"Kampanya hedefe ulaştı: {kampanya['ad']} ({kampanya['hedef']} uygun aday).")
            continue
        bulunan = sum(1 for l in leadler if l.get("kampanya_id") == kampanya["id"])
        # Taze uye taramasi acikken oncelik onundur: tazelik zamanla bozulur, beklerse degerini yitirir
        oncelik = 0 if kampanya.get("tazelik") else 1
        secenekler.append((oncelik, bulunan, kampanya["id"], kampanya))
    return min(secenekler)[3] if secenekler else None


def _arama_yap(bot: LinkedInBot, ayarlar: dict) -> None:
    global _arama_durdurma_gunu
    kampanya = _arama_kampanyasi(ayarlar)
    if not kampanya:
        return
    sorgular = kampanya_sorgulari(kampanya["sektor_kelimeleri"], kampanya["roller"], kampanya["sehir"],
                                  kampanya.get("ilceler"))
    sorgu_no, sayfa_no = divmod(kampanya["sayfa"], EN_FAZLA_ARAMA_SAYFASI)
    if sorgu_no >= len(sorgular):
        db.kampanya_guncelle(kampanya["id"], {"durum": "tamamlandi"})
        db.log(f"{kampanya['ad']}: LinkedIn'de bakılacak sonuç kalmadı, kampanya tamamlandı.", "uyari")
        return
    try:
        kartlar = bot.kisi_ara(sorgular[sorgu_no], sayfa_no + 1)
    except AramaSiniriDoldu:
        _arama_durdurma_gunu = date.today()
        _durum_yaz(arama_siniri=True)
        db.log("LinkedIn aylık arama sınırına ulaşıldı: bugün yeni arama yok, sıradaki adaylara gönderim sürüyor.", "uyari")
        return
    db.gonderim_kaydet(0, "arama")
    adaylar = adaylari_cikar(kartlar, kampanya["roller"], kampanya["sehir"])  # sehir listesi; ilce sorguda kullanildi
    # Kartlardan okunan LinkedIn uye numaralari: en buyugu "bugunun tavani" olarak kaydedilir,
    # tazelik tarihi bu olcumlerden hesaplanir (bkz. app/tazelik.py).
    numaralar = [a["uye_no"] for a in adaylar if a.get("uye_no")]
    if numaralar:
        tazelik.olcum_ekle(max(numaralar))
    for aday in adaylar:
        aday["tazelik_gun"] = tazelik.tahmini_gun(aday.get("uye_no"))
    pencere = kampanya.get("tazelik")
    if pencere:
        # Taze uye aramasi: pencereye girmeyenler atilir, en yeni katilan en uste alinir
        toplam = len(adaylar)
        adaylar = tazelik.sirala([a for a in adaylar if tazelik.taze_mi(a.get("uye_no"), pencere)])
        db.log(f"Taze üye taraması ({tazelik.PENCERE_ADI.get(pencere, pencere)}): "
               f"{toplam} karar vericiden {len(adaylar)} tanesi bu tazelik penceresine girdi.")
    mevcut_sirketler = {sade_metin(l["isletme_adi"]) for l in db.leads_getir() if l.get("isletme_adi")}
    secilenler = []
    sirali = adaylar if kampanya.get("tazelik") else sorted(adaylar, key=lambda a: a["oncelik"])
    for aday in sirali:
        sirket = sade_metin(aday["isletme_adi"])
        # Ayni sirketten tek kisiye, listede en oncelikli role sahip olana yazilir
        if sirket and sirket in mevcut_sirketler:
            continue
        if sirket:
            mevcut_sirketler.add(sirket)
        aday.update({
            "kampanya_id": kampanya["id"],
            "sektor": kampanya["sektor_kelimeleri"][0],
            "sehir": _sehir(aday["konum"]) or (kampanya["sehir"][0] if kampanya["sehir"] else ""),
        })
        secilenler.append(aday)
    eklenen = db.linkedin_adaylari_ekle(secilenler)
    bitti = len(kartlar) < SAYFA_BASINA_SONUC
    db.kampanya_guncelle(kampanya["id"], {"sayfa": (sorgu_no + 1) * EN_FAZLA_ARAMA_SAYFASI if bitti else kampanya["sayfa"] + 1})
    ozet = f"{kampanya['ad']}: LinkedIn arama {sorgu_no + 1}. grup, {sayfa_no + 1}. sayfa — {len(kartlar)} kişi okundu"
    if kartlar:
        db.log(f"{ozet}, {len(adaylar)} karar verici, {eklenen} yeni aday değerlendirmeye alındı.")
    else:
        db.log(f"{ozet}. Sonuç yok ya da sayfa okunamadı; ekran görüntüsü data\\hata_ekranlari klasöründe.", "uyari")


# ---------------- Değerlendirme ve puan ----------------

def _site_tamamla(ayarlar: dict, lead: dict, alanlar: dict) -> None:
    """LinkedIn sirket sayfasinda site yoksa, Serper anahtari varsa Google'dan bulunur."""
    anahtar = ayarlar.get("serper_api_key")
    if alanlar.get("website") or lead.get("website") or not anahtar or not lead.get("isletme_adi"):
        return
    try:
        alanlar["website"] = site_bul(lead["isletme_adi"], _sehir(lead.get("konum")) or "Türkiye", anahtar)
    except Exception as e:
        db.log(f"{lead['isletme_adi']}: web sitesi Google'dan bulunamadı ({e})", "uyari", lead["id"])


def _google_sirasi(ayarlar: dict, lead: dict, alanlar: dict, kampanya) -> None:
    anahtar = ayarlar.get("serper_api_key")
    website = alanlar.get("website") or lead.get("website")
    if not (anahtar and website and kampanya):
        return
    terim = f"{kampanya['sektor_kelimeleri'][0]} {_sehir(lead.get('konum')) or 'Türkiye'}"
    try:
        sira, sayfa = sira_kontrol_et(website, terim, anahtar)
    except Exception as e:
        db.log(f"{lead['isletme_adi']}: Google sırası kontrol edilemedi ({e})", "uyari", lead["id"])
        return
    alanlar.update({"google_arama_terimi": terim, "google_sirasi": sira, "google_sayfasi": sayfa})


def _degerlendirme_bitir(lead: dict, alanlar: dict, ozet: str) -> None:
    db.lead_guncelle(lead["id"], alanlar)
    db.gonderim_kaydet(lead["id"], "degerlendirme")
    db.log(f"{lead['linkedin_ad']} ({lead['isletme_adi'] or 'şirket okunamadı'}): {ozet}", lead_id=lead["id"])


def _degerlendir(bot: LinkedInBot, ayarlar: dict, lead: dict) -> None:
    """Sirket buyuklugu, web sitesi ve son 30 gun paylasimi toplanir, puan hesaplanir;
    esigi gecen 'DM'e hazir', gecemeyen 'elendi' olur."""
    puanlama, kontroller = ayarlar["puanlama"], ayarlar["kontroller"]
    kampanya = db.kampanya_getir(lead["kampanya_id"]) if lead.get("kampanya_id") else None
    alanlar, notlar = {}, []
    if kontroller.get("sirket", True):
        slug = sirket_slugu(bot.profil_sirket_linki(lead["linkedin_url"]) or "")
        if slug:
            bilgi = db.sirket_getir(slug)
            if not bilgi:
                bilgi = sirket_hakkinda_coz(bot.sirket_hakkinda_satirlari(slug))
                db.sirket_kaydet(slug, bilgi["boyut"], bilgi["website"], bilgi["sektor"])
            alanlar.update({
                "sirket_linkedin": f"https://www.linkedin.com/company/{slug}",
                "sirket_boyutu": bilgi["boyut"],
                "sirket_sektoru": bilgi["sektor"],
                "website": lead.get("website") or bilgi["website"],
            })
            if not bilgi["boyut"]:
                notlar.append("şirket büyüklüğü okunamadı")
        else:
            notlar.append("profilde şirket sayfası bulunamadı")

    bant = alanlar.get("sirket_boyutu")
    if kampanya and bant and bant not in kampanya["sirket_boyutlari"]:
        alanlar.update({"durum": "elendi", "puan": 0, "puan_detay": f"{bant} çalışan: kampanyanın büyüklük filtresi dışında"})
        _degerlendirme_bitir(lead, alanlar, f"{bant} çalışan, kampanyanın büyüklük filtresi dışında → elendi")
        return

    _site_tamamla(ayarlar, lead, alanlar)
    puan, _ = puan_hesapla({**lead, **alanlar}, puanlama)
    # Paylasimlara yalnizca sonucu degistirebilecekse bakilir; bosuna sayfa acmak LinkedIn'de iz birakir
    if kontroller.get("aktivite", True) and puan < puanlama["esik"] <= puan + puanlama["aktif_30_gun"]:
        gun = son_paylasim_gunu(bot.paylasim_metni(lead["linkedin_url"]))
        alanlar["son_paylasim_gun"] = gun
        if gun is None:
            notlar.append("paylaşımlar okunamadı")
    _google_sirasi(ayarlar, lead, alanlar, kampanya)

    puan, gerekceler = puan_hesapla({**lead, **alanlar}, puanlama)
    uygun = puan >= puanlama["esik"]
    alanlar.update({
        "puan": puan,
        "puan_detay": "; ".join(gerekceler + notlar),
        "durum": "hazir" if uygun else "elendi",
    })
    _degerlendirme_bitir(lead, alanlar, f"{puan} puan (eşik {puanlama['esik']}) → {'DM’e hazır' if uygun else 'elendi'}")
    if uygun and kampanya and db.kampanya_uygun_sayisi(kampanya["id"], puanlama["esik"]) >= kampanya["hedef"]:
        db.kampanya_guncelle(kampanya["id"], {"durum": "tamamlandi"})
        db.log(f"Kampanya hedefe ulaştı: {kampanya['ad']} ({kampanya['hedef']} uygun aday).")


def _siradaki_hazir_aday(ayarlar: dict):
    """Once kampanyalar arasi denge (her grup esit test edilsin), sonra sirket buyuklugu dagilimi
    (varsayilan 11-50 %40, 51-200 %40, 201-500 %20): hedef payin en gerisinde kalan dilim secilir."""
    # Esik sonradan yukseltildiyse eski puanla bekleyene yazilmaz; duraklatilan kampanyanin adaylari bekler
    hazirlar = db.gonderilecek_hazirlar(ayarlar["puanlama"]["esik"])
    if not hazirlar:
        return None
    bant_sayilari, kampanya_sayilari = db.istek_dagilimi()
    dagilim = ayarlar["boyut_dagilimi"]
    toplam_pay = sum(dagilim.values()) or 1
    toplam_istek = sum(bant_sayilari.values())

    def bant_acigi(bant):
        pay = dagilim.get(bant, 0) / toplam_pay
        if pay == 0:
            return -1.0
        return pay - (bant_sayilari.get(bant, 0) / toplam_istek if toplam_istek else 0)

    return max(hazirlar, key=lambda l: (-kampanya_sayilari.get(l.get("kampanya_id"), 0), bant_acigi(l.get("sirket_boyutu")), -l["id"]))


# ---------------- Gönderimler ----------------

def _ilk_ad(lead: dict) -> str:
    parcalar = (lead.get("linkedin_ad") or "").split()
    # "Dr. Ayşe Kaya" gibi unvanla baslayan adlarda hitap icin unvandan sonraki kelime alinir
    if len(parcalar) > 1 and parcalar[0].endswith(".") and len(parcalar[0]) <= 4:
        parcalar = parcalar[1:]
    return parcalar[0] if parcalar else ""


def _mesaj_doldur(sablon: str, lead: dict) -> str:
    return sablon.format(
        ad=_ilk_ad(lead),
        isletme_adi=lead.get("isletme_adi") or "şirketiniz",
        arama_terimi=lead.get("google_arama_terimi") or "",
        sira=lead.get("google_sirasi") or "",
        sayfa=lead.get("google_sayfasi") or "",
    )


def _ilk_mesaj_sablonu(lead: dict) -> str:
    kampanya = db.kampanya_getir(lead["kampanya_id"]) if lead.get("kampanya_id") else None
    return (kampanya or {}).get("ilk_mesaj") or GENEL_ILK_MESAJ


def _guvenlik_kontrolu_uyar(detay: str) -> None:
    global _guvenlik_kontrolu_bekliyor
    _guvenlik_kontrolu_bekliyor = True
    _durum_yaz(guvenlik_kontrolu=True)
    db.log(
        "LinkedIn güvenlik doğrulaması istedi, otomasyon durduruldu. Açılan tarayıcı "
        f"penceresinden elle kontrolü geç, sonra panelden 'Devam et' butonuna bas. Detay: {detay}",
        "hata",
    )


def guvenlik_kontrolunu_temizle() -> None:
    global _guvenlik_kontrolu_bekliyor
    _guvenlik_kontrolu_bekliyor = False
    _durum_yaz(guvenlik_kontrolu=False)


def _durum_kontrol_et(bot: LinkedInBot, lead: dict) -> None:
    try:
        durum = bot.baglanti_durumu_kontrol_et(lead["linkedin_url"])
    except GuvenlikKontroluGerekli:
        raise
    except Exception as e:
        db.log(f"Bağlantı durumu kontrolü hatası ({lead['linkedin_ad']}): {e}", "hata", lead["id"])
        durum = None
    db.gonderim_kaydet(lead["id"], "durum_kontrol")
    if durum == "baglanti_kabul":
        db.lead_guncelle(lead["id"], {"durum": "baglanti_kabul"})
        db.log(f"{lead['linkedin_ad']} bağlantı isteğini kabul etti.", lead_id=lead["id"])
    else:
        db.lead_guncelle(lead["id"], {"durum": "istek_gonderildi"})


def _baglanti_gonder(bot: LinkedInBot, ayarlar: dict, lead: dict) -> None:
    if db.gonderim_var_mi(lead["id"], "baglanti_istegi"):
        db.lead_guncelle(lead["id"], {"durum": "istek_gonderildi"})
        return
    not_metni = _mesaj_doldur(ayarlar["mesaj_sablonlari"]["baglanti_notu"], lead)
    try:
        sonuc = bot.baglanti_istegi_gonder(lead["linkedin_url"], not_metni)
    except GuvenlikKontroluGerekli:
        raise
    except Exception as e:
        sonuc = f"hata: {e}"
    if sonuc == "gonderildi":
        db.gonderim_kaydet(lead["id"], "baglanti_istegi")
        db.lead_guncelle(lead["id"], {"durum": "istek_gonderildi"})
        db.log(f"{lead['linkedin_ad']} kişisine bağlantı isteği gönderildi.", lead_id=lead["id"])
    else:
        db.lead_guncelle(lead["id"], {"durum": "hata", "notlar": f"Bağlantı isteği gönderilemedi: {sonuc}"})
        db.log(f"{lead['linkedin_ad']}: bağlantı isteği gönderilemedi ({sonuc}).", "uyari", lead["id"])


def _mesaj_gonder(bot: LinkedInBot, lead: dict) -> None:
    if db.gonderim_var_mi(lead["id"], "mesaj"):
        db.lead_guncelle(lead["id"], {"durum": "mesaj_gonderildi"})
        return
    mesaj = _mesaj_doldur(_ilk_mesaj_sablonu(lead), lead)
    try:
        sonuc = bot.mesaj_gonder(lead["linkedin_url"], mesaj)
    except GuvenlikKontroluGerekli:
        raise
    except Exception as e:
        sonuc = f"hata: {e}"
    if sonuc == "gonderildi":
        db.gonderim_kaydet(lead["id"], "mesaj")
        db.lead_guncelle(lead["id"], {"durum": "mesaj_gonderildi"})
        db.log(f"{lead['linkedin_ad']} kişisine ilk mesaj gönderildi.", lead_id=lead["id"])
    else:
        db.lead_guncelle(lead["id"], {"durum": "hata", "notlar": f"Mesaj gönderilemedi: {sonuc}"})
        db.log(f"{lead['linkedin_ad']}: mesaj gönderilemedi ({sonuc}).", "uyari", lead["id"])


def _temizlik_yap(bot: LinkedInBot, lead: dict) -> None:
    """Kabul etmeyenin istegini geri ceker, cevap vermeyenin baglantisini kaldirir."""
    tip = lead.get("temizlik_tipi") or "baglanti_kaldir"
    try:
        sonuc = (bot.istegi_geri_cek(lead["linkedin_url"]) if tip == "istek_geri_cek"
                 else bot.baglantiyi_kaldir(lead["linkedin_url"]))
    except GuvenlikKontroluGerekli:
        raise
    except Exception as e:
        sonuc = f"hata: {e}"
    db.gonderim_kaydet(lead["id"], "temizlik")
    if sonuc in ("kaldirildi", "geri_cekildi", "zaten_bagli_degil"):
        db.lead_guncelle(lead["id"], {"temizlik": "yapildi"})
        db.log(f"{lead['linkedin_ad']}: {temizlik.TIP_ADLARI[tip].lower()} yapıldı, takipten çıkarıldı.",
               lead_id=lead["id"])
    elif sonuc == "kabul_edilmis":
        # Geri cekilecekti ama kisi bu arada kabul etmis: temizlik iptal, normal akisa doner
        db.lead_guncelle(lead["id"], {"durum": "baglanti_kabul", "temizlik": None, "temizlik_tipi": None})
        db.log(f"{lead['linkedin_ad']}: isteği bu arada kabul etmiş, temizlik iptal edildi.", lead_id=lead["id"])
    else:
        db.lead_guncelle(lead["id"], {"temizlik": "hata", "notlar": f"Temizlik yapılamadı: {sonuc}"})
        db.log(f"{lead['linkedin_ad']}: temizlik yapılamadı ({sonuc}); Temizlik sayfasından elle bakabilirsin.",
               "uyari", lead["id"])


def _linkedin_islemleri(ayarlar: dict) -> None:
    global _oturum_tekrar_kontrol
    _durum_yaz(arama_siniri=_arama_durdurma_gunu == date.today())
    if _guvenlik_kontrolu_bekliyor or _giris_baslangici or not _calisma_saatinde_mi(ayarlar):
        return
    if _oturum_tekrar_kontrol and datetime.now() < _oturum_tekrar_kontrol:
        return

    limitler = ayarlar["limitler"]
    bekleyen = None
    if _gonderime_hazir_mi("durum_kontrol", DURUM_KONTROL_ARALIGI_SN, DURUM_KONTROL_GUNLUK):
        bekleyen = db.kontrol_edilecek_bekleyen(DURUM_KONTROL_TEKRAR_SAAT)
    baglanti_adayi = None
    baglanti_araligi = _hedef_aralik_sn(ayarlar, limitler["baglanti_gunluk"], limitler["baglanti_saatlik"])
    haftalik_dolu = db.son_hafta_sayisi("baglanti_istegi") >= limitler.get("baglanti_haftalik", 100)
    if not haftalik_dolu and _gonderime_hazir_mi("baglanti_istegi", baglanti_araligi, limitler["baglanti_gunluk"]):
        baglanti_adayi = _siradaki_hazir_aday(ayarlar)
    mesaj_adayi = None
    if _gonderime_hazir_mi("mesaj", _hedef_aralik_sn(ayarlar, limitler["mesaj_gunluk"]), limitler["mesaj_gunluk"]):
        # Temizlige alinmis kisiye artik mesaj gitmez
        adaylar = [l for l in db.leads_getir(durum="baglanti_kabul") if not l.get("temizlik")]
        mesaj_adayi = adaylar[-1] if adaylar else None
    degerlendirilecek = None
    deg_limiti = limitler.get("degerlendirme_gunluk", 25)
    if _gonderime_hazir_mi("degerlendirme", _hedef_aralik_sn(ayarlar, deg_limiti), deg_limiti):
        degerlendirilecek = db.degerlendirilecek_aday()
    temizlik_limiti = limitler.get("temizlik_gunluk", 20)
    temizlenecek = None
    if _gonderime_hazir_mi("temizlik", _hedef_aralik_sn(ayarlar, temizlik_limiti), temizlik_limiti):
        temizlik.otomatik_sirala(ayarlar)
        temizlenecek = db.temizlenecek_aday()
    arama_limiti = limitler.get("linkedin_arama_gunluk", 20)
    arama_gerekli = (
        _arama_durdurma_gunu != date.today()
        and db.bekleyen_aday_sayisi() < ADAY_TAMPONU
        and any(k["durum"] == "aktif" for k in db.kampanyalari_getir())
        and _gonderime_hazir_mi("arama", _hedef_aralik_sn(ayarlar, arama_limiti), arama_limiti)
    )

    # Yapacak is yoksa LinkedIn hic acilmaz; bos yere sayfa yuklemek de iz birakir
    if not (bekleyen or baglanti_adayi or mesaj_adayi or degerlendirilecek or temizlenecek or arama_gerekli):
        return

    try:
        bot = _bot_al(ayarlar.get("headless_tarayici", False))
        giris_ok = bot.giris_yapildi_mi()
    except Exception as e:
        db.log(f"LinkedIn tarayıcısı açılamadı veya kapanmış, yeniden açılacak: {e}", "uyari")
        _bot_sifirla()
        return
    onceki = anlik_durum()["bot_giris_yapildi"]
    _durum_yaz(bot_giris_yapildi=giris_ok)
    if not giris_ok:
        if onceki is not False:
            db.log("LinkedIn oturumu açık değil. 'LinkedIn'e Giriş Yap' düğmesine bas.", "uyari")
        _oturum_tekrar_kontrol = datetime.now() + timedelta(seconds=OTURUM_TEKRAR_KONTROL_SN)
        return
    _oturum_tekrar_kontrol = None

    try:
        if bekleyen:
            _durum_kontrol_et(bot, bekleyen)
        if baglanti_adayi:
            _baglanti_gonder(bot, ayarlar, baglanti_adayi)
        if mesaj_adayi:
            _mesaj_gonder(bot, mesaj_adayi)
        if degerlendirilecek:
            try:
                _degerlendir(bot, ayarlar, degerlendirilecek)
            except GuvenlikKontroluGerekli:
                raise
            except Exception as e:
                db.gonderim_kaydet(degerlendirilecek["id"], "degerlendirme")
                db.lead_guncelle(degerlendirilecek["id"], {"durum": "hata", "notlar": f"Değerlendirilemedi: {e}"})
                db.log(f"{degerlendirilecek['linkedin_ad']}: değerlendirilemedi ({e}).", "uyari", degerlendirilecek["id"])
        if temizlenecek:
            _temizlik_yap(bot, temizlenecek)
        if arama_gerekli:
            _arama_yap(bot, ayarlar)
    except GuvenlikKontroluGerekli as e:
        _guvenlik_kontrolu_uyar(str(e))


# ---------------- Giriş takibi, komutlar, döngü ----------------

def _giris_takibi() -> None:
    """Kullanici acilan pencereden giris yaparken bot ayni sekmede sayfa degistirmemeli;
    giris bitene kadar LinkedIn islemleri bekletilir."""
    global _giris_baslangici, _oturum_tekrar_kontrol
    if _giris_baslangici is None:
        return
    pencere_kapandi = False
    try:
        girdi = _bot is not None and _bot.oturum_cerezi_var_mi()
    except Exception:
        girdi, pencere_kapandi = False, True
    zaman_asimi = (datetime.now() - _giris_baslangici).total_seconds() > GIRIS_BEKLEME_SN
    if girdi:
        db.log("LinkedIn girişi algılandı, oturum kaydedildi.")
        _durum_yaz(bot_giris_yapildi=True)
        _oturum_tekrar_kontrol = None
    elif pencere_kapandi:
        # Cerezler pencere kapanirken diske yazilir; oturum sonraki acilista dogrulanir
        _bot_sifirla()
        _oturum_tekrar_kontrol = None
        db.log("LinkedIn penceresi kapatıldı. Giriş yaptıysan oturum kaydedildi, bir sonraki işlemde kontrol edilecek.", "uyari")
    elif zaman_asimi:
        db.log("LinkedIn girişi 10 dakika içinde tamamlanmadı. Tekrar 'LinkedIn'e Giriş Yap' düğmesine basabilirsin.", "uyari")
    if girdi or pencere_kapandi or zaman_asimi:
        _giris_baslangici = None
        _durum_yaz(giris_bekleniyor=False)


def _komut_calistir(komut: str) -> None:
    global _giris_baslangici
    if komut == "giris_yap":
        if _bot is not None and _bot.headless:
            _bot_sifirla()
        try:
            _bot_al(headless=False).giris_sayfasini_ac()
        except Exception:
            _bot_sifirla()
            try:
                _bot_al(headless=False).giris_sayfasini_ac()
            except Exception as e:
                db.log(f"LinkedIn giriş sayfası açılamadı: {e}", "hata")
                return
        _giris_baslangici = datetime.now()
        _durum_yaz(giris_bekleniyor=True)
        db.log("LinkedIn giriş sayfası açıldı. Açılan pencereden elle giriş yap.")
    elif komut == "guvenlik_devam":
        guvenlik_kontrolunu_temizle()
        db.log("Güvenlik kontrolü temizlendi, otomasyon devam ediyor.")
    elif komut == "kapat":
        _bot_sifirla()
        _kapanis.set()
    # "uyan" komutu bilerek bos: sadece bekleyen donguyu hemen calistirir


_kapanis = threading.Event()


def kapat_ve_bekle(zaman_asimi: float) -> None:
    """Tarayiciyi motorun kendi is parcaciginda kapatir (Playwright nesneleri baska is
    parcacigindan kullanilamaz) ve en fazla zaman_asimi saniye bekler."""
    _komutlar.put("kapat")
    _kapanis.wait(zaman_asimi)


def _dongu() -> None:
    db.init_db()
    while not _kapanis.is_set():
        try:
            while True:
                try:
                    _komut_calistir(_komutlar.get_nowait())
                except queue.Empty:
                    break
            if _kapanis.is_set():
                return
            _giris_takibi()
            ayarlar = load_settings()
            if ayarlar.get("otomasyon_aktif"):
                _linkedin_islemleri(ayarlar)
            _durum_yaz(son_tur_zamani=datetime.now().isoformat(timespec="seconds"))
        except Exception as e:
            db.log(f"Motor döngüsünde beklenmeyen hata: {e}", "hata")
        # Bekleme sirasinda gelen komut (ör. giris butonu) aninda islenir
        try:
            _komut_calistir(_komutlar.get(timeout=random.uniform(20, 40)))
        except queue.Empty:
            pass


def baslat_arka_planda() -> threading.Thread:
    t = threading.Thread(target=_dongu, daemon=True)
    t.start()
    return t
