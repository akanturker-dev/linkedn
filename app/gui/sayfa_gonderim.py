from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QPlainTextEdit, QVBoxLayout

from .. import engine, servis, tazelik
from ..sehirler import ilceler as sehrin_ilceleri, sehir_adlari
from ..sektorler import (
    GRUP_ACIKLAMALARI, GRUP_ADLARI, GRUP_KISA, HAVUZLAR, MAPS, SEO, WEB, gruplu_sektorler, sektor,
)
from .bilesenler import (
    AcilirListe, Kart, Metrik, Sayfa, bilgi_ver, cip, cip_dugme, dugme, duzeni_temizle, etiket, hap_ayarla,
    sayi_kutusu,
)
from .tema import yeniden_boya

HUNI = [
    ("bulunan", "Bulunan kişi"),
    ("uygun", "DM'e uygun"),
    ("istek", "İstek gönderildi"),
    ("kabul", "Bağlantı kabul"),
    ("mesaj", "Mesaj gönderildi"),
    ("cevap", "Cevap verdi"),
    ("gorusme", "Görüşme"),
    ("musteri", "Müşteri"),
]
NASIL_CALISIR = [
    "NEREDE ARIYOR: LinkedIn'in kendi kişi aramasında. Google, Google Maps, telefon rehberi ya da e-posta listesi kullanılmıyor; bulunan herkesin zaten LinkedIn hesabı var.",
    "NASIL ARIYOR: seçtiğin sektörün kelimelerini (Türkçe + İngilizce) karar verici unvanlarıyla birleştirip Türkiye filtresiyle aratır. Örnek arama: (Owner VEYA Sahibi VEYA General Manager VEYA Genel Müdür) + (otel VEYA hotel VEYA resort).",
    "KİMİ SEÇİYOR: şirketin çalışan sayısına, kişinin unvanına ve son paylaşımına bakıp puan verir; eşiğin altında kalanı eler ve aynı şirketten tek kişiye yazar.",
    "NASIL YAZIYOR: LinkedIn'de tanımadığın kişiye doğrudan mesaj atılamaz. Önce kısa bir bağlantı isteği gider; kişi kabul edince senin yazdığın satış mesajı LinkedIn'den gönderilir.",
    "SINIR: günlük ve haftalık sınırların altında kalır, gönderimleri çalışma saatlerine yayar.",
    "ULAŞAMADIĞI KİŞİLER: LinkedIn hesabı olmayan işletme sahibine bu asistanla ulaşılamaz. Öyle işletmeler için telefon ya da e-posta gerekir; bu asistan onu yapmıyor.",
    "CEVAPLAR: gelen cevabı LinkedIn'den sen okursun. Adaylar sayfasında kişiye sağ tıklayıp 'Cevap verdi' diye işaretlersin, Rapor ona göre hesaplar.",
]


# Taze taramada kullanilabilecek mesaj taslaklari: yukaridaki uc hizmet mesaji + bu taramaya ozel mesaj
SATIR_YUKSEKLIGI = 30  # acilir sektor listesinde tek satirin yuksekligi
TAZE_TASLAKLAR = [
    (MAPS, "Google Maps mesajı — yukarıdaki 2. adımdan"),
    (SEO, "SEO mesajı — yukarıdaki 2. adımdan"),
    (WEB, "Web sitesi mesajı — yukarıdaki 2. adımdan"),
    ("ozel", "Taze üyelere özel mesaj (hizmet bağımsız)"),
]
TAZE_ACIKLAMA = [
    "NEDEN: LinkedIn'e yeni katılan bir işletme sahibi henüz kimseden teklif almamış olur; mesaj okunma ve cevap oranı yüksektir.",
    "NASIL BULUYOR: LinkedIn'de \"kayıt tarihi\" diye bir arama filtresi YOK — bütün filtre listesi kontrol edildi, böyle bir seçenek bulunmuyor. Ama her arama sonucunun içinde kişinin LinkedIn üye numarası duruyor ve bu numaralar sırayla dağıtılıyor: numarası büyük olan LinkedIn'e sonra katılmış demektir.",
    "NE KADAR KESİN: sıralama kesindir — en yeni katılan gerçekten en üste gelir. \"3 gün önce katıldı\" gibi tarih etiketi ise tahmindir; asistan her taramada gördüğü en büyük numarayı kaydedip numaraların günlük artış hızını kendisi ölçer, birkaç hafta içinde tahmin isabetlenir. O zamana kadar ekranda \"kaba tahmin\" yazar.",
    "SADECE EN YENİ KATILANLAR: tarih tahminine hiç güvenmeyen seçenek. Asistan bulduğu herkesi üye "
    "numarasına göre yarıştırır ve elindeki en yeni 100 kişiden daha yeni olmayanı listeye almaz; her yeni "
    "buluşta çıta kendiliğinden yükselir. Kaç gün önce katıldığını bilmesi gerekmediği için en güvenilir "
    "seçenek budur — \"bana sadece en tazeleri getir\" demek istiyorsan bunu seç.",
    "DAR PENCERELER: 3 gün ve 1 hafta çok dardır; o aralıkta karar verici unvanlı kişi az çıkar. Bol sonuç için 3 ay ya da 6 ay ile başlamak daha verimlidir.",
    "SINIRLAR AYNI: bu tarama da günlük bağlantı/mesaj sınırlarına uyar; ayrı bir hız kullanmaz.",
]


