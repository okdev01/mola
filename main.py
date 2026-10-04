import math
import sys
from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QFont
from PySide6.QtWidgets import (QComboBox, QFileDialog, QHBoxLayout, QLineEdit,
    QListWidget, QListWidgetItem, QMessageBox, QSpinBox, QWidget, QVBoxLayout)

from desktop import Shell, button, label, metric, card, run
from engine import Countdown, Store


class Dial(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.remaining, self.total = 1500, 1500
        self.caption = "ODAK ZAMANI"
        self.setMinimumSize(280, 270)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        size = min(self.width(), self.height()) - 26
        x, y = (self.width()-size)/2, (self.height()-size)/2
        from PySide6.QtCore import QRectF
        rect = QRectF(x, y, size, size)
        painter.setPen(QPen(QColor("#2c3c56"), 9))
        painter.drawEllipse(rect)
        painter.setPen(QPen(QColor("#baff72"), 9, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(rect, 90*16, -int(360*16*self.remaining/self.total))
        painter.setPen(QColor("#eff5ff"))
        painter.setFont(QFont("Segoe UI", 42, QFont.Weight.Bold))
        seconds = math.ceil(self.remaining)
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{seconds//60:02d}:{seconds%60:02d}")
        painter.setFont(QFont("Segoe UI", 9))
        painter.setPen(QColor("#a6b5cf"))
        painter.drawText(QRectF(x,y+size*.64,size,35), Qt.AlignmentFlag.AlignCenter, self.caption)
        painter.end()


class Window(Shell):
    def __init__(self, folder):
        super().__init__("Mola", "Bir işe odaklan.\nSonra nefes al.", "Bugün, bir adım daha.",
                         "Kendine bir odak süresi ayır. Görevlerin ve ilerlemen burada kalsın.", "Odak & görevler")
        self.folder = folder
        self.setMinimumHeight(760)
        self.store = Store(folder / "mola.db")
        self.countdown = Countdown()
        self.session_title = ""
        metrics = QHBoxLayout()
        a, self.session_metric = metric("BUGÜNKÜ OTURUM", "0")
        b, self.minute_metric = metric("ODAK DAKİKASI", "0")
        c, self.task_metric = metric("AÇIK GÖREV", "0")
        for item in (a,b,c): metrics.addWidget(item)
        self.body.addLayout(metrics)
        columns = QHBoxLayout()
        clock_card, clock_layout = card()
        self.mode = QComboBox()
        self.mode.addItems(["Odak", "Kısa mola", "Uzun mola"])
        self.mode.currentIndexChanged.connect(self.change_mode)
        clock_layout.addWidget(self.mode)
        self.dial = Dial()
        clock_layout.addWidget(self.dial, 1)
        duration = QHBoxLayout()
        duration.addWidget(label("Süre (dakika)", "muted"))
        self.minutes = QSpinBox()
        self.minutes.setRange(1, 120)
        self.minutes.setValue(25)
        self.minutes.valueChanged.connect(self.change_duration)
        duration.addWidget(self.minutes)
        clock_layout.addLayout(duration)
        actions = QHBoxLayout()
        self.start_button = button("Başlat", self.start_pause, True)
        actions.addWidget(self.start_button)
        actions.addWidget(button("Sıfırla", self.reset))
        clock_layout.addLayout(actions)
        columns.addWidget(clock_card, 1)
        tasks_card, tasks_layout = card()
        tasks_layout.addWidget(label("Aklındakileri boşalt", "metric"))
        tasks_layout.addWidget(label("Bir görevi seçerek odak oturumuna bağlayabilirsin.", "muted", True))
        input_row = QHBoxLayout()
        self.task_input = QLineEdit()
        self.task_input.setMaxLength(200)
        self.task_input.setPlaceholderText("Yeni görev ekle…")
        self.task_input.returnPressed.connect(self.add_task)
        input_row.addWidget(self.task_input)
        input_row.addWidget(button("Ekle", self.add_task))
        tasks_layout.addLayout(input_row)
        self.tasks = QListWidget()
        self.tasks.itemChanged.connect(self.task_changed)
        tasks_layout.addWidget(self.tasks, 1)
        tools = QHBoxLayout()
        tools.addWidget(button("Seçili görevi sil", self.remove_task))
        tools.addWidget(button("Yedek al", self.backup))
        tasks_layout.addLayout(tools)
        columns.addWidget(tasks_card, 1)
        self.body.addLayout(columns, 1)
        self.finish_layout()
        self.timer = QTimer(self)
        self.timer.setInterval(200)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.refresh()
        self.status.setText("Hazır olduğunda başlat. Uygulama kapatılırsa süren oturum kaydedilmez.")

    def refresh(self):
        self.tasks.blockSignals(True)
        selected = self.tasks.currentItem().data(Qt.ItemDataRole.UserRole) if self.tasks.currentItem() else None
        self.tasks.clear()
        rows = self.store.tasks()
        for task in rows:
            item = QListWidgetItem(task["title"])
            item.setData(Qt.ItemDataRole.UserRole, task["id"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if task["done"] else Qt.CheckState.Unchecked)
            self.tasks.addItem(item)
            if task["id"] == selected: self.tasks.setCurrentItem(item)
        self.tasks.blockSignals(False)
        count, seconds = self.store.today()
        self.session_metric.setText(str(count))
        self.minute_metric.setText(str(seconds//60))
        self.task_metric.setText(str(sum(not t["done"] for t in rows)))

    def add_task(self):
        try:
            self.store.add(self.task_input.text())
            self.task_input.clear()
            self.refresh()
        except (ValueError, OSError) as exc:
            self.status.setText(str(exc))

    def task_changed(self, item):
        self.store.toggle(item.data(Qt.ItemDataRole.UserRole))
        self.refresh()

    def remove_task(self):
        item = self.tasks.currentItem()
        if item and QMessageBox.question(self, "Görevi sil", "Seçili görev silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.store.remove(item.data(Qt.ItemDataRole.UserRole))
            self.refresh()

    def change_mode(self, index):
        if hasattr(self, "minutes"):
            self.minutes.setValue([25,5,15][index])
            self.reset()

    def change_duration(self, value):
        if hasattr(self, "dial"):
            self.reset()

    def start_pause(self):
        if self.countdown.running:
            self.countdown.pause()
            self.start_button.setText("Devam et")
            self.status.setText("Duraklatıldı. Hazır olduğunda devam edebilirsin.")
        else:
            if self.countdown.remaining == 0:
                self.reset()
            if self.countdown.remaining == self.countdown.total:
                item = self.tasks.currentItem()
                self.session_title = item.text() if item else "Serbest odak"
            self.countdown.start()
            self.start_button.setText("Duraklat")
            self.status.setText(self.session_title if self.mode.currentIndex() == 0 else "Biraz dinlen. Süre bitince burada haber vereceğim.")
        active = self.countdown.running or self.countdown.remaining < self.countdown.total
        self.mode.setEnabled(not active)
        self.minutes.setEnabled(not active)
        self.tick()

    def reset(self):
        self.countdown.reset(self.minutes.value()*60)
        self.start_button.setText("Başlat")
        self.mode.setEnabled(True)
        self.minutes.setEnabled(True)
        self.tick()

    def tick(self):
        remaining = self.countdown.tick()
        self.dial.remaining, self.dial.total = remaining, self.countdown.total
        self.dial.caption = "ODAK ZAMANI" if self.mode.currentIndex() == 0 else "NEFES AL"
        self.dial.update()
        if remaining == 0 and not self.countdown.reported:
            if self.mode.currentIndex() == 0:
                self.store.complete(self.countdown.identifier, self.countdown.total, self.session_title)
                self.status.setText("Odak oturumu tamamlandı. Bir molayı hak ettin!")
            else:
                self.status.setText("Mola tamamlandı. Yeni bir odağa hazır mısın?")
            self.countdown.reported = True
            self.start_button.setText("Yeniden başlat")
            self.mode.setEnabled(True)
            self.minutes.setEnabled(True)
            self.refresh()

    def backup(self):
        path, _ = QFileDialog.getSaveFileName(self, "Yedek kaydet", "Mola-yedek.db", "Veritabanı (*.db)")
        if path:
            try:
                self.store.backup(path)
                self.status.setText("Yedek kaydedildi: " + path)
            except Exception as exc:
                self.show_error(str(exc))

    def closeEvent(self, event):
        if self.countdown.remaining < self.countdown.total and not self.countdown.reported:
            answer = QMessageBox.question(self, "Oturum devam ediyor", "Tamamlanmamış oturum kaydedilmez. Çıkılsın mı?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                event.ignore()
                return
        self.timer.stop()
        event.accept()

    def seed_demo(self):
        for text in ["Bugünün önceliklerini belirle", "Kitabımdan 20 sayfa oku", "Yürüyüş için zaman ayır"]:
            self.store.add(text)
        self.store.complete("demo-one", 1500, "Okuma")
        self.store.complete("demo-two", 1500, "Planlama")
        self.refresh()
        self.status.setText("Örnek görünüm · Gerçek görev ve oturum verisi içermez.")

    def smoke(self):
        before = self.tasks.count()
        self.task_input.setText("Test görevi")
        self.add_task()
        assert self.tasks.count() == before + 1
        self.tasks.item(0).setCheckState(Qt.CheckState.Checked)
        assert any(t["done"] for t in self.store.tasks())
        self.start_pause()
        assert self.countdown.running
        self.start_pause()
        assert not self.countdown.running
        self.reset()
        return ["persistent tasks", "completion checkbox", "timer start/pause/reset"]


if __name__ == "__main__":
    sys.exit(run(Window, "Mola"))
