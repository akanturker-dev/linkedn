import ctypes
import os
import sys
import traceback
from datetime import datetime

if sys.platform == "win32":
    # Windows koyu moddayken Qt'nin koyu renkleri acik temaya karismasin (test ortami kendi platformunu verir)
    os.environ.setdefault("QT_QPA_PLATFORM", "windows:darkmode=0")

from PySide6.QtCore import Qt, QTranslator
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from app import servis
from app.config import DATA_DIR
from app.gui.bilesenler import bilgi_ver
from app.gui.pencere import AnaPencere
from app.gui.tema import AKSAN, QSS, acik_palet

HATA_KAYDI = DATA_DIR / "hata_kaydi.txt"


def uygulama_simgesi() -> QIcon:
    simge = QIcon()
    for boyut in (16, 24, 32, 48, 64, 128, 256):
        resim = QPixmap(boyut, boyut)
        resim.fill(Qt.GlobalColor.transparent)
        ressam = QPainter(resim)
        ressam.setRenderHint(QPainter.RenderHint.Antialiasing)
        ressam.setPen(Qt.PenStyle.NoPen)
        ressam.setBrush(QColor(AKSAN))
        ressam.drawRoundedRect(0, 0, boyut, boyut, boyut * 0.22, boyut * 0.22)
        yazi = QFont("Segoe UI")
        yazi.setWeight(QFont.Weight.Bold)
        yazi.setPixelSize(max(8, int(boyut * 0.5)))
        ressam.setFont(yazi)
        ressam.setPen(QColor("white"))
        ressam.drawText(resim.rect(), Qt.AlignmentFlag.AlignCenter, "in")
        ressam.end()
        simge.addPixmap(resim)
    return simge


def _hata_yakala(tur, deger, iz) -> None:
    # pythonw ile konsol yok; yakalanmayan hatalar sessizce kaybolmasin
    metin = "".join(traceback.format_exception(tur, deger, iz))
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(HATA_KAYDI, "a", encoding="utf-8") as dosya:
            dosya.write(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}]\n{metin}")
    except OSError:
        pass
    if QApplication.instance():
        bilgi_ver(None, "Beklenmeyen hata", f"Bir hata oldu. Ayrıntılar data\\hata_kaydi.txt dosyasına yazıldı.\n\n{deger}",
                  "hata")


class TurkceMenuCevirisi(QTranslator):
    """Kurulu Qt paketinde Turkce ceviri dosyasi yok; metin kutularinin sag tik menusu burada cevrilir."""

    CEVIRILER = {
        "&Undo": "&Geri al",
        "&Redo": "&Yinele",
        "Cu&t": "&Kes",
        "&Copy": "K&opyala",
        "Copy &Link Location": "&Bağlantı adresini kopyala",
        "&Paste": "&Yapıştır",
        "Delete": "Sil",
        "Select All": "Tümünü seç",
        "&Step up": "&Artır",
        "Step &down": "A&zalt",
    }

    def translate(self, baglam, metin, ayrim=None, sayi=-1):
        return self.CEVIRILER.get(metin, "")

    def isEmpty(self) -> bool:
        return False


def uygulamayi_hazirla(argv) -> QApplication:
    uygulama = QApplication(argv)
    uygulama.setApplicationName("LinkedIn Müşteri Asistanı")
    uygulama.ceviri = TurkceMenuCevirisi(uygulama)
    uygulama.installTranslator(uygulama.ceviri)
    uygulama.setStyle("Fusion")
    uygulama.setPalette(acik_palet())
    uygulama.setFont(QFont("Segoe UI", 11))
    uygulama.setStyleSheet(QSS)
    uygulama.setWindowIcon(uygulama_simgesi())
    return uygulama


def pencereyi_ekrana_yerlestir(pencere, uygulama) -> None:
    """Pencere ekrana sigar ve ortalanir; buyuk ekranda satirlar okunaksiz uzamasin diye ust sinir vardir."""
    alan = uygulama.primaryScreen().availableGeometry()
    genislik = min(1680, int(alan.width() * 0.9))
    yukseklik = min(1040, int(alan.height() * 0.9))
    pencere.resize(genislik, yukseklik)
    pencere.move(alan.x() + (alan.width() - genislik) // 2, alan.y() + (alan.height() - yukseklik) // 2)


def main() -> int:
    sys.excepthook = _hata_yakala
    if sys.platform == "win32":
        # Gorev cubugunda Python simgesi yerine asistanin kendi simgesi gorunsun
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Akan.LinkedInMusteriAsistani")
    uygulama = uygulamayi_hazirla(sys.argv)
    try:
        servis.baslat()
    except servis.ZatenAcik as e:
        bilgi_ver(None, "Asistan zaten açık", str(e), "uyari")
        return 1
    pencere = AnaPencere()
    pencereyi_ekrana_yerlestir(pencere, uygulama)
    pencere.show()
    return uygulama.exec()


if __name__ == "__main__":
    sys.exit(main())