def durum_bilgisi(d: dict) -> tuple:
    """Botun tek cumlelik durumu ve hap rengi."""
    if d.get("guvenlik_kontrolu"):
        return "Güvenlik doğrulaması bekleniyor", "hata"
    if d.get("giris_bekleniyor"):
        return "LinkedIn girişi bekleniyor", "uyari"
    if d.get("calisiyor"):
        return "Çalışıyor", "iyi"
    return "Durduruldu", ""


class KonumSecimi:
    """Bir bolume ait sehir/ilce secimi. Sayfada iki tane var (normal tarama ve taze uye taramasi) ve
    ikisi birbirinden bagimsiz calisir; kod tek yerde durur diye ayri sinifa alindi."""

    def __init__(self, kart, sehir_ipucu: str, ilce_ipucu: str):
        self.sehirler = []
        self.ilceler = []
        kart.duzen.addWidget(etiket("Nerede arasın? Şehir ve ilçe", "alanBaslik"))
        kart.duzen.addWidget(etiket(sehir_ipucu, "soluk", kaydir=True))

        sehir_satiri = QHBoxLayout()
        sehir_satiri.setSpacing(10)
        self.sehir_secici = AcilirListe()
        for ad in sehir_adlari():
            self.sehir_secici.addItem(ad, ad)
        sehir_satiri.addWidget(self.sehir_secici, 1)
        sehir_satiri.addWidget(dugme("Şehir Ekle", self._sehir_ekle))
        kart.duzen.addLayout(sehir_satiri)
        self.sehir_ciplari = QGridLayout()
        self.sehir_ciplari.setSpacing(6)
        self.sehir_ciplari.setColumnStretch(4, 1)
        kart.duzen.addLayout(self.sehir_ciplari)

        ilce_satiri = QHBoxLayout()
        ilce_satiri.setSpacing(10)
        self.ilce_secici = AcilirListe()
        ilce_satiri.addWidget(self.ilce_secici, 1)
        ilce_satiri.addWidget(dugme("İlçe Ekle", self._ilce_ekle))
        kart.duzen.addLayout(ilce_satiri)
        self.ilce_ciplari = QGridLayout()
        self.ilce_ciplari.setSpacing(6)
        self.ilce_ciplari.setColumnStretch(4, 1)
        kart.duzen.addLayout(self.ilce_ciplari)
        kart.duzen.addWidget(etiket(ilce_ipucu, "soluk", kaydir=True))
        self.ciz()

    def ayarla(self, sehirler, ilceler) -> None:
        self.sehirler = list(sehirler or [])
        self.ilceler = list(ilceler or [])
        self.ciz()

    def ozet(self) -> str:
        nerede = ", ".join(self.sehirler) or "bütün Türkiye"
        return nerede + (" · ilçeler: " + ", ".join(self.ilceler) if self.ilceler else "")

    def _sehir_ekle(self) -> None:
        ad = self.sehir_secici.currentData()
        if ad and ad not in self.sehirler:
            self.sehirler.append(ad)
            self.ciz()

    def _sehir_cikar(self, ad: str) -> None:
        self.sehirler = [s for s in self.sehirler if s != ad]
        # Sehir cikinca onun ilceleri de listeden dusulur
        kalanlar = {i for _, liste in sehrin_ilceleri(self.sehirler) for i in liste}
        self.ilceler = [i for i in self.ilceler if i in kalanlar]
        self.ciz()

    def _ilce_ekle(self) -> None:
        ad = self.ilce_secici.currentData()
        if ad and ad not in self.ilceler:
            self.ilceler.append(ad)
            self.ciz()

    def _ilce_cikar(self, ad: str) -> None:
        self.ilceler = [i for i in self.ilceler if i != ad]
        self.ciz()

    def ciz(self) -> None:
        """Secili sehir ve ilceleri etiket olarak cizer; ilce listesini secili sehirlere gore yeniler."""
        duzeni_temizle(self.sehir_ciplari)
        if not self.sehirler:
            self.sehir_ciplari.addWidget(etiket("Şehir seçmedin: bütün Türkiye'de aranacak.", "soluk"), 0, 0, 1, 4)
        for sira, ad in enumerate(self.sehirler):
            self.sehir_ciplari.addWidget(cip_dugme(ad, lambda a=ad: self._sehir_cikar(a)), sira // 4, sira % 4,
                                         Qt.AlignmentFlag.AlignLeft)

        gruplar = sehrin_ilceleri(self.sehirler)
        model = QStandardItemModel()
        for sehir_adi, liste in gruplar:
            baslik = QStandardItem(f"{sehir_adi} ilçeleri")
            baslik.setFlags(Qt.ItemFlag.NoItemFlags)
            yazi = baslik.font()
            yazi.setBold(True)
            baslik.setFont(yazi)
            baslik.setSizeHint(QSize(0, SATIR_YUKSEKLIGI))
            model.appendRow(baslik)
            for ilce in liste:
                oge = QStandardItem("     " + ilce)
                oge.setData(ilce, Qt.ItemDataRole.UserRole)
                oge.setSizeHint(QSize(0, SATIR_YUKSEKLIGI))
                model.appendRow(oge)
        if not gruplar:
            bos = QStandardItem("Önce şehir seç")
            bos.setFlags(Qt.ItemFlag.NoItemFlags)
            model.appendRow(bos)
        self.ilce_secici.setModel(model)
        self.ilce_secici.setEnabled(bool(gruplar))
        if gruplar:
            self.ilce_secici.setCurrentIndex(1)

        duzeni_temizle(self.ilce_ciplari)
        if not self.ilceler:
            self.ilce_ciplari.addWidget(
                etiket("İlçe seçmedin: şehrin tamamında aranacak (önerilen).", "soluk"), 0, 0, 1, 4)
        for sira, ad in enumerate(self.ilceler):
            self.ilce_ciplari.addWidget(cip_dugme(ad, lambda a=ad: self._ilce_cikar(a)), sira // 4, sira % 4,
                                        Qt.AlignmentFlag.AlignLeft)


