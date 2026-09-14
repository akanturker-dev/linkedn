from PySide6.QtGui import QColor, QPalette

AKSAN = "#4F46E5"
AKSAN_KOYU = "#4338CA"
AKSAN_ACIK = "#EEF0FF"
SECIM_RENGI = "#E0E7FF"
ZEMIN = "#F5F6FA"
KENAR = "#E4E7EC"
YAZI = "#101828"
YAZI_2 = "#475467"
YAZI_3 = "#667085"

QSS = f"""
* {{ font-family: "Segoe UI"; font-size: 11pt; color: {YAZI}; }}
QMainWindow, QWidget#kok, QWidget#sayfa {{ background: {ZEMIN}; }}
QDialog, QMessageBox {{ background: #FFFFFF; }}
QToolTip {{ background: {YAZI}; color: #FFFFFF; border: none; padding: 6px 8px; font-size: 10.5pt; }}

QFrame#yanMenu {{ background: #FFFFFF; border-right: 1px solid {KENAR}; }}
QLabel#logo {{ background: {AKSAN}; color: #FFFFFF; font-weight: 700; border-radius: 8px; padding: 4px 10px; font-size: 12pt; }}
QLabel#uygulamaAdi {{ font-size: 13pt; font-weight: 700; }}
QLabel#menuBaslik {{ color: {YAZI_3}; font-size: 9.5pt; font-weight: 700; padding: 10px 14px 4px 14px; }}
QPushButton#menu {{ text-align: left; padding: 11px 14px; border: none; border-radius: 10px; background: transparent;
                    color: #344054; font-size: 11.5pt; font-weight: 600; }}
QPushButton#menu:hover {{ background: #F2F4F7; }}
QPushButton#menu:checked {{ background: {AKSAN_ACIK}; color: {AKSAN_KOYU}; }}

QLabel#sayfaBaslik {{ font-size: 20pt; font-weight: 700; }}
QLabel#sayfaAciklama {{ color: {YAZI_2}; font-size: 11pt; }}
QLabel#bolumBaslik {{ font-size: 13pt; font-weight: 700; }}
QLabel#ikincil {{ color: {YAZI_2}; }}
QLabel#soluk {{ color: {YAZI_3}; font-size: 10pt; }}

QFrame#kart {{ background: #FFFFFF; border: 1px solid {KENAR}; border-radius: 12px; }}
/* Sayfanin asil bolumu: renkli kenarlik ve hafif renkli zemin, goz once buraya gitsin */
QFrame#vurguKart {{ background: #FFFFFF; border: 2px solid {AKSAN}; border-radius: 14px; }}
QLabel#vurguRozet {{ background: {AKSAN}; color: #FFFFFF; border-radius: 10px; padding: 4px 12px;
                    font-size: 9.5pt; font-weight: 700; }}
QLabel#vurguBaslik {{ font-size: 16pt; font-weight: 700; color: {AKSAN_KOYU}; }}
QLabel#vurguAciklama {{ color: {YAZI_2}; font-size: 11.5pt; }}
QLabel#kpiDeger {{ font-size: 22pt; font-weight: 700; }}
QLabel#kpiEtiket {{ color: {YAZI_2}; font-size: 10.5pt; }}
QLabel#kpiOran {{ color: #067647; font-size: 10pt; font-weight: 700; }}

QLabel#hap {{ border-radius: 12px; padding: 4px 12px; font-weight: 700; font-size: 10.5pt; background: #F2F4F7; color: #344054; }}
QLabel#hap[tur="iyi"] {{ background: #ECFDF3; color: #067647; }}
QLabel#hap[tur="uyari"] {{ background: #FFFAEB; color: #B54708; }}
QLabel#hap[tur="hata"] {{ background: #FEF3F2; color: #B42318; }}

QPushButton {{ background: #FFFFFF; border: 1px solid #D0D5DD; border-radius: 8px; padding: 8px 16px; font-weight: 600;
              color: #344054; }}
QPushButton:hover {{ background: #F9FAFB; }}
QPushButton:pressed {{ background: #F2F4F7; }}
QPushButton:disabled {{ color: #98A2B3; background: #F9FAFB; }}
QPushButton#aksan {{ background: {AKSAN}; border-color: {AKSAN}; color: #FFFFFF; }}
QPushButton#aksan:hover {{ background: {AKSAN_KOYU}; }}
QPushButton#tehlike {{ background: #D92D20; border-color: #D92D20; color: #FFFFFF; }}
QPushButton#tehlike:hover {{ background: #B42318; }}
QPushButton[buyuk="evet"] {{ padding: 12px 18px; font-size: 12pt; }}

QLineEdit, QPlainTextEdit {{ background: #FFFFFF; border: 1px solid #D0D5DD; border-radius: 8px; padding: 8px 10px;
                            selection-background-color: {SECIM_RENGI}; selection-color: {YAZI}; }}
QLineEdit:focus, QPlainTextEdit:focus {{ border: 1px solid {AKSAN}; }}
QComboBox QAbstractItemView {{ background: #FFFFFF; selection-background-color: {SECIM_RENGI}; selection-color: {YAZI}; }}
QCheckBox {{ spacing: 8px; }}

QTableView {{ background: #FFFFFF; border: 1px solid {KENAR}; border-radius: 12px; gridline-color: #EAECF0;
             alternate-background-color: #FAFAFC; selection-background-color: {SECIM_RENGI}; selection-color: {YAZI}; }}
/* Qt hucre ic boslugunu ancak kenarlik da tanimliysa uygular (olculdu: yazi 6 px yerine 16 px'ten baslar) */
QTableView::item {{ padding: 0px 10px; border: 0px; }}
QHeaderView {{ background: #FFFFFF; }}
QHeaderView::section {{ background: #F9FAFB; color: {YAZI_2}; font-weight: 600; font-size: 10.5pt; border: none;
                       border-bottom: 1px solid {KENAR}; border-right: 1px solid #EAECF0; padding: 10px 10px; }}
QHeaderView::section:vertical {{ color: #98A2B3; font-weight: 400; padding: 0 8px; }}
QTableCornerButton::section {{ background: #F9FAFB; border: none; border-bottom: 1px solid {KENAR}; }}
QListWidget {{ background: #FFFFFF; border: 1px solid {KENAR}; border-radius: 12px; padding: 6px; }}
QListWidget::item {{ padding: 8px 10px; border-bottom: 1px solid #F2F4F7; }}
QTreeWidget {{ background: #FFFFFF; border: 1px solid {KENAR}; border-radius: 8px; }}
QTreeWidget::item {{ padding: 4px 2px; }}
QScrollArea {{ border: none; background: transparent; }}
QWidget#qt_scrollarea_viewport {{ background: transparent; }}

QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: #D0D5DD; border-radius: 5px; min-height: 36px; }}
QScrollBar::handle:vertical:hover {{ background: #98A2B3; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: #D0D5DD; border-radius: 5px; min-width: 36px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0px; height: 0px; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

QProgressBar {{ background: #F2F4F7; border: none; border-radius: 5px; max-height: 10px; }}
QProgressBar::chunk {{ background: {AKSAN}; border-radius: 5px; }}
QProgressBar[tur="dolu"]::chunk {{ background: #F79009; }}

QFrame#guvenlikBandi {{ background: #FEF3F2; border: 1px solid #FECDCA; border-radius: 12px; }}
QLabel#guvenlikYazi {{ color: #B42318; font-weight: 600; }}
QLabel#bildirim {{ font-weight: 600; color: #067647; }}
QLabel#bildirim[hata="evet"] {{ color: #B42318; }}
QLabel#sayac {{ color: {YAZI_3}; font-size: 10pt; }}
QLabel#sayac[asim="evet"] {{ color: #B42318; font-weight: 700; }}
QFrame#altCubuk {{ background: #FFFFFF; border-top: 1px solid {KENAR}; }}
QFrame#yanKutu {{ background: #F9FAFB; border: 1px solid {KENAR}; border-radius: 12px; }}
QLabel#alanBaslik {{ font-weight: 700; }}
QLabel#grupBaslik {{ font-weight: 700; color: {YAZI_2}; font-size: 10.5pt; }}
QLabel#vurgu {{ font-size: 16pt; font-weight: 700; }}
QLabel#onizleme {{ background: #F9FAFB; border: 1px solid {KENAR}; border-radius: 8px; padding: 10px 12px; color: {YAZI_2}; }}
QLabel#cip {{ background: #F2F4F7; color: #344054; border-radius: 10px; padding: 3px 10px; font-size: 10pt; font-weight: 600; }}
QLabel#cip[tur="maps"] {{ background: #ECFDF3; color: #067647; }}
QLabel#cip[tur="seo"] {{ background: #EFF8FF; color: #175CD3; }}
QLabel#cip[tur="web"] {{ background: #F4F3FF; color: #5925DC; }}
QLabel#metrikDeger {{ font-size: 15pt; font-weight: 700; }}
QLabel#metrikEtiket {{ color: {YAZI_3}; font-size: 9.5pt; }}
QLabel#durumYazi {{ font-weight: 600; color: {YAZI_2}; }}
QLabel#durumYazi[tur="iyi"] {{ color: #067647; }}
QLabel#durumYazi[tur="uyari"] {{ color: #B54708; }}
QLabel#durumYazi[tur="hata"] {{ color: #B42318; }}
QPushButton#durdur {{ background: #FFFFFF; border: 1px solid #FDA29B; color: #B42318; }}
QPushButton#durdur:hover {{ background: #FEF3F2; }}
QPushButton#cipDugme {{ background: #F2F4F7; border: 1px solid {KENAR}; border-radius: 12px; padding: 5px 12px;
                       font-size: 10pt; font-weight: 600; color: #344054; }}
QPushButton#cipDugme:hover {{ background: #FEF3F2; border-color: #FDA29B; color: #B42318; }}
QPushButton#silDugme {{ color: #B42318; }}
QPushButton#silDugme:hover {{ background: #FEF3F2; }}
QMenu {{ background: #FFFFFF; border: 1px solid {KENAR}; padding: 6px; }}
QMenu::item {{ padding: 8px 20px; border-radius: 6px; }}
QMenu::item:selected {{ background: {SECIM_RENGI}; color: {YAZI}; }}
QStatusBar {{ background: #FFFFFF; border-top: 1px solid {KENAR}; color: {YAZI_2}; }}
"""


