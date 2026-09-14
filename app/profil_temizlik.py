from pathlib import Path

from .config import CHROME_PROFILE_DIR

SINIR_BAYT = 1024 ** 3
# Oturum icin sadece cerezler ve onlari cozen anahtar (Local State) gerekir
KORUNACAK_DOSYALAR = {"Cookies", "Cookies-journal", "Local State"}


def _klasor_boyutu(yol: Path) -> int:
    toplam = 0
    for dosya in yol.rglob("*"):
        try:
            if dosya.is_file():
                toplam += dosya.stat().st_size
        except OSError:
            continue
    return toplam


def profili_temizle() -> int:
    """Profil 1 GB'i gecince cerezler ve Local State disindaki her seyi siler.
    Tarayici acilmadan once cagrilmali (acikken dosyalar kilitli olur). Silinen bayt sayisini dondurur."""
    if not CHROME_PROFILE_DIR.exists():
        return 0
    once = _klasor_boyutu(CHROME_PROFILE_DIR)
    if once < SINIR_BAYT:
        return 0
    yollar = sorted(CHROME_PROFILE_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True)
    for yol in yollar:
        try:
            if yol.is_file() and yol.name not in KORUNACAK_DOSYALAR:
                yol.unlink()
            elif yol.is_dir() and not any(yol.iterdir()):
                yol.rmdir()
        except OSError:
            continue
    return once - _klasor_boyutu(CHROME_PROFILE_DIR)
