from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFrame, QGridLayout, QHBoxLayout, QLineEdit, QPlainTextEdit, QProgressBar, QVBoxLayout,
    QWidget,
)

from .. import db, servis
from ..etiketler import KAMPANYA_ETIKET
from ..config import load_settings
from ..kampanyalar import BOYUT_BANTLARI, GENEL_ILK_MESAJ, HIZMETLER, ROL_GRUPLARI, ROL_TURKCELERI, UYGUN_GRUPLAR
from ..sektorler import GRUP_KISA as SEKTOR_KISA, SEKTORLER, kampanya_verisi
from .bilesenler import (
    AcilirListe, KaydirmaAlani, Metrik, Sayfa, bilgi_ver, cip, dugme, duzeni_temizle, etiket, hap_ayarla,
    sayi_kutusu, soru_sor,
)

GRUP_ADLARI = {
    "kurucu": "Kurucu ve sahipler",
    "genel_mudur": "Genel müdürler",
    "pazarlama_lideri": "Pazarlama liderleri",
    "pazarlama": "Pazarlama ve marka müdürleri",
    "departman": "Departman yöneticileri",
}
KAMPANYA_HAP = {"aktif": "iyi", "duraklatildi": "uyari", "tamamlandi": ""}
DURUM_DUGMESI = {"aktif": "Duraklat", "duraklatildi": "Başlat", "tamamlandi": "Yeniden başlat"}
METRIKLER = [("bulunan", "Bulunan"), ("istek", "İstek"), ("kabul", "Kabul"), ("mesaj", "Mesaj"),
             ("cevap", "Cevap"), ("gorusme", "Görüşme"), ("musteri", "Müşteri")]
BOS_KAMPANYA = {"ad": "", "hizmetler": [], "sektor_kelimeleri": [], "sehir": [], "ilceler": [],
                "sirket_boyutlari": ["11-50", "51-200"],
                "roller": [], "hedef": 100, "ilk_mesaj": GENEL_ILK_MESAJ}


def bant_metni(bant: str) -> str:
    return bant.replace("-", "–")


def grup_araligi(grup: str) -> str:
    """Rol grubunun dogru muhatap sayildigi sirket buyuklugu, ör. '11–200 çalışan'."""
    bantlar = [b for b in BOYUT_BANTLARI if grup in UYGUN_GRUPLAR[b]]
    if not bantlar:
        return ""
    alt, son = bantlar[0].split("-")[0], bantlar[-1]
    return f"{alt}+ çalışan" if son.endswith("+") else f"{alt}–{son.split('-')[1]} çalışan"


