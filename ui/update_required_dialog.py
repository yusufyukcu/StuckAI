import os
import webbrowser
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon


class UpdateRequiredDialog(QDialog):
    """Modern dialog shown when an update is required before continuing."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Update Required")
        self.setModal(True)
        self.setFixedSize(460, 260)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
            | Qt.WindowType.WindowCloseButtonHint
        )

        # Optional icon if available
        try:
            icon_path = os.path.join(os.path.dirname(__file__), "assets", "logo.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        title = QLabel("A new update is available")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            """
            QLabel {
                font-size: 20px;
                font-weight: 700;
                color: #111827;
            }
            """
        )

        subtitle = QLabel(
            "Please download the latest version to continue using Stuck AI.\n"
            "This update is required to maintain access to our AI services."
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: #4B5563;
            }
            """
        )

        button_row = QHBoxLayout()
        button_row.setSpacing(12)

        download_btn = QPushButton("Open Download Page")
        download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        download_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #2563EB; }
            QPushButton:pressed { background-color: #1D4ED8; }
            """
        )
        download_btn.clicked.connect(self._open_download_page)

        exit_btn = QPushButton("Exit")
        exit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        exit_btn.setStyleSheet(
            """
            QPushButton {
                background: white;
                color: #111827;
                border: 1px solid #E5E7EB;
                border-radius: 10px;
                padding: 10px 16px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover { background: #F9FAFB; }
            QPushButton:pressed { background: #F3F4F6; }
            """
        )
        exit_btn.clicked.connect(self.reject)

        button_row.addStretch()
        button_row.addWidget(exit_btn)
        button_row.addWidget(download_btn)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
        layout.addLayout(button_row)

        self.setStyleSheet(
            """
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F8FAFC, stop:1 #EEF2F7);
            }
            """
        )

    def _open_download_page(self):
        # If you have a dedicated download URL, replace below
        webbrowser.open("https://dashboard.stuckai.net")
        self.reject()



