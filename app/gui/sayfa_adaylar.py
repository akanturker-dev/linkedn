import os
from datetime import datetime

from PySide6.QtCore import QItemSelectionModel, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QHeaderView, QLineEdit,
    QMenu, QPlainTextEdit, QTableView, QVBoxLayout,
)

from .. import db, servis
from ..disa_aktar import excele_aktar
from ..etiketler import DURUM_ETIKET
from .bilesenler import Sayfa, adres_ac, bilgi_ver, dugme, etiket, soru_sor
from .tablo_modeli import (
    KOLON_SIRASI, AdayFiltresi, AdayModeli, KisiCizici, RozetCizici, durum_rengi, paylasim_metni, puan_rengi_bulucu,
    sira_metni, tarih_metni,
)

# Kisi sutunu kalan genisligi doldurur; kampanya adlari ("Güzellik ve estetik merkezleri") ic boslukla birlikte sigsin
SUTUN_GENISLIKLERI = {"isletme_adi": 200, "sirket_boyutu": 95, "puan": 80, "kampanya": 235,
                      "son_paylasim": 125, "tazelik": 190, "durum": 165, "son_islem_tarihi": 145}
TEMAS_EDILMIS = ("istek_gonderildi", "baglanti_kabul", "mesaj_gonderildi", "cevap_verdi", "gorusme", "musteri")
MANUEL_ISARETLER = [("cevap_verdi", "Cevap verdi"), ("gorusme", "Görüşme yapıldı"), ("musteri", "Müşteri oldu"),
                    ("ilgilenmiyor", "İlgilenmiyor")]
BOS_REHBER = (
    "Henüz aday yok. Sol menüden 'LinkedIn'e Giriş Yap', ardından 'Otomasyonu Başlat'a bas.\n"
    "Bot çalışma saatlerinde Kampanyalar sayfasındaki gruplar için LinkedIn'de karar verici arar, "
    "şirket büyüklüğüne ve son paylaşımlarına bakıp puanlar."
)


class AdayDetayi(QDialog):
    def __init__(self, lead: dict, kampanya_adi: str, esik: int, ebeveyn=None):
        super().__init__(ebeveyn)
        self.lead, self.secilen_durum = lead, None
        self.setWindowTitle(lead.get("linkedin_ad") or "Aday")
        self.setMinimumWidth(680)
        duzen = QVBoxLayout(self)
        duzen.setContentsMargins(24, 22, 24, 22)
        duzen.setSpacing(14)
        baslik = etiket(lead.get("linkedin_ad") or "Aday", "bolumBaslik")
        duzen.addWidget(baslik)
        if lead.get("linkedin_unvan"):
            duzen.addWidget(etiket(lead["linkedin_unvan"], "ikincil", kaydir=True))

        puan = "-" if lead.get("puan") is None else f"{lead['puan']} (eşik {esik})"
        bilgi = QFormLayout()
        bilgi.setHorizontalSpacing(18)
        bilgi.setVerticalSpacing(8)
        for satir_basligi, deger in (
            ("Rol", lead.get("linkedin_rol") or "-"),
            ("Şirket", lead.get("isletme_adi") or "okunamadı"),
            ("Çalışan sayısı", lead.get("sirket_boyutu") or "bilinmiyor"),
            ("Şirket sektörü", lead.get("sirket_sektoru") or "-"),
            ("Konum", lead.get("konum") or "-"),
            ("Web sitesi", lead.get("website") or "bulunamadı"),
            ("Google", sira_metni(lead)),
            ("Son paylaşım", paylasim_metni(lead.get("son_paylasim_gun"))),
            ("Puan", puan),
            ("Puanın gerekçesi", lead.get("puan_detay") or "-"),
            ("Kampanya", kampanya_adi or "-"),
            ("Durum", DURUM_ETIKET.get(lead["durum"], lead["durum"])),
            ("Son işlem", tarih_metni(lead.get("son_islem_tarihi"))),
        ):
            deger_yazisi = etiket(str(deger), kaydir=True)
            deger_yazisi.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            bilgi.addRow(etiket(satir_basligi, "ikincil"), deger_yazisi)
        duzen.addLayout(bilgi)

        self.url_kutusu = QLineEdit(lead.get("linkedin_url") or "")
        self.not_kutusu = QPlainTextEdit(lead.get("notlar") or "")
        self.not_kutusu.setFixedHeight(90)
        form = QFormLayout()
        form.addRow("LinkedIn profili", self.url_kutusu)
        form.addRow("Notlar", self.not_kutusu)
        duzen.addLayout(form)

        duzen.addWidget(etiket("Mesajdan sonra ne oldu?", "ikincil"))
        isaretler = QHBoxLayout()
        for kod, ad in MANUEL_ISARETLER:
            isaretler.addWidget(dugme(ad, lambda k=kod: self._isaretle(k)))
        isaretler.addStretch(1)
        duzen.addLayout(isaretler)

        alt = QHBoxLayout()
        alt.addWidget(dugme("LinkedIn'de aç", lambda: adres_ac(lead.get("linkedin_url"))))
        alt.addStretch(1)
        alt.addWidget(dugme("Vazgeç", self.reject))
        kaydet = dugme("Kaydet", self._kaydet, "aksan")
        kaydet.setDefault(True)
        alt.addWidget(kaydet)
        duzen.addLayout(alt)

    def _isaretle(self, durum: str) -> None:
        self.secilen_durum = durum
        self._kaydet()

    def _kaydet(self) -> None:
        url = self.url_kutusu.text().strip()
        if url and "linkedin.com/" not in url:
            bilgi_ver(self, "Geçersiz adres", "Bu bir LinkedIn adresi değil. Örnek: https://www.linkedin.com/in/ahmet-yilmaz",
                      "uyari")
            return
        self.accept()

    def degerler(self) -> dict:
        degerler = {"linkedin_url": self.url_kutusu.text().strip(), "notlar": self.not_kutusu.toPlainText()}
        if self.secilen_durum:
            degerler["durum"] = self.secilen_durum
        return degerler


