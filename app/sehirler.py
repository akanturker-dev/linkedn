"""Aramanin yapilacagi sehirler ve ilceler: is hacmi ve odeme gucu sirasina gore dizildi.
Kucuk ve dusuk butceli yerler bilerek listede yok; listede yer kaplamasin, arama hakkini harcamasin.

Sehir = kisinin LinkedIn konumunda aranir (profillerde konum sehir duzeyinde yazilir).
Ilce = arama cumlesine eklenen ek kelime; profilinde/sirketinde o ilce gecenleri bulur, aday sayisini daraltir.
"""

SEHIRLER = [
    {"ad": "İstanbul", "aciklama": "Türkiye ticaretinin merkezi: şirket sayısı ve bütçe en yüksek.",
     "ilceler": ["Ataşehir", "Şişli", "Beşiktaş", "Kadıköy", "Sarıyer", "Ümraniye", "Bakırköy", "Başakşehir",
                 "Beylikdüzü", "Üsküdar", "Kartal", "Maltepe", "Kâğıthane", "Pendik", "Tuzla", "Fatih",
                 "Zeytinburnu", "Bağcılar", "Büyükçekmece"]},
    {"ad": "Ankara", "aciklama": "Kamu, savunma ve kurumsal hizmet şirketlerinin merkezi.",
     "ilceler": ["Çankaya", "Yenimahalle", "Ostim", "Etimesgut", "Gölbaşı", "Sincan", "Altındağ"]},
    {"ad": "İzmir", "aciklama": "İhracat, üretim ve turizm; kurumsallaşmış orta ölçekli şirket çok.",
     "ilceler": ["Bayraklı", "Konak", "Bornova", "Karşıyaka", "Çiğli", "Gaziemir", "Torbalı", "Çeşme", "Urla"]},
    {"ad": "Bursa", "aciklama": "Otomotiv, tekstil ve mobilya sanayisi; ihracatçı yoğun.",
     "ilceler": ["Nilüfer", "Osmangazi", "Yıldırım", "İnegöl", "Gürsu", "Kestel", "Mudanya"]},
    {"ad": "Kocaeli", "aciklama": "Sanayi ve lojistiğin kalbi: fabrika ve depo yoğunluğu en yüksek illerden.",
     "ilceler": ["Gebze", "İzmit", "Çayırova", "Dilovası", "Körfez", "Darıca"]},
    {"ad": "Antalya", "aciklama": "Turizm, otel ve gayrimenkul; sezonluk bütçeler yüksek.",
     "ilceler": ["Muratpaşa", "Konyaaltı", "Kepez", "Alanya", "Manavgat", "Serik", "Kemer"]},
    {"ad": "Gaziantep", "aciklama": "Gıda, tekstil ve halı sanayisi; güçlü ihracatçı taban.",
     "ilceler": ["Şehitkamil", "Şahinbey"]},
    {"ad": "Konya", "aciklama": "Makine, otomotiv yan sanayi ve tarım ekipmanı üretimi.",
     "ilceler": ["Selçuklu", "Meram", "Karatay"]},
    {"ad": "Adana", "aciklama": "Tarım, gıda ve tekstil sanayisi; bölge ticaret merkezi.",
     "ilceler": ["Çukurova", "Seyhan", "Sarıçam", "Yüreğir"]},
    {"ad": "Kayseri", "aciklama": "Mobilya, metal ve kablo üretimi; kurumsal aile şirketleri.",
     "ilceler": ["Melikgazi", "Kocasinan", "Talas"]},
    {"ad": "Mersin", "aciklama": "Liman, lojistik ve ihracat; dış ticaret şirketleri yoğun.",
     "ilceler": ["Yenişehir", "Mezitli", "Akdeniz", "Tarsus"]},
    {"ad": "Denizli", "aciklama": "Tekstil, ev tekstili ve mermer ihracatı.",
     "ilceler": ["Merkezefendi", "Pamukkale"]},
    {"ad": "Tekirdağ", "aciklama": "Çorlu–Çerkezköy hattı: tekstil, kimya ve ambalaj fabrikaları.",
     "ilceler": ["Çorlu", "Çerkezköy", "Süleymanpaşa", "Kapaklı", "Ergene"]},
    {"ad": "Manisa", "aciklama": "Beyaz eşya, elektronik ve gıda üretimi; organize sanayi güçlü.",
     "ilceler": ["Yunusemre", "Şehzadeler", "Turgutlu", "Salihli"]},
    {"ad": "Muğla", "aciklama": "Lüks turizm, otel, villa ve marina işletmeleri.",
     "ilceler": ["Bodrum", "Marmaris", "Fethiye", "Milas", "Menteşe"]},
    {"ad": "Eskişehir", "aciklama": "Havacılık, makine ve seramik sanayisi; üniversite ekonomisi.",
     "ilceler": ["Tepebaşı", "Odunpazarı"]},
    {"ad": "Sakarya", "aciklama": "Otomotiv ana ve yan sanayi; fabrika yoğunluğu yüksek.",
     "ilceler": ["Serdivan", "Adapazarı", "Arifiye", "Hendek"]},
    {"ad": "Samsun", "aciklama": "Karadeniz'in ticaret ve lojistik merkezi.",
     "ilceler": ["Atakum", "İlkadım", "Tekkeköy"]},
    {"ad": "Aydın", "aciklama": "Tarım, gıda ihracatı ve sahil turizmi.",
     "ilceler": ["Efeler", "Kuşadası", "Didim", "Nazilli"]},
    {"ad": "Balıkesir", "aciklama": "Gıda, tarım sanayi ve Bandırma limanı.",
     "ilceler": ["Bandırma", "Altıeylül", "Karesi", "Edremit", "Ayvalık"]},
]

_ADA_GORE = {s["ad"]: s for s in SEHIRLER}


def sehir(ad: str):
    return _ADA_GORE.get(ad)


def sehir_adlari() -> list:
    return [s["ad"] for s in SEHIRLER]


def ilceler(sehir_adlari_listesi: list) -> list:
    """Secili sehirlerin ilceleri: [(sehir adi, [ilce, ...]), ...] — sehirlerin kendi sirasiyla."""
    secili = [s for s in SEHIRLER if s["ad"] in (sehir_adlari_listesi or [])]
    return [(s["ad"], list(s["ilceler"])) for s in secili]
