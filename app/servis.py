import re
import socket

from . import db, engine
from . import tazelik
from .config import DEFAULT_SETTINGS, load_settings, save_settings
from . import sektorler
from .kampanyalar import BOYUT_BANTLARI, TUM_ROLLER
from .linkedin_arama import kampanya_sorgulari
from .linkedin_bot import NOT_KARAKTER_SINIRI
from .profil_temizlik import profili_temizle
from .puanlama import puan_hesapla, ulasilabilir_en_yuksek

TEK_ORNEK_PORTU = 47831
ORNEK_ADAY = {
    "ad": "Ayşe",
    "isletme_adi": "Örnek Şirket",
    "arama_terimi": "otel İstanbul",
    "sira": 12,
    "sayfa": 2,
}
SABLON_DEGISKENLERI = "{ad}, {isletme_adi}, {arama_terimi}, {sira}, {sayfa}"
SABLON_ADLARI = {
    "maps_mesaji": "Google Maps sektörlerine giden ilk mesaj",
    "seo_mesaji": "SEO sektörlerine giden ilk mesaj",
    "web_mesaji": "Web sitesi sektörlerine giden ilk mesaj",
    "taze_mesaji": "LinkedIn'e yeni katılanlara giden ilk mesaj",
    "baglanti_notu": "Bağlantı isteği notu",
}
# Hangi hizmet havuzunun mesaji hangi ayar anahtarinda
SABLON_ANAHTARLARI = {
    sektorler.MAPS: "maps_mesaji",
    sektorler.SEO: "seo_mesaji",
    sektorler.WEB: "web_mesaji",
}
MANUEL_DURUMLAR = ("cevap_verdi", "gorusme", "musteri", "ilgilenmiyor")
KABUL_SONRASI = ("baglanti_kabul", "mesaj_gonderildi", "cevap_verdi", "gorusme", "musteri")
CEVAP_DURUMLARI = ("cevap_verdi", "gorusme", "musteri")
YENIDEN_DEGERLENDIRILEBILIR = ("yeni", "hazir", "elendi", "hata")
SORGU_ALANLARI = ("sektor_kelimeleri", "roller", "sehir", "ilceler")
# Degerlendirmede puan gerekcesine eklenen notlar (engine._degerlendir)
NOT_BOYUT_YOK = "şirket büyüklüğü okunamadı"
NOT_SIRKET_YOK = "profilde şirket sayfası bulunamadı"
NOT_PAYLASIM_YOK = "paylaşımlar okunamadı"
# Onceki surumlerin varsayilan baglanti notlari: kullanici degistirmediyse yeni stratejideki notla degistirilir
ESKI_BAGLANTI_NOTLARI = (
    "Merhaba {ad}, {isletme_adi} için web sitenizi ve Google görünürlüğünüzü inceledim, küçük bir önerim var. "
    "Bağlantı kurabilir miyiz?",
    "Merhaba {ad}, {isletme_adi} tarafına bakarken dijital görünürlükle ilgili dikkatimi çeken birkaç nokta oldu. "
    "Bağlantıda olalım isterim.",
)
# '|' kayit ayraci; tirnak ve parantez LinkedIn'in mantiksal aramasini bozar
_ARAMA_BOZAN = re.compile(r'["|()]')

_kilit_soketi = None


class AyarHatasi(ValueError):
    pass


class ZatenAcik(RuntimeError):
    pass


def baslat() -> None:
    """Veritabanini hazirlar, gerekirse Chrome profilini temizler, ilk acilista baslangic kampanyalarini
    yukler ve motoru baslatir. Iki asistan ayni anda calismasin diye yerel bir port kilit gibi tutulur."""
    global _kilit_soketi
    soket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
        soket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
    try:
        soket.bind(("127.0.0.1", TEK_ORNEK_PORTU))
    except OSError:
        soket.close()
        raise ZatenAcik("Asistan zaten açık (masaüstü uygulaması ya da web paneli). Önce onu kapat.")
    _kilit_soketi = soket

    db.init_db()
    _eski_ayarlari_guncelle()
    silinen = profili_temizle()
    if silinen:
        db.log(f"Chrome profili 1 GB'ı geçtiği için temizlendi ({silinen // (1024 * 1024)} MB silindi, oturum korundu).")
    baslangic_kampanyalarini_yukle()
    engine.baslat_arka_planda()