class AdaylarSayfasi(Sayfa):
    degisti = Signal()

    def __init__(self):
        super().__init__("Adaylar", "LinkedIn'de bulunan karar vericiler. Puanı eşiği geçenlere (DM'e hazır) istek ve mesaj gider; "
                                    "satırın üstünde sağ tıkla ya da çift tıkla.")
        self.baslik_sag.addWidget(dugme("Excel'e Aktar", self._excele_aktar))

        arac = QHBoxLayout()
        arac.setSpacing(10)
        self.arama_kutusu = QLineEdit()
        self.arama_kutusu.setPlaceholderText("Kişi, şirket, rol, unvan, konum veya not ara...")
        self.arama_kutusu.setClearButtonEnabled(True)
        self.durum_secici = QComboBox()
        self.durum_secici.addItem("Bütün durumlar", "")
        for kod, ad in DURUM_ETIKET.items():
            self.durum_secici.addItem(ad, kod)
        self.kampanya_secici = QComboBox()
        self.kampanya_secici.addItem("Bütün kampanyalar", None)
        self.sadece_uygun = QCheckBox("Sadece DM'e uygunlar")
        for kutu in (self.durum_secici, self.kampanya_secici):
            kutu.setMinimumHeight(38)
            kutu.setMinimumWidth(200)
        self.arama_kutusu.textChanged.connect(self._filtrele)
        self.durum_secici.currentIndexChanged.connect(self._filtrele)
        self.kampanya_secici.currentIndexChanged.connect(self._filtrele)
        self.sadece_uygun.toggled.connect(self._filtrele)
        arac.addWidget(self.arama_kutusu, 1)
        arac.addWidget(self.durum_secici)
        arac.addWidget(self.kampanya_secici)
        arac.addWidget(self.sadece_uygun)
        self.icerik.addLayout(arac)

        self.model = AdayModeli(self)
        self.filtre = AdayFiltresi(self)
        self.filtre.setSourceModel(self.model)
        self.tablo = QTableView()
        self.tablo.setModel(self.filtre)
        self.tablo.setSortingEnabled(True)
        self.tablo.sortByColumn(KOLON_SIRASI["son_islem_tarihi"], Qt.SortOrder.DescendingOrder)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tablo.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setWordWrap(False)
        self.tablo.setShowGrid(False)
        self.tablo.verticalHeader().setDefaultSectionSize(54)
        self.tablo.setItemDelegateForColumn(KOLON_SIRASI["kisi"], KisiCizici(self.tablo))
        self.tablo.setItemDelegateForColumn(KOLON_SIRASI["durum"], RozetCizici(durum_rengi, self.tablo))
        self.tablo.setItemDelegateForColumn(KOLON_SIRASI["puan"], RozetCizici(puan_rengi_bulucu(self.model), self.tablo))
        for anahtar, genislik in SUTUN_GENISLIKLERI.items():
            self.tablo.setColumnWidth(KOLON_SIRASI[anahtar], genislik)
        self.tablo.horizontalHeader().setSectionResizeMode(KOLON_SIRASI["kisi"], QHeaderView.ResizeMode.Stretch)
        self.tablo.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tablo.customContextMenuRequested.connect(self._sag_tik)
        self.tablo.doubleClicked.connect(lambda i: self._detay_ac(self.model.lead(self.filtre.mapToSource(i).row())))
        silme = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete), self.tablo)
        silme.activated.connect(self._sil)
        self.icerik.addWidget(self.tablo, 1)

        self.alt_bilgi = etiket("", "soluk")
        self.bos_rehber = etiket(BOS_REHBER, "ikincil", kaydir=True)
        self.bos_rehber.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icerik.addWidget(self.bos_rehber)
        self.icerik.addWidget(self.alt_bilgi)
        self._kampanya_imzasi = None

    def yenile(self, veri: dict) -> None:
        kampanyalar = veri["kampanyalar"]
        imza = [(k["id"], k["ad"]) for k in kampanyalar]
        if imza != self._kampanya_imzasi:
            self._kampanya_imzasi = imza
            secili = self.kampanya_secici.currentData()
            self.kampanya_secici.blockSignals(True)
            self.kampanya_secici.clear()
            self.kampanya_secici.addItem("Bütün kampanyalar", None)
            for kampanya_id, ad in imza:
                self.kampanya_secici.addItem(ad, kampanya_id)
            indeks = self.kampanya_secici.findData(secili)
            self.kampanya_secici.setCurrentIndex(max(0, indeks))
            self.kampanya_secici.blockSignals(False)

        secili_idler = {l["id"] for l in self._secililer()}
        kaydirma = self.tablo.verticalScrollBar().value()
        self.model.verileri_ayarla(veri["leadler"], {k["id"]: k["ad"] for k in kampanyalar},
                                   veri["ayarlar"]["puanlama"]["esik"])
        if secili_idler and not self.tablo.selectionModel().hasSelection():
            bayrak = QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows
            for satir in range(self.filtre.rowCount()):
                indeks = self.filtre.index(satir, 0)
                if self.model.lead(self.filtre.mapToSource(indeks).row())["id"] in secili_idler:
                    self.tablo.selectionModel().select(indeks, bayrak)
        self.tablo.verticalScrollBar().setValue(kaydirma)
        self.bos_rehber.setVisible(not veri["leadler"])
        self.alt_bilgi.setText(f"{self.filtre.rowCount()} / {len(veri['leadler'])} aday gösteriliyor")

    def _filtrele(self) -> None:
        self.filtre.filtre_ayarla(self.arama_kutusu.text(), self.durum_secici.currentData() or "",
                                  self.kampanya_secici.currentData(), self.sadece_uygun.isChecked())
        self.alt_bilgi.setText(f"{self.filtre.rowCount()} / {self.model.rowCount()} aday gösteriliyor")

    def _secililer(self) -> list:
        satirlar = {self.filtre.mapToSource(i).row() for i in self.tablo.selectionModel().selectedRows()}
        return [self.model.lead(s) for s in sorted(satirlar)]

    def _detay_ac(self, lead: dict) -> None:
        pencere = AdayDetayi(lead, self.model.kampanya_adlari.get(lead.get("kampanya_id")), self.model.esik, self)
        if pencere.exec():
            servis.lead_guncelle(lead["id"], pencere.degerler())
            self.degisti.emit()

    def _sag_tik(self, konum) -> None:
        leadler = self._secililer()
        if not leadler:
            return
        menu = QMenu(self)

        def ekle(metin, islem):
            menu.addAction(metin).triggered.connect(lambda: islem())

        if len(leadler) == 1:
            lead = leadler[0]
            ekle("Detayı aç", lambda: self._detay_ac(lead))
            ekle("LinkedIn profilini aç", lambda: adres_ac(lead.get("linkedin_url")))
            if lead.get("sirket_linkedin"):
                ekle("Şirketin LinkedIn sayfasını aç", lambda: adres_ac(lead["sirket_linkedin"]))
            if lead.get("website"):
                ekle("Web sitesini aç", lambda: adres_ac(lead["website"]))
            menu.addSeparator()
        for kod, ad in MANUEL_ISARETLER:
            ekle(f"{ad} ({len(leadler)})", lambda k=kod: self._isaretle(leadler, k))
        menu.addSeparator()
        ekle(f"Baştan değerlendir ({len(leadler)})", lambda: self._isaretle(leadler, "yeni"))
        ekle(f"Sil ({len(leadler)})", self._sil)
        menu.exec(self.tablo.viewport().mapToGlobal(konum))

    def _isaretle(self, leadler: list, durum: str) -> None:
        servis.durum_isaretle([l["id"] for l in leadler], durum)
        self.degisti.emit()

    def _sil(self) -> None:
        leadler = self._secililer()
        if not leadler:
            return
        soru = f"{len(leadler)} aday silinsin mi? Bu işlem geri alınamaz."
        if any(l["durum"] in TEMAS_EDILMIS for l in leadler):
            soru += ("\n\nBazılarına LinkedIn'den zaten yazıldı. Silersen ve kişi ileride tekrar bulunursa ona yeniden "
                     "yazılabilir; bunun yerine 'İlgilenmiyor' işaretlemek daha güvenli.")
        if not soru_sor(self, "Adayları sil", soru, "Sil"):
            return
        for lead in leadler:
            db.lead_sil(lead["id"])
        self.degisti.emit()

    def _excele_aktar(self) -> None:
        masaustu = os.path.join(os.path.expanduser("~"), "Desktop")
        varsayilan = os.path.join(masaustu, f"LinkedIn adaylar {datetime.now():%Y-%m-%d}.xlsx")
        yol, _ = QFileDialog.getSaveFileName(self, "Excel'e aktar", varsayilan, "Excel dosyası (*.xlsx)")
        if not yol:
            return
        gorunen = [self.model.lead(self.filtre.mapToSource(self.filtre.index(s, 0)).row()) for s in range(self.filtre.rowCount())]
        try:
            excele_aktar(yol, gorunen, self.model.kampanya_adlari)
        except PermissionError:
            bilgi_ver(self, "Aktarılamadı", "Dosya şu an açık olabilir. Excel'de açıksa kapatıp tekrar dene.", "uyari")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(yol))
