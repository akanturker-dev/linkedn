from math import ceil

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QGridLayout, QHBoxLayout, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget,
)

from .. import engine, servis
from ..config import load_settings
from ..linkedin_bot import NOT_KARAKTER_SINIRI
from ..puanlama import ulasilabilir_en_yuksek
from .bilesenler import Kart, Sayfa, adres_ac, dugme, etiket, hap_ayarla, sayi_kutusu
from .tema import yeniden_boya

SERPER_ADRESI = "https://serper.dev"
PUAN_SATIRLARI = [
    ("rol_uyumlu", "Doğru muhatap: unvanı şirketin büyüklüğüne uyuyor"),
    ("rol_diger", "Karar verici ama bu büyüklük için ideal değil"),
    ("boyut_11_200", "Şirket 11–200 çalışan (tatlı nokta)"),
    ("boyut_201_500", "Şirket 201–500 çalışan"),
    ("aktif_30_gun", "Son 30 günde LinkedIn'de paylaşım yapmış"),
    ("web_sitesi", "Şirketin web sitesi var"),
    ("esik", "DM eşiği: en az bu kadar puan alana yazılır"),
]
LIMIT_SATIRLARI = [
    ("baglanti_saatlik", "Bağlantı isteği / saat", 30),
    ("baglanti_gunluk", "Bağlantı isteği / gün", 100),
    ("baglanti_haftalik", "Bağlantı isteği / hafta", 300),
    ("mesaj_gunluk", "Mesaj / gün", 100),
    ("linkedin_arama_gunluk", "LinkedIn araması / gün", 100),
    ("degerlendirme_gunluk", "Aday değerlendirme / gün", 200),
    ("temizlik_gunluk", "Temizlik (çıkarma) / gün", 100),
]
DAGILIM_BANTLARI = [("11-50", "11–50 çalışan"), ("51-200", "51–200 çalışan"), ("201-500", "201–500 çalışan")]
ILK_TEST_KISI = 600  # 6 grup x 100 kisi


