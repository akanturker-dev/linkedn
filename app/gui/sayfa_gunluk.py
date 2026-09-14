from datetime import datetime

from PySide6.QtGui import QColor
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from .bilesenler import Sayfa


class GunlukSayfasi(Sayfa):
    def __init__(self):
        super().__init__("Günlük", "Botun yaptığı her işin kaydı. Kırmızılar hata, turuncular uyarıdır; en yenisi en üstte.")
        self.liste = QListWidget()
        self.liste.setWordWrap(True)
        self.icerik.addWidget(self.liste, 1)
        self._son_log_id = None

    def yenile(self, veri: dict) -> None:
        loglar = veri["loglar"]
        son_id = loglar[0]["id"] if loglar else None
        if son_id == self._son_log_id:
            return
        self._son_log_id = son_id
        self.liste.clear()
        for kayit in loglar:
            zaman = datetime.fromisoformat(kayit["zaman"]).strftime("%d.%m.%Y  %H:%M:%S")
            oge = QListWidgetItem(f"{zaman}     {kayit['mesaj']}")
            if kayit["seviye"] == "hata":
                oge.setForeground(QColor("#B42318"))
            elif kayit["seviye"] == "uyari":
                oge.setForeground(QColor("#B54708"))
            self.liste.addItem(oge)
