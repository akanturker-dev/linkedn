from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QCompleter, QComboBox, QFrame, QHBoxLayout, QLabel, QMessageBox, QPushButton, QScrollArea, QSpinBox, QVBoxLayout, QWidget,
)

from .tema import yeniden_boya

MESAJ_SIMGELERI = {
    "bilgi": QMessageBox.Icon.Information,
    "uyari": QMessageBox.Icon.Warning,
    "hata": QMessageBox.Icon.Critical,
}


def etiket(metin: str = "", ad: str = None, kaydir: bool = False) -> QLabel:
    yazi = QLabel(metin)
    if ad:
        yazi.setObjectName(ad)
    yazi.setWordWrap(kaydir)
    return yazi


def dugme(metin: str, tiklaninca, ad: str = None, buyuk: bool = False) -> QPushButton:
    buton = QPushButton(metin)
    if ad:
        buton.setObjectName(ad)
    if buyuk:
        buton.setProperty("buyuk", "evet")
    buton.setCursor(Qt.CursorShape.PointingHandCursor)
    # Pencerelerde Enter tusu yanlislikla "Vazgec"e ya da bir durum dugmesine basmasin; varsayilan dugme ayrica secilir
    buton.setAutoDefault(False)
    buton.clicked.connect(lambda: tiklaninca())
    return buton


def sayi_kutusu(en_az: int, en_fazla: int, sonek: str = "") -> QSpinBox:
    kutu = QSpinBox()
    kutu.setRange(en_az, en_fazla)
    kutu.setSuffix(sonek)
    kutu.setMinimumSize(100, 36)
    return kutu


def cip(metin: str, tur: str = "") -> QLabel:
    yazi = etiket(metin, "cip")
    yazi.setProperty("tur", tur)
    return yazi


def cip_dugme(metin: str, tiklaninca, tur: str = "") -> QPushButton:
    """Kaldirilabilir etiket: uzerine tiklayinca listeden cikar."""
    buton = QPushButton(f"{metin}  ✕")
    buton.setObjectName("cipDugme")
    buton.setProperty("tur", tur)
    buton.setCursor(Qt.CursorShape.PointingHandCursor)
    buton.setAutoDefault(False)
    buton.setToolTip("Listeden çıkarmak için tıkla")
    buton.clicked.connect(lambda: tiklaninca())
    return buton


def adres_ac(adres: str) -> None:
    adres = (adres or "").strip()
    if not adres:
        return
    if not adres.lower().startswith(("http://", "https://")):
        adres = "https://" + adres
    QDesktopServices.openUrl(QUrl(adres))


def hap_ayarla(yazi: QLabel, metin: str, tur: str = "") -> None:
    yazi.setText(metin)
    yazi.setProperty("tur", tur)
    yeniden_boya(yazi)


def bilgi_ver(ebeveyn, baslik: str, metin: str, tur: str = "bilgi") -> None:
    """Qt'nin hazir dugmeleri Ingilizce ('OK') cikiyor; Turkce 'Tamam' dugmeli bilgi, uyari ya da hata penceresi."""
    kutu = QMessageBox(MESAJ_SIMGELERI.get(tur, QMessageBox.Icon.Information), baslik, metin,
                       QMessageBox.StandardButton.NoButton, ebeveyn)
    kutu.addButton("Tamam", QMessageBox.ButtonRole.AcceptRole)
    kutu.exec()


def soru_sor(ebeveyn, baslik: str, metin: str, evet: str = "Evet", hayir: str = "Vazgeç") -> bool:
    """Onay sorusu; Enter ya da Esc'e yanlislikla basilirsa guvenli secenek (Vazgec) secilir."""
    kutu = QMessageBox(QMessageBox.Icon.Question, baslik, metin, QMessageBox.StandardButton.NoButton, ebeveyn)
    evet_dugmesi = kutu.addButton(evet, QMessageBox.ButtonRole.AcceptRole)
    kutu.setDefaultButton(kutu.addButton(hayir, QMessageBox.ButtonRole.RejectRole))
    kutu.exec()
    return kutu.clickedButton() is evet_dugmesi