class AyarlarSayfasi(Sayfa):
    kaydedildi = Signal(dict)

    def __init__(self, ayarlar: dict):
        super().__init__(
            "Ayarlar",
            "Normal kullanımda buraya girmene gerek yok: sektör ve mesaj Mesaj Gönder sayfasında. Burada çalışma "
            "saatleri, günlük sınırlar ve istersen gelişmiş kurallar var. Değişiklikler 'Ayarları Kaydet'e basınca "
            "geçerli olur.",
            kaydirilabilir=True,
            alt_cubuk=True,
        )
        self.icerik.addWidget(self._tempo_karti())
        satir = QHBoxLayout()
        self.gelismis_dugmesi = dugme("Gelişmiş ayarları göster", self._gelismisi_degistir)
        satir.addWidget(self.gelismis_dugmesi)
        satir.addStretch(1)
        self.icerik.addLayout(satir)
        self.icerik.addWidget(etiket(
            "Gelişmiş kısımda puanlama kuralları, şirket büyüklüğü dağılımı, aday kontrolleri, bağlantı isteği notu "
            "ve Google anahtarı var. Hiç dokunmasan da asistan çalışır.", "soluk", kaydir=True))
        # Gelismis ayarlar kapali baslar: gunluk kullanimda sadece saatler ve sinirlar gerekiyor
        self.gelismis = QWidget()
        kolonlar = QHBoxLayout(self.gelismis)
        kolonlar.setContentsMargins(0, 0, 0, 0)
        kolonlar.setSpacing(18)
        for kartlar in ((self._puanlama_karti(), self._dagilim_karti(), self._temizlik_karti()),
                        (self._kontrol_karti(), self._not_karti(), self._google_karti())):
            kolon = QVBoxLayout()
            kolon.setSpacing(18)
            for kart in kartlar:
                kolon.addWidget(kart)
            kolon.addStretch(1)
            kolonlar.addLayout(kolon, 1)
        self.gelismis.setVisible(False)
        self.icerik.addWidget(self.gelismis)

        self.alt.addWidget(dugme("Ayarları Kaydet", self.kaydet, "aksan", buyuk=True))
        self.alt.addWidget(dugme("Değişiklikleri geri al", self._geri_al))
        self.bildirim = etiket("", "bildirim", kaydir=True)
        self.alt.addWidget(self.bildirim, 1)
        self._forma_yukle(ayarlar)

    def _gelismisi_degistir(self) -> None:
        gorunur = not self.gelismis.isVisible()
        self.gelismis.setVisible(gorunur)
        self.gelismis_dugmesi.setText("Gelişmiş ayarları gizle" if gorunur else "Gelişmiş ayarları göster")

    # ---------------- Kartlar ----------------

    def _puanlama_karti(self) -> Kart:
        kart = Kart("Puanlama", "Her aday puanlanır; yalnızca eşiği geçenlere bağlantı isteği ve mesaj gider. "
                                "Türkiye şartı zorunlu: arama sadece Türkiye'deki kişileri getirir.")
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(16)
        izgara.setVerticalSpacing(10)
        self.puan_kutulari = {}
        for satir, (anahtar, ad) in enumerate(PUAN_SATIRLARI):
            esik_mi = anahtar == "esik"
            kutu = sayi_kutusu(1 if esik_mi else 0, 30 if esik_mi else 10, " puan")
            izgara.addWidget(etiket(ad, "alanBaslik" if esik_mi else None, kaydir=True), satir, 0)
            izgara.addWidget(kutu, satir, 1)
            kutu.valueChanged.connect(self._puan_ozetini_guncelle)
            self.puan_kutulari[anahtar] = kutu
        izgara.setColumnStretch(0, 1)
        kart.duzen.addLayout(izgara)
        self.puan_ornegi = etiket("", "ikincil", kaydir=True)
        self.puan_ozeti = etiket("", "durumYazi", kaydir=True)
        kart.duzen.addWidget(self.puan_ornegi)
        kart.duzen.addWidget(self.puan_ozeti)
        kart.duzen.addWidget(etiket(
            "Doğru muhatap kuralı: 1–20 çalışan kurucu ya da sahip · 20–100 kurucu, genel müdür, pazarlama müdürü · "
            "100–500 pazarlama direktörü, pazarlama lideri, dijital pazarlama müdürü · 500+ departman yöneticileri.",
            "soluk", kaydir=True))
        return kart

    def _dagilim_karti(self) -> Kart:
        kart = Kart("Şirket büyüklüğü dağılımı", "Bağlantı istekleri bu paylara göre dağıtılır: hangi dilim payının "
                    "gerisindeyse sıradaki istek oradan gider. Önce kampanyalar arasında denge kurulur, her grup eşit test edilir.")
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(16)
        izgara.setVerticalSpacing(10)
        self.dagilim_kutulari = {}
        for satir, (bant, ad) in enumerate(DAGILIM_BANTLARI):
            kutu = sayi_kutusu(0, 100)
            kutu.setPrefix("%")
            kutu.valueChanged.connect(self._dagilim_ozetini_guncelle)
            izgara.addWidget(etiket(ad), satir, 0)
            izgara.addWidget(kutu, satir, 1)
            self.dagilim_kutulari[bant] = kutu
        izgara.setColumnStretch(0, 1)
        kart.duzen.addLayout(izgara)
        self.dagilim_ozeti = etiket("", "durumYazi", kaydir=True)
        kart.duzen.addWidget(self.dagilim_ozeti)
        return kart

    def _temizlik_karti(self) -> Kart:
        kart = Kart("Haftalık temizlik kuralları", "Bot bu süreler dolunca kişileri kendiliğinden temizlik sırasına "
                                                   "alır. 0 yazarsan o kural kapanır, temizliği sen elle yaparsın "
                                                   "(Temizlik sayfası).")
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(16)
        izgara.setVerticalSpacing(10)
        self.temizlik_kutulari = {}
        for satir, (anahtar, ad) in enumerate((
            ("cevapsiz_gun", "Mesaja kaç gün cevap gelmezse çıkar"),
            ("bekleyen_istek_gun", "İstek kaç gündür kabul edilmezse geri çek"),
        )):
            kutu = sayi_kutusu(0, 120, " gün")
            izgara.addWidget(etiket(ad, kaydir=True), satir, 0)
            izgara.addWidget(kutu, satir, 1)
            self.temizlik_kutulari[anahtar] = kutu
        izgara.setColumnStretch(0, 1)
        kart.duzen.addLayout(izgara)
        self.is_cikmayan_kutusu = QCheckBox("Cevap verip iş çıkmayanları (İlgilenmiyor) da çıkar")
        kart.duzen.addWidget(self.is_cikmayan_kutusu)
        kart.duzen.addWidget(etiket(
            "Asıl faydası olan kural ikincisi: kabul edilmemiş istek yığılması LinkedIn'in hesaba baktığı sinyaldir. "
            "Sıraya alınanlar bir anda değil, günlük temizlik sınırına uyularak çıkarılır.", "soluk", kaydir=True))
        return kart

    def _kontrol_karti(self) -> Kart:
        kart = Kart("Aday kontrolleri", "Puan için bot her adayın LinkedIn'deki şirket sayfasına ve gerekirse son "
                                        "paylaşımlarına bakar.")
        self.sirket_kutusu = QCheckBox("Şirket sayfasına bak: çalışan sayısı ve web sitesi")
        self.aktivite_kutusu = QCheckBox("Son paylaşımına bak (yalnızca puanı değiştirecekse)")
        for kutu in (self.sirket_kutusu, self.aktivite_kutusu):
            kutu.toggled.connect(self._puan_ozetini_guncelle)
            kart.duzen.addWidget(kutu)
        kart.duzen.addWidget(etiket(
            "Kapatırsan LinkedIn'de daha az sayfa açılır ama o puanlar alınamaz: şirket kontrolü kapalıyken büyüklük "
            "puanı ve büyüklük filtresi, paylaşım kontrolü kapalıyken 'son 30 gün' puanı çalışmaz.", "soluk", kaydir=True))
        return kart

    def _tempo_karti(self) -> Kart:
        kart = Kart("Çalışma saatleri ve sınırlar", "LinkedIn'in spam saymaması için bot bu sınırların altında kalır "
                                                    "ve işleri güne yayar.")
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(14)
        izgara.setVerticalSpacing(10)
        self.saat_bas = sayi_kutusu(0, 23, ":00")
        self.saat_bit = sayi_kutusu(1, 24, ":00")
        self.limit_kutulari = {anahtar: sayi_kutusu(1, en_fazla) for anahtar, _, en_fazla in LIMIT_SATIRLARI}
        ciftler = [("Başlangıç saati", self.saat_bas), ("Bitiş saati", self.saat_bit)]
        ciftler += [(ad, self.limit_kutulari[anahtar]) for anahtar, ad, _ in LIMIT_SATIRLARI]
        for sira, (ad, kutu) in enumerate(ciftler):
            satir, sutun = divmod(sira, 2)
            izgara.addWidget(etiket(ad, kaydir=True), satir, sutun * 2)
            izgara.addWidget(kutu, satir, sutun * 2 + 1)
            kutu.valueChanged.connect(self._tempo_ozetini_guncelle)
        izgara.setColumnStretch(0, 1)
        izgara.setColumnStretch(2, 1)
        kart.duzen.addLayout(izgara)
        self.tempo_ozeti = etiket("", "ikincil", kaydir=True)
        self.tempo_uyarisi = etiket("", "durumYazi", kaydir=True)
        kart.duzen.addWidget(self.tempo_ozeti)
        kart.duzen.addWidget(self.tempo_uyarisi)
        return kart

    def _not_karti(self) -> Kart:
        kart = Kart("Bağlantı isteği notu", "Bağlantı isteğine eklenen kısa not (bütün kampanyalar). İstek kabul edilince "
                                            "her kampanyanın kendi ilk mesajı gider; o mesajlar Kampanyalar sayfasında.")
        self.not_kutusu = QPlainTextEdit()
        self.not_kutusu.setFixedHeight(96)
        self.not_kutusu.textChanged.connect(self._not_sayacini_guncelle)
        self.not_sayaci = etiket("", "sayac")
        kart.duzen.addWidget(self.not_kutusu)
        kart.duzen.addWidget(self.not_sayaci, alignment=Qt.AlignmentFlag.AlignRight)
        kart.duzen.addWidget(etiket(
            "Değişkenler: {ad} kişinin adı, {isletme_adi} şirketin adı. Notta hizmet anlatma; amaç sadece bağlantının "
            "kabul edilmesi.", "soluk", kaydir=True))
        return kart

    def _google_karti(self) -> Kart:
        kart = Kart("Google kontrolü (isteğe bağlı)", "Serper.dev anahtarı girersen LinkedIn'de web sitesi yazmayan "
                    "şirketlerin sitesi Google'dan bulunur ve şirketin Google sırası kaydedilir. Boş bırakabilirsin.")
        satir = QHBoxLayout()
        self.api_kutusu = QLineEdit()
        self.api_kutusu.setPlaceholderText("Serper.dev API anahtarı")
        self.api_kutusu.setEchoMode(QLineEdit.EchoMode.Password)
        goster = QPushButton("Göster")
        goster.setCheckable(True)
        goster.setAutoDefault(False)
        goster.toggled.connect(lambda acik: (
            self.api_kutusu.setEchoMode(QLineEdit.EchoMode.Normal if acik else QLineEdit.EchoMode.Password),
            goster.setText("Gizle" if acik else "Göster"),
        ))
        satir.addWidget(self.api_kutusu, 1)
        satir.addWidget(goster)
        satir.addWidget(dugme("serper.dev'i aç", lambda: adres_ac(SERPER_ADRESI)))
        kart.duzen.addLayout(satir)
        return kart

    # ---------------- Canlı özetler ----------------

    def _puan_ozetini_guncelle(self) -> None:
        p = {anahtar: kutu.value() for anahtar, kutu in self.puan_kutulari.items()}
        kontroller = {"sirket": self.sirket_kutusu.isChecked(), "aktivite": self.aktivite_kutusu.isChecked()}
        ornek = p["rol_uyumlu"] + p["boyut_11_200"] + p["aktif_30_gun"] + p["web_sitesi"]
        self.puan_ornegi.setText(
            f"Örnek: 51–200 çalışanlı bir otelin genel müdürü, son 30 günde paylaşım yapmış, şirketin sitesi var = "
            f"{p['rol_uyumlu']} + {p['boyut_11_200']} + {p['aktif_30_gun']} + {p['web_sitesi']} = {ornek} puan.")
        en_yuksek = ulasilabilir_en_yuksek(p, kontroller)
        if en_yuksek < p["esik"]:
            hap_ayarla(self.puan_ozeti, f"Açık kontrollerle en fazla {en_yuksek} puan alınabiliyor, eşik {p['esik']}: "
                                        "kimseye mesaj gitmez. Eşiği düşür ya da kontrolleri aç.", "hata")
        else:
            hap_ayarla(self.puan_ozeti, f"En yüksek puan {en_yuksek}. {p['esik']} ve üstü puan alanlara yazılır.", "iyi")

    def _dagilim_ozetini_guncelle(self) -> None:
        toplam = sum(kutu.value() for kutu in self.dagilim_kutulari.values())
        if toplam == 0:
            hap_ayarla(self.dagilim_ozeti, "En az bir dilimin payı 0'dan büyük olmalı.", "hata")
        elif toplam == 100:
            hap_ayarla(self.dagilim_ozeti, "Toplam %100.", "iyi")
        else:
            hap_ayarla(self.dagilim_ozeti, f"Toplam %{toplam}: paylar bu toplama göre oranlanır.", "uyari")

    def _tempo_ozetini_guncelle(self) -> None:
        bas, bit = self.saat_bas.value(), self.saat_bit.value()
        lim = {anahtar: kutu.value() for anahtar, kutu in self.limit_kutulari.items()}
        if bas >= bit:
            self.tempo_ozeti.setText("")
            hap_ayarla(self.tempo_uyarisi, "Başlangıç saati bitiş saatinden önce olmalı.", "hata")
            self.tempo_uyarisi.setVisible(True)
            return
        pencere_dk = (bit - bas) * 60
        baglanti_dk = max(pencere_dk / lim["baglanti_gunluk"], 60 / lim["baglanti_saatlik"])
        haftalik = min(lim["baglanti_haftalik"], lim["baglanti_gunluk"] * 7)
        self.tempo_ozeti.setText(
            f"Bot LinkedIn'de sadece {bas:02d}:00–{bit:02d}:00 arasında çalışır. Bağlantı isteği yaklaşık "
            f"{baglanti_dk:.0f} dakikada bir, mesaj {pencere_dk / lim['mesaj_gunluk']:.0f} dakikada bir, aday "
            f"değerlendirme {pencere_dk / lim['degerlendirme_gunluk']:.0f} dakikada bir yapılır; arama en fazla "
            f"{pencere_dk / lim['linkedin_arama_gunluk']:.0f} dakikada bir (sırada {engine.ADAY_TAMPONU} aday varsa "
            f"aranmaz). Aralıklar rastgele biraz değişir. Haftada en fazla {haftalik} bağlantı isteği: {ILK_TEST_KISI} "
            f"kişilik ilk test (6 grup × 100) yaklaşık {ceil(ILK_TEST_KISI / haftalik)} hafta sürer.")
        uyarilar = []
        if lim["baglanti_haftalik"] > 100:
            uyarilar.append("LinkedIn çoğu hesapta haftada yaklaşık 100 davete izin verir; fazlası hesabı kısıtlatabilir.")
        if lim["baglanti_gunluk"] > 25:
            uyarilar.append("Günde 25'ten fazla istek spam gibi görünebilir.")
        if lim["linkedin_arama_gunluk"] > 30:
            uyarilar.append("Ücretsiz hesaplarda aylık arama sınırı var; yüksek değer bu sınıra ay bitmeden takılmana yol açabilir.")
        hap_ayarla(self.tempo_uyarisi, " ".join(uyarilar), "uyari" if uyarilar else "")
        self.tempo_uyarisi.setVisible(bool(uyarilar))

    def _not_sayacini_guncelle(self) -> None:
        try:
            uzunluk = len(self.not_kutusu.toPlainText().strip().format(**servis.ORNEK_ADAY))
            metin = f"Örnek bir ad ve şirketle {uzunluk} / {NOT_KARAKTER_SINIRI} karakter"
            asim = uzunluk > NOT_KARAKTER_SINIRI
        except (KeyError, ValueError, IndexError):
            metin, asim = "Notta hatalı değişken var", True
        self.not_sayaci.setText(metin)
        self.not_sayaci.setProperty("asim", "evet" if asim else "hayir")
        yeniden_boya(self.not_sayaci)

    # ---------------- Yükle / kaydet ----------------

    def _formdaki_degerler(self) -> dict:
        return {
            "serper_api_key": self.api_kutusu.text().strip(),
            "calisma_saatleri": {"baslangic": self.saat_bas.value(), "bitis": self.saat_bit.value()},
            "limitler": {anahtar: kutu.value() for anahtar, kutu in self.limit_kutulari.items()},
            "puanlama": {anahtar: kutu.value() for anahtar, kutu in self.puan_kutulari.items()},
            "boyut_dagilimi": {bant: kutu.value() for bant, kutu in self.dagilim_kutulari.items()},
            "kontroller": {"sirket": self.sirket_kutusu.isChecked(), "aktivite": self.aktivite_kutusu.isChecked()},
            "temizlik": {**{a: k.value() for a, k in self.temizlik_kutulari.items()},
                         "is_cikmayan": self.is_cikmayan_kutusu.isChecked()},
            "mesaj_sablonlari": {"baglanti_notu": self.not_kutusu.toPlainText().strip()},
        }

    def _forma_yukle(self, ayarlar: dict) -> None:
        self._yuklenen = ayarlar
        self.api_kutusu.setText(ayarlar.get("serper_api_key", ""))
        self.saat_bas.setValue(ayarlar["calisma_saatleri"]["baslangic"])
        self.saat_bit.setValue(ayarlar["calisma_saatleri"]["bitis"])
        for anahtar, kutu in self.limit_kutulari.items():
            kutu.setValue(ayarlar["limitler"].get(anahtar, 1))
        for anahtar, kutu in self.puan_kutulari.items():
            kutu.setValue(ayarlar["puanlama"].get(anahtar, 0))
        for bant, kutu in self.dagilim_kutulari.items():
            kutu.setValue(ayarlar["boyut_dagilimi"].get(bant, 0))
        for anahtar, kutu in self.temizlik_kutulari.items():
            kutu.setValue((ayarlar.get("temizlik") or {}).get(anahtar, 0))
        self.is_cikmayan_kutusu.setChecked((ayarlar.get("temizlik") or {}).get("is_cikmayan", True))
        self.sirket_kutusu.setChecked(ayarlar["kontroller"].get("sirket", True))
        self.aktivite_kutusu.setChecked(ayarlar["kontroller"].get("aktivite", True))
        self.not_kutusu.setPlainText(ayarlar["mesaj_sablonlari"].get("baglanti_notu", ""))
        self._puan_ozetini_guncelle()
        self._dagilim_ozetini_guncelle()
        self._tempo_ozetini_guncelle()
        self._not_sayacini_guncelle()
        self._anlik = self._formdaki_degerler()

    def degisiklik_var(self) -> bool:
        return self._formdaki_degerler() != self._anlik

    def ayrilabilir_mi(self) -> bool:
        """Kaydedilmemis degisiklik varsa sorar; sayfadan cikilabilecekse True dondurur."""
        if not self.degisiklik_var():
            return True
        kutu = QMessageBox(self)
        kutu.setWindowTitle("Kaydedilmemiş değişiklik")
        kutu.setText("Ayarlarda kaydedilmemiş değişiklik var. Kaydedilsin mi?")
        kaydet = kutu.addButton("Kaydet", QMessageBox.ButtonRole.AcceptRole)
        atla = kutu.addButton("Kaydetme", QMessageBox.ButtonRole.DestructiveRole)
        kutu.addButton("Vazgeç", QMessageBox.ButtonRole.RejectRole)
        kutu.exec()
        if kutu.clickedButton() is kaydet:
            return self.kaydet()
        if kutu.clickedButton() is atla:
            self._forma_yukle(load_settings())
            return True
        return False

    def kaydet(self) -> bool:
        onceki = self._yuklenen
        try:
            ayarlar = servis.ayarlari_kaydet(self._formdaki_degerler())
        except servis.AyarHatasi as e:
            self._bildir(str(e), hata=True)
            return False
        mesaj = "Ayarlar kaydedildi ✓"
        if ayarlar["puanlama"] != onceki["puanlama"] or ayarlar["kontroller"] != onceki["kontroller"]:
            mesaj += "  Bekleyen adayların puanları yeni kurala göre yeniden hesaplandı."
        self._forma_yukle(ayarlar)
        self._bildir(mesaj)
        self.kaydedildi.emit(ayarlar)
        return True

    def _geri_al(self) -> None:
        self._forma_yukle(load_settings())
        self._bildir("Kaydedilmiş ayarlara dönüldü.")

    def _bildir(self, metin: str, hata: bool = False) -> None:
        self.bildirim.setText(metin)
        self.bildirim.setProperty("hata", "evet" if hata else "hayir")
        yeniden_boya(self.bildirim)
        QTimer.singleShot(9000, lambda: self.bildirim.setText("") if self.bildirim.text() == metin else None)