class KampanyaKarti(QFrame):
    def __init__(self, sayfa: "KampanyalarSayfasi"):
        super().__init__()
        self.setObjectName("kart")
        self.kampanya, self.satir = None, None
        self._cip_imzasi = None
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(22, 18, 22, 18)
        duzen.setSpacing(8)

        ust = QHBoxLayout()
        self.ad = etiket("", "bolumBaslik", kaydir=True)
        self.hap = etiket("", "hap")
        ust.addWidget(self.ad, 1)
        ust.addWidget(self.hap, 0, Qt.AlignmentFlag.AlignTop)
        duzen.addLayout(ust)
        self.ciplar = QHBoxLayout()
        self.ciplar.setSpacing(6)
        duzen.addLayout(self.ciplar)
        self.sektor = etiket("", "ikincil", kaydir=True)
        self.boyut = etiket("", "ikincil", kaydir=True)
        self.roller = etiket("", "soluk", kaydir=True)
        for parca in (self.sektor, self.boyut, self.roller):
            duzen.addWidget(parca)

        duzen.addSpacing(4)
        ilerleme = QHBoxLayout()
        self.ilerleme = etiket("", "alanBaslik")
        self.ilerleme_orani = etiket("", "soluk")
        ilerleme.addWidget(self.ilerleme)
        ilerleme.addStretch(1)
        ilerleme.addWidget(self.ilerleme_orani)
        duzen.addLayout(ilerleme)
        self.cubuk = QProgressBar()
        self.cubuk.setTextVisible(False)
        duzen.addWidget(self.cubuk)

        duzen.addSpacing(4)
        metrikler = QHBoxLayout()
        metrikler.setSpacing(2)
        self.metrikler = {}
        for anahtar, baslik in METRIKLER:
            self.metrikler[anahtar] = Metrik(baslik)
            metrikler.addWidget(self.metrikler[anahtar], 1)
        duzen.addLayout(metrikler)

        duzen.addSpacing(4)
        dugmeler = QHBoxLayout()
        dugmeler.setSpacing(8)
        dugmeler.addWidget(dugme("Düzenle", lambda: sayfa.duzenle(self.kampanya)))
        self.durum_dugmesi = dugme("", lambda: sayfa.durum_degistir(self.kampanya, self.satir))
        dugmeler.addWidget(self.durum_dugmesi)
        dugmeler.addStretch(1)
        dugmeler.addWidget(dugme("Sil", lambda: sayfa.sil(self.kampanya), "silDugme"))
        duzen.addLayout(dugmeler)

    def guncelle(self, kampanya: dict, satir: dict) -> None:
        self.kampanya, self.satir = kampanya, satir
        self.ad.setText(kampanya["ad"])
        hap_ayarla(self.hap, KAMPANYA_ETIKET.get(kampanya["durum"], kampanya["durum"]), KAMPANYA_HAP.get(kampanya["durum"], ""))
        imza = (tuple(kampanya["hizmetler"]), tuple(kampanya["sehir"]), tuple(kampanya.get("ilceler") or []))
        if imza != self._cip_imzasi:
            self._cip_imzasi = imza
            duzeni_temizle(self.ciplar)
            for kod in kampanya["hizmetler"]:
                self.ciplar.addWidget(cip(HIZMETLER.get(kod, kod), kod))
            konum = ", ".join(kampanya["sehir"]) or "Bütün Türkiye"
            if kampanya.get("ilceler"):
                konum += " · " + ", ".join(kampanya["ilceler"])
            self.ciplar.addWidget(cip(konum))
            self.ciplar.addStretch(1)
        self.sektor.setText("Sektör kelimeleri: " + ", ".join(kampanya["sektor_kelimeleri"]))
        self.boyut.setText("Şirket büyüklüğü: " + ", ".join(bant_metni(b) for b in kampanya["sirket_boyutlari"]) + " çalışan")
        self.roller.setText("Unvanlar: " + ", ".join(kampanya["roller"]))
        self.roller.setToolTip("\n".join(f"{r} — {ROL_TURKCELERI[r][0]}" if r in ROL_TURKCELERI else r
                                         for r in kampanya["roller"]))
        hedef, uygun = kampanya["hedef"], satir["uygun"]
        self.ilerleme.setText(f"DM'e uygun aday: {uygun} / {hedef}")
        self.ilerleme_orani.setText(f"%{min(100, round(100 * uygun / hedef))}" if hedef else "")
        self.cubuk.setMaximum(max(1, hedef))
        self.cubuk.setValue(min(uygun, hedef))
        for anahtar, metrik in self.metrikler.items():
            metrik.ayarla(satir[anahtar])
        self.durum_dugmesi.setText(DURUM_DUGMESI.get(kampanya["durum"], "Başlat"))


