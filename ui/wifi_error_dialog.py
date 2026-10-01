import os
import sys
import subprocess
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QWidget, QFrame
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap, QFont
from logic.windows_subprocess import popen_hidden

class WifiErrorDialog(QDialog):
    """Dialog to show WiFi connection error"""
    
    # Signal to notify parent that Supabase service should be reinitialized
    service_ready = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_style()
        
    def setup_ui(self):
        """Setup the dialog UI"""
        self.setWindowTitle("No Internet Connection")
        self.setFixedSize(400, 500)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowCloseButtonHint)
        
        # Main layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Image container
        image_container = QWidget()
        image_container.setFixedSize(200, 200)
        image_container.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(0, 0, 0, 0)
        
        # WiFi error image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setFixedSize(180, 180)
        
        # Load wifi_error.png
        image_path = os.path.abspath("ui/assets/wifi_error.png")
        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    180, 180, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled_pixmap)
            else:
                self.image_label.setText("📶")
                self.image_label.setStyleSheet("font-size: 80px; color: #EF4444;")
        else:
            # Fallback if image not found
            self.image_label.setText("📶")
            self.image_label.setStyleSheet("font-size: 80px; color: #EF4444;")
        
        image_layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(image_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Title
        title_label = QLabel("No Internet Connection")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1F2937; margin-bottom: 10px;")
        layout.addWidget(title_label)
        
        # Message
        message_label = QLabel(
            "Please check your internet connection and try again."
        )
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setWordWrap(True)
        message_label.setFont(QFont("Arial", 12))
        message_label.setStyleSheet("color: #6B7280; line-height: 1.5;")
        layout.addWidget(message_label)
        
        # Spacer
        layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        
        # Retry button
        retry_btn = QPushButton("Retry")
        retry_btn.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        retry_btn.setFixedSize(120, 45)
        retry_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #2563EB;
            }
            QPushButton:pressed {
                background: #1D4ED8;
            }
        """)
        retry_btn.clicked.connect(self.on_retry)
        button_layout.addWidget(retry_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        cancel_btn.setFixedSize(120, 45)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #6B7280;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #4B5563;
            }
            QPushButton:pressed {
                background: #374151;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Auto-retry timer (disabled)
        # self.retry_timer = QTimer()
        # self.retry_timer.timeout.connect(self.on_retry)
        
    def setup_style(self):
        """Setup dialog styling"""
        self.setStyleSheet("""
            QDialog {
                background: white;
                border-radius: 12px;
            }
        """)
        
    def on_retry(self):
        """Handle retry button click"""
        from logic.network_utils import check_wifi_connection
        
        if check_wifi_connection():
            # WiFi is connected, restart the application
            print("🔧 WiFi connected - restarting application")
            
            # Restart the application
            import sys
            import os
            import subprocess
            
            # Get the current script path
            current_script = sys.argv[0]
            
            # Close current application
            self.accept()
            
            # Restart the application
            try:
                popen_hidden([sys.executable, current_script])
                sys.exit(0)
            except Exception as e:
                print(f"Error restarting application: {e}")
                sys.exit(1)
        else:
            # WiFi still not connected, do nothing (silent)
            pass
    
    def start_auto_retry(self, interval_ms=5000):
        """Start automatic retry every 5 seconds (disabled)"""
        # Auto-retry disabled
        pass
    
    def stop_auto_retry(self):
        """Stop automatic retry (disabled)"""
        # Auto-retry disabled
        pass 