def duzeni_temizle(duzen) -> None:
    """Duzendeki butun parcalari kaldirir; yeniden kurmadan once kullanilir."""
    while duzen.count():
        oge = duzen.takeAt(0)
        parca = oge.widget()
        if parca is not None:
            # Once ebeveynden kopar: yalniz deleteLater birakilirsa parca silinene kadar ekranda gorunmeye devam eder
            parca.setParent(None)
            parca.deleteLater()
        elif oge.layout():
            duzeni_temizle(oge.layout())


class AcilirListe(QComboBox):
    """Uzun listelerde acilir kisim ekrani kaplamasin ve dugmeden kopmasin.

    Iki olculmus sorun cozuluyor:
      1. Qt'nin maxVisibleItems ayari stil sayfasi kullanilinca islemiyor (olculdu: 55 satirda liste
         ekran boyu kadar aciliyor). Tek calisan yol, acildiktan sonra pencereyi kisitlamak.
      2. Liste uzun olunca Qt acilir pencereyi secili satiri dugmeye hizalayacak sekilde yukari itiyor;
         65 satirlik sektor listesinde ekranin en tepesinde (y=0) aciliyordu, dugmeyle alakasi kalmiyordu.
         Bu yuzden pencere acildiktan sonra dugmenin hemen altina tasiniyor; asagi sigmiyorsa ustune.
    """

    EN_FAZLA_YUKSEKLIK = 380
    EN_FAZLA_SATIR = 11
    # Bu satir sayisini asan listelerde yazarak arama acilir: 65 sektoru kaydirmak yerine "otel" yazilir
    ARAMA_ESIGI = 12

    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setMinimumHeight(40)

    def setModel(self, model) -> None:
        super().setModel(model)
        self._aramayi_ayarla()

    def _aramayi_ayarla(self) -> None:
        """Uzun listelerde kutuya yazarak suzme."""
        if self.count() < self.ARAMA_ESIGI or self.isEditable():
            return
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.lineEdit().setPlaceholderText("Yazarak ara ya da listeden seç")
        tamamlayici = QCompleter(self.model(), self)
        tamamlayici.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        tamamlayici.setFilterMode(Qt.MatchFlag.MatchContains)
        tamamlayici.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(tamamlayici)

    def showPopup(self) -> None:
        pencere = self.view().window()
        pencere.setMinimumHeight(0)
        pencere.setMaximumHeight(16777215)
        super().showPopup()
        pencere.setFixedHeight(self._yukseklik(pencere))
        self._pencereyi_dugmenin_altina_al(pencere, pencere.height())

    def _yukseklik(self, pencere) -> int:
        """Ne ekrani kaplasin ne de bes satira sikissin: en fazla EN_FAZLA_SATIR satir gosterilir."""
        gorunum = self.view()
        # Ilk satir grup basligi olabilir ve digerlerinden kisa olcer; en genis satir esas alinir
        satir = max((gorunum.sizeHintForRow(i) for i in range(min(self.count(), 6))), default=0)
        if satir <= 0:
            return min(pencere.height(), self.EN_FAZLA_YUKSEKLIK)
        cerceve = max(pencere.height() - gorunum.height(), 0)
        istenen = satir * min(self.count(), self.EN_FAZLA_SATIR) + cerceve
        return max(min(istenen, self.EN_FAZLA_YUKSEKLIK), min(pencere.height(), self.EN_FAZLA_YUKSEKLIK))

    def _pencereyi_dugmenin_altina_al(self, pencere, yukseklik: int) -> None:
        ekran = self.screen().availableGeometry()
        sol_ust = self.mapToGlobal(self.rect().bottomLeft())
        y = sol_ust.y() + 1
        if y + yukseklik > ekran.bottom():
            ustu = self.mapToGlobal(self.rect().topLeft()).y() - yukseklik - 1
            y = ustu if ustu >= ekran.top() else max(ekran.bottom() - yukseklik, ekran.top())
        x = min(max(sol_ust.x(), ekran.left()), max(ekran.right() - pencere.width(), ekran.left()))
        pencere.move(x, y)


class KaydirmaAlani(QScrollArea):
    """Cercevesiz, icerigi genislige yayilan kayan alan (sayfalar ve uzun pencereler icin)."""

    def __init__(self, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)