def _eski_ayarlari_guncelle() -> None:
    """Onceki surumden kalan ayarlari yeni duzene tasir: ilk mesajlar artik kampanyalarda oldugu icin eski ilk
    mesaj sablonlari silinir; hic degistirilmemis eski varsayilan baglanti notu yenisiyle degistirilir."""
    ayarlar = load_settings()
    sablonlar = ayarlar["mesaj_sablonlari"]
    eskiler = [anahtar for anahtar in sablonlar if anahtar not in SABLON_ADLARI]
    for anahtar in eskiler:
        del sablonlar[anahtar]
    not_degisti = sablonlar.get("baglanti_notu") in ESKI_BAGLANTI_NOTLARI
    if not_degisti:
        sablonlar["baglanti_notu"] = DEFAULT_SETTINGS["mesaj_sablonlari"]["baglanti_notu"]
    if eskiler or not_degisti:
        save_settings(ayarlar)
    if not_degisti:
        db.log("Bağlantı isteği notu yeni stratejiye göre güncellendi (Ayarlar sayfasından değiştirebilirsin).")


def baslangic_kampanyalarini_yukle() -> None:
    """Ilk acilista 6 test sektoru kurulur; sonraki acilislarda eski kampanyalar sektor koduyla eslestirilir."""
    ayarlar = load_settings()
    if db.kampanya_sayisi() == 0:
        for kod in sektorler.BASLANGIC_KODLARI:
            veri = sektorler.kampanya_verisi(kod, sektor_mesaji(kod, ayarlar))
            db.kampanya_ekle({**veri, "durum": "aktif"})
        db.log(f"{len(sektorler.BASLANGIC_KODLARI)} başlangıç sektörü yüklendi (her birinde hedef: 100 uygun aday).")
        return
    _kampanya_kaynaklarini_esle()


def sektor_mesaji(kod: str, ayarlar: dict) -> str:
    """Sektorun sattigi hizmete gore ilk mesaj (Maps / SEO / Web sitesi)."""
    havuz = sektorler.sektor(kod)["hizmet"]
    return ayarlar["mesaj_sablonlari"][SABLON_ANAHTARLARI[havuz]]


def _kampanya_kaynaklarini_esle() -> None:
    """Onceki surumde adiyla kurulmus kampanyalari sektor koduna baglar."""
    adlar = {s['ad']: s['kod'] for s in sektorler.SEKTORLER}
    for kampanya in db.kampanyalari_getir():
        if kampanya.get("kaynak"):
            continue
        kod = sektorler.ESKI_KAMPANYA_ADLARI.get(kampanya["ad"]) or adlar.get(kampanya["ad"])
        if kod:
            db.kampanya_guncelle(kampanya["id"], {"kaynak": kod})


def kapat(zaman_asimi: float = 8.0) -> None:
    engine.kapat_ve_bekle(zaman_asimi)


# ---------------- Ayarlar ----------------

def sablon_dogrula(ad: str, sablon: str, karakter_siniri: int = None) -> None:
    try:
        dolu = sablon.format(**ORNEK_ADAY)
    except KeyError as e:
        raise AyarHatasi(f"'{ad}' içinde tanımsız değişken var: {{{e.args[0]}}}. Kullanılabilenler: {SABLON_DEGISKENLERI}")
    except (ValueError, IndexError):
        raise AyarHatasi(f"'{ad}' içinde hatalı süslü parantez var. Değişkenleri {{ad}} gibi yaz.")
    if karakter_siniri and len(dolu) > karakter_siniri:
        raise AyarHatasi(f"'{ad}' çok uzun ({len(dolu)} karakter). LinkedIn en fazla {karakter_siniri} karaktere izin veriyor.")


