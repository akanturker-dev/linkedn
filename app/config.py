import json
import threading
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SETTINGS_PATH = DATA_DIR / "settings.json"
CHROME_PROFILE_DIR = BASE_DIR / "chrome_profile"
DB_PATH = DATA_DIR / "leads.db"

DEFAULT_SETTINGS = {
    "serper_api_key": "",
    "calisma_saatleri": {"baslangic": 9, "bitis": 19},
    "limitler": {
        "baglanti_saatlik": 8,
        "baglanti_gunluk": 15,
        "baglanti_haftalik": 100,
        "mesaj_gunluk": 20,
        "linkedin_arama_gunluk": 20,
        "degerlendirme_gunluk": 25,
        "temizlik_gunluk": 20,
    },
    # Haftalik temizlik kurallari: kac gun sonra kendiliginden siraya alinsin (0 = kapali, elle yaparsin)
    "temizlik": {"cevapsiz_gun": 14, "bekleyen_istek_gun": 21, "is_cikmayan": True},
    # Puan esigi gecmeyen adaya istek/DM gitmez. 201-500'e +2: metinde bu dilime %20 pay ayrilmis ama puan
    # verilmemisti; puansiz haliyle o dilimden kimse esige ulasamazdi
    "puanlama": {
        "rol_uyumlu": 3,
        "rol_diger": 1,
        "boyut_11_200": 3,
        "boyut_201_500": 2,
        "aktif_30_gun": 3,
        "web_sitesi": 1,
        "esik": 8,
    },
    "boyut_dagilimi": {"11-50": 40, "51-200": 40, "201-500": 20},
    "kontroller": {"sirket": True, "aktivite": True},
    # Not, kabul sonrasi gidecek ilk mesajla ayni cumleyle baslamaz: ayni cumlenin iki kez gelmesi bot gibi durur
    "mesaj_sablonlari": {
        "taze_mesaji": (
            "Merhaba {ad}, LinkedIn'de yeni denk geldim. {isletme_adi} tarafında dijital görünürlük "
            "(Google'da bulunabilirlik, site ve harita sonuçları) tarafına bakan biri var mı? Yeni başlayan "
            "işlerde ilk aylarda yapılan birkaç küçük ayar sonradan aylarca zaman kazandırıyor; isterseniz "
            "sizin için baktığım 2-3 noktayı burada kısaca yazayım."
        ),
        "maps_mesaji": (
            "Merhaba {ad}, {isletme_adi} tarafına bakarken Google'daki görünürlüğünüzle ilgili dikkatimi çeken "
            "birkaç nokta oldu. Özellikle harita sonuçları ve yorumlar tarafında geliştirilirse doğrudan gelen "
            "müşteri sayısına etki edebilecek 2-3 alan gördüm. İsterseniz size burada kısaca göndereyim, herhangi "
            "bir sunum hazırlamanıza gerek yok."
        ),
        "web_mesaji": (
            "Merhaba {ad}, {isletme_adi} tarafına bakarken web siteniz tarafında dikkatimi çeken birkaç nokta "
            "oldu. Özellikle siteye gelen ziyaretçiyi müşteriye çevirme tarafında geliştirilirse doğrudan yeni "
            "taleplere etki edebilecek 2-3 alan gördüm. İsterseniz size burada kısaca göndereyim, herhangi bir "
            "sunum hazırlamanıza gerek yok."
        ),
        "seo_mesaji": (
            "Merhaba {ad}, {isletme_adi} tarafına bakarken web sitenizin Google'daki görünürlüğüyle ilgili "
            "dikkatimi çeken birkaç nokta oldu. Özellikle sizi arayan müşterilerin karşısına çıkma tarafında "
            "geliştirilirse doğrudan yeni taleplere etki edebilecek 2-3 alan gördüm. İsterseniz size burada kısaca "
            "göndereyim, herhangi bir sunum hazırlamanıza gerek yok."
        ),
        "baglanti_notu": (
            "Merhaba {ad}, sektördeki işletmelerin dijital görünürlüğünü incelerken profilinize denk geldim. "
            "Bağlantıda olalım isterim."
        ),
    },
    "otomasyon_aktif": False,
    "headless_tarayici": False,
}

_lock = threading.Lock()


def _ensure_dirs():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict:
    _ensure_dirs()
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return json.loads(json.dumps(DEFAULT_SETTINGS))
    with _lock, open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Eksik anahtarlari varsayilanla tamamla (surum gecisinde ayar dosyasi eski kalabilir)
    merged = json.loads(json.dumps(DEFAULT_SETTINGS))
    for key, value in data.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key].update(value)
        else:
            merged[key] = value
    return merged


def save_settings(settings: dict) -> None:
    _ensure_dirs()
    with _lock, open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
