from datetime import datetime

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QRect, QRectF, QSortFilterProxyModel, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PySide6.QtWidgets import QApplication, QStyle, QStyledItemDelegate, QStyleOptionViewItem

from .. import tazelik
from ..etiketler import DURUM_ETIKET
from ..metin import sade_metin
from .tema import SECIM_RENGI, YAZI, YAZI_3

DURUM_ROLU = Qt.ItemDataRole.UserRole + 1
PUAN_ROLU = Qt.ItemDataRole.UserRole + 2
ALT_YAZI_ROLU = Qt.ItemDataRole.UserRole + 3

DURUM_RENK = {
    "yeni": ("#F2F4F7", "#344054"),
    "hazir": ("#EEF0FF", "#3538CD"),
    "elendi": ("#F2F4F7", "#667085"),
    "istek_gonderildi": ("#FFFAEB", "#B54708"),
    "baglanti_kabul": ("#ECFDF3", "#067647"),
    "mesaj_gonderildi": ("#E0F2FE", "#026AA2"),
    "cevap_verdi": ("#FDF2FA", "#C11574"),
    "gorusme": ("#F4F3FF", "#5925DC"),
    "musteri": ("#DCFAE6", "#05603A"),
    "ilgilenmiyor": ("#F2F4F7", "#667085"),
    "hata": ("#FEF3F2", "#B42318"),
}

# Rol ayri sutun degil, kisinin adinin altinda yazar (KisiCizici): uzun unvanlar kesilmez, tablo sadelesir
KOLONLAR = [
    ("kisi", "Kişi"),
    ("isletme_adi", "Şirket"),
    ("sirket_boyutu", "Çalışan"),
    ("puan", "Puan"),
    ("kampanya", "Kampanya"),
    ("son_paylasim", "Son paylaşım"),
    ("tazelik", "LinkedIn'e katılma"),
    ("durum", "Durum"),
    ("son_islem_tarihi", "Son işlem"),
]
KOLON_SIRASI = {k: i for i, (k, _) in enumerate(KOLONLAR)}
_ARAMA_ALANLARI = ("linkedin_ad", "linkedin_rol", "linkedin_unvan", "isletme_adi", "konum", "sektor", "notlar")


def tarih_metni(iso: str) -> str:
    if not iso:
        return "-"
    try:
        return datetime.fromisoformat(iso).strftime("%d.%m.%Y %H:%M")
    except ValueError:
        return iso


def paylasim_metni(gun) -> str:
    if gun is None:
        return "-"
    if gun < 0:
        return "Paylaşım yok"
    if gun == 0:
        return "Bugün"
    if gun >= 60:
        return f"{gun // 30} ay önce"
    return f"{gun} gün önce"


def sira_metni(lead: dict) -> str:
    if lead.get("google_sirasi"):
        return f"{lead['google_sayfasi']}. sayfa, {lead['google_sirasi']}. sıra"
    return "İlk 30'da yok" if lead.get("google_arama_terimi") else "Kontrol edilmedi"