class GonderimSayfasi(Sayfa):
    degisti = Signal()

    def __init__(self, ayarlar: dict):
        super().__init__(
            "Mesaj Gönder",
            "Üç adım: kime yazılacağını seç, mesajı onayla, başlat. Gerisini bot yapar; sen sadece gelen cevapları okursun.",
            kaydirilabilir=True,
        )
        self._secili = []
        self._yuklendi = False
        self._taze_ozel_metin = ""
        self._taze_onceki_taslak = TAZE_TASLAKLAR[0][0]
        self.icerik.addWidget(self._durum_karti())
        # Taze uye taramasi en ustte: asil kullanilan bolum bu
        self.icerik.addWidget(self._taze_karti())
        self.icerik.addWidget(self._sektor_karti())
        self.icerik.addWidget(self._mesaj_karti())
        self.icerik.addWidget(self._baslat_karti())
        self.icerik.addWidget(self._huni_karti())
        self.icerik.addWidget(self._nasil_karti())
        self.icerik.addStretch(1)
        self._forma_yukle(ayarlar)

    # ---------------- Kartlar ----------------

    def _durum_karti(self) -> Kart:
        kart = Kart("Durum")
        satir = QHBoxLayout()
        self.durum_hapi = etiket("", "hap")
        satir.addWidget(self.durum_hapi)
        satir.addStretch(1)
        self.giris_dugmesi = dugme("LinkedIn'e Giriş Yap", self._linkedin_giris, "aksan")
        satir.addWidget(self.giris_dugmesi)
        kart.duzen.addLayout(satir)
        self.oturum_yazisi = etiket("", "ikincil", kaydir=True)
        kart.duzen.addWidget(self.oturum_yazisi)
        self.bugun_yazisi = etiket("", "ikincil", kaydir=True)
        kart.duzen.addWidget(self.bugun_yazisi)
        self.uyari_yazisi = etiket("", "durumYazi", kaydir=True)
        kart.duzen.addWidget(self.uyari_yazisi)
        return kart

    def _taze_karti(self) -> Kart:
        """LinkedIn'e yeni katilmis kisileri tek sektorde tarar. Sayfanin asil bolumu bu oldugu icin
        vurgulu cizilir ve kendi sehir/ilce secimi vardir."""
        kart = Kart(
            "Taze üyeler — LinkedIn'e yeni katılanları tara",
            "Bu bölüm tek başına çalışır: kendi sektörü, kendi şehri, kendi mesajı var. Seçtiğin sektörde "
            "LinkedIn'e yakın zamanda katılmış karar vericileri arar; en yeni katılan en üste gelir.",
            vurgulu=True,
            rozet="ASIL BÖLÜM",
        )
        sektor_satiri = QHBoxLayout()
        sektor_satiri.setSpacing(10)
        sektor_satiri.addWidget(etiket("Hangi sektörde arasın?", "alanBaslik"))
        self.taze_sektor_secici = AcilirListe()
        self.taze_sektor_secici.setMinimumWidth(420)
        self.taze_sektor_secici.setModel(self._sektor_modeli())
        self.taze_sektor_secici.currentIndexChanged.connect(self._taze_sektor_degisti)
        sektor_satiri.addWidget(self.taze_sektor_secici)
        sektor_satiri.addStretch(1)
        kart.duzen.addLayout(sektor_satiri)
        self.taze_sektor_aciklamasi = etiket("", "soluk", kaydir=True)
        kart.duzen.addWidget(self.taze_sektor_aciklamasi)

        satir = QHBoxLayout()
        satir.setSpacing(10)
        satir.addWidget(etiket("Ne kadar yeni olsun?", "alanBaslik"))
        self.tazelik_listesi = AcilirListe()
        self.tazelik_listesi.setMinimumWidth(300)
        for kod, ad, _ in tazelik.PENCERELER:
            self.tazelik_listesi.addItem(ad, kod)
        self.tazelik_listesi.setCurrentIndex(
            [k for k, _, _ in tazelik.PENCERELER].index(tazelik.VARSAYILAN_PENCERE))
        satir.addWidget(self.tazelik_listesi)
        satir.addStretch(1)
        kart.duzen.addLayout(satir)

        kart.duzen.addSpacing(8)
        self.taze_konum = KonumSecimi(
            kart,
            "Bu tarama sadece burada seçtiğin şehirlere bakar; yukarıdaki normal taramanın şehirleriyle "
            "karışmaz. Boş bırakırsan bütün Türkiye'de arar.",
            "İlçe seçmek zorunlu değil. Taze üye zaten az bulunur; ilçe de seçersen aday sayısı iyice düşer. "
            "Önerim: sadece şehir seç.",
        )

        kart.duzen.addSpacing(8)
        taslak_satiri = QHBoxLayout()
        taslak_satiri.setSpacing(10)
        taslak_satiri.addWidget(etiket("Hangi mesaj gitsin?", "alanBaslik"))
        self.taze_taslak_listesi = AcilirListe()
        self.taze_taslak_listesi.setMinimumWidth(300)
        for kod, ad in TAZE_TASLAKLAR:
            self.taze_taslak_listesi.addItem(ad, kod)
        self.taze_taslak_listesi.currentIndexChanged.connect(self._taze_taslak_degisti)
        taslak_satiri.addWidget(self.taze_taslak_listesi)
        taslak_satiri.addStretch(1)
        kart.duzen.addLayout(taslak_satiri)
        kart.duzen.addWidget(etiket(
            "Sektörü seçtiğinde o sektörün sattığın hizmetine ait mesaj taslağı buraya kendiliğinden gelir. "
            "İstersen buradan başka bir taslağa geçebilir ya da aşağıdaki kutuda bu taramaya özel "
            "değiştirebilirsin; aşağıdaki mesajlar bozulmaz.",
            "soluk", kaydir=True))

        self.taze_mesaj_kutusu = QPlainTextEdit()
        self.taze_mesaj_kutusu.setFixedHeight(118)
        self.taze_mesaj_kutusu.textChanged.connect(self._taze_onizle)
        kart.duzen.addWidget(self.taze_mesaj_kutusu)
        self.taze_onizleme = etiket("", "onizleme", kaydir=True)
        self.taze_onizleme.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        kart.duzen.addWidget(self.taze_onizleme)

        dugmeler = QHBoxLayout()
        dugmeler.setSpacing(10)
        self.taze_baslat = dugme("Taze üyeleri taramaya başla", self._taze_baslat, "aksan", buyuk=True)
        self.taze_durdur = dugme("Taze taramayı durdur", self._taze_durdur, "durdur")
        dugmeler.addWidget(self.taze_baslat)
        dugmeler.addWidget(self.taze_durdur)
        dugmeler.addStretch(1)
        kart.duzen.addLayout(dugmeler)
        self.taze_durumu = etiket("", "durumYazi", kaydir=True)
        kart.duzen.addWidget(self.taze_durumu)

        for aciklama in TAZE_ACIKLAMA:
            kart.duzen.addWidget(etiket(aciklama, "soluk", kaydir=True))
        return kart

    def _sektor_karti(self) -> Kart:
        kart = Kart("1. LinkedIn'de ara ve LinkedIn'de mesaj at",
                    "Bot kişileri LinkedIn'in kendi aramasında bulur ve mesajı LinkedIn'den yollar. Google, harita, "
                    "telefon ya da e-posta kullanılmaz; bu yüzden bulunan herkesin LinkedIn hesabı vardır. "
                    "Aşağıdaki üç grup, kişiyi nerede bulduğumuzu değil, o sektöre HANGİ HİZMETİ satacağını gösterir.")
        kart.duzen.addWidget(etiket(
            "Aramayı şöyle kurar: sektörün Türkçe ve İngilizce kelimeleri + karar verici unvanları + Türkiye "
            "filtresi. Örnek: (Owner / Sahibi / General Manager / Genel Müdür) + (otel / hotel / resort). "
            "Aynı şirketten tek kişiye yazar; LinkedIn hesabı olmayan işletmeye ulaşamaz.", "soluk", kaydir=True))
        kart.duzen.addSpacing(6)

        kart.duzen.addWidget(etiket("Sektör seç, listeye ekle", "alanBaslik"))
        secim_satiri = QHBoxLayout()
        secim_satiri.setSpacing(10)
        self.sektor_secici = AcilirListe()
        self.sektor_secici.setModel(self._sektor_modeli())
        self.sektor_secici.setCurrentIndex(1)
        self.sektor_secici.currentIndexChanged.connect(self._sektor_aciklamasini_yaz)
        secim_satiri.addWidget(self.sektor_secici, 1)
        secim_satiri.addWidget(dugme("Listeye Ekle", self._sektor_ekle, "aksan"))
        kart.duzen.addLayout(secim_satiri)
        self.sektor_aciklamasi = etiket("", "ikincil", kaydir=True)
        kart.duzen.addWidget(self.sektor_aciklamasi)

        kart.duzen.addWidget(etiket("Seçtiğin sektörler", "alanBaslik"))
        self.secili_duzeni = QVBoxLayout()
        self.secili_duzeni.setSpacing(6)
        kart.duzen.addLayout(self.secili_duzeni)
        kart.duzen.addWidget(etiket(
            "İpucu: 2-3 sektörle başla. Bot hepsine sırayla yazar; hangisinin cevap verdiğini Rapor sayfasında "
            "görürsün, sonra kazanan sektöre yüklenirsin. Listeden çıkardığın sektör durur, bulunan adaylar silinmez.",
            "soluk", kaydir=True))

        kart.duzen.addSpacing(12)
        self.konum = KonumSecimi(
            kart,
            "Boş bırakırsan bütün Türkiye'de arar. Şehir seçersen sadece o şehirdeki kişilere yazar. Listede "
            "yalnızca iş hacmi yüksek şehirler ve zengin ilçeler var; en büyükten küçüğe sıralı.",
            "İlçe seçmek zorunlu değil. Seçersen bot yalnızca profilinde ya da şirketinde o ilçe geçen kişileri "
            "bulur: hedef daralır, aday sayısı azalır. Emin değilsen sadece şehir seç.",
        )
        return kart

    def _mesaj_karti(self) -> Kart:
        kart = Kart("2. Ne yazalım?", "Bağlantı isteği kabul edilince LinkedIn üzerinden gidecek satış mesajı. "
                                      "Sattığın üç hizmete üç ayrı mesaj yazılır; sadece seçtiğin gruplarınki "
                                      "kullanılır, istediğin gibi değiştirebilirsin.")
        self.mesaj_kutulari, self.mesaj_basliklari, self.onizlemeler = {}, {}, {}
        for havuz in HAVUZLAR:
            baslik = etiket("", "alanBaslik", kaydir=True)
            kutu = QPlainTextEdit()
            kutu.setFixedHeight(118)
            kutu.textChanged.connect(lambda h=havuz: self._onizle(h))
            onizleme = etiket("", "onizleme", kaydir=True)
            onizleme.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            kart.duzen.addWidget(baslik)
            kart.duzen.addWidget(etiket(GRUP_ACIKLAMALARI[havuz], "soluk", kaydir=True))
            kart.duzen.addWidget(kutu)
            kart.duzen.addWidget(onizleme)
            kart.duzen.addSpacing(8)
            self.mesaj_kutulari[havuz], self.mesaj_basliklari[havuz], self.onizlemeler[havuz] = kutu, baslik, onizleme
        kart.duzen.addWidget(etiket(
            "Mesajı problemden aç, ilk mesajda hizmet listesi sayma: önce cevap, sonra problem, sonra hizmet. "
            "{ad} kişinin adı, {isletme_adi} şirketin adı yerine geçer.", "soluk", kaydir=True))
        return kart

    def _baslat_karti(self) -> Kart:
        kart = Kart("3. Günlük sınır ve başlat", "LinkedIn spam sayarsa hesabı kısıtlar. Bot bu sayıları asla aşmaz "
                                                 "ve gönderimleri gün içine yayar. Sınırlar her iki tarama için de "
                                                 "geçerlidir.")
        izgara = QGridLayout()
        izgara.setHorizontalSpacing(14)
        izgara.setVerticalSpacing(10)
        self.istek_kutusu = sayi_kutusu(1, 100, " kişi")
        self.mesaj_kutusu_gunluk = sayi_kutusu(1, 100, " mesaj")
        for sira, (ad, kutu, ipucu) in enumerate((
            ("Günde en fazla bağlantı isteği", self.istek_kutusu, "Güvenli aralık 10-20. LinkedIn haftada ~100 davete izin veriyor."),
            ("Günde en fazla mesaj", self.mesaj_kutusu_gunluk, "Bağlantı isteğini kabul edenlere gider; 20 rahat bir sayı."),
        )):
            izgara.addWidget(etiket(ad, kaydir=True), sira, 0)
            izgara.addWidget(kutu, sira, 1)
            izgara.addWidget(etiket(ipucu, "soluk", kaydir=True), sira, 2)
            kutu.valueChanged.connect(self._tempo_yaz)
        izgara.setColumnStretch(2, 1)
        kart.duzen.addLayout(izgara)
        self.tempo_yazisi = etiket("", "ikincil", kaydir=True)
        kart.duzen.addWidget(self.tempo_yazisi)

        dugmeler = QHBoxLayout()
        dugmeler.setSpacing(10)
        self.baslat_dugmesi = dugme("Kaydet ve Göndermeye Başla", self._baslat, "aksan", buyuk=True)
        self.durdur_dugmesi = dugme("Durdur", self._durdur, "durdur", buyuk=True)
        dugmeler.addWidget(self.baslat_dugmesi)
        dugmeler.addWidget(self.durdur_dugmesi)
        dugmeler.addStretch(1)
        kart.duzen.addLayout(dugmeler)
        self.bildirim = etiket("", "bildirim", kaydir=True)
        kart.duzen.addWidget(self.bildirim)
        return kart

    def _huni_karti(self) -> Kart:
        kart = Kart("Şu ana kadar", "Soldan sağa: bot kaç kişi buldu, kaçı uygundu, kaçına yazıldı, kaçı cevap verdi.")
        satir = QHBoxLayout()
        satir.setSpacing(4)
        self.huni = {}
        for anahtar, ad in HUNI:
            self.huni[anahtar] = Metrik(ad)
            satir.addWidget(self.huni[anahtar], 1)
        kart.duzen.addLayout(satir)
        return kart

    def _nasil_karti(self) -> Kart:
        kart = Kart("Bot ne yapıyor, nasıl yapıyor?")
        for adim in NASIL_CALISIR:
            kart.duzen.addWidget(etiket(adim, "ikincil", kaydir=True))
        return kart

    # ---------------- Sektör listesi ----------------

    @staticmethod
    def _sektor_modeli() -> QStandardItemModel:
        """Acilir listede once grup basligi (secilemez), altinda o gruptaki sektorler."""
        model = QStandardItemModel()
        for havuz, liste in gruplu_sektorler():
            baslik = QStandardItem(GRUP_ADLARI[havuz])
            baslik.setFlags(Qt.ItemFlag.NoItemFlags)
            yazi = baslik.font()
            yazi.setBold(True)
            baslik.setFont(yazi)
            baslik.setSizeHint(QSize(0, SATIR_YUKSEKLIGI))
            model.appendRow(baslik)
            for s in liste:
                oge = QStandardItem("     " + s["ad"])
                oge.setData(s["kod"], Qt.ItemDataRole.UserRole)
                # Varsayilan satir 20 piksel olculdu: fareyle isabet ettirmesi zor, rahat tiklanir yapilir
                oge.setSizeHint(QSize(0, SATIR_YUKSEKLIGI))
                model.appendRow(oge)
        return model

    def _sektor_aciklamasini_yaz(self) -> None:
        s = sektor(self.sektor_secici.currentData(Qt.ItemDataRole.UserRole))
        self.sektor_aciklamasi.setText(f"{s['ad']}: {s['aciklama']}" if s else "")

    def _sektor_ekle(self) -> None:
        kod = self.sektor_secici.currentData(Qt.ItemDataRole.UserRole)
        if not kod:
            return
        if kod in self._secili:
            self._bildir(f"{sektor(kod)['ad']} zaten listende.", hata=True)
            return
        self._secili.append(kod)
        self._secilileri_ciz()

    # ---------------- Taze üye taraması ----------------

    def _taze_sektor_degisti(self) -> None:
        """Sektor secilince hem aciklamasi yazilir hem de sattigin hizmetin mesaj taslagi kutuya gelir."""
        kod = self.taze_sektor_secici.currentData(Qt.ItemDataRole.UserRole)
        s = sektor(kod) if kod else None
        if not s:
            self.taze_sektor_aciklamasi.setText("")
            return
        self.taze_sektor_aciklamasi.setText(f"{GRUP_KISA[s['hizmet']]} satacaksın — {s['aciklama']}")
        # Taslak listesini sektorun hizmetine cevir; bu, kutuyu da o mesajla doldurur.
        # Liste zaten o siradaysa sinyal cikmaz, o yuzden doldurma elle de cagrilir.
        kodlar = [self.taze_taslak_listesi.itemData(i) for i in range(self.taze_taslak_listesi.count())]
        self.taze_taslak_listesi.setCurrentIndex(kodlar.index(s["hizmet"]))
        self._taze_taslak_degisti()

    def _taze_taslak_degisti(self) -> None:
        """Secilen taslagi kutuya kopyalar. Ozel mesajda kullanicinin yazdigi metin saklanir,
        geri donunce kaybolmaz."""
        kod = self.taze_taslak_listesi.currentData()
        if self._taze_onceki_taslak == "ozel":
            self._taze_ozel_metin = self.taze_mesaj_kutusu.toPlainText()
        self._taze_onceki_taslak = kod
        if kod == "ozel":
            self.taze_mesaj_kutusu.setPlainText(self._taze_ozel_metin)
        else:
            # Asagidaki kutudan canli kopyalanir: orada yaptigin son degisiklik buraya da gelir
            self.taze_mesaj_kutusu.setPlainText(self.mesaj_kutulari[kod].toPlainText())

    def _taze_onizle(self) -> None:
        metin = self.taze_mesaj_kutusu.toPlainText().strip()
        if not metin:
            self.taze_onizleme.setText("Mesaj boş.")
            return
        try:
            self.taze_onizleme.setText("Örnek kişiyle önizleme:\n" + metin.format(**servis.ORNEK_ADAY))
        except (KeyError, ValueError, IndexError):
            self.taze_onizleme.setText("Mesajda hatalı değişken var. Sadece {ad} ve {isletme_adi} kullan.")

    def _taze_baslat(self) -> None:
        kod = self.tazelik_listesi.currentData()
        sektor_kodu = self.taze_sektor_secici.currentData(Qt.ItemDataRole.UserRole)
        try:
            servis.taze_tarama_baslat(sektor_kodu, kod, self.taze_mesaj_kutusu.toPlainText(),
                                      self.taze_konum.sehirler, self.taze_konum.ilceler)
            if self.taze_taslak_listesi.currentData() == "ozel":
                # Sadece ozel mesaj kalici olarak saklanir; hizmet mesajlarinin kopyasi ustune yazmaz
                servis.ayarlari_kaydet(
                    {"mesaj_sablonlari": {"taze_mesaji": self.taze_mesaj_kutusu.toPlainText().strip()}})
        except servis.AyarHatasi as e:
            self._bildir(str(e), hata=True)
            return
        servis.otomasyonu_ayarla(True)
        self._bildir(f"Taze üye taraması başladı: {sektor(sektor_kodu)['ad']} — "
                     f"{tazelik.PENCERE_ADI[kod]}, {self.taze_konum.ozet()}.")
        self._taze_durumunu_yaz()
        self.degisti.emit()

    def _taze_durdur(self) -> None:
        if servis.taze_tarama_durdur():
            self._bildir("Taze üye taraması durduruldu. Bulunanlar listede kalır.")
        else:
            self._bildir("Çalışan bir taze üye taraması yok.")
        self._taze_durumunu_yaz()
        self.degisti.emit()

    def _taze_durumunu_yaz(self) -> None:
        kampanya = servis.taze_kampanya()
        calisiyor = bool(kampanya) and kampanya["durum"] == "aktif"
        if not kampanya:
            metin, tur = "Henüz taze üye taraması kurulmadı.", ""
        elif calisiyor:
            metin, tur = (f"Çalışıyor: {kampanya['ad']}. Bulunan adayları Adaylar sayfasından görebilirsin.", "iyi")
        else:
            metin, tur = f"Duraklatıldı: {kampanya['ad']}.", "uyari"
        self.taze_durumu.setText(metin)
        self.taze_durumu.setProperty("tur", tur)
        yeniden_boya(self.taze_durumu)
        self.taze_durdur.setEnabled(calisiyor)

    def _sektor_cikar(self, kod: str) -> None:
        self._secili = [k for k in self._secili if k != kod]
        self._secilileri_ciz()

    def _secilileri_ciz(self) -> None:
        duzeni_temizle(self.secili_duzeni)
        if not self._secili:
            self.secili_duzeni.addWidget(etiket("Henüz sektör seçmedin. Yukarıdan seç ve 'Listeye Ekle'ye bas.",
                                                "soluk", kaydir=True))
        for kod in self._secili:
            s = sektor(kod)
            satir = QHBoxLayout()
            satir.setSpacing(10)
            satir.addWidget(cip(GRUP_KISA[s["hizmet"]], s["hizmet"]))
            satir.addWidget(etiket(s["ad"], "alanBaslik"))
            satir.addStretch(1)
            satir.addWidget(dugme("Listeden çıkar", lambda k=kod: self._sektor_cikar(k), "silDugme"))
            self.secili_duzeni.addLayout(satir)
        self._mesaj_basliklarini_yaz()

    def _mesaj_basliklarini_yaz(self) -> None:
        for havuz in HAVUZLAR:
            adlar = [sektor(k)["ad"] for k in self._secili if sektor(k)["hizmet"] == havuz]
            grup = GRUP_KISA[havuz]
            self.mesaj_basliklari[havuz].setText(
                f"{grup} satacağın sektörlere LinkedIn'den gidecek mesaj — {', '.join(adlar)}" if adlar
                else f"{grup} satacağın sektörlere gidecek mesaj (bu gruptan seçili sektör yok)"
            )

    # ---------------- Yükle / kaydet ----------------

    def _forma_yukle(self, ayarlar: dict) -> None:
        sablonlar = ayarlar["mesaj_sablonlari"]
        for havuz in HAVUZLAR:
            self.mesaj_kutulari[havuz].setPlainText(sablonlar.get(servis.SABLON_ANAHTARLARI[havuz], ""))
        self.istek_kutusu.setValue(ayarlar["limitler"]["baglanti_gunluk"])
        self.mesaj_kutusu_gunluk.setValue(ayarlar["limitler"]["mesaj_gunluk"])
        self._secilileri_ciz()
        self._sektor_aciklamasini_yaz()
        self._tempo_yaz()
        self._taze_forma_yukle(ayarlar)

    def _taze_forma_yukle(self, ayarlar: dict) -> None:
        self._taze_ozel_metin = ayarlar["mesaj_sablonlari"].get("taze_mesaji", "")
        if self.taze_taslak_listesi.currentData() == "ozel":
            self.taze_mesaj_kutusu.setPlainText(self._taze_ozel_metin)
        kampanya = servis.taze_kampanya()
        if kampanya and kampanya.get("tazelik") in tazelik.PENCERE_ADI:
            self.tazelik_listesi.setCurrentIndex(
                [k for k, _, _ in tazelik.PENCERELER].index(kampanya["tazelik"]))
        if kampanya and sektor(kampanya.get("taze_sektor")):
            self._taze_sektoru_sec(kampanya["taze_sektor"])
            self.taze_konum.ayarla(kampanya["sehir"], kampanya.get("ilceler"))
        # Liste zaten ilk sektorde acilir (0. satir secilemeyen grup basligidir), yani "degisti" sinyali
        # cikmayabilir; aciklama ve mesaj taslagi bos kalmasin diye doldurma burada bir kez elle cagrilir.
        self._taze_sektor_degisti()
        self._taze_durumunu_yaz()

    def _taze_sektoru_sec(self, kod: str) -> None:
        model = self.taze_sektor_secici.model()
        for sira in range(model.rowCount()):
            if model.item(sira).data(Qt.ItemDataRole.UserRole) == kod:
                self.taze_sektor_secici.setCurrentIndex(sira)
                return

    def _onizle(self, havuz: str) -> None:
        metin = self.mesaj_kutulari[havuz].toPlainText().strip()
        if not metin:
            self.onizlemeler[havuz].setText("Mesaj boş.")
            return
        try:
            self.onizlemeler[havuz].setText("Örnek kişiyle önizleme:\n" + metin.format(**servis.ORNEK_ADAY))
        except (KeyError, ValueError, IndexError):
            self.onizlemeler[havuz].setText("Mesajda hatalı değişken var. Sadece {ad} ve {isletme_adi} kullan.")

    def _tempo_yaz(self) -> None:
        istek, mesaj = self.istek_kutusu.value(), self.mesaj_kutusu_gunluk.value()
        haftalik = min(istek * 7, 100)
        self.tempo_yazisi.setText(
            f"Bu hızla günde {istek} kişiye bağlantı isteği, {mesaj} kişiye mesaj gider; haftada yaklaşık {haftalik} "
            f"yeni kişi demek. Bot bunları çalışma saatlerine yayar (Ayarlar'dan değişir) ve sırada "
            f"{engine.ADAY_TAMPONU} aday varsa yeni arama yapmaz."
        )

    def _baslat(self) -> None:
        try:
            sayac = servis.sektor_kampanyalari_kur(
                self._secili,
                {havuz: self.mesaj_kutulari[havuz].toPlainText().strip() for havuz in HAVUZLAR},
                self.konum.sehirler,
                self.konum.ilceler,
            )
            servis.ayarlari_kaydet({"limitler": {"baglanti_gunluk": self.istek_kutusu.value(),
                                                 "mesaj_gunluk": self.mesaj_kutusu_gunluk.value()}})
        except servis.AyarHatasi as e:
            self._bildir(str(e), hata=True)
            return
        servis.otomasyonu_ayarla(True)
        self._bildir(f"Kuruldu ve başladı: {len(self._secili)} sektör, {self.konum.ozet()} "
                     f"({sayac['yeni']} yeni, {sayac['duraklatilan']} durduruldu).")
        self.degisti.emit()

    def _durdur(self) -> None:
        servis.otomasyonu_ayarla(False)
        self._bildir("Durduruldu. Gönderim yapılmıyor; bulunan adaylar listede duruyor.")
        self.degisti.emit()

    def _linkedin_giris(self) -> None:
        engine.komut_gonder("giris_yap")
        bilgi_ver(self, "LinkedIn girişi",
                  "Birkaç saniye içinde asistanın kendi Chrome penceresi açılacak (senin normal Chrome'undan ayrı).\n\n"
                  "LinkedIn'e o pencereden giriş yap. Giriş bitince pencereyi kapatma, simge durumuna küçült: "
                  "asistan o pencereyi kullanıyor.")
        QTimer.singleShot(1500, self.degisti.emit)

    def _bildir(self, metin: str, hata: bool = False) -> None:
        self.bildirim.setText(metin)
        self.bildirim.setProperty("hata", "evet" if hata else "hayir")
        yeniden_boya(self.bildirim)
        QTimer.singleShot(12000, lambda: self.bildirim.setText("") if self.bildirim.text() == metin else None)

    # ---------------- Yenileme ----------------

    def yenile(self, veri: dict) -> None:
        d, ayarlar = veri["durum"], veri["ayarlar"]
        if not self._yuklendi:
            self._yuklendi = True
            self._secili = servis.secili_sektor_kodlari()
            self.konum.ayarla(*servis.secili_konumlar())
            self._forma_yukle(ayarlar)

        metin, tur = durum_bilgisi(d)
        hap_ayarla(self.durum_hapi, metin, tur)
        giris_yapildi = d.get("bot_giris_yapildi")
        self.oturum_yazisi.setText({
            True: "LinkedIn oturumu açık, bot senin hesabınla çalışabiliyor.",
            False: "LinkedIn oturumu açık değil: önce 'LinkedIn'e Giriş Yap'a bas.",
        }.get(giris_yapildi, "LinkedIn oturumu henüz kontrol edilmedi; ilk işlemde kontrol edilecek."))
        self.giris_dugmesi.setVisible(giris_yapildi is not True)
        limitler = ayarlar["limitler"]
        self.bugun_yazisi.setText(
            f"Son 24 saat: {d.get('baglanti_son_gun', 0)}/{limitler['baglanti_gunluk']} bağlantı isteği · "
            f"{d.get('mesaj_son_gun', 0)}/{limitler['mesaj_gunluk']} mesaj · son 7 gün "
            f"{d.get('baglanti_son_hafta', 0)}/{limitler['baglanti_haftalik']} istek"
        )
        uyarilar = []
        if d.get("arama_siniri"):
            uyarilar.append("LinkedIn aylık arama sınırı doldu: bugün yeni kişi aranmıyor, sıradakilere gönderim sürüyor.")
        if d.get("calisiyor") and not self._secili:
            uyarilar.append("Çalışıyor ama seçili sektör yok: yukarıdan sektör seçip 'Kaydet ve Göndermeye Başla'ya bas.")
        hap_ayarla(self.uyari_yazisi, " ".join(uyarilar), "uyari" if uyarilar else "")
        self.uyari_yazisi.setVisible(bool(uyarilar))

        calisiyor = bool(d.get("calisiyor"))
        self.durdur_dugmesi.setVisible(calisiyor)
        self.baslat_dugmesi.setText("Kaydet ve Devam Et" if calisiyor else "Kaydet ve Göndermeye Başla")

        toplam = {anahtar: sum(s[anahtar] for s in veri["rapor"]) for anahtar, _ in HUNI}
        for anahtar, _ in HUNI:
            self.huni[anahtar].ayarla(toplam[anahtar])
