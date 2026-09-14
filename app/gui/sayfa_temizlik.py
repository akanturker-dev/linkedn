from PySide6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QHBoxLayout, QHeaderView, QMenu, QTableView, QVBoxLayout,
)

from .. import servis, temizlik
from ..etiketler import DURUM_ETIKET
from ..metin import sade_metin
from .bilesenler import Kart, Metrik, Sayfa, adres_ac, bilgi_ver, dugme, etiket, soru_sor
from .tablo_modeli import ALT_YAZI_ROLU, DURUM_ROLU, DURUM_RENK, KisiCizici, RozetCizici

RENK_ROLU = Qt.ItemDataRole.UserRole + 10
ONERI_RENKLERI = {
    "iyi": ("#ECFDF3", "#067647"),
    "uyari": ("#FFFAEB", "#B54708"),
    "hata": ("#FEF3F2", "#B42318"),
    "": ("#F2F4F7", "#475467"),
}
# Aciliyet: tabloda en ustte ne gorunsun (buyuk sayi once)
ACILIYET = {"hata": 4, "cevapsiz": 4, "kabul_yok": 4, "is_yok": 3, "sirada": 2, "mesaj_sirasi": 1, "bekle": 1,
            "kabul_bekleniyor": 1, "cevap": 0, "dokunma": 0, "yapildi": -1}
KOLONLAR = [
    ("kisi", "Kişi"),
    ("isletme_adi", "Şirket"),
    ("durum", "Durum"),
    ("istek_gun", "İstek"),
    ("mesaj_gun", "Mesaj"),
    ("cevap", "Cevap"),
    ("oneri", "Ne yapmalı?"),
]
KOLON_SIRASI = {k: i for i, (k, _) in enumerate(KOLONLAR)}
SUTUN_GENISLIKLERI = {"isletme_adi": 210, "durum": 165, "istek_gun": 110, "mesaj_gun": 110, "cevap": 95, "oneri": 320}
SUZGECLER = [
    ("hepsi", "Hepsi"),
    ("cevapsiz", "Cevap vermeyenler"),
    ("kabul_yok", "Kabul etmeyenler"),
    ("is_yok", "İş çıkmayanlar"),
    ("cevap", "Cevap verenler"),
    ("sirada", "Temizlik sırasında"),
    ("yapildi", "Temizlenenler"),
]
OZET = [
    ("toplam", "Yazılan kişi"),
    ("cevap", "Cevap geldi"),
    ("bekleyen_mesaj", "Mesaj/cevap bekleniyor"),
    ("cevapsiz", "Cevapsız kaldı"),
    ("kabul_yok", "Kabul etmedi"),
    ("is_yok", "İş çıkmadı"),
    ("sirada", "Temizlik sırasında"),
    ("yapildi", "Temizlendi"),
]
GUN_SECENEKLERI = {"cevapsiz": (3, 7, 14, 30), "kabul_yok": (14, 21, 30, 45)}


def gun_metni(gun) -> str:
    if gun is None:
        return "-"
    if gun == 0:
        return "Bugün"
    return f"{gun} gün önce"


