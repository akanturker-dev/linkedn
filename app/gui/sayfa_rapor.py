from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView, QGridLayout, QHBoxLayout, QHeaderView, QProgressBar, QTableWidget, QTableWidgetItem,
)

from ..kampanyalar import HIZMETLER
from .bilesenler import Kart, Sayfa, duzeni_temizle, etiket

# Bir gruba bundan az mesaj gittiyse cevap orani sans eseri yuksek/dusuk cikabilir; kazanan ilan edilmez
EN_AZ_MESAJ = 20
KOLONLAR = [
    ("kampanya", "Kampanya"), ("hizmet", "Hizmet"), ("bulunan", "Bulunan"), ("uygun", "DM'e uygun"),
    ("istek", "İstek"), ("kabul", "Kabul"), ("mesaj", "Mesaj"), ("cevap", "Cevap"), ("gorusme", "Görüşme"),
    ("musteri", "Müşteri"),
]
SAYI_KOLONLARI = [anahtar for anahtar, _ in KOLONLAR[2:]]
# Yuzde, bir onceki asamaya gore donusumdur
ORAN_TABANI = {"uygun": "bulunan", "istek": "uygun", "kabul": "istek", "mesaj": "kabul", "cevap": "mesaj",
               "gorusme": "cevap", "musteri": "gorusme"}
SATIR_YUKSEKLIGI = 46


def yuzde(pay: int, payda: int) -> str:
    return f"%{round(100 * pay / payda)}" if payda else "-"


def bant_adi(bant) -> str:
    return f"{bant.replace('-', '–')} çalışan" if bant else "Bilinmiyor"