class KampanyalarSayfasi(Sayfa):
    degisti = Signal()

    def __init__(self):
        super().__init__(
            "Kampanyalar",
            "Gelişmiş bölüm; girmesen de olur. Mesaj Gönder sayfasında seçtiğin her sektör burada bir kampanya "
            "olarak görünür: sektör → şirket büyüklüğü → karar verici unvanı. Buradan hedefi, unvanları, şehri ve "
            "mesajı tek tek değiştirebilirsin.",
            kaydirilabilir=True,
        )
        self.baslik_sag.addWidget(dugme("Yeni Kampanya", self.yeni, "aksan", buyuk=True), 0, Qt.AlignmentFlag.AlignTop)
        self.izgara = QGridLayout()
        self.izgara.setSpacing(18)
        self.izgara.setColumnStretch(0, 1)
        self.izgara.setColumnStretch(1, 1)
        self.icerik.addLayout(self.izgara)
        self.bos = etiket("Henüz kampanya yok. Sağ üstteki 'Yeni Kampanya' ile başla.", "ikincil")
        self.icerik.addWidget(self.bos)
        self.icerik.addStretch(1)
        self.kartlar = {}
        self._imza = None

    def yenile(self, veri: dict) -> None:
        satirlar = {s["kampanya"]["id"]: s for s in veri["rapor"]}
        imza = [k["id"] for k in veri["kampanyalar"]]
        if imza != self._imza:
            self._imza = imza
            for kart in self.kartlar.values():
                self.izgara.removeWidget(kart)
                kart.deleteLater()
            self.kartlar = {}
            for sira, kampanya_id in enumerate(imza):
                kart = KampanyaKarti(self)
                self.izgara.addWidget(kart, sira // 2, sira % 2)
                self.kartlar[kampanya_id] = kart
        for kampanya in veri["kampanyalar"]:
            self.kartlar[kampanya["id"]].guncelle(kampanya, satirlar[kampanya["id"]])
        self.bos.setVisible(not imza)

    def yeni(self) -> None:
        if KampanyaDuzenleyici(None, self).exec():
            self.degisti.emit()

    def duzenle(self, kampanya: dict) -> None:
        if KampanyaDuzenleyici(kampanya, self).exec():
            self.degisti.emit()

    def durum_degistir(self, kampanya: dict, satir: dict) -> None:
        if kampanya["durum"] == "aktif":
            servis.kampanya_durumu_ayarla(kampanya["id"], "duraklatildi")
        elif kampanya["durum"] == "tamamlandi" and satir["uygun"] >= kampanya["hedef"]:
            bilgi_ver(
                self, "Hedefe ulaşıldı",
                f"'{kampanya['ad']}' hedefine ulaştı ({kampanya['hedef']} uygun aday). Devam etmesini istiyorsan "
                "'Düzenle'den hedefi artır.",
            )
            return
        else:
            servis.kampanya_durumu_ayarla(kampanya["id"], "aktif")
        self.degisti.emit()

    def sil(self, kampanya: dict) -> None:
        bekleyen = db.kampanya_bekleyen_sayisi(kampanya["id"])
        soru = f"'{kampanya['ad']}' kampanyası silinsin mi?"
        if bekleyen:
            soru += (f"\n\nBu kampanyada henüz yazılmamış {bekleyen} aday da listeden kaldırılır. "
                     "Yazılmış olanlar listede kalır ve süreçleri devam eder.")
        soru += "\n\nSadece durdurmak istiyorsan 'Duraklat' daha iyi: sonuçlar Rapor'da kalır."
        if not soru_sor(self, "Kampanyayı sil", soru, "Sil"):
            return
        servis.kampanya_sil(kampanya["id"])
        self.degisti.emit()


class KampanyaDuzenleyici(QDialog):
    def __init__(self, kampanya: dict = None, ebeveyn=None):
        super().__init__(ebeveyn)
        self.kampanya = kampanya
        self._rol_sirasi = []
        self.setWindowTitle(f"Kampanyayı düzenle: {kampanya['ad']}" if kampanya else "Yeni kampanya")
        alan = self.screen().availableGeometry()
        self.resize(min(1240, int(alan.width() * 0.9)), min(940, int(alan.height() * 0.9)))

        dis = QVBoxLayout(self)
        dis.setContentsMargins(0, 0, 0, 0)
        dis.setSpacing(0)
        kaydirma = KaydirmaAlani()
        govde = QWidget()
        duzen = QVBoxLayout(govde)
        duzen.setContentsMargins(28, 22, 28, 18)
        duzen.setSpacing(12)
        kaydirma.setWidget(govde)
        dis.addWidget(kaydirma, 1)

        if not kampanya:
            satir = QHBoxLayout()
            satir.setSpacing(12)
            satir.addWidget(etiket("Hazır sektörden başla", "alanBaslik"))
            self.sablon_secici = AcilirListe()
            self.sablon_secici.addItem("Boş kampanya", "")
            for s in SEKTORLER:
                grup = SEKTOR_KISA[s['hizmet']]
                self.sablon_secici.addItem(f"{grup} · {s['ad']}", s['kod'])
            self.sablon_secici.currentIndexChanged.connect(self._sablon_secildi)
            satir.addWidget(self.sablon_secici, 1)
            duzen.addLayout(satir)
            duzen.addWidget(etiket("Listede LinkedIn'de satış yapabileceğin bütün sektörler var: seçince bütün "
                                   "alanlar dolar, istediğini değiştirirsin.", "soluk", kaydir=True))
            duzen.addSpacing(6)

        alanlar = QGridLayout()
        alanlar.setHorizontalSpacing(32)
        alanlar.setVerticalSpacing(14)
        alanlar.setColumnStretch(0, 1)
        alanlar.setColumnStretch(1, 1)

        self.ad_kutusu = QLineEdit()
        self.ad_kutusu.setPlaceholderText("ör. Oteller")
        alanlar.addLayout(self._alan("Kampanya adı", self.ad_kutusu), 0, 0)

        hizmet_satiri = QHBoxLayout()
        hizmet_satiri.setSpacing(18)
        self.hizmet_kutulari = {}
        for kod, ad in HIZMETLER.items():
            self.hizmet_kutulari[kod] = QCheckBox(ad)
            hizmet_satiri.addWidget(self.hizmet_kutulari[kod])
        hizmet_satiri.addStretch(1)
        alanlar.addLayout(self._alan("Satacağın hizmet", hizmet_satiri,
                                     "Raporda hangi hizmetin hangi sektörde sattığını görmek için."), 0, 1)

        self.sektor_kutusu = QLineEdit()
        self.sektor_kutusu.setPlaceholderText("ör. otel, hotel, resort, konaklama")
        alanlar.addLayout(self._alan("Sektör kelimeleri", self.sektor_kutusu,
                                     "Virgülle ayır; Türkçe ve İngilizce birlikte yaz. LinkedIn'de kişinin unvanında ve "
                                     "şirket adında aranır."), 1, 0)

        self.sehir_kutusu = QLineEdit()
        self.sehir_kutusu.setPlaceholderText("Boş bırakırsan bütün Türkiye (virgülle birden fazla şehir)")
        self.ilce_kutusu = QLineEdit()
        self.ilce_kutusu.setPlaceholderText("İlçe (isteğe bağlı, virgülle)")
        konum_kutulari = QVBoxLayout()
        konum_kutulari.setSpacing(6)
        konum_kutulari.addWidget(self.sehir_kutusu)
        konum_kutulari.addWidget(self.ilce_kutusu)
        alanlar.addLayout(self._alan("Şehir ve ilçe (isteğe bağlı)", konum_kutulari,
                                     "Türkiye şartı her zaman geçerli. Şehir yazarsan sadece o şehirdekiler alınır; "
                                     "ilçe arama cümlesine eklenir ve aday sayısını daraltır."), 1, 1)

        boyutlar = QGridLayout()
        boyutlar.setHorizontalSpacing(18)
        boyutlar.setVerticalSpacing(6)
        self.boyut_kutulari = {}
        for sira, bant in enumerate(BOYUT_BANTLARI):
            self.boyut_kutulari[bant] = QCheckBox(f"{bant_metni(bant)} çalışan")
            boyutlar.addWidget(self.boyut_kutulari[bant], sira // 3, sira % 3)
        alanlar.addLayout(self._alan("Şirket büyüklüğü", boyutlar,
                                     "Tatlı nokta 11–200 çalışan. Büyüklüğü seçtiklerinin dışında çıkan şirketler elenir."),
                          2, 0)

        self.hedef_kutusu = sayi_kutusu(1, 5000, " aday")
        hedef_satiri = QHBoxLayout()
        hedef_satiri.addWidget(self.hedef_kutusu)
        hedef_satiri.addStretch(1)
        alanlar.addLayout(self._alan("Hedef: DM'e uygun aday sayısı", hedef_satiri,
                                     "Bu kadar uygun aday bulununca arama durur, bulunanlara gönderim sürer. "
                                     "İlk test için 100 önerilir."), 2, 1)
        duzen.addLayout(alanlar)

        duzen.addSpacing(8)
        duzen.addWidget(etiket("Karar verici unvanları", "bolumBaslik"))
        duzen.addWidget(etiket(
            "Aynı şirketten tek kişiye yazılır; listede önce seçilen unvan önceliklidir. Unvan şirketin büyüklüğüne "
            "uyarsa +3 puan alır: 1–20 çalışan kurucu/sahip · 20–100 kurucu, genel müdür, pazarlama müdürü · 100–500 "
            "pazarlama direktörü/lideri · 500+ departman yöneticileri.", "soluk", kaydir=True))
        self.rol_kutulari = {}
        for grup, roller in ROL_GRUPLARI.items():
            duzen.addSpacing(4)
            duzen.addWidget(etiket(f"{GRUP_ADLARI[grup]}  ·  {grup_araligi(grup)} için ideal", "grupBaslik"))
            izgara = QGridLayout()
            izgara.setHorizontalSpacing(24)
            izgara.setVerticalSpacing(6)
            izgara.setColumnStretch(0, 1)
            izgara.setColumnStretch(1, 1)
            for sira, rol in enumerate(roller):
                turkce = ROL_TURKCELERI.get(rol)
                self.rol_kutulari[rol] = QCheckBox(f"{rol}  ({turkce[0]})" if turkce else rol)
                izgara.addWidget(self.rol_kutulari[rol], sira // 2, sira % 2)
            duzen.addLayout(izgara)

        duzen.addSpacing(10)
        duzen.addWidget(etiket("İlk mesaj", "bolumBaslik"))
        duzen.addWidget(etiket(
            "Bağlantı isteği kabul edilince bu kampanyanın adaylarına gider. Mesajı problemden aç; ilk mesajda hizmet "
            "listesi sayma: önce cevap, sonra problem, sonra hizmet.", "soluk", kaydir=True))
        self.mesaj_kutusu = QPlainTextEdit()
        self.mesaj_kutusu.setFixedHeight(112)
        duzen.addWidget(self.mesaj_kutusu)
        self.onizleme = etiket("", "onizleme", kaydir=True)
        self.onizleme.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        duzen.addWidget(self.onizleme)
        duzen.addWidget(etiket("Değişkenler: {ad} kişinin adı, {isletme_adi} şirketin adı.", "soluk"))
        self.mesaj_kutusu.textChanged.connect(self._onizle)

        alt = QFrame()
        alt.setObjectName("altCubuk")
        alt_duzeni = QHBoxLayout(alt)
        alt_duzeni.setContentsMargins(28, 12, 28, 12)
        alt_duzeni.setSpacing(10)
        alt_duzeni.addStretch(1)
        alt_duzeni.addWidget(dugme("Vazgeç", self.reject))
        kaydet = dugme("Kaydet", self._kaydet, "aksan")
        kaydet.setDefault(True)
        alt_duzeni.addWidget(kaydet)
        dis.addWidget(alt)

        self._doldur(kampanya or BOS_KAMPANYA)

    @staticmethod
    def _alan(baslik: str, parca, ipucu: str = None) -> QVBoxLayout:
        kolon = QVBoxLayout()
        kolon.setSpacing(6)
        kolon.addWidget(etiket(baslik, "alanBaslik"))
        if isinstance(parca, QWidget):
            kolon.addWidget(parca)
        else:
            kolon.addLayout(parca)
        if ipucu:
            kolon.addWidget(etiket(ipucu, "soluk", kaydir=True))
        kolon.addStretch(1)
        return kolon

    def _sablon_secildi(self) -> None:
        kod = self.sablon_secici.currentData()
        if not kod:
            self._doldur(BOS_KAMPANYA)
            return
        self._doldur(kampanya_verisi(kod, servis.sektor_mesaji(kod, load_settings())))

    def _doldur(self, k: dict) -> None:
        self.ad_kutusu.setText(k.get("ad", ""))
        for kod, kutu in self.hizmet_kutulari.items():
            kutu.setChecked(kod in k.get("hizmetler", []))
        self.sektor_kutusu.setText(", ".join(k.get("sektor_kelimeleri", [])))
        self.sehir_kutusu.setText(", ".join(k.get("sehir") or []))
        self.ilce_kutusu.setText(", ".join(k.get("ilceler") or []))
        for bant, kutu in self.boyut_kutulari.items():
            kutu.setChecked(bant in k.get("sirket_boyutlari", []))
        self._rol_sirasi = list(k.get("roller", []))
        for rol, kutu in self.rol_kutulari.items():
            kutu.setChecked(rol in self._rol_sirasi)
        self.hedef_kutusu.setValue(k.get("hedef", 100))
        self.mesaj_kutusu.setPlainText(k.get("ilk_mesaj", GENEL_ILK_MESAJ))
        self._onizle()

    def _secili_roller(self) -> list:
        # Kampanyadaki oncelik sirasi korunur; yeni isaretlenenler sona eklenir
        secili = [rol for rol, kutu in self.rol_kutulari.items() if kutu.isChecked()]
        onceki = [rol for rol in self._rol_sirasi if rol in secili]
        return onceki + [rol for rol in secili if rol not in onceki]

    def _onizle(self) -> None:
        metin = self.mesaj_kutusu.toPlainText().strip()
        if not metin:
            self.onizleme.setText("Mesaj boş.")
            return
        try:
            self.onizleme.setText("Örnek kişiyle önizleme:\n" + metin.format(**servis.ORNEK_ADAY))
        except (KeyError, ValueError, IndexError):
            self.onizleme.setText("Mesajda hatalı değişken var. Değişkenleri {ad} ve {isletme_adi} gibi yaz.")

    def _kaydet(self) -> None:
        veri = {
            "ad": self.ad_kutusu.text(),
            "hizmetler": [kod for kod, kutu in self.hizmet_kutulari.items() if kutu.isChecked()],
            "sektor_kelimeleri": [p.strip() for p in self.sektor_kutusu.text().split(",") if p.strip()],
            "sehir": [p.strip() for p in self.sehir_kutusu.text().split(",") if p.strip()],
            "ilceler": [p.strip() for p in self.ilce_kutusu.text().split(",") if p.strip()],
            "sirket_boyutlari": [bant for bant, kutu in self.boyut_kutulari.items() if kutu.isChecked()],
            "roller": self._secili_roller(),
            "hedef": self.hedef_kutusu.value(),
            "ilk_mesaj": self.mesaj_kutusu.toPlainText(),
        }
        try:
            servis.kampanya_kaydet(veri, self.kampanya["id"] if self.kampanya else None)
        except servis.AyarHatasi as e:
            bilgi_ver(self, "Eksik bilgi", str(e), "uyari")
            return
        self.accept()