class TemizlikModeli(QAbstractTableModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._satirlar = []

    def verileri_ayarla(self, satirlar: list) -> None:
        aynisi = [s["lead"]["id"] for s in satirlar] == [s["lead"]["id"] for s in self._satirlar]
        if aynisi:
            self._satirlar = satirlar
            if satirlar:
                self.dataChanged.emit(self.index(0, 0), self.index(len(satirlar) - 1, len(KOLONLAR) - 1))
            return
        self.beginResetModel()
        self._satirlar = satirlar
        self.endResetModel()

    def satir(self, sira: int) -> dict:
        return self._satirlar[sira]

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._satirlar)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(KOLONLAR)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return KOLONLAR[section][1]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        satir = self._satirlar[index.row()]
        lead, anahtar = satir["lead"], KOLONLAR[index.column()][0]
        if role == Qt.ItemDataRole.DisplayRole:
            return self._metin(satir, lead, anahtar)
        if role == Qt.ItemDataRole.UserRole:
            return self._siralama(satir, lead, anahtar)
        if role == ALT_YAZI_ROLU and anahtar == "kisi":
            return lead.get("linkedin_rol") or lead.get("linkedin_unvan") or ""
        if role == DURUM_ROLU:
            return lead["durum"]
        if role == RENK_ROLU:
            return satir["renk"]
        if role == Qt.ItemDataRole.ToolTipRole:
            return self._ipucu(satir, lead, anahtar)
        if role == Qt.ItemDataRole.TextAlignmentRole and anahtar in ("istek_gun", "mesaj_gun", "cevap"):
            return Qt.AlignmentFlag.AlignCenter
        return None

    @staticmethod
    def _metin(satir, lead, anahtar):
        if anahtar == "kisi":
            return lead.get("linkedin_ad") or "-"
        if anahtar == "durum":
            return DURUM_ETIKET.get(lead["durum"], lead["durum"])
        if anahtar == "istek_gun":
            return gun_metni(satir["istek_gun"])
        if anahtar == "mesaj_gun":
            return gun_metni(satir["mesaj_gun"])
        if anahtar == "cevap":
            return "Evet" if satir["cevap"] else "Yok"
        if anahtar == "oneri":
            return satir["metin"]
        return str(lead.get(anahtar) or "-")

    @staticmethod
    def _siralama(satir, lead, anahtar):
        if anahtar in ("istek_gun", "mesaj_gun"):
            return satir[anahtar] if satir[anahtar] is not None else -1
        if anahtar == "cevap":
            return 1 if satir["cevap"] else 0
        if anahtar == "oneri":
            # Once en acil olan: cevapsiz/kabul etmeyen, sonra bekleyenler
            return ACILIYET.get(satir["oneri"], 0) * 1000 + (satir["mesaj_gun"] or satir["istek_gun"] or 0)
        return sade_metin(TemizlikModeli._metin(satir, lead, anahtar))

    @staticmethod
    def _ipucu(satir, lead, anahtar):
        if anahtar == "kisi":
            return "\n".join(filter(None, [lead.get("linkedin_unvan"), lead.get("konum"), lead.get("linkedin_url")]))
        if anahtar == "oneri":
            return lead.get("notlar") or None
        return None