def ayarlari_dogrula(ayarlar: dict) -> None:
    saatler = ayarlar["calisma_saatleri"]
    if not (0 <= saatler["baslangic"] < saatler["bitis"] <= 24):
        raise AyarHatasi("Çalışma saatleri hatalı: başlangıç bitişten küçük olmalı (0-24 arası).")
    if any(not isinstance(d, int) or d < 1 for d in ayarlar["limitler"].values()):
        raise AyarHatasi("Limitlerin hepsi en az 1 olmalı.")
    puanlama = ayarlar["puanlama"]
    if any(not isinstance(d, int) or d < 0 for d in puanlama.values()) or puanlama["esik"] < 1:
        raise AyarHatasi("Puanlar 0 ya da daha büyük, eşik en az 1 olmalı.")
    dagilim = ayarlar["boyut_dagilimi"]
    if any(not isinstance(d, int) or d < 0 for d in dagilim.values()) or sum(dagilim.values()) == 0:
        raise AyarHatasi("Şirket büyüklüğü dağılımında en az bir dilimin payı 0'dan büyük olmalı.")
    temizlik_kurali = ayarlar.get("temizlik") or {}
    for anahtar in ("cevapsiz_gun", "bekleyen_istek_gun"):
        deger = temizlik_kurali.get(anahtar, 0)
        if not isinstance(deger, int) or deger < 0:
            raise AyarHatasi("Temizlik gün sayıları 0 ya da daha büyük olmalı (0 = kural kapalı).")
    for anahtar, sablon in ayarlar["mesaj_sablonlari"].items():
        sinir = NOT_KARAKTER_SINIRI if anahtar == "baglanti_notu" else None
        sablon_dogrula(SABLON_ADLARI.get(anahtar, anahtar), sablon, sinir)


def ayarlari_kaydet(degisiklikler: dict) -> dict:
    ayarlar = load_settings()
    onceki = {alan: dict(ayarlar[alan]) for alan in ("puanlama", "kontroller")}
    for anahtar, deger in degisiklikler.items():
        if deger is None:
            continue
        if isinstance(deger, dict) and isinstance(ayarlar.get(anahtar), dict):
            ayarlar[anahtar].update(deger)
        else:
            ayarlar[anahtar] = deger
    if isinstance(ayarlar.get("serper_api_key"), str):
        ayarlar["serper_api_key"] = ayarlar["serper_api_key"].strip()
    ayarlari_dogrula(ayarlar)
    save_settings(ayarlar)
    if any(onceki[alan] != ayarlar[alan] for alan in onceki):
        puanlari_yenile(ayarlar)
    return ayarlar


def puanlari_yenile(ayarlar: dict) -> dict:
    """Puan agirliklari, esik ya da kontroller degisince henuz yazilmamis adaylar kayitli bilgileriyle yeniden
    puanlanir; 'DM'e hazir' listesi her zaman guncel kurala uyar. Hic bakilmamis bir kontrol sonucu
    degistirebilecekse aday yeniden degerlendirmeye alinir."""
    puanlama, kontroller = ayarlar["puanlama"], ayarlar["kontroller"]
    esik = puanlama["esik"]
    kampanyalar = {k["id"]: k for k in db.kampanyalari_getir()}
    sayac = {"hazir": 0, "elendi": 0, "yeni": 0}
    for lead in db.leads_getir():
        if lead["durum"] not in ("hazir", "elendi"):
            continue
        kampanya = kampanyalar.get(lead.get("kampanya_id"))
        bant = lead.get("sirket_boyutu")
        if kampanya and bant and bant not in kampanya["sirket_boyutlari"]:
            continue  # buyukluk filtresi disinda: puandan bagimsiz elenmis
        detay = lead.get("puan_detay") or ""
        puan, gerekceler = puan_hesapla(lead, puanlama)
        olasi = puan
        # Buyuklugu hic okunmamis (sirket kontrolu kapaliyken degerlendirilmis) aday; bilinen buyukluk tekrar okunmaz
        if (kontroller.get("sirket", True) and not bant and not lead.get("sirket_linkedin")
                and NOT_SIRKET_YOK not in detay):
            olasi += max(puanlama["boyut_11_200"], puanlama["boyut_201_500"])
            olasi += max(0, puanlama["rol_uyumlu"] - puanlama["rol_diger"])
        if kontroller.get("aktivite", True) and lead.get("son_paylasim_gun") is None and NOT_PAYLASIM_YOK not in detay:
            olasi += puanlama["aktif_30_gun"]
        if puan < esik <= olasi:
            alanlar = {"durum": "yeni", "puan": None, "puan_detay": None}
        else:
            notlar = [n for n in (NOT_BOYUT_YOK, NOT_SIRKET_YOK, NOT_PAYLASIM_YOK) if n in detay]
            alanlar = {"durum": "hazir" if puan >= esik else "elendi", "puan": puan,
                       "puan_detay": "; ".join(gerekceler + notlar)}
        if alanlar["durum"] != lead["durum"] or alanlar["puan"] != lead.get("puan"):
            db.lead_guncelle(lead["id"], alanlar)
            if alanlar["durum"] != lead["durum"]:
                sayac[alanlar["durum"]] += 1
    if any(sayac.values()):
        db.log(f"Puan kuralları değişti: {sayac['hazir']} aday DM'e hazır oldu, {sayac['elendi']} aday elendi, "
               f"{sayac['yeni']} aday yeniden değerlendirilecek.")
    return sayac


