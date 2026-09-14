import sqlite3
import threading
from datetime import datetime, timedelta

from .config import DB_PATH, DATA_DIR

_write_lock = threading.Lock()
LISTE_ALANLARI = ("hizmetler", "sektor_kelimeleri", "sirket_boyutlari", "roller", "sehir", "ilceler")
SIRKET_ONBELLEK_GUN = 30
# Duraklatilan kampanyanin adaylari degerlendirilmez, istek almaz ve arama tamponunu doldurmaz
_ACIK_KAMPANYA = "(kampanya_id IS NULL OR kampanya_id NOT IN (SELECT id FROM kampanyalar WHERE durum = 'duraklatildi'))"
# Kendisine hic baglanti istegi ya da mesaj gitmemis aday
_TEMASSIZ = (
    "durum IN ('yeni', 'hazir', 'elendi', 'hata') AND id NOT IN "
    "(SELECT lead_id FROM gonderimler WHERE tip IN ('baglanti_istegi', 'mesaj'))"
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
    conn.execute("PRAGMA busy_timeout = 8000")
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_conn()
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS kampanyalar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ad TEXT NOT NULL,
                hizmetler TEXT,
                sektor_kelimeleri TEXT,
                sirket_boyutlari TEXT,
                roller TEXT,
                sehir TEXT NOT NULL DEFAULT '',
                ilceler TEXT,
                hedef INTEGER NOT NULL DEFAULT 100,
                ilk_mesaj TEXT NOT NULL DEFAULT '',
                durum TEXT NOT NULL DEFAULT 'aktif',
                sayfa INTEGER NOT NULL DEFAULT 0,
                kaynak TEXT,
                tazelik TEXT,
                taze_sektor TEXT,
                olusturma_tarihi TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kampanya_id INTEGER,
                isletme_adi TEXT NOT NULL DEFAULT '',
                sektor TEXT,
                sehir TEXT,
                website TEXT,
                google_arama_terimi TEXT,
                google_sirasi INTEGER,
                google_sayfasi INTEGER,
                linkedin_url TEXT,
                linkedin_ad TEXT,
                linkedin_unvan TEXT,
                linkedin_rol TEXT,
                konum TEXT,
                sirket_linkedin TEXT,
                sirket_boyutu TEXT,
                sirket_sektoru TEXT,
                son_paylasim_gun INTEGER,
                puan INTEGER,
                puan_detay TEXT,
                temizlik TEXT,
                temizlik_tipi TEXT,
                temizlik_tarihi TEXT,
                uye_no INTEGER,
                tazelik_gun INTEGER,
                durum TEXT NOT NULL DEFAULT 'yeni',
                notlar TEXT,
                olusturma_tarihi TEXT NOT NULL,
                son_islem_tarihi TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sirketler (
                slug TEXT PRIMARY KEY,
                boyut TEXT,
                website TEXT,
                sektor TEXT,
                guncelleme TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS gonderimler (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "lead_id INTEGER NOT NULL, tip TEXT NOT NULL, zaman TEXT NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS uye_no_tavani (gun TEXT PRIMARY KEY, numara INTEGER NOT NULL)"
        )
        conn.execute(
            "CREATE TABLE IF NOT EXISTS aktivite_log (id INTEGER PRIMARY KEY AUTOINCREMENT, zaman TEXT NOT NULL, "
            "seviye TEXT NOT NULL DEFAULT 'bilgi', mesaj TEXT NOT NULL, lead_id INTEGER)"
        )
        _kolonlari_tamamla(conn)
        # Onceki surumden kalan puansiz adaylar once degerlendirilir: puani olmayana istek gitmez
        conn.execute("UPDATE leads SET durum = 'yeni' WHERE durum = 'linkedin_bulundu'")
        conn.execute("UPDATE leads SET durum = 'yeni' WHERE durum = 'hazir' AND puan IS NULL")
        # Maps doneminden kalan (isletme_adi, sehir, website) tekilligi, ayni sirketten ikinci kisinin
        # site bilgisi guncellenirken cakisirdi; kisiyi LinkedIn adresi tekillestirir
        conn.execute("DROP INDEX IF EXISTS ux_leads_dedupe")
        try:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_leads_linkedin ON leads(linkedin_url) "
                "WHERE linkedin_url IS NOT NULL"
            )
        except sqlite3.IntegrityError:
            pass  # eski veride ayni adres iki kez varsa indeks kurulmaz; ekleme sirasindaki kontrol yeterli
    conn.close()


def _kolonlari_tamamla(conn: sqlite3.Connection) -> None:
    """Eski surumde olusmus veritabanina yeni kolonlari ekler; mevcut veriye dokunmaz."""
    yeni_kolonlar = (
        ("linkedin_rol", "TEXT"), ("linkedin_unvan", "TEXT"), ("konum", "TEXT"), ("kampanya_id", "INTEGER"),
        ("sirket_linkedin", "TEXT"), ("sirket_boyutu", "TEXT"), ("sirket_sektoru", "TEXT"),
        ("son_paylasim_gun", "INTEGER"), ("puan", "INTEGER"), ("puan_detay", "TEXT"),
        ("temizlik", "TEXT"), ("temizlik_tipi", "TEXT"), ("temizlik_tarihi", "TEXT"),
        ("uye_no", "INTEGER"), ("tazelik_gun", "INTEGER"),
    )
    mevcut = {satir["name"] for satir in conn.execute("PRAGMA table_info(leads)")}
    for kolon, tur in yeni_kolonlar:
        if kolon not in mevcut:
            conn.execute(f"ALTER TABLE leads ADD COLUMN {kolon} {tur}")
    # kaynak: kampanyanin hangi sektorden kuruldugu, ilceler: aramada kullanilan ilce listesi
    kampanya_kolonlari = {satir["name"] for satir in conn.execute("PRAGMA table_info(kampanyalar)")}
    for kolon in ("kaynak", "ilceler"):
        if kolon not in kampanya_kolonlari:
            conn.execute(f"ALTER TABLE kampanyalar ADD COLUMN {kolon} TEXT")


def _yaz(sql: str, parametreler=()) -> int:
    conn = get_conn()
    with _write_lock, conn:
        cur = conn.execute(sql, parametreler)
        son_id = cur.lastrowid
    conn.close()
    return son_id


def _oku(sql: str, parametreler=()) -> list:
    conn = get_conn()
    rows = conn.execute(sql, parametreler).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------------- Günlük ----------------

def log(mesaj: str, seviye: str = "bilgi", lead_id: int = None) -> None:
    _yaz("INSERT INTO aktivite_log (zaman, seviye, mesaj, lead_id) VALUES (?, ?, ?, ?)", (_now(), seviye, mesaj, lead_id))


def son_loglar(limit: int = 200):
    return _oku("SELECT * FROM aktivite_log ORDER BY id DESC LIMIT ?", (limit,))


# ---------------- Kampanyalar ----------------

def _kampanya_coz(satir: dict) -> dict:
    kampanya = dict(satir)
    for alan in LISTE_ALANLARI:
        kampanya[alan] = [p for p in (kampanya.get(alan) or "").split("|") if p]
    return kampanya


def _kampanya_satiri(veri: dict) -> dict:
    def deger(alan, icerik):
        if alan not in LISTE_ALANLARI:
            return icerik
        # Tek metin gelirse (eski kayitlar, elle cagri) tek elemanli liste sayilir
        if isinstance(icerik, str):
            icerik = [icerik] if icerik else []
        return "|".join(icerik)

    return {k: deger(k, v) for k, v in veri.items()}


def kampanya_ekle(veri: dict) -> int:
    satir = _kampanya_satiri({**veri, "olusturma_tarihi": _now()})
    kolonlar = ", ".join(satir)
    return _yaz(f"INSERT INTO kampanyalar ({kolonlar}) VALUES ({', '.join('?' * len(satir))})", tuple(satir.values()))


def kampanya_guncelle(kampanya_id: int, alanlar: dict) -> None:
    satir = _kampanya_satiri(alanlar)
    if satir:
        _yaz(f"UPDATE kampanyalar SET {', '.join(f'{k} = ?' for k in satir)} WHERE id = ?", (*satir.values(), kampanya_id))


def kampanyalari_getir() -> list:
    return [_kampanya_coz(r) for r in _oku("SELECT * FROM kampanyalar ORDER BY id")]


def kampanya_getir(kampanya_id: int):
    satirlar = _oku("SELECT * FROM kampanyalar WHERE id = ?", (kampanya_id,))
    return _kampanya_coz(satirlar[0]) if satirlar else None


def kampanya_sil(kampanya_id: int) -> None:
    _yaz("DELETE FROM kampanyalar WHERE id = ?", (kampanya_id,))


def kampanya_sayisi() -> int:
    return _oku("SELECT COUNT(*) AS n FROM kampanyalar")[0]["n"]


def kampanya_uygun_sayisi(kampanya_id: int, esik: int) -> int:
    return _oku(
        "SELECT COUNT(*) AS n FROM leads WHERE kampanya_id = ? AND puan >= ?", (kampanya_id, esik)
    )[0]["n"]


def kampanya_bekleyen_sayisi(kampanya_id: int) -> int:
    """Kampanyadaki, kendisine henuz yazilmamis aday sayisi (kampanya silinirse bunlar da silinir)."""
    return _oku(f"SELECT COUNT(*) AS n FROM leads WHERE kampanya_id = ? AND {_TEMASSIZ}", (kampanya_id,))[0]["n"]


def kampanya_bekleyenlerini_sil(kampanya_id: int) -> int:
    conn = get_conn()
    with _write_lock, conn:
        silinen = conn.execute(f"DELETE FROM leads WHERE kampanya_id = ? AND {_TEMASSIZ}", (kampanya_id,)).rowcount
    conn.close()
    return silinen


# ---------------- Şirket bilgisi hafızası ----------------

def sirket_getir(slug: str):
    sinir = (datetime.now() - timedelta(days=SIRKET_ONBELLEK_GUN)).isoformat(timespec="seconds")
    satirlar = _oku("SELECT * FROM sirketler WHERE slug = ? AND guncelleme > ?", (slug, sinir))
    return satirlar[0] if satirlar else None


def sirket_kaydet(slug: str, boyut, website, sektor) -> None:
    _yaz(
        "INSERT OR REPLACE INTO sirketler (slug, boyut, website, sektor, guncelleme) VALUES (?, ?, ?, ?, ?)",
        (slug, boyut, website, sektor, _now()),
    )


# ---------------- Adaylar ----------------

def linkedin_adaylari_ekle(adaylar: list) -> int:
    """LinkedIn aramasindan gelen kisileri ekler; ayni LinkedIn adresi varsa atlar. Eklenen sayiyi dondurur."""
    if not adaylar:
        return 0
    conn = get_conn()
    eklenen = 0
    with _write_lock, conn:
        mevcut = {r["linkedin_url"] for r in conn.execute("SELECT linkedin_url FROM leads WHERE linkedin_url IS NOT NULL")}
        for aday in adaylar:
            if aday["linkedin_url"] in mevcut:
                continue
            simdi = _now()
            conn.execute(
                """
                INSERT INTO leads (kampanya_id, isletme_adi, sektor, sehir, linkedin_url, linkedin_ad, linkedin_unvan,
                                   linkedin_rol, konum, durum, olusturma_tarihi, son_islem_tarihi,
                                   uye_no, tazelik_gun)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'yeni', ?, ?, ?, ?)
                """,
                (
                    aday.get("kampanya_id"), aday.get("isletme_adi") or "", aday.get("sektor"), aday.get("sehir"),
                    aday["linkedin_url"], aday.get("linkedin_ad"), aday.get("linkedin_unvan"),
                    aday.get("linkedin_rol"), aday.get("konum"), simdi, simdi,
                    aday.get("uye_no"), aday.get("tazelik_gun"),
                ),
            )
            mevcut.add(aday["linkedin_url"])
            eklenen += 1
    conn.close()
    return eklenen


def leads_getir(durum: str = None, kampanya_id: int = None):
    sql, parametreler = "SELECT * FROM leads WHERE 1=1", []
    if durum:
        sql += " AND durum = ?"
        parametreler.append(durum)
    if kampanya_id:
        sql += " AND kampanya_id = ?"
        parametreler.append(kampanya_id)
    return _oku(sql + " ORDER BY id DESC", parametreler)


def lead_getir(lead_id: int):
    satirlar = _oku("SELECT * FROM leads WHERE id = ?", (lead_id,))
    return satirlar[0] if satirlar else None


def lead_guncelle(lead_id: int, alanlar: dict) -> None:
    if not alanlar:
        return
    alanlar = {**alanlar, "son_islem_tarihi": _now()}
    _yaz(f"UPDATE leads SET {', '.join(f'{k} = ?' for k in alanlar)} WHERE id = ?", (*alanlar.values(), lead_id))


def lead_sil(lead_id: int) -> None:
    _yaz("DELETE FROM leads WHERE id = ?", (lead_id,))


def bekleyen_aday_sayisi() -> int:
    """Henuz baglanti istegi gonderilmemis (degerlendirme ya da istek bekleyen) aday sayisi."""
    return _oku(f"SELECT COUNT(*) AS n FROM leads WHERE durum IN ('yeni', 'hazir') AND {_ACIK_KAMPANYA}")[0]["n"]


def degerlendirilecek_aday():
    satirlar = _oku(f"SELECT * FROM leads WHERE durum = 'yeni' AND {_ACIK_KAMPANYA} ORDER BY id ASC LIMIT 1")
    return satirlar[0] if satirlar else None


def gonderilecek_hazirlar(esik: int) -> list:
    """Baglanti istegi sirasi: puani esigi gecen, kampanyasi duraklatilmamis 'DM'e hazir' adaylar."""
    return _oku(f"SELECT * FROM leads WHERE durum = 'hazir' AND puan >= ? AND {_ACIK_KAMPANYA} ORDER BY id DESC", (esik,))


def tavan_olcumu_kaydet(gun: str, numara: int) -> None:
    """O gun gorulen en buyuk LinkedIn uye numarasi. Tazelik tarihi bu olcumlerden hesaplanir."""
    conn = get_conn()
    with _write_lock, conn:
        conn.execute(
            "INSERT INTO uye_no_tavani (gun, numara) VALUES (?, ?) "
            "ON CONFLICT(gun) DO UPDATE SET numara = MAX(numara, excluded.numara)",
            (gun, numara),
        )
    conn.close()


def en_yeni_uye_no_bari(kota: int):
    """Simdiye kadar bulunmus en yeni 'kota' kisiden en dusugunun uye numarasi.
    Kota dolmadiysa None: o zaman herkes alinir ve cita zamanla kendiliginden yukselir."""
    satirlar = _oku(
        "SELECT uye_no FROM leads WHERE uye_no IS NOT NULL ORDER BY uye_no DESC LIMIT ?", (kota,)
    )
    return satirlar[-1]["uye_no"] if len(satirlar) >= kota else None


def tavan_olcumleri() -> list:
    return [(r["gun"], r["numara"]) for r in _oku("SELECT gun, numara FROM uye_no_tavani ORDER BY gun ASC")]


def gonderim_zamanlari(tip: str) -> dict:
    """Her aday icin o tipteki ilk gonderim zamani: istek ya da mesaj ne zaman gitti."""
    return {
        r["lead_id"]: r["zaman"]
        for r in _oku("SELECT lead_id, MIN(zaman) AS zaman FROM gonderimler WHERE tip = ? GROUP BY lead_id", (tip,))
    }


def temizlige_al(lead_idleri: list, tip: str) -> int:
    """Secilen adaylari temizlik sirasina koyar; bot gunluk sinira uyarak tek tek isler."""
    if not lead_idleri:
        return 0
    isaret = ", ".join("?" * len(lead_idleri))
    conn = get_conn()
    with _write_lock, conn:
        sayi = conn.execute(
            "UPDATE leads SET temizlik = 'sirada', temizlik_tipi = ?, temizlik_tarihi = ? "
            f"WHERE id IN ({isaret}) AND (temizlik IS NULL OR temizlik = 'hata')",
            (tip, _now(), *lead_idleri),
        ).rowcount
    conn.close()
    return sayi


def temizlikten_cikar(lead_idleri: list) -> int:
    """Siradan cikarir (henuz yapilmamis temizlik isini iptal eder)."""
    if not lead_idleri:
        return 0
    isaret = ", ".join("?" * len(lead_idleri))
    conn = get_conn()
    with _write_lock, conn:
        sayi = conn.execute(
            f"UPDATE leads SET temizlik = NULL, temizlik_tipi = NULL WHERE id IN ({isaret}) AND temizlik = 'sirada'",
            tuple(lead_idleri),
        ).rowcount
    conn.close()
    return sayi


def temizlenecek_aday():
    """Sirada bekleyen en eski temizlik isi."""
    satirlar = _oku(
        "SELECT * FROM leads WHERE temizlik = 'sirada' AND linkedin_url IS NOT NULL "
        "ORDER BY temizlik_tarihi ASC LIMIT 1"
    )
    return satirlar[0] if satirlar else None


def kontrol_edilecek_bekleyen(tekrar_saat: int):
    """Istegi bekleyen ve son kontrolunden en az tekrar_saat gecmis en eski adayi dondurur."""
    sinir = (datetime.now() - timedelta(hours=tekrar_saat)).isoformat(timespec="seconds")
    satirlar = _oku(
        "SELECT * FROM leads WHERE durum = 'istek_gonderildi' AND temizlik IS NULL "
        "AND (son_islem_tarihi IS NULL OR son_islem_tarihi < ?) "
        "ORDER BY son_islem_tarihi ASC LIMIT 1",
        (sinir,),
    )
    return satirlar[0] if satirlar else None


# ---------------- Gönderimler ve sayaçlar ----------------

def gonderim_kaydet(lead_id: int, tip: str) -> None:
    _yaz("INSERT INTO gonderimler (lead_id, tip, zaman) VALUES (?, ?, ?)", (lead_id, tip, _now()))


def _son_sayi(tip: str, sure: timedelta) -> int:
    sinir = (datetime.now() - sure).isoformat(timespec="seconds")
    return _oku("SELECT COUNT(*) AS n FROM gonderimler WHERE tip = ? AND zaman > ?", (tip, sinir))[0]["n"]


def son_saat_sayisi(tip: str) -> int:
    return _son_sayi(tip, timedelta(hours=1))


def son_gun_sayisi(tip: str) -> int:
    return _son_sayi(tip, timedelta(hours=24))


def son_hafta_sayisi(tip: str) -> int:
    return _son_sayi(tip, timedelta(days=7))


def son_gonderim_zamani(tip: str):
    satirlar = _oku("SELECT zaman FROM gonderimler WHERE tip = ? ORDER BY zaman DESC LIMIT 1", (tip,))
    return satirlar[0]["zaman"] if satirlar else None


def gonderim_var_mi(lead_id: int, tip: str) -> bool:
    return bool(_oku("SELECT 1 FROM gonderimler WHERE lead_id = ? AND tip = ? LIMIT 1", (lead_id, tip)))


def temas_edilen_idler(tip: str) -> set:
    return {r["lead_id"] for r in _oku("SELECT DISTINCT lead_id FROM gonderimler WHERE tip = ?", (tip,))}


def istek_dagilimi() -> tuple:
    """Gonderilen baglanti isteklerinin sirket buyuklugune ve kampanyaya gore sayilari (40/40/20 dengesi icin)."""
    satirlar = _oku(
        "SELECT l.sirket_boyutu AS bant, l.kampanya_id AS kampanya, COUNT(*) AS n FROM gonderimler g "
        "JOIN leads l ON l.id = g.lead_id WHERE g.tip = 'baglanti_istegi' GROUP BY l.sirket_boyutu, l.kampanya_id"
    )
    bantlar, kampanyalar = {}, {}
    for s in satirlar:
        bantlar[s["bant"]] = bantlar.get(s["bant"], 0) + s["n"]
        kampanyalar[s["kampanya"]] = kampanyalar.get(s["kampanya"], 0) + s["n"]
    return bantlar, kampanyalar


def istatistikler() -> dict:
    return {
        "toplam_aday": _oku("SELECT COUNT(*) AS n FROM leads")[0]["n"],
        "durum_dagilimi": {r["durum"]: r["n"] for r in _oku("SELECT durum, COUNT(*) AS n FROM leads GROUP BY durum")},
        "baglanti_son_saat": son_saat_sayisi("baglanti_istegi"),
        "baglanti_son_gun": son_gun_sayisi("baglanti_istegi"),
        "mesaj_son_gun": son_gun_sayisi("mesaj"),
        "baglanti_son_hafta": son_hafta_sayisi("baglanti_istegi"),
        "arama_son_gun": son_gun_sayisi("arama"),
        "degerlendirme_son_gun": son_gun_sayisi("degerlendirme"),
        "temizlik_son_gun": son_gun_sayisi("temizlik"),
        "temizlik_sirada": _oku("SELECT COUNT(*) AS n FROM leads WHERE temizlik = 'sirada'")[0]["n"],
    }