class AdayModeli(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._leads = []
        self.kampanya_adlari = {}
        self.esik = 8

    def verileri_ayarla(self, leads: list, kampanya_adlari: dict, esik: int) -> None:
        self.kampanya_adlari, self.esik = kampanya_adlari, esik
        # Ayni satirlar geldiyse sifirlama yapma: secim ve kaydirma yeri korunur
        if [l["id"] for l in leads] == [l["id"] for l in self._leads]:
            self._leads = leads
            if leads:
                self.dataChanged.emit(self.index(0, 0), self.index(len(leads) - 1, len(KOLONLAR) - 1))
            return
        self.beginResetModel()
        self._leads = leads
        self.endResetModel()

    def lead(self, satir: int) -> dict:
        return self._leads[satir]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._leads)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(KOLONLAR)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return KOLONLAR[section][1]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        lead = self._leads[index.row()]
        anahtar = KOLONLAR[index.column()][0]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._metin(lead, anahtar)
        if role == Qt.ItemDataRole.UserRole:
            return self._siralama_degeri(lead, anahtar)
        if role == DURUM_ROLU:
            return lead["durum"]
        if role == PUAN_ROLU:
            return lead.get("puan")
        if role == ALT_YAZI_ROLU and anahtar == "kisi":
            return lead.get("linkedin_rol") or lead.get("linkedin_unvan") or ""
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._ipucu(lead, anahtar)
        if role == Qt.ItemDataRole.TextAlignmentRole and anahtar in ("sirket_boyutu", "son_paylasim", "tazelik", "son_islem_tarihi"):
            return Qt.AlignmentFlag.AlignCenter
        return None

    def _metin(self, lead: dict, anahtar: str) -> str:
        if anahtar == "kisi":
            return lead.get("linkedin_ad") or "-"
        if anahtar == "puan":
            return "-" if lead.get("puan") is None else str(lead["puan"])
        if anahtar == "kampanya":
            return self.kampanya_adlari.get(lead.get("kampanya_id"), "-")
        if anahtar == "son_paylasim":
            return paylasim_metni(lead.get("son_paylasim_gun"))
        if anahtar == "tazelik":
            return tazelik.etiket(lead.get("uye_no"))
        if anahtar == "durum":
            return DURUM_ETIKET.get(lead["durum"], lead["durum"])
        if anahtar == "son_islem_tarihi":
            return tarih_metni(lead.get("son_islem_tarihi"))
        return str(lead.get(anahtar) or "-")

    def _siralama_degeri(self, lead: dict, anahtar: str):
        if anahtar == "puan":
            return -1 if lead.get("puan") is None else int(lead["puan"])
        if anahtar == "son_paylasim":
            gun = lead.get("son_paylasim_gun")
            return 99999 if gun is None or gun < 0 else int(gun)
        if anahtar == "tazelik":
            # Numarasi okunamayan en sona; kucuk gun = yeni katilmis
            gun = tazelik.tahmini_gun(lead.get("uye_no"))
            return 999999 if gun is None else gun
        if anahtar == "son_islem_tarihi":
            return lead.get("son_islem_tarihi") or ""
        return sade_metin(self._metin(lead, anahtar))

    def _ipucu(self, lead: dict, anahtar: str):
        if anahtar == "kisi":
            return "\n".join(filter(None, [lead.get("linkedin_unvan"), lead.get("konum"), lead.get("linkedin_url")])) or None
        if anahtar == "isletme_adi":
            return "\n".join(filter(None, [lead.get("sirket_sektoru"), lead.get("website")])) or None
        if anahtar == "puan":
            return lead.get("puan_detay") or None
        if anahtar == "durum":
            return lead.get("notlar") or None
        return None