def acik_palet() -> QPalette:
    """Windows koyu moddayken Qt, QSS'in boyamadigi parcalara (acilir liste, sayi kutusu, uyari penceresi)
    koyu renk verir; acik temanin icinde siyah kutular cikar. Butun roller acik renklerle sabitlenir."""
    palet = QPalette()
    renkler = {
        QPalette.ColorRole.Window: ZEMIN,
        QPalette.ColorRole.WindowText: YAZI,
        QPalette.ColorRole.Base: "#FFFFFF",
        QPalette.ColorRole.AlternateBase: "#FAFAFC",
        QPalette.ColorRole.ToolTipBase: YAZI,
        QPalette.ColorRole.ToolTipText: "#FFFFFF",
        QPalette.ColorRole.PlaceholderText: "#98A2B3",
        QPalette.ColorRole.Text: YAZI,
        QPalette.ColorRole.Button: "#FFFFFF",
        QPalette.ColorRole.ButtonText: "#344054",
        QPalette.ColorRole.BrightText: "#FFFFFF",
        QPalette.ColorRole.Highlight: SECIM_RENGI,
        QPalette.ColorRole.HighlightedText: YAZI,
        QPalette.ColorRole.Link: AKSAN,
        QPalette.ColorRole.Light: "#FFFFFF",
        QPalette.ColorRole.Midlight: "#F2F4F7",
        QPalette.ColorRole.Mid: "#D0D5DD",
        QPalette.ColorRole.Dark: "#98A2B3",
        QPalette.ColorRole.Shadow: YAZI_3,
    }
    for rol, renk in renkler.items():
        palet.setColor(rol, QColor(renk))
    for rol in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text, QPalette.ColorRole.ButtonText):
        palet.setColor(QPalette.ColorGroup.Disabled, rol, QColor("#98A2B3"))
    return palet


def yeniden_boya(widget) -> None:
    """Dinamik ozellik (setProperty) degisince QSS kurallarinin yeniden uygulanmasi icin gerekli."""
    widget.style().unpolish(widget)
    widget.style().polish(widget)
    widget.update()
