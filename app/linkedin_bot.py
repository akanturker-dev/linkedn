import random
import re
import time

from playwright.sync_api import sync_playwright

from .config import CHROME_PROFILE_DIR, DATA_DIR
from .linkedin_arama import arama_adresi
from .metin import sade_metin

DEBUG_DIR = DATA_DIR / "hata_ekranlari"

# LinkedIn dogrulama/guvenlik kontrolune yonlendirince URL'de bu parcalar gorulur
CHECKPOINT_PARCALARI = ("checkpoint/challenge", "checkpoint/rescue", "/authwall")
# Ucretsiz hesaplarda aylik kisi arama sinirina ulasilinca cikan uyarinin parcalari (sadelestirilmis)
ARAMA_SINIRI_PARCALARI = ("ticari kullanim sinir", "commercial use limit", "monthly limit for profile search")

BAGLAN_REGEX = re.compile(r"Bağlantı kur|Baglanti kur|^Connect$", re.I)
DIGER_REGEX = re.compile(r"Diğer|Diger|^More$", re.I)
NOT_EKLE_REGEX = re.compile(r"Not ekle|Add a note", re.I)
NOTSUZ_GONDER_REGEX = re.compile(r"Notsuz gönder|Notsuz gonder|Send without a note|^Send$", re.I)
DAVET_GONDER_REGEX = re.compile(r"Davet gönder|Davet gonder|Send invitation", re.I)
MESAJ_BUTON_REGEX = re.compile(r"Mesaj gönder|Mesaj gonder|^Message$", re.I)
BEKLIYOR_REGEX = re.compile(r"Bekliyor|^Pending$", re.I)
BAGLANTIYI_KALDIR_REGEX = re.compile(r"Bağlantıyı kaldır|Baglantiyi kaldir|Remove connection", re.I)
GERI_CEK_REGEX = re.compile(r"Geri çek|Geri cek|^Withdraw$", re.I)
ONAY_REGEX = re.compile(r"^Kaldır$|^Kaldir$|^Remove$|^Geri çek$|^Geri cek$|^Withdraw$|^Evet$|^Yes$", re.I)

# LinkedIn'in "not ekle" alani icin karakter siniri (bolgeye gore 200-300 arasi degisebilir, guvenli tarafta kal)
NOT_KARAKTER_SINIRI = 200

# Her sonuc kartinin sadece asil sahibinin linkini alir. Kartlarin icindeki "ortak baglanti" linkleri de /in/
# adresidir; link bazli toplanirsa bir kisinin adiyla baskasina mesaj gidebilirdi.
# 13 Eylul 2026'da gercek LinkedIn'de olculdu: sonuclar artik <li> icinde DEGIL, sinif adlari da her derlemede
# degisen rastgele harflerden olusuyor. Bu yuzden kart, linkten yukari cikarak bulunur: ikinci bir kisinin
# profil linki goruldugu anda durulur, bir onceki kapsayici o kisinin kartidir. Kart icindeki ACoAA... kimligi
# de alinir; icinde LinkedIn uye numarasi vardir (bkz. app/tazelik.py).
_KARTLARI_TOPLA_JS = """
() => {
  const kartiBul = (a) => {
    const url = a.href.split('?')[0].replace(/\\/$/, '');
    let dugum = a, sonuc = null;
    for (let i = 0; i < 12 && dugum; i++) {
      const linkler = new Set([...dugum.querySelectorAll('a[href*="/in/"]')]
        .map(x => x.href.split('?')[0].replace(/\\/$/, '')));
      if (linkler.size > 1) break;          // baska bir kisi de girdi: bir onceki kapsayici dogru kart
      if ((dugum.innerText || '').trim().length > 40) sonuc = dugum;
      dugum = dugum.parentElement;
    }
    return sonuc;
  };
  const gorulen = new Set();
  const sonuc = [];
  for (const a of document.querySelectorAll('main a[href*="/in/"]')) {
    const url = a.href.split('?')[0].replace(/\\/$/, '');
    if (gorulen.has(url)) continue;
    const kart = kartiBul(a);
    if (!kart) continue;
    const satirlar = kart.innerText.split('\\n').map(s => s.trim()).filter(Boolean);
    if (satirlar.length < 2) continue;
    gorulen.add(url);
    const kimlik = (kart.outerHTML.match(/ACoAA[A-Za-z0-9_-]{15,40}/) || [])[0] || null;
    sonuc.push({url, satirlar, kimlik});
  }
  return sonuc;
}
"""