class AdayFiltresi(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(Qt.ItemDataRole.UserRole)
        self._metin, self._durum, self._kampanya, self._sadece_uygun = "", "", None, False

    def filtre_ayarla(self, metin: str, durum: str, kampanya_id, sadece_uygun: bool) -> None:
        self._metin, self._durum = sade_metin(metin.strip()), durum
        self._kampanya, self._sadece_uygun = kampanya_id, sadece_uygun
        self.invalidateFilter()

    def filterAcceptsRow(self, satir, ebeveyn):
        model = self.sourceModel()
        lead = model.lead(satir)
        if self._durum and lead["durum"] != self._durum:
            return False
        if self._kampanya and lead.get("kampanya_id") != self._kampanya:
            return False
        if self._sadece_uygun and (lead.get("puan") or 0) < model.esik:
            return False
        if not self._metin:
            return True
        return self._metin in sade_metin(" ".join(str(lead.get(a) or "") for a in _ARAMA_ALANLARI))

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        # Excel gibi: siralama/filtre ne olursa olsun satir numaralari 1'den baslar
        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return super().headerData(section, orientation, role)


class KisiCizici(QStyledItemDelegate):
    """Kisi hucresini iki satir cizer: ustte ad (kalin), altta rolu (soluk)."""

    def paint(self, painter, option, index):
        secenek = QStyleOptionViewItem(option)
        self.initStyleOption(secenek, index)
        secenek.text = ""
        stil = secenek.widget.style() if secenek.widget else QApplication.style()
        # Zemin (secim, zebra satir) stilin kendi cizimiyle; yazilar asagida elle
        stil.drawControl(QStyle.ControlElement.CE_ItemViewItem, secenek, painter, secenek.widget)

        painter.save()
        alan = option.rect.adjusted(12, 3, -10, -3)
        ad_fontu = QFont(option.font)
        ad_fontu.setWeight(QFont.Weight.DemiBold)
        rol_fontu = QFont(option.font)
        rol_fontu.setPointSizeF(max(8.0, option.font.pointSizeF() - 1.5))
        ad_olcusu, rol_olcusu = QFontMetrics(ad_fontu), QFontMetrics(rol_fontu)
        rol = index.data(ALT_YAZI_ROLU) or ""
        toplam = ad_olcusu.height() + (rol_olcusu.height() if rol else 0)
        ust = alan.top() + max(0, (alan.height() - toplam) // 2)
        sola_orta = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        painter.setFont(ad_fontu)
        painter.setPen(QColor(YAZI))
        ad = ad_olcusu.elidedText(index.data(Qt.ItemDataRole.DisplayRole) or "-", Qt.TextElideMode.ElideRight, alan.width())
        painter.drawText(QRect(alan.left(), ust, alan.width(), ad_olcusu.height()), sola_orta, ad)
        if rol:
            painter.setFont(rol_fontu)
            painter.setPen(QColor(YAZI_3))
            rol = rol_olcusu.elidedText(rol, Qt.TextElideMode.ElideRight, alan.width())
            painter.drawText(QRect(alan.left(), ust + ad_olcusu.height(), alan.width(), rol_olcusu.height()), sola_orta, rol)
        painter.restore()


class RozetCizici(QStyledItemDelegate):
    """Hucreyi renkli, yuvarlak kenarli bir etiket olarak cizer; renk_bul(indeks) -> (zemin, yazi)."""

    def __init__(self, renk_bul, ebeveyn=None):
        super().__init__(ebeveyn)
        self._renk_bul = renk_bul

    def paint(self, painter, option, index):
        painter.save()
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(SECIM_RENGI))
        metin = index.data(Qt.ItemDataRole.DisplayRole) or ""
        if metin in ("", "-"):
            painter.setPen(QColor("#98A2B3"))
            painter.drawText(option.rect.adjusted(10, 0, 0, 0), Qt.AlignmentFlag.AlignVCenter, "-")
            painter.restore()
            return
        arka, yazi = self._renk_bul(index)
        font = QFont(option.font)
        font.setWeight(QFont.Weight.Bold)
        font.setPointSizeF(max(8.0, font.pointSizeF() - 0.5))
        painter.setFont(font)
        olcu = painter.fontMetrics()
        yukseklik = olcu.height() + 8
        genislik = min(olcu.horizontalAdvance(metin) + 24, option.rect.width() - 14)
        kutu = QRectF(option.rect.x() + 8, option.rect.center().y() - yukseklik / 2 + 0.5, genislik, yukseklik)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(arka))
        painter.drawRoundedRect(kutu, yukseklik / 2, yukseklik / 2)
        painter.setPen(QColor(yazi))
        painter.drawText(kutu, Qt.AlignmentFlag.AlignCenter, metin)
        painter.restore()


def durum_rengi(index) -> tuple:
    return DURUM_RENK.get(index.data(DURUM_ROLU), ("#F2F4F7", "#344054"))


def puan_rengi_bulucu(model: AdayModeli):
    def bul(index) -> tuple:
        puan = index.data(PUAN_ROLU) or 0
        if puan >= model.esik:
            return ("#ECFDF3", "#067647")
        if puan >= model.esik - 2:
            return ("#FFFAEB", "#B54708")
        return ("#F2F4F7", "#475467")
    return bul