class TemizlikFiltresi(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(Qt.ItemDataRole.UserRole)
        self._suzgec = "hepsi"

    def suzgec_ayarla(self, kod: str) -> None:
        self._suzgec = kod
        self.invalidateFilter()

    def filterAcceptsRow(self, satir_no, ebeveyn):
        if self._suzgec == "hepsi":
            return True
        satir = self.sourceModel().satir(satir_no)
        if self._suzgec == "kabul_yok":
            return satir["oneri"] in ("kabul_yok", "kabul_bekleniyor")
        if self._suzgec == "cevap":
            return satir["oneri"] in ("cevap", "dokunma")
        return satir["oneri"] == self._suzgec

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Vertical and role == Qt.ItemDataRole.DisplayRole:
            return str(section + 1)
        return super().headerData(section, orientation, role)


class GunSecici(QDialog):
    """'Kaç gündür?' sorusu: her seçeneğin yanında kaç kişiye dokunacağı yazar."""

    def __init__(self, baslik: str, aciklama: str, tur: str, satirlar: list, ebeveyn=None):
        super().__init__(ebeveyn)
        self.secilen = None
        self.setWindowTitle(baslik)
        self.setMinimumWidth(560)
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(24, 22, 24, 18)
        duzen.setSpacing(12)
        duzen.addWidget(etiket(baslik, "bolumBaslik"))
        duzen.addWidget(etiket(aciklama, "ikincil", kaydir=True))
        for gun in GUN_SECENEKLERI[tur]:
            sayi = len(temizlik.hedefler(tur, gun, satirlar))
            satir = QHBoxLayout()
            satir.addWidget(etiket(f"{gun} gün ve üzeri", "alanBaslik"))
            satir.addWidget(etiket(f"{sayi} kişi", "ikincil"))
            satir.addStretch(1)
            dugmecik = dugme("Bunları çıkar", lambda g=gun: self._sec(g), "aksan" if sayi else None)
            dugmecik.setEnabled(bool(sayi))
            satir.addWidget(dugmecik)
            duzen.addLayout(satir)
        duzen.addWidget(etiket(
            "Seçtiklerin sıraya alınır; bot günlük sınıra uyarak tek tek çıkarır, hepsini bir anda yapmaz.",
            "soluk", kaydir=True))
        alt = QHBoxLayout()
        alt.addStretch(1)
        alt.addWidget(dugme("Vazgeç", self.reject))
        duzen.addLayout(alt)

    def _sec(self, gun: int) -> None:
        self.secilen = gun
        self.accept()


class TemizlikSayfasi(Sayfa):
    degisti = Signal()

    def __init__(self):
        super().__init__(
            "Haftalık Temizlik",
            "Yazdığın herkesin takibi burada: kim cevap verdi, kim vermedi, kim isteği kabul bile etmedi. "
            "Cevapsız kalanları buradan listeden çıkarırsın; bot bunu günlük sınıra uyarak tek tek yapar.",
            kaydirilabilir=True,
        )
        self.icerik.addWidget(self._ozet_karti())
        self.icerik.addWidget(self._dugme_karti())
        self.icerik.addWidget(self._tablo_karti(), 1)
        self.icerik.addWidget(self._bilgi_karti())
        self._satirlar = []

    # ---------------- Kartlar ----------------

    def _ozet_karti(self) -> Kart:
        kart = Kart("Özet", "Sayılar, bugüne kadar bağlantı isteği gönderdiğin herkesi kapsar.")
        satir = QHBoxLayout()
        satir.setSpacing(4)
        self.ozet = {}
        for anahtar, ad in OZET:
            self.ozet[anahtar] = Metrik(ad)
            satir.addWidget(self.ozet[anahtar], 1)
        kart.duzen.addLayout(satir)
        self.sirada_yazisi = etiket("", "durumYazi", kaydir=True)
        kart.duzen.addWidget(self.sirada_yazisi)
        return kart

    def _dugme_karti(self) -> Kart:
        kart = Kart("Toplu temizlik", "Kaç kişi birikmiş olursa olsun tek düğmeyle sıraya alırsın.")
        satir = QHBoxLayout()
        satir.setSpacing(10)
        satir.addWidget(dugme("Cevap vermeyenleri çıkar…", lambda: self._toplu("cevapsiz"), "aksan"))
        satir.addWidget(dugme("Kabul etmeyenlerin isteğini geri çek…", lambda: self._toplu("kabul_yok"), "aksan"))
        satir.addWidget(dugme("İş çıkmayanları çıkar", self._is_cikmayan))
        satir.addStretch(1)
        kart.duzen.addLayout(satir)
        self.dugme_bilgisi = etiket("", "bildirim", kaydir=True)
        kart.duzen.addWidget(self.dugme_bilgisi)
        return kart

    def _tablo_karti(self) -> Kart:
        kart = Kart("Yazdığın kişiler", "Satıra sağ tıkla: tek kişiyi sıraya al ya da sıradan çıkar. "
                                        "Kırmızılar 7 günü geçmiş cevapsızlar ve kabul edilmemiş istekler.")
        arac = QHBoxLayout()
        arac.setSpacing(10)
        self.suzgec = QComboBox()
        self.suzgec.setMinimumHeight(38)
        self.suzgec.setMinimumWidth(230)
        for kod, ad in SUZGECLER:
            self.suzgec.addItem(ad, kod)
        self.suzgec.currentIndexChanged.connect(self._suzgecle)
        arac.addWidget(self.suzgec)
        self.sayim = etiket("", "soluk")
        arac.addWidget(self.sayim)
        arac.addStretch(1)
        kart.duzen.addLayout(arac)

        self.model = TemizlikModeli(self)
        self.filtre = TemizlikFiltresi(self)
        self.filtre.setSourceModel(self.model)
        self.tablo = QTableView()
        self.tablo.setModel(self.filtre)
        self.tablo.setSortingEnabled(True)
        self.tablo.sortByColumn(KOLON_SIRASI["oneri"], Qt.SortOrder.DescendingOrder)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setWordWrap(False)
        self.tablo.setShowGrid(False)
        self.tablo.setMinimumHeight(420)
        self.tablo.verticalHeader().setDefaultSectionSize(54)
        self.tablo.setItemDelegateForColumn(KOLON_SIRASI["kisi"], KisiCizici(self.tablo))
        self.tablo.setItemDelegateForColumn(
            KOLON_SIRASI["durum"], RozetCizici(lambda i: DURUM_RENK.get(i.data(DURUM_ROLU), ("#F2F4F7", "#344054")),
                                               self.tablo))
        self.tablo.setItemDelegateForColumn(
            KOLON_SIRASI["oneri"], RozetCizici(lambda i: ONERI_RENKLERI.get(i.data(RENK_ROLU) or "", ONERI_RENKLERI[""]),
                                               self.tablo))
        for anahtar, genislik in SUTUN_GENISLIKLERI.items():
            self.tablo.setColumnWidth(KOLON_SIRASI[anahtar], genislik)
        self.tablo.horizontalHeader().setSectionResizeMode(KOLON_SIRASI["kisi"], QHeaderView.ResizeMode.Stretch)
        self.tablo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tablo.customContextMenuRequested.connect(self._sag_tik)
        kart.duzen.addWidget(self.tablo)
        return kart

    def _bilgi_karti(self) -> Kart:
        kart = Kart("Neyi neden yapıyoruz?")
        for yazi in (
            "Kabul edilmeyen bekleyen istekler: LinkedIn'in hesabı değerlendirirken baktığı asıl sinyal budur. "
            "Kabul edilmeyen istek yığılırsa hesap kısıtlanabilir; 21 günü geçenlerin isteğini geri çekmek gerçekten "
            "riski azaltır. (Geri çekilen kişiye LinkedIn 3 hafta yeni istek göndertmez.)",
            "Kabul edip cevap vermeyenler: bunları silmek hesap riskini azaltmaz ama ağını ve bu listeyi temiz tutar; "
            "kimi takip edeceğin karışmaz.",
            "Görüşme yaptıkların ve müşterilerin hiçbir şekilde temizliğe alınmaz.",
            "Bot hepsini bir anda yapmaz: günlük temizlik sınırına uyar (Ayarlar > Gelişmiş) ve işleri gün içine yayar. "
            "Ayarlar'daki kural açıksa (varsayılan 14 gün cevapsız, 21 gün kabul edilmemiş) sıraya kendisi de alır.",
        ):
            kart.duzen.addWidget(etiket(yazi, "ikincil", kaydir=True))
        return kart

    # ---------------- İşlemler ----------------

    def _secililer(self) -> list:
        satirlar = {self.filtre.mapToSource(i).row() for i in self.tablo.selectionModel().selectedRows()}
        return [self.model.satir(s) for s in sorted(satirlar)]

    def _suzgecle(self) -> None:
        self.filtre.suzgec_ayarla(self.suzgec.currentData())
        self.sayim.setText(f"{self.filtre.rowCount()} / {self.model.rowCount()} kişi gösteriliyor")

    def _toplu(self, tur: str) -> None:
        if tur == "cevapsiz":
            baslik = "Cevap vermeyenleri çıkar"
            aciklama = ("Mesaj gönderdiğin ama cevap vermeyen kişilerin bağlantısı kaldırılır. "
                        "Kaç gündür cevap vermemiş olanları çıkaralım?")
        else:
            baslik = "Kabul etmeyenlerin isteğini geri çek"
            aciklama = ("Gönderdiğin ama kabul edilmemiş bağlantı istekleri geri çekilir. Hesap sağlığı için en "
                        "faydalı temizlik budur. Kaç gündür bekleyenleri geri çekelim?")
        pencere = GunSecici(baslik, aciklama, tur, self._satirlar, self)
        if pencere.exec() and pencere.secilen:
            sayi = temizlik.toplu_siraya_al(tur, pencere.secilen)
            self._bildir(f"{sayi} kişi sıraya alındı. Bot günlük sınıra uyarak tek tek çıkaracak.")
            self.degisti.emit()

    def _is_cikmayan(self) -> None:
        sayi = len(temizlik.hedefler("is_yok", 0, self._satirlar))
        if not sayi:
            bilgi_ver(self, "İş çıkmayan yok", "Şu an 'İlgilenmiyor' diye işaretlediğin, listede duran kimse yok.")
            return
        if not soru_sor(self, "İş çıkmayanları çıkar",
                        f"Cevap verip iş çıkmayan {sayi} kişinin bağlantısı kaldırılsın mı? "
                        "Görüşme yaptıkların ve müşterilerin bu listeye girmez.", "Sıraya al"):
            return
        self._bildir(f"{temizlik.toplu_siraya_al('is_yok')} kişi sıraya alındı.")
        self.degisti.emit()

    def _sag_tik(self, konum) -> None:
        satirlar = self._secililer()
        if not satirlar:
            return
        idler = [s["lead"]["id"] for s in satirlar]
        menu = QMenu(self)

        def ekle(metin, islem):
            menu.addAction(metin).triggered.connect(lambda: islem())

        if len(satirlar) == 1:
            lead = satirlar[0]["lead"]
            ekle("LinkedIn profilini aç", lambda: adres_ac(lead.get("linkedin_url")))
            menu.addSeparator()
        ekle(f"Takipten çıkar: bağlantıyı kaldır ({len(idler)})", lambda: self._siraya(idler, "baglanti_kaldir"))
        ekle(f"İsteği geri çek ({len(idler)})", lambda: self._siraya(idler, "istek_geri_cek"))
        ekle(f"Temizlik sırasından çıkar ({len(idler)})", lambda: self._siradan(idler))
        menu.addSeparator()
        ekle(f"İlgilenmiyor işaretle ({len(idler)})", lambda: self._isaretle(idler))
        menu.exec(self.tablo.viewport().mapToGlobal(konum))

    def _siraya(self, idler: list, tip: str) -> None:
        sayi = temizlik.siraya_al(idler, tip)
        self._bildir(f"{sayi} kişi sıraya alındı." if sayi
                     else "Seçtiklerin zaten sırada ya da dokunulmaz (görüşme/müşteri).")
        self.degisti.emit()

    def _siradan(self, idler: list) -> None:
        self._bildir(f"{temizlik.siradan_cikar(idler)} kişi sıradan çıkarıldı.")
        self.degisti.emit()

    def _isaretle(self, idler: list) -> None:
        servis.durum_isaretle(idler, "ilgilenmiyor")
        self._bildir(f"{len(idler)} kişi 'İlgilenmiyor' işaretlendi.")
        self.degisti.emit()

    def _bildir(self, metin: str) -> None:
        self.dugme_bilgisi.setText(metin)

    # ---------------- Yenileme ----------------

    def yenile(self, veri: dict) -> None:
        self._satirlar = temizlik.tablo(veri["leadler"])
        self.model.verileri_ayarla(self._satirlar)
        sayilar = temizlik.sayilar(self._satirlar)
        for anahtar, _ in OZET:
            self.ozet[anahtar].ayarla(sayilar[anahtar])
        durum = veri["durum"]
        sirada = sayilar["sirada"]
        limit = veri["ayarlar"]["limitler"].get("temizlik_gunluk", 20)
        if sirada:
            self.sirada_yazisi.setText(
                f"Sırada {sirada} kişi var; bot bugün {durum.get('temizlik_son_gun', 0)}/{limit} temizlik yaptı. "
                "Otomasyon çalışmıyorsa sıra beklemede kalır."
            )
        else:
            self.sirada_yazisi.setText(f"Sırada bekleyen temizlik yok. Bot bugün "
                                       f"{durum.get('temizlik_son_gun', 0)}/{limit} temizlik yaptı.")
        self._suzgecle()