class GuvenlikKontroluGerekli(Exception):
    pass


class AramaSiniriDoldu(Exception):
    pass


class LinkedInBot:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.tarayici = ""
        self._pw = None
        self._context = None

    def baslat(self) -> "LinkedInBot":
        self._pw = sync_playwright().start()
        CHROME_PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        ortak = {"user_data_dir": str(CHROME_PROFILE_DIR), "headless": self.headless, "locale": "tr-TR"}
        if self.headless:
            ortak["viewport"] = {"width": 1280, "height": 900}
        else:
            ortak["no_viewport"] = True
        try:
            # Kurulu gercek Chrome, projeye ait ayri profil klasoruyle (Akan'in kendi Chrome profiline dokunmaz)
            self._context = self._pw.chromium.launch_persistent_context(channel="chrome", **ortak)
            self.tarayici = "Google Chrome"
        except Exception:
            self._context = self._pw.chromium.launch_persistent_context(**ortak)
            self.tarayici = "Chromium"
        return self

    def durdur(self) -> None:
        try:
            if self._context:
                self._context.close()
        finally:
            if self._pw:
                self._pw.stop()
            self._context = None
            self._pw = None

    def _sayfa(self):
        if not self._context:
            raise RuntimeError("Tarayıcı başlatılmadı, önce baslat() çağır.")
        return self._context.pages[0] if self._context.pages else self._context.new_page()

    def oturum_cerezi_var_mi(self) -> bool:
        """li_at LinkedIn'in oturum cerezidir. Tarayici kapandiysa bu cagri hata firlatir."""
        if not self._context:
            raise RuntimeError("Tarayıcı başlatılmadı.")
        return any(c["name"] == "li_at" for c in self._context.cookies("https://www.linkedin.com"))

    def _guvenlik_kontrolu_var_mi(self, sayfa) -> bool:
        return any(parca in sayfa.url for parca in CHECKPOINT_PARCALARI)

    def _hata_ekrani_kaydet(self, sayfa, isim: str) -> None:
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            sayfa.screenshot(path=str(DEBUG_DIR / f"{isim}.png"))
        except Exception:
            pass

    def _bekle(self, min_sn=1.2, max_sn=3.0) -> None:
        time.sleep(random.uniform(min_sn, max_sn))

    def _kontrol_et_ve_firlat(self, sayfa, baglam: str) -> None:
        if self._guvenlik_kontrolu_var_mi(sayfa):
            self._hata_ekrani_kaydet(sayfa, f"guvenlik_{baglam}_{int(time.time())}")
            raise GuvenlikKontroluGerekli(f"LinkedIn güvenlik kontrolü çıktı ({baglam}): {sayfa.url}")

    def giris_yapildi_mi(self) -> bool:
        sayfa = self._sayfa()
        sayfa.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=30000)
        self._bekle(1.5, 2.5)
        if self._guvenlik_kontrolu_var_mi(sayfa):
            return False
        return "/feed" in sayfa.url

    def giris_sayfasini_ac(self) -> None:
        sayfa = self._sayfa()
        sayfa.goto("https://www.linkedin.com/login", wait_until="domcontentloaded", timeout=30000)

    def kisi_ara(self, anahtar_kelime: str, sayfa_no: int = 1) -> list:
        """LinkedIn kisi aramasinin bir sonuc sayfasini acar; her kart icin {url, satirlar} dondurur."""
        sayfa = self._sayfa()
        sayfa.goto(arama_adresi(anahtar_kelime, sayfa_no), wait_until="domcontentloaded", timeout=30000)
        self._bekle(2.0, 4.0)
        self._kontrol_et_ve_firlat(sayfa, "arama")
        try:
            sayfa.wait_for_selector('main a[href*="/in/"]', timeout=12000)
        except Exception:
            pass  # sonuc yok ya da gec yuklendi; asagida sayfa metninden anlasilir
        metin = sade_metin(sayfa.inner_text("body")[:30000])
        if any(parca in metin for parca in ARAMA_SINIRI_PARCALARI):
            self._hata_ekrani_kaydet(sayfa, f"arama_siniri_{int(time.time())}")
            raise AramaSiniriDoldu("LinkedIn aylık arama sınırına ulaşıldı.")
        for _ in range(3):
            # Tembel yuklenen kartlar da gelsin diye sayfa yavasca kaydirilir
            sayfa.mouse.wheel(0, random.randint(500, 900))
            self._bekle(0.6, 1.4)
        kartlar = sayfa.evaluate(_KARTLARI_TOPLA_JS)
        if not kartlar:
            self._hata_ekrani_kaydet(sayfa, f"arama_sonucsuz_{int(time.time())}")
        return kartlar

    def _ac(self, adres: str, baglam: str):
        sayfa = self._sayfa()
        sayfa.goto(adres, wait_until="domcontentloaded", timeout=30000)
        self._bekle(2.0, 3.5)
        self._kontrol_et_ve_firlat(sayfa, baglam)
        return sayfa

    def _ana_metin(self, sayfa) -> str:
        try:
            return sayfa.inner_text("main", timeout=8000)
        except Exception:
            return ""

    def profil_sirket_linki(self, profil_url: str):
        """Profildeki guncel sirketin LinkedIn sayfa adresi (ust karttaki ilk sirket linki)."""
        sayfa = self._ac(profil_url, "profil_sirket")
        return sayfa.evaluate(
            """() => {
                for (const a of document.querySelectorAll('main a[href*="/company/"]')) {
                    if (/\\/company\\/[^/?#]+/.test(a.href)) return a.href.split('?')[0];
                }
                return null;
            }"""
        )

    def sirket_hakkinda_satirlari(self, slug: str) -> list:
        sayfa = self._ac(f"https://www.linkedin.com/company/{slug}/about/", "sirket")
        return self._ana_metin(sayfa).splitlines()

    def paylasim_metni(self, profil_url: str) -> str:
        sayfa = self._ac(profil_url.rstrip("/") + "/recent-activity/all/", "paylasimlar")
        sayfa.mouse.wheel(0, random.randint(400, 800))
        self._bekle(1.0, 2.0)
        return self._ana_metin(sayfa)[:12000]

    def baglanti_istegi_gonder(self, profil_url: str, not_metni: str = "") -> str:
        sayfa = self._sayfa()
        sayfa.goto(profil_url, wait_until="domcontentloaded", timeout=30000)
        self._bekle()
        self._kontrol_et_ve_firlat(sayfa, "profil")

        baglan = sayfa.get_by_role("button", name=BAGLAN_REGEX)
        if baglan.count() == 0:
            diger = sayfa.get_by_role("button", name=DIGER_REGEX)
            if diger.count() == 0:
                self._hata_ekrani_kaydet(sayfa, f"buton_bulunamadi_{int(time.time())}")
                return "buton_bulunamadi"
            diger.first.click()
            self._bekle(0.5, 1.3)
            baglan = sayfa.get_by_role("menuitem", name=BAGLAN_REGEX)
            if baglan.count() == 0:
                self._hata_ekrani_kaydet(sayfa, f"buton_bulunamadi_{int(time.time())}")
                return "buton_bulunamadi"

        baglan.first.click()
        self._bekle(1.0, 2.2)
        self._kontrol_et_ve_firlat(sayfa, "baglanti_modal")

        not_ekle = sayfa.get_by_role("button", name=NOT_EKLE_REGEX)
        if not_ekle.count() > 0 and not_metni:
            not_ekle.first.click()
            self._bekle(0.5, 1.2)
            kutu = sayfa.get_by_role("textbox")
            if kutu.count() > 0:
                kutu.first.fill(not_metni[:NOT_KARAKTER_SINIRI])
            gonder = sayfa.get_by_role("button", name=DAVET_GONDER_REGEX)
            if gonder.count() > 0:
                gonder.first.click()
                self._bekle()
                return "gonderildi"

        notsuz = sayfa.get_by_role("button", name=NOTSUZ_GONDER_REGEX)
        if notsuz.count() > 0:
            notsuz.first.click()
            self._bekle()
            return "gonderildi"

        self._hata_ekrani_kaydet(sayfa, f"gonderim_belirsiz_{int(time.time())}")
        return "belirsiz"

    def baglanti_durumu_kontrol_et(self, profil_url: str) -> str:
        sayfa = self._sayfa()
        sayfa.goto(profil_url, wait_until="domcontentloaded", timeout=30000)
        self._bekle()
        self._kontrol_et_ve_firlat(sayfa, "durum_kontrol")

        if sayfa.get_by_role("button", name=MESAJ_BUTON_REGEX).count() > 0:
            return "baglanti_kabul"
        if sayfa.get_by_role("button", name=BEKLIYOR_REGEX).count() > 0:
            return "istek_gonderildi"
        return "bilinmiyor"

    def mesaj_gonder(self, profil_url: str, mesaj: str) -> str:
        sayfa = self._sayfa()
        sayfa.goto(profil_url, wait_until="domcontentloaded", timeout=30000)
        self._bekle()
        self._kontrol_et_ve_firlat(sayfa, "mesaj_profil")

        buton = sayfa.get_by_role("button", name=MESAJ_BUTON_REGEX)
        if buton.count() == 0:
            self._hata_ekrani_kaydet(sayfa, f"mesaj_butonu_yok_{int(time.time())}")
            return "buton_bulunamadi"
        buton.first.click()
        self._bekle(1.2, 2.5)

        kutu = sayfa.get_by_role("textbox")
        if kutu.count() == 0:
            self._hata_ekrani_kaydet(sayfa, f"mesaj_kutusu_yok_{int(time.time())}")
            return "kutu_bulunamadi"
        kutu.last.click()
        kutu.last.fill(mesaj)
        self._bekle(0.6, 1.4)
        sayfa.keyboard.press("Enter")
        self._bekle()
        return "gonderildi"

    def baglantiyi_kaldir(self, profil_url: str) -> str:
        """Kabul edilmis bir baglantiyi kaldirir: profil > Diger > Baglantiyi kaldir > onay."""
        sayfa = self._sayfa()
        sayfa.goto(profil_url, wait_until="domcontentloaded", timeout=30000)
        self._bekle()
        self._kontrol_et_ve_firlat(sayfa, "temizlik_profil")

        diger = sayfa.get_by_role("button", name=DIGER_REGEX)
        if diger.count() == 0:
            self._hata_ekrani_kaydet(sayfa, f"temizlik_diger_yok_{int(time.time())}")
            return "buton_bulunamadi"
        diger.first.click()
        self._bekle(0.5, 1.3)
        kaldir = sayfa.get_by_role("menuitem", name=BAGLANTIYI_KALDIR_REGEX)
        if kaldir.count() == 0:
            # Secenek hic cikmiyorsa kisi zaten bagli degildir: is bitmis sayilir
            if sayfa.get_by_role("button", name=BAGLAN_REGEX).count() > 0:
                return "zaten_bagli_degil"
            self._hata_ekrani_kaydet(sayfa, f"temizlik_secenek_yok_{int(time.time())}")
            return "buton_bulunamadi"
        kaldir.first.click()
        self._bekle(0.8, 1.6)
        onay = sayfa.get_by_role("button", name=ONAY_REGEX)
        if onay.count() > 0:
            onay.last.click()
            self._bekle()
            return "kaldirildi"
        self._hata_ekrani_kaydet(sayfa, f"temizlik_onay_yok_{int(time.time())}")
        return "belirsiz"

    def istegi_geri_cek(self, profil_url: str) -> str:
        """Kabul edilmemis baglanti istegini geri ceker: profil > Bekliyor > Geri cek.
        LinkedIn geri cekilen kisiye 3 hafta yeni istek gonderilmesine izin vermez."""
        sayfa = self._sayfa()
        sayfa.goto(profil_url, wait_until="domcontentloaded", timeout=30000)
        self._bekle()
        self._kontrol_et_ve_firlat(sayfa, "geri_cek_profil")

        bekliyor = sayfa.get_by_role("button", name=BEKLIYOR_REGEX)
        if bekliyor.count() == 0:
            if sayfa.get_by_role("button", name=MESAJ_BUTON_REGEX).count() > 0:
                return "kabul_edilmis"
            self._hata_ekrani_kaydet(sayfa, f"geri_cek_buton_yok_{int(time.time())}")
            return "buton_bulunamadi"
        bekliyor.first.click()
        self._bekle(0.8, 1.6)
        geri_cek = sayfa.get_by_role("button", name=GERI_CEK_REGEX)
        if geri_cek.count() > 0:
            geri_cek.last.click()
            self._bekle()
            return "geri_cekildi"
        self._hata_ekrani_kaydet(sayfa, f"geri_cek_onay_yok_{int(time.time())}")
        return "belirsiz"