def en_yuksek_puan(ayarlar: dict) -> int:
    return ulasilabilir_en_yuksek(ayarlar["puanlama"], ayarlar["kontroller"])


def otomasyonu_ayarla(aktif: bool) -> None:
    ayarlar = load_settings()
    ayarlar["otomasyon_aktif"] = aktif
    save_settings(ayarlar)
    db.log("Otomasyon başlatıldı." if aktif else "Otomasyon durduruldu.")
    engine.komut_gonder("uyan")


# ---------------- Kampanyalar ----------------

def _temiz(metin) -> str:
    return " ".join(_ARAMA_BOZAN.sub(" ", str(metin or "")).split())


def _liste_temiz(degerler) -> list:
    """Listedeki her kaydi temizler, bosu ve tekrari atar (sektor kelimeleri, sehirler, ilceler)."""
    temiz = []
    for deger in degerler or []:
        deger = _temiz(deger)
        if deger and deger not in temiz:
            temiz.append(deger)
    return temiz


def _aramasi_bitti_mi(kampanya: dict) -> bool:
    sorgular = kampanya_sorgulari(kampanya["sektor_kelimeleri"], kampanya["roller"], kampanya["sehir"],
                                  kampanya.get("ilceler"))
    return kampanya["sayfa"] // engine.EN_FAZLA_ARAMA_SAYFASI >= len(sorgular)


def kampanya_kaydet(veri: dict, kampanya_id: int = None) -> int:
    veri = {
        **veri,
        "ad": (veri.get("ad") or "").strip(),
        "sehir": _liste_temiz(veri.get("sehir")),
        "ilceler": _liste_temiz(veri.get("ilceler")),
        "sektor_kelimeleri": _liste_temiz(veri.get("sektor_kelimeleri")),
        "ilk_mesaj": (veri.get("ilk_mesaj") or "").strip(),
    }
    if not veri["ad"]:
        raise AyarHatasi("Kampanyaya bir ad ver.")
    if not veri["sektor_kelimeleri"]:
        raise AyarHatasi("En az bir sektör kelimesi gir (ör. otel, hotel).")
    if not veri.get("roller"):
        raise AyarHatasi("En az bir unvan seç.")
    bilinmeyen = [r for r in veri["roller"] if r not in TUM_ROLLER]
    if bilinmeyen:
        raise AyarHatasi(f"Bilinmeyen unvan: {', '.join(bilinmeyen)}. Listeden seç.")
    if not veri.get("sirket_boyutlari") or any(b not in BOYUT_BANTLARI for b in veri["sirket_boyutlari"]):
        raise AyarHatasi("En az bir şirket büyüklüğü seç.")
    if not isinstance(veri.get("hedef"), int) or veri["hedef"] < 1:
        raise AyarHatasi("Hedef aday sayısı en az 1 olmalı.")
    if not veri["ilk_mesaj"]:
        raise AyarHatasi("İlk mesajı boş bırakma.")
    sablon_dogrula("İlk mesaj", veri["ilk_mesaj"])

    if kampanya_id:
        mevcut = db.kampanya_getir(kampanya_id)
        if not mevcut:
            raise AyarHatasi("Kampanya bulunamadı; silinmiş olabilir.")
        # Kelimeler, unvanlar ya da sehir degistiyse LinkedIn aramasi bastan baslar (bulunanlar tekrar eklenmez)
        if any(mevcut[alan] != veri.get(alan, mevcut[alan]) for alan in SORGU_ALANLARI):
            veri["sayfa"] = 0
        # Tamamlanmis kampanya duzenlendiyse (ör. hedef artirildi) yeniden calisir; hedef hala doluysa motor yine kapatir
        if mevcut["durum"] == "tamamlandi":
            veri["durum"] = "aktif"
            if "sayfa" not in veri and _aramasi_bitti_mi(mevcut):
                veri["sayfa"] = 0
        db.kampanya_guncelle(kampanya_id, veri)
        db.log(f"Kampanya güncellendi: {veri['ad']}")
        engine.komut_gonder("uyan")
        return kampanya_id
    yeni_id = db.kampanya_ekle({**veri, "durum": "aktif"})
    db.log(f"Yeni kampanya eklendi: {veri['ad']}")
    engine.komut_gonder("uyan")
    return yeni_id


