_SADELESTIRME = str.maketrans(
    {"İ": "i", "I": "i", "ı": "i", "Ş": "s", "ş": "s", "Ğ": "g", "ğ": "g",
     "Ü": "u", "ü": "u", "Ö": "o", "ö": "o", "Ç": "c", "ç": "c"}
)


def sade_metin(metin) -> str:
    """Turkce harfleri sadelestirip kucultur: 'KADIKÖY', 'kadıköy' ve 'kadikoy' ayni sonucu verir.
    str.lower/casefold 'I'yi 'ı' yerine 'i' yapar ve 'İ'yi iki karaktere boler; bu yuzden kullanilmaz."""
    return str(metin or "").translate(_SADELESTIRME).lower()
