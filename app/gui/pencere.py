from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QMainWindow, QMessageBox, QPushButton, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import db, engine, servis
from ..config import load_settings
from .bilesenler import bilgi_ver, dugme, etiket, hap_ayarla
from .sayfa_adaylar import AdaylarSayfasi
from .sayfa_ayarlar import AyarlarSayfasi
from .sayfa_gonderim import GonderimSayfasi, durum_bilgisi
from .sayfa_gunluk import GunlukSayfasi
from .sayfa_kampanyalar import KampanyalarSayfasi
from .sayfa_rapor import RaporSayfasi
from .sayfa_temizlik import TemizlikSayfasi
from .tema import yeniden_boya

YENILEME_MS = 4000
YAN_MENU_GENISLIGI = 264


class AnaPencere(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LinkedIn Müşteri Asistanı")
        self._durum = {}
        ayarlar = load_settings()
        self.gonderim = GonderimSayfasi(ayarlar)
        self.adaylar = AdaylarSayfasi()
        self.temizlik = TemizlikSayfasi()
        self.rapor = RaporSayfasi()
        self.kampanyalar = KampanyalarSayfasi()
        self.ayarlar = AyarlarSayfasi(ayarlar)
        self.gunluk = GunlukSayfasi()
        # Menu sirasi kullanim sirasi: once gonderim kurulur, sonra adaylar ve sonuclar okunur
        self._sayfalar = [
            ("Mesaj Gönder", self.gonderim),
            ("Adaylar", self.adaylar),
            ("Temizlik", self.temizlik),
            ("Rapor", self.rapor),
            ("Kampanyalar", self.kampanyalar),
            ("Ayarlar", self.ayarlar),
            ("Günlük", self.gunluk),
        ]

        kok = QWidget()
        kok.setObjectName("kok")
        yatay = QHBoxLayout(kok)
        yatay.setContentsMargins(0, 0, 0, 0)
        yatay.setSpacing(0)
        yatay.addWidget(self._yan_menu_kur())
        sag = QVBoxLayout()
        sag.setContentsMargins(0, 0, 0, 0)
        sag.setSpacing(0)
        sag.addWidget(self._guvenlik_bandi_kur())
        self.yigin = QStackedWidget()
        for _, sayfa in self._sayfalar:
            self.yigin.addWidget(sayfa)
        sag.addWidget(self.yigin, 1)
        yatay.addLayout(sag, 1)
        self.setCentralWidget(kok)

        self.gonderim.degisti.connect(self.yenile)
        self.kampanyalar.degisti.connect(self.yenile)
        self.adaylar.degisti.connect(self.yenile)
        self.temizlik.degisti.connect(self.yenile)
        self.ayarlar.kaydedildi.connect(lambda _ayarlar: self.yenile())

        self._menu_dugmeleri[0].setChecked(True)
        self.yenile()
        self._zamanlayici = QTimer(self)
        self._zamanlayici.timeout.connect(self.yenile)
        self._zamanlayici.start(YENILEME_MS)

    # ---------------- Kurulum ----------------

    def _yan_menu_kur(self) -> QFrame:
        menu = QFrame()
        menu.setObjectName("yanMenu")
        menu.setFixedWidth(YAN_MENU_GENISLIGI)
        duzen = QVBoxLayout(menu)
        duzen.setContentsMargins(16, 22, 16, 18)
        duzen.setSpacing(4)

        marka = QHBoxLayout()
        marka.setSpacing(10)
        marka.addWidget(etiket("in", "logo"), 0, Qt.AlignmentFlag.AlignVCenter)
        adlar = QVBoxLayout()
        adlar.setSpacing(0)
        adlar.addWidget(etiket("Müşteri Asistanı", "uygulamaAdi"))
        adlar.addWidget(etiket("LinkedIn · Türkiye", "soluk"))
        marka.addLayout(adlar, 1)
        duzen.addLayout(marka)
        duzen.addSpacing(20)
        duzen.addWidget(etiket("MENÜ", "menuBaslik"))

        self._menu_grubu = QButtonGroup(self)
        self._menu_grubu.setExclusive(True)
        self._menu_dugmeleri = []
        for indeks, (ad, _) in enumerate(self._sayfalar):
            buton = QPushButton(ad)
            buton.setObjectName("menu")
            buton.setCheckable(True)
            buton.setCursor(Qt.CursorShape.PointingHandCursor)
            buton.clicked.connect(lambda _=False, i=indeks: self._sayfa_ac(i))
            self._menu_grubu.addButton(buton, indeks)
            self._menu_dugmeleri.append(buton)
            duzen.addWidget(buton)
        duzen.addStretch(1)

        kutu = QFrame()
        kutu.setObjectName("yanKutu")
        kutu_duzeni = QVBoxLayout(kutu)
        kutu_duzeni.setContentsMargins(14, 14, 14, 14)
        kutu_duzeni.setSpacing(8)
        self.durum_hapi = etiket("", "hap")
        hap_satiri = QHBoxLayout()
        hap_satiri.addWidget(self.durum_hapi)
        hap_satiri.addStretch(1)
        kutu_duzeni.addLayout(hap_satiri)
        self.oturum_yazisi = etiket("", "ikincil", kaydir=True)
        self.bugun_yazisi = etiket("", "soluk", kaydir=True)
        kutu_duzeni.addWidget(self.oturum_yazisi)
        kutu_duzeni.addWidget(self.bugun_yazisi)
        duzen.addWidget(kutu)
        duzen.addSpacing(10)
        duzen.addWidget(dugme("LinkedIn'e Giriş Yap", self._linkedin_giris))
        duzen.addSpacing(4)
        self.otomasyon_dugmesi = dugme("Otomasyonu Başlat", self._otomasyonu_degistir, "aksan", buyuk=True)
        duzen.addWidget(self.otomasyon_dugmesi)
        return menu

    def _guvenlik_bandi_kur(self) -> QWidget:
        self.guvenlik_kabi = QWidget()
        self.guvenlik_kabi.setObjectName("sayfa")
        dis = QVBoxLayout(self.guvenlik_kabi)
        dis.setContentsMargins(32, 18, 32, 0)
        bant = QFrame()
        bant.setObjectName("guvenlikBandi")
        duzen = QHBoxLayout(bant)
        duzen.setContentsMargins(18, 12, 12, 12)
        duzen.addWidget(etiket(
            "LinkedIn güvenlik doğrulaması istedi, bot durdu. Asistanın Chrome penceresinde doğrulamayı elle geç, "
            "sonra buradan devam et.", "guvenlikYazi", kaydir=True), 1)
        duzen.addWidget(dugme("Doğrulamayı geçtim, devam et", self._guvenlik_devam, "tehlike"))
        dis.addWidget(bant)
        self.guvenlik_kabi.hide()
        return self.guvenlik_kabi

    # ---------------- Yenileme ----------------

    def yenile(self) -> None:
        try:
            ayarlar = load_settings()
            leadler = db.leads_getir()
            kampanyalar = db.kampanyalari_getir()
            veri = {
                "durum": servis.durum(),
                "ayarlar": ayarlar,
                "leadler": leadler,
                "kampanyalar": kampanyalar,
                "rapor": servis.rapor(leadler, kampanyalar, ayarlar["puanlama"]["esik"]),
                "bantlar": servis.bant_raporu(leadler, ayarlar),
                "loglar": db.son_loglar(300),
            }
        except Exception as e:
            self.statusBar().showMessage(f"Veriler okunamadı: {e}")
            return
        self._durum = veri["durum"]
        self._yan_menuyu_guncelle(veri)
        self.yigin.currentWidget().yenile(veri)
        if veri["loglar"]:
            self.statusBar().showMessage(f"Son olay: {veri['loglar'][0]['mesaj']}")

    def _yan_menuyu_guncelle(self, veri: dict) -> None:
        d, limitler = veri["durum"], veri["ayarlar"]["limitler"]
        metin, tur = durum_bilgisi(d)
        hap_ayarla(self.durum_hapi, metin, tur)
        self.oturum_yazisi.setText({True: "LinkedIn: bağlı", False: "LinkedIn: giriş yapılmamış"}.get(
            d.get("bot_giris_yapildi"), "LinkedIn: henüz kontrol edilmedi"))
        self.bugun_yazisi.setText(f"Son 24 saat: {d.get('baglanti_son_gun', 0)}/{limitler['baglanti_gunluk']} istek · "
                                  f"{d.get('mesaj_son_gun', 0)}/{limitler['mesaj_gunluk']} mesaj")
        self.guvenlik_kabi.setVisible(bool(d.get("guvenlik_kontrolu")))
        calisiyor = bool(d.get("calisiyor"))
        ad = "durdur" if calisiyor else "aksan"
        if self.otomasyon_dugmesi.objectName() != ad:
            self.otomasyon_dugmesi.setObjectName(ad)
            self.otomasyon_dugmesi.setText("Otomasyonu Durdur" if calisiyor else "Otomasyonu Başlat")
            yeniden_boya(self.otomasyon_dugmesi)

    def _sayfa_ac(self, indeks: int) -> None:
        simdiki = self.yigin.currentIndex()
        if indeks != simdiki and self.yigin.currentWidget() is self.ayarlar and not self.ayarlar.ayrilabilir_mi():
            self._menu_dugmeleri[simdiki].setChecked(True)
            return
        self.yigin.setCurrentIndex(indeks)
        self._menu_dugmeleri[indeks].setChecked(True)
        self.yenile()

    # ---------------- Düğmeler ----------------

    def _linkedin_giris(self) -> None:
        engine.komut_gonder("giris_yap")
        bilgi_ver(
            self,
            "LinkedIn girişi",
            "Birkaç saniye içinde asistanın kendi Chrome penceresi açılacak (senin normal Chrome'undan ayrı bir profil).\n\n"
            "LinkedIn'e o pencereden giriş yap. Giriş bitince o pencereyi kapatma, simge durumuna küçült: "
            "asistan o pencereyi kullanıyor.",
        )
        QTimer.singleShot(1500, self.yenile)

    def _otomasyonu_degistir(self) -> None:
        servis.otomasyonu_ayarla(not self._durum.get("calisiyor"))
        self.yenile()

    def _guvenlik_devam(self) -> None:
        engine.komut_gonder("guvenlik_devam")
        QTimer.singleShot(800, self.yenile)

    # ---------------- Kapanış ----------------

    def closeEvent(self, olay) -> None:
        if not self.ayarlar.ayrilabilir_mi():
            olay.ignore()
            return
        if self._durum.get("calisiyor"):
            kutu = QMessageBox(self)
            kutu.setWindowTitle("Asistan çalışıyor")
            kutu.setText("Otomasyon çalışıyor. Programı kapatırsan LinkedIn araması ve mesaj gönderme durur.")
            kapat = kutu.addButton("Kapat", QMessageBox.ButtonRole.DestructiveRole)
            kucult = kutu.addButton("Simge durumuna küçült", QMessageBox.ButtonRole.AcceptRole)
            kutu.addButton("Vazgeç", QMessageBox.ButtonRole.RejectRole)
            kutu.exec()
            if kutu.clickedButton() is kucult:
                olay.ignore()
                self.showMinimized()
                return
            if kutu.clickedButton() is not kapat:
                olay.ignore()
                return
        self._zamanlayici.stop()
        self.statusBar().showMessage("Kapatılıyor, Chrome penceresi kapatılıyor...")
        servis.kapat()
        olay.accept()