def secili_sektor_kodlari() -> list:
    """Su an calisan sektorlerin kodlari (Mesaj Gonder sayfasindaki secili liste)."""
    # Taze uye taramasi bir sektor degil, ayri bir tarama: sektor listesinde gorunmez
    return [k["kaynak"] for k in db.kampanyalari_getir()
            if k.get("kaynak") and k["kaynak"] != TAZE_KAYNAK and k["durum"] == "aktif"]


def secili_konumlar() -> tuple:
    """Mesaj Gonder sayfasindaki sehir ve ilce secimi: calisan sektor kampanyalarindan okunur."""
    for kampanya in db.kampanyalari_getir():
        if kampanya.get("kaynak") and kampanya["durum"] == "aktif":
            return list(kampanya["sehir"]), list(kampanya.get("ilceler") or [])
    return [], []


TAZE_KAYNAK = "taze_uyeler"


def taze_kampanya():
    """Taze uye taramasi kampanyasi (varsa)."""
    return next((k for k in db.kampanyalari_getir() if k.get("kaynak") == TAZE_KAYNAK), None)


def taze_tarama_baslat(sektor_kodu: str, pencere_kodu: str, mesaj: str, sehirler=None, ilceler=None,
                       hedef: int = 300) -> dict:
    """Secilen TEK sektorde, LinkedIn'e yeni katilmis karar vericileri arar. Kayit tarihi LinkedIn'de
    yayinlanmadigi icin tazelik, kartin icindeki LinkedIn uye numarasindan cikarilir (bkz. app/tazelik.py):
    numara siralamasi kesindir, tarih etiketi tahmindir."""
    s = sektorler.sektor(sektor_kodu)
    if not s:
        raise AyarHatasi("Önce taze üye aranacak sektörü seç.")
    if pencere_kodu not in tazelik.PENCERE_ADI:
        raise AyarHatasi("Geçersiz tazelik aralığı seçildi.")
    if not (mesaj or "").strip():
        raise AyarHatasi("Önce bu kişilere gidecek mesajı yaz.")
    veri = {
        **sektorler.kampanya_verisi(sektor_kodu, mesaj.strip(), hedef=hedef, sehirler=sehirler, ilceler=ilceler),
        "ad": f"Taze üyeler — {s['ad']} ({tazelik.PENCERE_ADI[pencere_kodu]})",
        "kaynak": TAZE_KAYNAK,
        "tazelik": pencere_kodu,
        "taze_sektor": sektor_kodu,
    }
    mevcut = taze_kampanya()
    if mevcut:
        # Sektor ya da tazelik araligi degistiyse tarama bastan baslar: eski sayfalar baska secime gore taranmisti
        ayni = mevcut.get("tazelik") == pencere_kodu and mevcut.get("taze_sektor") == sektor_kodu
        kampanya_kaydet({**veri, "sayfa": mevcut["sayfa"] if ayni else 0}, mevcut["id"])
        kampanya_durumu_ayarla(mevcut["id"], "aktif")
        yeni = False
    else:
        kampanya_kaydet(veri)
        yeni = True
    db.log(f"Taze üye taraması başladı: {s['ad']} — {tazelik.PENCERE_ADI[pencere_kodu]}.")
    return {"yeni": yeni, "pencere": pencere_kodu, "sektor": sektor_kodu}


def taze_tarama_durdur() -> bool:
    kampanya = taze_kampanya()
    if not kampanya or kampanya["durum"] != "aktif":
        return False
    kampanya_durumu_ayarla(kampanya["id"], "duraklatildi")
    db.log("Taze üye taraması durduruldu; bulunan adaylar listede kalır.")
    return True


