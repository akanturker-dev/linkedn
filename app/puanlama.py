"""Aday puani: yalnizca esigi gecen (varsayilan 8+) adaylara bağlantı isteği ve DM gider."""

from .kampanyalar import BUYUKLUK_BILINMIYORSA_UYGUN, UYGUN_GRUPLAR, rol_grubu

KUCUK_ORTA_BANTLAR = ("11-50", "51-200")


def puan_hesapla(lead: dict, puanlama: dict) -> tuple:
    """(puan, gerekceler) dondurur. Turkiye sarti puanda degil, aramada ve konum kontrolunde uygulanir."""
    puan, gerekceler = 0, []
    bant = lead.get("sirket_boyutu")
    grup = rol_grubu(lead.get("linkedin_rol"))
    uygun = UYGUN_GRUPLAR.get(bant, BUYUKLUK_BILINMIYORSA_UYGUN)
    if grup and grup in uygun:
        puan += puanlama["rol_uyumlu"]
        gerekceler.append(f"doğru muhatap +{puanlama['rol_uyumlu']}")
    elif grup:
        puan += puanlama["rol_diger"]
        gerekceler.append(f"rol bu büyüklük için ideal değil +{puanlama['rol_diger']}")
    if bant in KUCUK_ORTA_BANTLAR:
        puan += puanlama["boyut_11_200"]
        gerekceler.append(f"{bant} çalışan +{puanlama['boyut_11_200']}")
    elif bant == "201-500":
        puan += puanlama["boyut_201_500"]
        gerekceler.append(f"201-500 çalışan +{puanlama['boyut_201_500']}")
    gun = lead.get("son_paylasim_gun")
    if gun is not None and 0 <= gun <= 30:
        puan += puanlama["aktif_30_gun"]
        gerekceler.append(f"son 30 günde paylaşım +{puanlama['aktif_30_gun']}")
    if lead.get("website"):
        puan += puanlama["web_sitesi"]
        gerekceler.append(f"web sitesi var +{puanlama['web_sitesi']}")
    return puan, gerekceler


def ulasilabilir_en_yuksek(puanlama: dict, kontroller: dict) -> int:
    """Acik kontrollere gore bir adayin alabilecegi en yuksek puan; esik bundan buyukse kimseye yazilmaz."""
    en_yuksek = puanlama["rol_uyumlu"] + puanlama["web_sitesi"]
    if kontroller.get("sirket", True):
        en_yuksek += max(puanlama["boyut_11_200"], puanlama["boyut_201_500"])
    if kontroller.get("aktivite", True):
        en_yuksek += puanlama["aktif_30_gun"]
    return en_yuksek