class RaporSayfasi(Sayfa):
    def __init__(self):
        super().__init__(
            "Rapor",
            "Hangi sektör cevap veriyor, görüşmeye dönüyor ve para ödüyor? İlk testte her gruptan yaklaşık 100 kişiye "
            "yazılır; kazanan gruba yüklenirsin.",
            kaydirilabilir=True,
        )
        ust = QHBoxLayout()
        ust.setSpacing(18)
        self.one_cikanlar = {}
        for anahtar, baslik in (("cevap", "En çok cevap veren grup"), ("gorusme", "En çok görüşmeye dönen"),
                                ("musteri", "Para ödeyen")):
            kart = Kart(baslik)
            deger, aciklama = etiket("", "vurgu", kaydir=True), etiket("", "ikincil", kaydir=True)
            kart.duzen.addWidget(deger)
            kart.duzen.addWidget(aciklama)
            kart.duzen.addStretch(1)
            ust.addWidget(kart, 1)
            self.one_cikanlar[anahtar] = (deger, aciklama)
        self.icerik.addLayout(ust)

        tablo_karti = Kart("Kampanyaların karşılaştırması",
                           "Sayının yanındaki yüzde, bir önceki sütuna göre dönüşüm oranıdır (ör. cevap / mesaj).")
        self.tablo = QTableWidget(0, len(KOLONLAR))
        self.tablo.setHorizontalHeaderLabels([ad for _, ad in KOLONLAR])
        self.tablo.verticalHeader().hide()
        self.tablo.verticalHeader().setDefaultSectionSize(SATIR_YUKSEKLIGI)
        self.tablo.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tablo.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.tablo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tablo.setShowGrid(False)
        self.tablo.setAlternatingRowColors(True)
        self.tablo.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        baslik = self.tablo.horizontalHeader()
        baslik.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        baslik.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        baslik.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        tablo_karti.duzen.addWidget(self.tablo)
        self.icerik.addWidget(tablo_karti)

        bant_karti = Kart("Şirket büyüklüğüne göre", "Gönderilen bağlantı isteklerinin büyüklük dilimlerine dağılımı. "
                                                     "Hedef paylar Ayarlar sayfasından değişir.")
        self.bant_izgarasi = QGridLayout()
        self.bant_izgarasi.setHorizontalSpacing(22)
        self.bant_izgarasi.setVerticalSpacing(12)
        bant_karti.duzen.addLayout(self.bant_izgarasi)
        self.bant_bos = etiket("Henüz bağlantı isteği gönderilmedi.", "soluk")
        bant_karti.duzen.addWidget(self.bant_bos)
        self.icerik.addWidget(bant_karti)

        nasil = Kart("Cevap, görüşme ve müşteri nasıl sayılır?")
        nasil.duzen.addWidget(etiket(
            "Bot LinkedIn'deki cevapları okumaz. Biri cevap verince Adaylar sayfasında o kişiye sağ tıklayıp "
            "'Cevap verdi', görüşme yapınca 'Görüşme yapıldı', anlaşınca 'Müşteri oldu' seç. Rapor bu işaretlerle "
            "hesaplanır; mesajdan sonra 'İlgilenmiyor' işaretlenen kişi de cevap vermiş sayılır.",
            "ikincil", kaydir=True))
        self.icerik.addWidget(nasil)
        self.icerik.addStretch(1)
        self._bant_imzasi = None
        self._bant_satirlari = {}

    def yenile(self, veri: dict) -> None:
        satirlar = veri["rapor"]
        kazanan_id = self._one_cikanlari_yaz(satirlar)
        self._tabloyu_yaz(satirlar, kazanan_id)
        self._bantlari_yaz(veri["bantlar"])

    def _one_cikanlari_yaz(self, satirlar: list):
        """Uc ozet kartini doldurur; en yuksek cevap oranli kampanyanin kimligini dondurur."""
        deger, aciklama = self.one_cikanlar["cevap"]
        yeterli = [s for s in satirlar if s["mesaj"] >= EN_AZ_MESAJ]
        kazanan = max(yeterli, key=lambda s: (s["cevap"] / s["mesaj"], s["cevap"]), default=None)
        if kazanan:
            deger.setText(kazanan["kampanya"]["ad"])
            aciklama.setText(f"{kazanan['mesaj']} mesajdan {kazanan['cevap']} cevap "
                             f"({yuzde(kazanan['cevap'], kazanan['mesaj'])}).")
        else:
            en_cok = max(satirlar, key=lambda s: s["mesaj"], default=None)
            deger.setText("Henüz erken")
            metin = f"Oranın anlamlı olması için bir gruba en az {EN_AZ_MESAJ} mesaj gitmeli."
            if en_cok and en_cok["mesaj"]:
                metin += f" En çok mesaj giden: {en_cok['kampanya']['ad']} ({en_cok['mesaj']})."
            aciklama.setText(metin)

        deger, aciklama = self.one_cikanlar["gorusme"]
        en_iyi = max(satirlar, key=lambda s: (s["gorusme"], -s["mesaj"]), default=None)
        if en_iyi and en_iyi["gorusme"]:
            deger.setText(en_iyi["kampanya"]["ad"])
            aciklama.setText(f"{en_iyi['gorusme']} görüşme, {en_iyi['mesaj']} mesajdan "
                             f"({yuzde(en_iyi['gorusme'], en_iyi['mesaj'])}).")
        else:
            deger.setText("Henüz görüşme yok")
            aciklama.setText("Görüşme yapınca Adaylar sayfasında kişiyi 'Görüşme yapıldı' diye işaretle.")

        deger, aciklama = self.one_cikanlar["musteri"]
        en_iyi = max(satirlar, key=lambda s: (s["musteri"], -s["mesaj"]), default=None)
        if en_iyi and en_iyi["musteri"]:
            deger.setText(en_iyi["kampanya"]["ad"])
            aciklama.setText(f"{en_iyi['musteri']} müşteri, {en_iyi['mesaj']} mesajdan.")
        else:
            deger.setText("Henüz müşteri yok")
            aciklama.setText("Anlaşınca kişiyi 'Müşteri oldu' diye işaretle; para ödeyen sektör burada görünür.")
        return kazanan["kampanya"]["id"] if kazanan else None

    def _tabloyu_yaz(self, satirlar: list, kazanan_id) -> None:
        self.tablo.setRowCount(len(satirlar))
        for sira, satir in enumerate(satirlar):
            kampanya = satir["kampanya"]
            hucreler = {
                "kampanya": kampanya["ad"],
                "hizmet": " + ".join(HIZMETLER.get(h, h) for h in kampanya["hizmetler"]) or "-",
            }
            for anahtar in SAYI_KOLONLARI:
                taban = ORAN_TABANI.get(anahtar)
                if taban and satir[taban]:
                    hucreler[anahtar] = f"{satir[anahtar]}  ·  {yuzde(satir[anahtar], satir[taban])}"
                else:
                    hucreler[anahtar] = str(satir[anahtar])
            for sutun, (anahtar, _) in enumerate(KOLONLAR):
                oge = QTableWidgetItem(hucreler[anahtar])
                if anahtar in SAYI_KOLONLARI:
                    oge.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                if anahtar == "kampanya" and kampanya["id"] == kazanan_id:
                    kalin = QFont(self.tablo.font())
                    kalin.setWeight(QFont.Weight.Bold)
                    oge.setFont(kalin)
                    oge.setToolTip("En yüksek cevap oranı")
                self.tablo.setItem(sira, sutun, oge)
        yukseklik = self.tablo.horizontalHeader().sizeHint().height() + SATIR_YUKSEKLIGI * max(1, len(satirlar)) + 6
        self.tablo.setFixedHeight(yukseklik)

    def _bantlari_yaz(self, bantlar: list) -> None:
        self.bant_bos.setVisible(sum(b["istek"] for b in bantlar) == 0)
        imza = [b["bant"] for b in bantlar]
        if imza != self._bant_imzasi:
            self._bant_imzasi = imza
            duzeni_temizle(self.bant_izgarasi)
            self._bant_satirlari = {}
            for sutun, baslik in enumerate(("Şirket büyüklüğü", "Gerçekleşen pay", "", "İstek", "Kabul", "Cevap")):
                self.bant_izgarasi.addWidget(etiket(baslik, "soluk"), 0, sutun)
            for sira, bant in enumerate(bantlar, start=1):
                cubuk = QProgressBar()
                cubuk.setTextVisible(False)
                cubuk.setMaximum(100)
                parcalar = (etiket(bant_adi(bant["bant"]), "alanBaslik"), etiket("", "ikincil"), cubuk,
                            etiket(""), etiket(""), etiket(""))
                for sutun, parca in enumerate(parcalar):
                    self.bant_izgarasi.addWidget(parca, sira, sutun)
                self._bant_satirlari[bant["bant"]] = parcalar[1:]
            self.bant_izgarasi.setColumnStretch(2, 1)
        for bant in bantlar:
            pay, cubuk, istek, kabul, cevap = self._bant_satirlari[bant["bant"]]
            pay.setText(f"%{bant['pay']}  (hedef %{bant['hedef']})" if bant["bant"] else f"%{bant['pay']}")
            cubuk.setValue(bant["pay"])
            istek.setText(str(bant["istek"]))
            kabul.setText(f"{bant['kabul']}  ·  {yuzde(bant['kabul'], bant['istek'])}")
            cevap.setText(str(bant["cevap"]))