def sektor_kampanyalari_kur(kodlar: list, mesajlar: dict, sehirler=None, ilceler=None) -> dict:
    """Secilen sektorleri kampanyaya cevirir: yenisini kurar, mevcudu gunceller ve calistirir, listeden
    cikarilani duraklatir. Hicbir aday ya da gecmis silinmez. mesajlar: {hizmet havuzu: ilk mesaj}."""
    if not kodlar:
        raise AyarHatasi("En az bir sektör seç: kime yazılacağını bilmeden gönderim başlayamaz.")
    ayarlar = ayarlari_kaydet(
        {"mesaj_sablonlari": {SABLON_ANAHTARLARI[havuz]: mesaj for havuz, mesaj in mesajlar.items()}}
    )
    mevcut = {k["kaynak"]: k for k in db.kampanyalari_getir() if k.get("kaynak")}
    sayac = {"yeni": 0, "guncel": 0, "duraklatilan": 0}
    for kod in kodlar:
        if not sektorler.sektor(kod):
            continue
        veri = sektorler.kampanya_verisi(kod, sektor_mesaji(kod, ayarlar), sehirler=sehirler, ilceler=ilceler)
        eski = mevcut.get(kod)
        if eski:
            kampanya_kaydet({**veri, "hedef": eski["hedef"] or veri["hedef"]}, eski["id"])
            if eski["durum"] != "aktif":
                kampanya_durumu_ayarla(eski["id"], "aktif")
            sayac["guncel"] += 1
        else:
            kampanya_kaydet(veri)
            sayac["yeni"] += 1
    for kod, kampanya in mevcut.items():
        if kod not in kodlar and kampanya["durum"] == "aktif":
            kampanya_durumu_ayarla(kampanya["id"], "duraklatildi")
            sayac["duraklatilan"] += 1
    return sayac


def kampanya_durumu_ayarla(kampanya_id: int, durum: str) -> None:
    kampanya = db.kampanya_getir(kampanya_id)
    if not kampanya:
        return
    alanlar = {"durum": durum}
    # Butun aramalari bitmis kampanya yeniden baslatilirsa LinkedIn'e bastan bakilir: sonuclar zamanla degisir
    if durum == "aktif" and kampanya["durum"] == "tamamlandi" and _aramasi_bitti_mi(kampanya):
        alanlar["sayfa"] = 0
    db.kampanya_guncelle(kampanya_id, alanlar)
    db.log(f"Kampanya {'başlatıldı' if durum == 'aktif' else 'duraklatıldı'}: {kampanya['ad']}")
    engine.komut_gonder("uyan")


def kampanya_sil(kampanya_id: int) -> int:
    """Kampanyayi ve ona ait, henuz yazilmamis adaylari siler; yazilmis adaylar ve surecleri kalir."""
    kampanya = db.kampanya_getir(kampanya_id)
    silinen = db.kampanya_bekleyenlerini_sil(kampanya_id)
    db.kampanya_sil(kampanya_id)
    if kampanya:
        db.log(f"Kampanya silindi: {kampanya['ad']} ({silinen} bekleyen aday kaldırıldı, yazılmış olanlar listede kalır).")
    return silinen


# ---------------- Adaylar ----------------

def lead_guncelle(lead_id: int, alanlar: dict) -> dict:
    mevcut = db.lead_getir(lead_id)
    if not mevcut:
        raise LookupError("Aday bulunamadı")
    alanlar = {k: v for k, v in alanlar.items() if v is not None}
    if "linkedin_url" in alanlar:
        alanlar["linkedin_url"] = alanlar["linkedin_url"].strip()
    yeni_url = alanlar.get("linkedin_url")
    # Elle baska bir kisi girildiyse (ve ona henuz yazilmadiysa) sirket, paylasim ve puan bastan olculur
    if (
        yeni_url
        and yeni_url != (mevcut["linkedin_url"] or "")
        and "linkedin.com/in/" in yeni_url
        and mevcut["durum"] in YENIDEN_DEGERLENDIRILEBILIR
    ):
        alanlar.update({"durum": "yeni", "sirket_linkedin": None, "sirket_boyutu": None, "son_paylasim_gun": None,
                        "puan": None, "puan_detay": None})
    db.lead_guncelle(lead_id, alanlar)
    return db.lead_getir(lead_id)


