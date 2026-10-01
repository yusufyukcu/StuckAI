from __future__ import annotations

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QFontDatabase


class MaintenanceDialog(QDialog):
    def __init__(self, parent=None, message: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("Maintenance In Progress")
        self.setModal(True)
        self.setFixedSize(560, 280)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(16)

        # Load fonts (best-effort)
        try:
            QFontDatabase.addApplicationFont("fonts/Poppins-SemiBold.ttf")
            QFontDatabase.addApplicationFont("fonts/Poppins-Medium.ttf")
            QFontDatabase.addApplicationFont("fonts/Poppins-Regular.ttf")
            QFontDatabase.addApplicationFont("fonts/Inter_24pt-Regular.ttf")
        except Exception:
            pass

        title = QLabel("We are performing an important update")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        try:
            title.setFont(QFont("Poppins", 18, QFont.Weight.DemiBold))
        except Exception:
            pass
        title.setStyleSheet("color:#0F172A;")

        subtitle = QLabel(message or "Please try again later.\nFor details, contact support@stuckai.net")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setWordWrap(True)
        try:
            subtitle.setFont(QFont("Inter", 12, QFont.Weight.Medium))
        except Exception:
            pass
        subtitle.setStyleSheet("color:#475569;")

        button_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        ok_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        try:
            ok_btn.setFont(QFont("Inter", 11, QFont.Weight.Medium))
        except Exception:
            pass
        ok_btn.setStyleSheet(
            "QPushButton{background:#3B82F6;color:white;border:none;border-radius:12px;padding:10px 18px;}"
            "QPushButton:hover{background:#2563EB;}"
        )
        ok_btn.clicked.connect(self.accept)
        button_row.addStretch()
        button_row.addWidget(ok_btn)

        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addStretch()
        layout.addLayout(button_row)
        self.setStyleSheet("QDialog{background:#FFFFFF;border-radius:12px;}")