class Kart(QFrame):
    """vurgulu=True: sayfanin asil bolumu. Renkli kenarlik, buyuk baslik ve istege bagli bir rozetle
    diger kartlardan ayrilir ki goz once oraya gitsin."""

    def __init__(self, baslik: str = None, aciklama: str = None, ebeveyn=None, vurgulu: bool = False,
                 rozet: str = None):
        super().__init__(ebeveyn)
        self.setObjectName("vurguKart" if vurgulu else "kart")
        self.duzen = QVBoxLayout(self)
        self.duzen.setContentsMargins(*((26, 22, 26, 24) if vurgulu else (22, 18, 22, 20)))
        self.duzen.setSpacing(12)
        if rozet:
            self.duzen.addWidget(etiket(rozet, "vurguRozet"), 0, Qt.AlignmentFlag.AlignLeft)
        if baslik:
            self.duzen.addWidget(etiket(baslik, "vurguBaslik" if vurgulu else "bolumBaslik", kaydir=vurgulu))
        if aciklama:
            self.duzen.addWidget(etiket(aciklama, "vurguAciklama" if vurgulu else "ikincil", kaydir=True))


class KpiKart(QFrame):
    def __init__(self, baslik: str, ebeveyn=None):
        super().__init__(ebeveyn)
        self.setObjectName("kart")
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(18, 14, 18, 14)
        duzen.setSpacing(2)
        self.deger = etiket("0", "kpiDeger")
        self.baslik = etiket(baslik, "kpiEtiket")
        self.oran = etiket("", "kpiOran")
        for parca in (self.deger, self.baslik, self.oran):
            duzen.addWidget(parca)

    def ayarla(self, deger, oran: str = "") -> None:
        self.deger.setText(str(deger))
        self.oran.setText(oran)


class Metrik(QWidget):
    """Kartlarin icindeki kucuk sayi: ustte deger, altta ne oldugu."""

    def __init__(self, baslik: str, ebeveyn=None):
        super().__init__(ebeveyn)
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(0, 0, 0, 0)
        duzen.setSpacing(0)
        self.deger = etiket("0", "metrikDeger")
        self.baslik = etiket(baslik, "metrikEtiket")
        for parca in (self.deger, self.baslik):
            parca.setAlignment(Qt.AlignmentFlag.AlignHCenter)
            duzen.addWidget(parca)

    def ayarla(self, deger) -> None:
        self.deger.setText(str(deger))


class Sayfa(QWidget):
    """Butun sayfalarin ortak iskeleti: solda buyuk baslik ve aciklama, sagda sayfaya ozel dugmeler;
    istenirse icerik kayar ve altta her zaman gorunen bir dugme cubugu olur."""

    def __init__(self, baslik: str, aciklama: str, kaydirilabilir: bool = False, alt_cubuk: bool = False):
        super().__init__()
        self.setObjectName("sayfa")
        dis = QVBoxLayout(self)
        dis.setContentsMargins(0, 0, 0, 0)
        dis.setSpacing(0)

        govde = QWidget()
        govde.setObjectName("sayfa")
        self.icerik = QVBoxLayout(govde)
        self.icerik.setContentsMargins(32, 26, 32, 26)
        self.icerik.setSpacing(18)

        ust = QHBoxLayout()
        yazilar = QVBoxLayout()
        yazilar.setSpacing(4)
        yazilar.addWidget(etiket(baslik, "sayfaBaslik"))
        yazilar.addWidget(etiket(aciklama, "sayfaAciklama", kaydir=True))
        ust.addLayout(yazilar, 1)
        self.baslik_sag = QHBoxLayout()
        self.baslik_sag.setSpacing(10)
        ust.addLayout(self.baslik_sag)
        self.icerik.addLayout(ust)

        if kaydirilabilir:
            kaydirma = KaydirmaAlani()
            kaydirma.setWidget(govde)
            dis.addWidget(kaydirma, 1)
        else:
            dis.addWidget(govde, 1)

        if alt_cubuk:
            cubuk = QFrame()
            cubuk.setObjectName("altCubuk")
            self.alt = QHBoxLayout(cubuk)
            self.alt.setContentsMargins(32, 12, 32, 12)
            self.alt.setSpacing(12)
            dis.addWidget(cubuk)

    def yenile(self, veri: dict) -> None:
        pass