def durum_isaretle(lead_idleri: list, durum: str) -> None:
    for lead_id in lead_idleri:
        alanlar = {"durum": durum}
        if durum == "yeni":
            alanlar.update({"puan": None, "puan_detay": None})
        db.lead_guncelle(lead_id, alanlar)


# ---------------- Rapor ----------------

def _cevap_verdi_mi(lead: dict, mesaj_idleri: set) -> bool:
    # Mesajdan sonra "ilgilenmiyorum" diyen de cevap vermistir: sektorun ilgisini olcmek icin sayilir
    return lead["durum"] in CEVAP_DURUMLARI or (lead["durum"] == "ilgilenmiyor" and lead["id"] in mesaj_idleri)


def rapor(leadler: list = None, kampanyalar: list = None, esik: int = None) -> list:
    """Kampanya bazinda huni: bulunan -> uygun -> istek -> kabul -> mesaj -> cevap -> gorusme -> musteri."""
    esik = load_settings()["puanlama"]["esik"] if esik is None else esik
    leadler = db.leads_getir() if leadler is None else leadler
    kampanyalar = db.kampanyalari_getir() if kampanyalar is None else kampanyalar
    istek_idleri = db.temas_edilen_idler("baglanti_istegi")
    mesaj_idleri = db.temas_edilen_idler("mesaj")
    satirlar = []
    for kampanya in kampanyalar:
        ls = [l for l in leadler if l.get("kampanya_id") == kampanya["id"]]
        satirlar.append(
            {
                "kampanya": kampanya,
                "bulunan": len(ls),
                "uygun": sum(1 for l in ls if (l.get("puan") or 0) >= esik),
                "istek": sum(1 for l in ls if l["id"] in istek_idleri),
                "kabul": sum(1 for l in ls if l["durum"] in KABUL_SONRASI or l["id"] in mesaj_idleri),
                "mesaj": sum(1 for l in ls if l["id"] in mesaj_idleri),
                "cevap": sum(1 for l in ls if _cevap_verdi_mi(l, mesaj_idleri)),
                "gorusme": sum(1 for l in ls if l["durum"] in ("gorusme", "musteri")),
                "musteri": sum(1 for l in ls if l["durum"] == "musteri"),
            }
        )
    return satirlar


def bant_raporu(leadler: list = None, ayarlar: dict = None) -> list:
    """Gonderilen baglanti isteklerinin sirket buyuklugune gore dagilimi ve sonuclari; hedef paylarla karsilastirilir."""
    ayarlar = ayarlar or load_settings()
    leadler = db.leads_getir() if leadler is None else leadler
    istek_idleri = db.temas_edilen_idler("baglanti_istegi")
    mesaj_idleri = db.temas_edilen_idler("mesaj")
    dagilim = ayarlar["boyut_dagilimi"]
    toplam_pay = sum(dagilim.values()) or 1
    istekliler = [l for l in leadler if l["id"] in istek_idleri]
    bantlar = [b for b in BOYUT_BANTLARI if dagilim.get(b, 0) > 0 or any(l.get("sirket_boyutu") == b for l in istekliler)]
    if any(not l.get("sirket_boyutu") for l in istekliler):
        bantlar.append(None)
    satirlar = []
    for bant in bantlar:
        ls = [l for l in istekliler if (l.get("sirket_boyutu") or None) == bant]
        satirlar.append(
            {
                "bant": bant,
                "hedef": round(100 * dagilim.get(bant, 0) / toplam_pay) if bant else 0,
                "istek": len(ls),
                "pay": round(100 * len(ls) / len(istekliler)) if istekliler else 0,
                "kabul": sum(1 for l in ls if l["durum"] in KABUL_SONRASI or l["id"] in mesaj_idleri),
                "cevap": sum(1 for l in ls if _cevap_verdi_mi(l, mesaj_idleri)),
            }
        )
    return satirlar


def durum() -> dict:
    ayarlar = load_settings()
    return {
        **engine.anlik_durum(),
        "calisiyor": ayarlar.get("otomasyon_aktif", False),
        "en_yuksek_puan": en_yuksek_puan(ayarlar),
        **db.istatistikler(),
    }
