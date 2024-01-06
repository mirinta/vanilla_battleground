import os
import json

import psutil
from PyQt5.QtCore import (QThread, pyqtSignal, QEvent, Qt)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QHBoxLayout,
    QVBoxLayout,
    QAction,
    QPushButton,
    QListWidget,
    QAbstractItemView,
    QTextEdit,
    QSystemTrayIcon,
    QMenu, QFileDialog)

from core.Worker import Worker


class MainWindow(QMainWindow):
    stop_signal = pyqtSignal()

    def __init__(self, parent=None):
        super(MainWindow, self).__init__(parent)
        self.worker = None
        self.thread = None

        icon = QIcon(
            os.path.join(
                os.path.dirname(__file__),
                "../resource/icon.png"))
        self.setWindowIcon(icon)
        self.setWindowTitle("Vanilla WoW Key Presser")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowStaysOnTopHint)
        self.setWindowFlags(self.windowFlags() &
                            ~Qt.WindowMaximizeButtonHint)
        self.setFixedSize(450, 600)
        self.setCentralWidget(QWidget(self))
        main_layout = QVBoxLayout()
        self.centralWidget().setLayout(main_layout)

        self.pid_list = QListWidget(self)
        self.pid_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.pid_list.currentRowChanged.connect(self.on_pid_changed)
        pid_layout = QVBoxLayout()
        pid_layout.addWidget(QLabel("PID(s) of Running WowClassic.exe"))
        pid_layout.addWidget(self.pid_list)
        main_layout.addLayout(pid_layout)

        self.config_path = QLabel(self)
        self.config_path.setStyleSheet(
            "border-bottom-width: 1px; border-bottom-style: solid; border-radius: 0px;")
        self.select_config = QPushButton("...", self)
        self.select_config.setMaximumWidth(40)
        self.select_config.clicked.connect(self.on_select_config_clicked)
        config_layout = QHBoxLayout()
        config_layout.addWidget(self.config_path)
        config_layout.addWidget(self.select_config)
        main_layout.addWidget(QLabel("Configuration:", self))
        main_layout.addLayout(config_layout)

        self.refresh_button = QPushButton("Refresh", self)
        self.refresh_button.clicked.connect(self.on_refresh_clicked)
        self.stop_button = QPushButton("Stop", self)
        self.stop_button.clicked.connect(self.on_stop_clicked)
        self.start_button = QPushButton("Start", self)
        self.start_button.clicked.connect(self.on_start_clicked)
        button_layout = QHBoxLayout()
        for btn in [self.refresh_button, self.stop_button, self.start_button]:
            btn.setFixedHeight(80)
            button_layout.addWidget(btn)
        main_layout.addLayout(button_layout)
        self.refresh_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.start_button.setEnabled(False)

        self.messages = QTextEdit(self)
        self.messages.setReadOnly(True)
        main_layout.addWidget(QLabel("Program Messages:"))
        main_layout.addWidget(self.messages)

        self.tray_icon = QSystemTrayIcon(icon, self)
        show_action = QAction("Show", self)
        hide_action = QAction("Hide", self)
        exit_action = QAction("Exit", self)
        show_action.triggered.connect(self.showNormal)
        hide_action.triggered.connect(self.hide)
        exit_action.triggered.connect(QApplication.instance().quit)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        tray_menu = QMenu(self)
        for i in [show_action, hide_action, exit_action]:
            tray_menu.addAction(i)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def on_select_config_clicked(self):
        config_dir = os.path.join(os.path.dirname(__file__), "../config")
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Select configuration", config_dir, "JSON file (*.json)", options=options)
        self.config_path.setText(file_name)
        self.start_button.setDisabled(
            self.pid_list.currentRow() < 0 or not file_name)

    def on_refresh_clicked(self):
        self.pid_list.clear()
        self.pid_list.addItems(
            [str(p.pid) for p in psutil.process_iter() if p.name() == "WowClassic.exe"])

    def on_start_clicked(self):
        if not self.pid_list.count() or self.pid_list.currentRow(
        ) < 0 or not self.config_path.text():
            return

        import json
        with open(self.config_path.text(), 'r') as f:
            config = json.load(f)

        self.thread = QThread()
        self.worker = Worker()
        self.stop_signal.connect(self.worker.stop)

        self.worker.key_sequence = config['key_sequence']
        self.worker.sleep_times = config['sleep_times']
        self.worker.wow_pid = int(self.pid_list.currentItem().text())
        self.worker.moveToThread(self.thread)
        self.worker.report_msg.connect(self.messages.append)
        self.worker.work_finished.connect(self.thread.quit)
        self.worker.work_finished.connect(self.worker.deleteLater)

        self.thread.started.connect(self.update_button_status)
        self.thread.started.connect(self.worker.start)
        self.thread.finished.connect(self.worker.stop)
        self.thread.finished.connect(self.update_button_status)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_stop_clicked(self):
        self.stop_signal.emit()

    def on_pid_changed(self, index):
        no_selection = index < 0 or self.pid_list.count() == 0
        self.start_button.setDisabled(
            no_selection or not self.config_path.text())

    def update_button_status(self):
        self.refresh_button.setEnabled(self.thread.isFinished())
        self.stop_button.setDisabled(self.thread.isFinished())
        self.start_button.setEnabled(self.thread.isFinished())
        self.pid_list.setEnabled(self.thread.isFinished())
        self.select_config.setEnabled(self.thread.isFinished())

    def on_tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            if self.isHidden():
                self.showNormal()
            else:
                self.hide()

    def changeEvent(self, event):
        if event.type() == QEvent.WindowStateChange:
            if self.windowState() & Qt.WindowMinimized:
                self.hide()
        super(MainWindow, self).changeEvent(event)

    def closeEvent(self, event):
        self.stop_signal.emit()
        super(MainWindow, self).closeEvent(event)
