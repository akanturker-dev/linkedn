"""Kampanyanin yapi taslari: hizmetler, sirket buyukluk dilimleri, karar verici rolleri ve genel ilk mesaj.
Hangi sektore hangi paketin gidecegi sektorler.py icindedir."""

HIZMETLER = {"maps": "Google Maps itibar", "seo": "SEO", "web": "Web sitesi"}

# LinkedIn'in sirket buyuklugu dilimleri
BOYUT_BANTLARI = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1001+"]

ROL_GRUPLARI = {
    "kurucu": ["Founder", "Co-Founder", "Owner", "CEO", "Managing Partner"],
    "genel_mudur": ["General Manager", "Managing Director"],
    "pazarlama_lideri": ["Marketing Director", "Head of Marketing", "CMO"],
    "pazarlama": ["Marketing Manager", "Digital Marketing Manager", "Brand Manager"],
    "departman": [
        "Export Manager", "After Sales Manager", "Operations Director", "Business Development Director",
        "Sales Director", "Commercial Director", "E-commerce Manager", "International Patient Manager",
    ],
}

# Sirket buyuklugune gore dogru muhatap: 1-20 kurucu; 20-100 kurucu + genel mudur + pazarlama muduru;
# 100-500 pazarlama lideri ve dijital pazarlama; 500+ departman yoneticileri
UYGUN_GRUPLAR = {
    "1-10": {"kurucu"},
    "11-50": {"kurucu", "genel_mudur", "pazarlama"},
    "51-200": {"kurucu", "genel_mudur", "pazarlama_lideri", "pazarlama", "departman"},
    "201-500": {"pazarlama_lideri", "pazarlama", "departman"},
    "501-1000": {"pazarlama_lideri", "departman"},
    "1001+": {"pazarlama_lideri", "departman"},
}
BUYUKLUK_BILINMIYORSA_UYGUN = {"kurucu", "genel_mudur", "pazarlama_lideri"}

# Turkiye'deki profillerde unvan cogu zaman Ingilizce, bazen Turkce yazilir; aramada ikisi birlikte kullanilir
ROL_TURKCELERI = {
    "Founder": ["Kurucu"],
    "Co-Founder": ["Kurucu Ortak"],
    "Owner": ["Sahibi"],
    "Managing Partner": ["Yönetici Ortak"],
    "General Manager": ["Genel Müdür"],
    "Managing Director": ["Yönetici Direktör"],
    "Marketing Director": ["Pazarlama Direktörü"],
    "Head of Marketing": ["Pazarlama Lideri"],
    "Marketing Manager": ["Pazarlama Müdürü"],
    "Digital Marketing Manager": ["Dijital Pazarlama Müdürü"],
    "Brand Manager": ["Marka Müdürü"],
    "Operations Director": ["Operasyon Direktörü"],
    "After Sales Manager": ["Satış Sonrası Müdürü", "Satış Sonrası Hizmetler Müdürü"],
    "Sales Director": ["Satış Direktörü"],
    "Export Manager": ["İhracat Müdürü"],
    "Commercial Director": ["Ticari Direktör"],
    "Business Development Director": ["İş Geliştirme Direktörü"],
    "E-commerce Manager": ["E-Ticaret Müdürü"],
    "International Patient Manager": ["Uluslararası Hasta Müdürü"],
}

_ACILIS = "Merhaba {ad}, {isletme_adi} tarafına bakarken dijital görünürlükle ilgili dikkatimi çeken birkaç nokta oldu. "
_KAPANIS = "İsterseniz size burada kısaca göndereyim, herhangi bir sunum hazırlamanıza gerek yok."

GENEL_ILK_MESAJ = _ACILIS + _KAPANIS

TUM_ROLLER = [rol for grup in ROL_GRUPLARI.values() for rol in grup]


def rol_ifadeleri(rol: str) -> list:
    return [rol] + ROL_TURKCELERI.get(rol, [])


def rol_grubu(rol: str):
    for grup, roller in ROL_GRUPLARI.items():
        if rol in roller:
            return grup
    return None
