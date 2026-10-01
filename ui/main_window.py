import sys
import os
import base64
import threading
import json
import math
import subprocess
import uuid
import hashlib
import webbrowser
import requests
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import threading as _threading

# Data visualization imports
try:
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Matplotlib not available for advanced charts")

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QGridLayout, QTextEdit, QPushButton, QLabel, QTabWidget, 
    QScrollArea, QFrame, QCheckBox, QProgressBar, QMessageBox,
    QFileDialog, QSplitter, QStatusBar, QDialog, QSpacerItem, QSizePolicy,
    QGroupBox, QSpinBox, QComboBox, QLineEdit, QStackedWidget, QGraphicsDropShadowEffect
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QByteArray, QTimer, QRectF, QRect, QMimeData, QPropertyAnimation, QEasingCurve, QEvent, QPoint
from PyQt6.QtGui import QFont, QPixmap, QIcon, QPalette, QColor, QPainter, QPen, QBrush, QLinearGradient, QRadialGradient, QDragEnterEvent, QDragMoveEvent, QDropEvent, QMovie, QImage

# Font loading functionality - temporarily disabled
loaded_custom_fonts = []  # Empty list for now
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply

# Try to import multimedia modules for video playback
try:
    from PyQt6.QtMultimedia import QMediaPlayer
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    MULTIMEDIA_AVAILABLE = True
except ImportError:
    MULTIMEDIA_AVAILABLE = False
    print("PyQt6 Multimedia module not available for video playback")

try:
    from PyQt6.QtSvg import QSvgRenderer
    SVG_AVAILABLE = True
except ImportError:
    SVG_AVAILABLE = False
    print("SVG support not available")

# Local imports
from logic.scene_analysis import process_text
from logic.smart_scene_analysis import process_text_smart, smart_media_cache, get_scenes_to_analyze_in_background
from logic.utils import get_asset_path, read_input_file, write_json_output, get_default_download_path
from logic.stock_api_service import stock_service
from logic.supabase_auth import SupabaseAuthService
from logic.cost_tracking_service import CostTrackingService
from logic.scene_cost_tracking_service import SceneCostTrackingService
from logic.leonardo_ai_service import LeonardoAIService
from logic.windows_subprocess import run_hidden
from ui.smart_analysis_thread import SmartAnalysisThread, BackgroundSceneAnalysisThread, SmartLazyLoadingThread
from ui.highlightable_text_widget import HighlightableTextWidget
from ui.download_thread import DownloadThread

@dataclass
class User:
    """User data class"""
    id: str
    username: str
    email: str
    created_at: str
    last_login: str
    is_active: bool = True

class UserManager:
    """User management system"""
    def __init__(self):
        self.current_user: Optional[User] = None
        self.users_file = "data/users.json"
        self.users: List[User] = []
        self.load_users()
    
    def load_users(self):
        """Load users from file"""
        try:
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.users = []
                    for user_data in data.get('users', []):
                        user = User(
                            id=user_data['id'],
                            username=user_data['username'],
                            email=user_data['email'],
                            created_at=user_data['created_at'],
                            last_login=user_data.get('last_login', ''),
                            is_active=user_data.get('is_active', True)
                        )
                        self.users.append(user)
        except Exception as e:
            print(f"Error loading users: {e}")
            self.users = []
    
    def save_users(self):
        """Save users to file"""
        try:
            os.makedirs(os.path.dirname(self.users_file), exist_ok=True)
            data = {
                'users': []
            }
            for user in self.users:
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'created_at': user.created_at,
                    'last_login': user.last_login,
                    'is_active': user.is_active
                }
                data['users'].append(user_data)
            
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def hash_password(self, password: str) -> str:
        """Hash password using SHA-256"""
        return hashlib.sha256(password.encode()).hexdigest()
    
    def create_user(self, username: str, email: str, password: str) -> bool:
        """Create new user"""
        # Check if username or email already exists
        for user in self.users:
            if user.username == username or user.email == email:
                return False
        
        # Create new user
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_user = User(
            id=str(uuid.uuid4()),
            username=username,
            email=email,
            created_at=current_time,
            last_login=current_time
        )
        
        self.users.append(new_user)
        self.save_users()
        return True
    
    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user (for now, accept any user)"""
        # For demo purposes, accept any username/password combination
        # In real implementation, you would check against hashed passwords
        for user in self.users:
            if user.username == username:
                user.last_login = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                self.save_users()
                return user
        
        # If user doesn't exist, create a demo user
        if self.create_user(username, username + "@demo.com", password):
            return self.authenticate_user(username, password)
        
        return None
    
    def logout(self):
        """Logout current user"""
        self.current_user = None

class LoginDialog(QDialog):
    """User login dialog"""
    login_successful = pyqtSignal(User)
    
    def __init__(self, parent=None, user_manager=None):
        super().__init__(parent)
        self.user_manager = user_manager
        self.setWindowTitle("User Login")
        self.setFixedSize(400, 300)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
        self.center_dialog()
    
    def center_dialog(self):
        """Center the dialog on the parent window"""
        if self.parent():
            parent_rect = self.parent().geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            self.move(x, y)
    
    def setup_ui(self):
        """Setup the dialog UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Main container
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 20px;
                border: 2px solid #D1D5DB;
                box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(40, 32, 40, 32)
        container_layout.setSpacing(24)
        container.setLayout(container_layout)
        
        # Header
        header_label = QLabel("👤 User Login")
        header_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        header_label.setStyleSheet("color: #1F2937; background: transparent;")
        header_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(header_label)
        
        # Username input
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")
        self.username_input.setFont(QFont("Arial", 14))
        self.username_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
            }
        """)
        container_layout.addWidget(self.username_input)
        
        # Password input
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setFont(QFont("Arial", 14))
        self.password_input.setStyleSheet("""
            QLineEdit {
                border: 2px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                background: white;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
            }
        """)
        container_layout.addWidget(self.password_input)
        
        # Demo info
        demo_label = QLabel("💡 Demo: Enter any username and password")
        demo_label.setFont(QFont("Arial", 12))
        demo_label.setStyleSheet("color: #6B7280; background: transparent;")
        demo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        container_layout.addWidget(demo_label)
        
        container_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Login button
        login_btn = QPushButton("Login")
        login_btn.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        login_btn.setFixedSize(120, 40)
        login_btn.setStyleSheet("""
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
        """)
        login_btn.clicked.connect(self.on_login)
        button_layout.addWidget(login_btn)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        cancel_btn.setFixedSize(120, 40)
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
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        container_layout.addLayout(button_layout)
        layout.addWidget(container)
        
        # Connect enter key to login
        self.username_input.returnPressed.connect(self.on_login)
        self.password_input.returnPressed.connect(self.on_login)
    
    def on_login(self):
        """Handle login button click"""
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()
        
        if not username or not password:
            QMessageBox.warning(self, "Login Error", "Please enter both username and password.")
            return
        
        if self.user_manager:
            user = self.user_manager.authenticate_user(username, password)
            if user:
                self.user_manager.current_user = user
                self.login_successful.emit(user)
                self.accept()
            else:
                QMessageBox.warning(self, "Login Error", "Invalid username or password.")
        else:
            QMessageBox.warning(self, "Login Error", "User manager not available.")


# Icon paths (PNG for sidebar, SVG for others)
ICONS = {
    "create": "ui/assets/star.svg",
    "home": "ui/assets/home.png",
    "ai_review": "ui/assets/review.png",
    "downloads": "ui/assets/download.png",
    "history": "ui/assets/history.png",
    "settings": "ui/assets/settings.png",
    "info": "ui/assets/info.png",
    "user": "ui/assets/user.svg"  # Add user icon
}


class DragDropUploadWidget(QWidget):
    """Custom widget with drag & drop functionality and loading animation"""
    file_dropped = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.is_loading = False
        self.animation_angle = 0
        
        # Setup animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        
        # Enable drag and drop
        self.setAcceptDrops(True)
        
        # Setup UI
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the UI elements"""
        # Make the widget responsive instead of fixed-size
        try:
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        except Exception:
            pass
        self.setMinimumSize(320, 320)
        
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(16)
        self.setLayout(layout)
        self._layout = layout
        
        # Upload icon container
        self.upload_icon_container = QWidget()
        self.upload_icon_container.setFixedSize(100, 100)
        layout.addWidget(self.upload_icon_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Title - Use Poppins SemiBold
        self.upload_title = QLabel("DRAG & DROP")
        # Use Poppins SemiBold for title
        try:
            main_window = self.parent()
            while main_window and not isinstance(main_window, MainWindow):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
                self.upload_title.setFont(QFont("Poppins SemiBold", 24, QFont.Weight.Bold))
            elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
                self.upload_title.setFont(QFont("Poppins", 24, QFont.Weight.Bold))
            else:
                self.upload_title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        except:
            self.upload_title.setFont(QFont("Arial", 24, QFont.Weight.Bold))
        self.upload_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_title.setStyleSheet("""
            QLabel {
                color: #374151; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(self.upload_title)
        
        # Subtitle - Use Inter Regular
        self.upload_subtitle = QLabel("Your Video File Here")
        # Use Inter Regular for subtitle
        try:
            main_window = self.parent()
            while main_window and not isinstance(main_window, MainWindow):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
                self.upload_subtitle.setFont(QFont("Inter 24pt", 16))
            else:
                self.upload_subtitle.setFont(QFont("Arial", 16))
        except:
            self.upload_subtitle.setFont(QFont("Arial", 16))
        self.upload_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_subtitle.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent; 
                border: none;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(self.upload_subtitle)
        
        # Description - Use Inter Regular
        self.upload_desc = QLabel("Supports MP4, MOV, AVI, MKV up to 4K")
        # Use Inter Regular for description
        try:
            main_window = self.parent()
            while main_window and not isinstance(main_window, MainWindow):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
                self.upload_desc.setFont(QFont("Inter 24pt", 12))
            else:
                self.upload_desc.setFont(QFont("Arial", 12))
        except:
            self.upload_desc.setFont(QFont("Arial", 12))
        self.upload_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.upload_desc.setStyleSheet("""
            QLabel {
                color: #9CA3AF; 
                background: transparent; 
                border: none;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(self.upload_desc)
        
        # Small spacer to keep button close to description
        layout.addSpacing(8)
        
        # Upload button - Use Poppins Medium
        self.upload_btn = QPushButton("📁 SELECT VIDEO FILE")
        # Use Poppins Medium for button
        try:
            main_window = self.parent()
            while main_window and not isinstance(main_window, MainWindow):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
                self.upload_btn.setFont(QFont("Poppins SemiBold", 14, QFont.Weight.Medium))
            elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
                self.upload_btn.setFont(QFont("Poppins", 14, QFont.Weight.Medium))
            else:
                self.upload_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        except:
            self.upload_btn.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        self.upload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # Fixed size policy to prevent stretching
        try:
            self.upload_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        # Height and width adapt to container; prevents clipping on smaller screens
        self.upload_btn.setMinimumHeight(42)
        self.upload_btn.setMaximumWidth(360)
        self.upload_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 25px;
                font-weight: bold;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                padding-left: 16px; padding-right: 16px;
            }
            QPushButton:hover { background: #2563EB; }
            QPushButton:pressed { background: #1D4ED8; }
        """)
        # Keep the button pill-shaped according to its runtime height
        try:
            self.upload_btn.installEventFilter(self)
        except Exception:
            pass
        layout.addWidget(self.upload_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.update_normal_state()
        # Apply initial responsive tuning
        try:
            self._apply_responsive_styles()
        except Exception:
            pass
        # Ensure initial pill radius is correct after layout
        try:
            QTimer.singleShot(0, self._update_button_radius)
        except Exception:
            pass
    
    def update_normal_state(self):
        """Update widget to normal state"""
        self.is_loading = False
        self.animation_timer.stop()
        
        self.setStyleSheet("""
            DragDropUploadWidget {
                background: #F8FAFC;
                border: none;
                border-radius: 20px;
            }
        """)
        
        # Reset icon container size and style
        self.upload_icon_container.setFixedSize(100, 100)
        self.upload_icon_container.setStyleSheet("""
            QWidget {
                background: #EEF2FF;
                border: none;
                border-radius: 50px;
            }
        """)
        
        # Simple and reliable icon reset
        # Create or recreate the icon directly
        if not hasattr(self, 'video_icon') or not self.video_icon:
            self.video_icon = QLabel("🎬", self.upload_icon_container)
        else:
            # Update existing icon
            self.video_icon.setParent(self.upload_icon_container)
            self.video_icon.setText("🎬")
        
        # Set icon properties
        self.video_icon.setFont(QFont("Arial", 40))
        self.video_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video_icon.setStyleSheet("background: transparent; color: #6B7280;")
        
        # Position icon in center of container
        self.video_icon.setGeometry(0, 0, 100, 100)
        self.video_icon.show()
        
        # No loading icon needed - just clean green circle animation
        
        # Reset text colors and content
        self.upload_title.setText("DRAG & DROP")
        self.upload_title.setStyleSheet("""
            QLabel {
                color: #374151; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        self.upload_subtitle.setText("Your Video File Here")
        self.upload_subtitle.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent; 
                border: none;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        self.upload_desc.show()
        self.upload_btn.show()
    
    def update_loading_state(self):
        """Update widget to loading state with green spinning circle"""
        self.is_loading = True
        
        self.setStyleSheet("""
            DragDropUploadWidget {
                background: #F0FDF4;
                border: 2px solid #10B981;
                border-radius: 20px;
            }
        """)
        
        # Update text
        self.upload_title.setText("ANALYSING")
        self.upload_title.setStyleSheet("color: #10B981; background: transparent;")
        self.upload_subtitle.setText("Processing your video...")
        self.upload_subtitle.setStyleSheet("color: #047857; background: transparent; border: none;")
        
        # Hide description and button
        self.upload_desc.hide()
        self.upload_btn.hide()
        
        # Start ultra smooth animation
        self.animation_timer.start(60)  # 60ms for ultra smooth animation
    
    def update_animation(self):
        """Update the spinning and pulsing animation"""
        if not self.is_loading:
            return
            
        self.animation_angle += 6  # Optimized smooth rotation: 6 degrees each frame
        if self.animation_angle >= 360:
            self.animation_angle = 0
        
        # Calculate ultra smooth continuous pulsing (büyüyüp küçülme)
        import math
        # Use abs(sin) for smooth continuous pulse without sudden jumps
        pulse_wave = abs(math.sin(self.animation_angle * math.pi / 180 * 0.4))  # Always positive wave
        pulse_scale = 0.94 + 0.12 * pulse_wave  # Smooth range: 0.94 to 1.06 scale
        container_size = int(100 * pulse_scale)  # Base size 100px
        
        # Calculate animated corner radius (köşelerin büyüyüp küçülmesi)
        base_radius = 50  # Half of base container size
        corner_radius = int(base_radius * pulse_scale)
        
        # Update icon container with beautiful gradient green circle and animated corners
        self.upload_icon_container.setFixedSize(container_size, container_size)
        self.upload_icon_container.setStyleSheet(f"""
            QWidget {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #10B981,
                    stop:0.3 #059669,
                    stop:0.7 #047857,
                    stop:1 #065F46);
                border: none;
                border-radius: {corner_radius}px;
                /* box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3); */
            }}
        """)
        
        # Hide video icon during loading - just show the beautiful green circle
        if hasattr(self, 'video_icon') and self.video_icon:
            self.video_icon.hide()
    
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event"""
        if event.mimeData().hasUrls():
            # Check if any of the URLs point to video files
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    if any(file_path.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']):
                        event.acceptProposedAction()
                        self.setStyleSheet("""
                            DragDropUploadWidget {
                                background: #EBF8FF;
                                border: 2px solid #3B82F6;
                                border-radius: 20px;
                            }
                        """)
                        return
        event.ignore()
    
    def dragMoveEvent(self, event: QDragMoveEvent):
        """Handle drag move event"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave event"""
        if not self.is_loading:
            self.update_normal_state()
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event"""
        files = [u.toLocalFile() for u in event.mimeData().urls()]
        
        for file_path in files:
            if any(file_path.lower().endswith(ext) for ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']):
                self.update_loading_state()
                self.file_dropped.emit(file_path)
                event.acceptProposedAction()
                return
        
        event.ignore()
        self.update_normal_state()


    def resizeEvent(self, event):
        """Keep layout and control sizes responsive on resize"""
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        try:
            self._apply_responsive_styles()
        except Exception:
            pass

    def _apply_responsive_styles(self):
        """Adjust paddings, icon and button sizes for small screens"""
        try:
            # Get the main window width and check if it's a laptop screen
            main_window = self.parent()
            while main_window and not isinstance(main_window, MainWindow):
                main_window = main_window.parent()
            
            if main_window and hasattr(main_window, 'width'):
                w = int(main_window.width())
                # Also check if this is a laptop by looking at height
                h = int(main_window.height())
                # Laptop screens typically have height < 1000px
                is_laptop = h < 1000
                print(f"🔍 Main window: {w}x{h}px, Laptop detected: {is_laptop}")
            else:
                w = int(self.width())
                is_laptop = False
        except Exception:
            w = 1200  # Default to large screen size
            is_laptop = False

        # Defaults
        margins = 40
        icon = 100
        # Button max width scales with container but stays reasonable
        btn_max = min(360, max(240, int(w * 0.8)))
        title_size = 24
        subtitle_size = 16
        desc_size = 12
        btn_height = 46
        btn_font_size = 14
        btn_padding = 16

        if w < 360:
            margins = 14
            icon = 72
            btn_max = min(btn_max, 220)
            title_size = 16
            subtitle_size = 11
            desc_size = 9
            btn_height = 36
            btn_font_size = 11
            btn_padding = 12
        elif w < 420:
            margins = 16
            icon = 80
            btn_max = min(btn_max, 260)
            title_size = 18
            subtitle_size = 12
            desc_size = 10
            btn_height = 38
            btn_font_size = 12
            btn_padding = 14
        elif w < 540:
            margins = 24
            icon = 90
            btn_max = min(btn_max, 300)
            title_size = 20
            subtitle_size = 14
            desc_size = 11
            btn_height = 40
            btn_font_size = 13
            btn_padding = 15
        elif w < 720:
            btn_height = 42
            btn_font_size = 13
            btn_padding = 15
        elif w < 1024:
            btn_height = 44
            btn_font_size = 14
            btn_padding = 16

        # Apply values
        if self.layout():
            self.layout().setContentsMargins(margins, margins, margins, margins)
        try:
            self.upload_icon_container.setFixedSize(icon, icon)
        except Exception:
            pass
        # Keep the icon container blue and perfectly round
        try:
            corner = int(icon / 2)
            self.upload_icon_container.setStyleSheet(f"""
                QWidget {{
                    background: #EEF2FF;
                    border: none;
                    border-radius: {corner}px;
                }}
            """)
        except Exception:
            pass
        try:
            self.upload_btn.setMaximumWidth(btn_max)
            self.upload_btn.setMinimumHeight(btn_height)
        except Exception:
            pass

        # Hide button on laptops and small screens, show only on large desktop screens
        try:
            print(f"🔍 DragDropUploadWidget: Screen width detected: {w}px")
            
            # Hide button if it's a laptop OR if width is small
            if is_laptop or w < 1366:
                print(f"📱 Hiding button - Laptop detected: {is_laptop}, Width: {w}px")
                self.upload_btn.hide()
            else:  # Show button only on large desktop screens
                print(f"🖥️ Showing button - Desktop mode, Width: {w}px")
                self.upload_btn.show()
                btn_font = self.upload_btn.font()
                btn_font.setPointSize(btn_font_size)
                self.upload_btn.setFont(btn_font)
                
                # Update button style with responsive padding
                self.upload_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #3B82F6;
                        color: white;
                        border: none;
                        border-radius: {btn_height//2}px;
                        font-weight: bold;
                        font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                        padding-left: {btn_padding}px; 
                        padding-right: {btn_padding}px;
                        padding-top: 8px;
                        padding-bottom: 8px;
                    }}
                    QPushButton:hover {{ background: #2563EB; }}
                    QPushButton:pressed {{ background: #1D4ED8; }}
                """)
        except Exception as e:
            print(f"❌ Error in button visibility logic: {e}")
            # Fallback: show button by default
            self.upload_btn.show()

        # Update font sizes conservatively
        try:
            f = self.upload_title.font(); f.setPointSize(title_size); self.upload_title.setFont(f)
            f = self.upload_subtitle.font(); f.setPointSize(subtitle_size); self.upload_subtitle.setFont(f)
            f = self.upload_desc.font(); f.setPointSize(desc_size); self.upload_desc.setFont(f)
        except Exception:
            pass

        # Keep the movie-clapper icon centered inside the blue circle
        try:
            if hasattr(self, 'video_icon') and self.video_icon:
                self.video_icon.setGeometry(0, 0, icon, icon)
                icon_font = max(18, int(icon * 0.4))
                ff = self.video_icon.font(); ff.setPointSize(icon_font); self.video_icon.setFont(ff)
        except Exception:
            pass

        # Update pill radius after size adjustments
        try:
            self._update_button_radius()
        except Exception:
            pass

    def _update_button_radius(self):
        """Dynamically set button border-radius to half of its height for true pill."""
        try:
            h = max(1, int(self.upload_btn.height()))
            radius = max(10, h // 2)
            self.upload_btn.setStyleSheet(f"""
                QPushButton {{
                    background: #3B82F6;
                    color: white;
                    border: none;
                    border-radius: {radius}px;
                    font-weight: bold;
                    font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                    padding-left: 16px; padding-right: 16px;
                }}
                QPushButton:hover {{ background: #2563EB; }}
                QPushButton:pressed {{ background: #1D4ED8; }}
            """)
        except Exception:
            pass

    def eventFilter(self, obj, event):
        try:
            if obj is self.upload_btn and event.type() == QEvent.Type.Resize:
                self._update_button_radius()
        except Exception:
            pass
        return super().eventFilter(obj, event)

class AnimatedStatsContainer(QWidget):
    """Premium animated container with smooth fade transition effect"""
    def __init__(self):
        super().__init__()
        self.setFixedSize(260, 110)
        
        # Animation properties
        self.animation_phase = 0.0
        self.fade_intensity = 1.0
        
        # Enable styled background for container
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Setup premium fade animation timer
        self.fade_timer = QTimer()
        self.fade_timer.timeout.connect(self.update_fade_animation)
        self.fade_timer.start(50)  # Smooth 20fps animation
        
        # Initialize style
        self.update_fade_animation()
        
    def update_fade_animation(self):
        """Update smooth premium fade effect"""
        import math
        
        # Increment animation phase for smooth transition
        self.animation_phase += 0.04  # Slightly faster but still premium
        if self.animation_phase >= 6.28:  # 2 * pi for full cycle
            self.animation_phase = 0.0
        
        # Calculate smooth fade intensity with more visible range
        self.fade_intensity = 0.6 + 0.4 * math.sin(self.animation_phase)  # Range: 0.6 to 1.0 (more visible)
        
        # Calculate premium visual values with better contrast
        base_alpha = int(180 + 75 * self.fade_intensity)  # More dramatic fade
        gradient_alpha = int(160 + 95 * self.fade_intensity)  # Better visibility
        border_alpha = int(120 + 135 * self.fade_intensity)  # More border animation
        glow_size = int(20 * self.fade_intensity)
        
        # Soft gradient transition effect matching main background
        self.setStyleSheet(f"""
            AnimatedStatsContainer {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(249, 250, 251, 255),
                    stop:0.1 rgba(248, 250, 252, 245),
                    stop:0.3 rgba(243, 244, 246, {int(235 + 15 * self.fade_intensity)}),
                    stop:0.7 rgba(239, 240, 242, {int(230 + 20 * self.fade_intensity)}),
                    stop:1 rgba(249, 250, 251, 255));
                border: 2px solid rgba(229, 231, 235, {int(180 + 50 * self.fade_intensity)});
                border-radius: 12px;
            }}
        """)


class AnimatedStatsLabel(QLabel):
    """Simple label for stats without individual animation"""
    def __init__(self, text: str, color: str = "#3B82F6"):
        super().__init__(text)
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background: transparent;
                font-weight: bold;
            }}
        """)
class AnimatedLoadingBall(QWidget):
    """Animated green gradient ball with pulsing and rotation effects"""
    
    def __init__(self):
        super().__init__()
        self.animation_angle = 0.0
        self.pulse_scale = 1.0
        self.is_animating = False
        
        # Setup animation timer
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        
        # Set widget style
        self.setStyleSheet("""
            AnimatedLoadingBall {
                background: transparent;
                border: none;
            }
        """)
    
    def start_animation(self):
        """Start the animation"""
        self.is_animating = True
        self.animation_timer.start(60)  # 60ms for smooth animation
    
    def stop_animation(self):
        """Stop the animation"""
        self.is_animating = False
        self.animation_timer.stop()
    
    def update_animation(self):
        """Update the spinning and pulsing animation"""
        if not self.is_animating:
            return
            
        self.animation_angle += 6  # Smooth rotation: 6 degrees each frame
        if self.animation_angle >= 360:
            self.animation_angle = 0
        
        # Calculate smooth continuous pulsing (büyüyüp küçülme)
        import math
        # Use abs(sin) for smooth continuous pulse without sudden jumps
        pulse_wave = abs(math.sin(self.animation_angle * math.pi / 180 * 0.4))  # Always positive wave
        self.pulse_scale = 0.94 + 0.12 * pulse_wave  # Smooth range: 0.94 to 1.06 scale
        
        # Trigger repaint
        self.update()
    
    def paintEvent(self, event):
        """Custom paint event to draw animated green gradient ball"""
        import math
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get widget dimensions
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # Calculate ball size with pulsing effect
        base_size = min(width, height) * 0.8
        ball_size = int(base_size * self.pulse_scale)
        
        # Calculate center position
        center_x = width // 2
        center_y = height // 2
        
        # Calculate ball rectangle
        ball_rect = QRectF(
            center_x - ball_size // 2,
            center_y - ball_size // 2,
            ball_size,
            ball_size
        )
        
        # Create radial gradient for the ball
        gradient = QRadialGradient(center_x, center_y, ball_size // 2)
        
        # Beautiful green gradient colors
        gradient.setColorAt(0.0, QColor(16, 185, 129))      # #10B981 - Bright green
        gradient.setColorAt(0.3, QColor(5, 150, 105))       # #059669 - Medium green
        gradient.setColorAt(0.7, QColor(4, 120, 87))        # #047857 - Dark green
        gradient.setColorAt(1.0, QColor(6, 95, 70))         # #065F46 - Deep green
        
        # Create brush with gradient
        brush = QBrush(gradient)
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)  # No border
        
        # Draw the ball
        painter.drawEllipse(ball_rect)
        
        # Add subtle glow effect
        glow_gradient = QRadialGradient(center_x, center_y, ball_size // 1.5)
        glow_gradient.setColorAt(0.0, QColor(16, 185, 129, 0))
        glow_gradient.setColorAt(0.7, QColor(16, 185, 129, 0))
        glow_gradient.setColorAt(1.0, QColor(16, 185, 129, 30))
        
        glow_brush = QBrush(glow_gradient)
        painter.setBrush(glow_brush)
        painter.drawEllipse(ball_rect)

class AnimatedGradientWidget(QWidget):
    """Widget with animated flowing gradient effect using custom painting"""
    
    def __init__(self):
        super().__init__()
        self.animation_phase = 0.0
        
        # Setup timer for gradient animation
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_timer.start(60)  # Update every 60ms for premium smooth animation
        
        # Remove conflicting CSS styling - let custom painting handle everything
        self.setStyleSheet("""
            AnimatedGradientWidget {
                background: transparent;
                border: none;
            }
        """)
        
    def update_animation(self):
        """Update animation phase and trigger repaint"""
        self.animation_phase += 0.04  # Premium slow animation speed
        if self.animation_phase >= 6.28:  # 2 * pi for full circle
            self.animation_phase = 0.0

        # Trigger repaint to update the gradient
        self.update()
        
    def paintEvent(self, event):
        """Custom paint event to draw animated gradient that perfectly fills the content area"""
        import math
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Get widget dimensions
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # Create vertical flowing wave effect - premium slow motion
        wave_offset = math.sin(self.animation_phase) * 0.4
        
        # Start from top, flow downward with wave motion
        x1 = int(width * (0.5 + wave_offset))
        y1 = 0  # Top of widget
        x2 = int(width * (0.5 - wave_offset))
        y2 = height  # Bottom of widget
        
        # Create animated gradient
        gradient = QLinearGradient(x1, y1, x2, y2)
        
        # Premium blue gradient colors
        gradient.setColorAt(0.0, QColor(255, 255, 255, 255))    # White
        gradient.setColorAt(0.2, QColor(240, 249, 255, 255))    # Very light blue
        gradient.setColorAt(0.4, QColor(224, 242, 254, 255))    # Light blue
        gradient.setColorAt(0.6, QColor(186, 230, 253, 255))    # Medium blue
        gradient.setColorAt(0.8, QColor(125, 211, 252, 255))    # Bright blue
        gradient.setColorAt(1.0, QColor(56, 189, 248, 255))     # Deep blue
        
        # Create brush with gradient
        brush = QBrush(gradient)
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)  # No border
        
        # Fill entire widget area - no rounded corners (let content widget handle the rounding)
        painter.fillRect(rect, brush)


class Sidebar(QWidget):
    """Modern sidebar widget"""
    navigation_clicked = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.current_page = "home"
        self._icon_cache = {}  # Cache for SVG icons
        self.setup_ui()
    
    def create_icon(self, icon_path: str, size: QSize = QSize(24, 24), color: str = "white") -> QIcon:
        """Create QIcon from SVG or PNG file"""
        # Check cache first
        cache_key = f"{icon_path}_{size.width()}_{size.height()}_{color}"
        if cache_key in self._icon_cache:
            return self._icon_cache[cache_key]
        
        try:
            # Convert to absolute path
            abs_path = os.path.abspath(icon_path)
            
            if not os.path.exists(abs_path):
                return QIcon()
            
            # Handle PNG files
            if icon_path.lower().endswith('.png'):
                pixmap = QPixmap(abs_path)
                if not pixmap.isNull():
                    # Determine device pixel ratio (DPR) for crisp rendering on HiDPI screens
                    try:
                        screen = self.window().windowHandle().screen() if self.window() and self.window().windowHandle() else None
                        dpr = float(screen.devicePixelRatio()) if screen else 1.0
                        if dpr <= 0:
                            dpr = 1.0
                    except Exception:
                        dpr = 1.0
                    # Scale to physical pixels then set DPR so logical size remains 'size'
                    target_w = max(1, int(size.width() * dpr))
                    target_h = max(1, int(size.height() * dpr))
                    scaled_pixmap = pixmap.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    try:
                        scaled_pixmap.setDevicePixelRatio(dpr)
                    except Exception:
                        pass
                    icon = QIcon(scaled_pixmap)
                    
                    # Cache the result
                    self._icon_cache[cache_key] = icon
                    return icon
                else:
                    return QIcon()
            
            # Handle SVG files
            elif icon_path.lower().endswith('.svg'):
                # Read SVG content with multiple encoding attempts
                try:
                    # Try different encodings
                    encodings = ['utf-8', 'utf-16', 'utf-16-le', 'utf-16-be', 'latin-1']
                    svg_content = None
                    
                    for encoding in encodings:
                        try:
                            with open(abs_path, 'r', encoding=encoding) as f:
                                svg_content = f.read().strip()
                            break
                        except UnicodeDecodeError:
                            continue
                    
                    if svg_content is None:
                        return QIcon()
                    
                except Exception as e:
                    return QIcon()
                
                # Replace currentColor with desired color
                svg_content = svg_content.replace('currentColor', color)
                svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
                
                # If SVG support is available, use it
                if SVG_AVAILABLE:
                    renderer = QSvgRenderer()
                    svg_bytes = QByteArray()
                    svg_bytes.append(svg_content.encode('utf-8'))
                    
                    if renderer.load(svg_bytes):
                        # Create pixmap
                        pixmap = QPixmap(size)
                        pixmap.fill(Qt.GlobalColor.transparent)
                        
                        painter = QPainter(pixmap)
                        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                        renderer.render(painter)
                        painter.end()
                        
                        icon = QIcon(pixmap)
                        # Cache the icon
                        self._icon_cache[cache_key] = icon
                        return icon
                    else:
                        return QIcon()
                
                return QIcon()
            else:
                return QIcon()
                
        except Exception as e:
            return QIcon()
        
    def setup_ui(self):
        """Setup sidebar UI"""
        # Fixed sidebar dimensions
        self.setFixedWidth(250)  # Fixed width for consistent layout
        self.setMinimumHeight(600)  # Minimum height, will expand with window
        
        # Enable styled background
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        
        # Set CSS for left rounded corners with gradient
        self.setStyleSheet("""
            Sidebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #1E293B, stop:1 #0F172A);
                border-top-left-radius: 20px;
                border-bottom-left-radius: 20px;
                border-top-right-radius: 0px;
                border-bottom-right-radius: 0px;
            }
        """)
        
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # Logo container section
        logo_container = QFrame()
        logo_container.setFixedHeight(64)  # Only fix height, let width be flexible
        logo_container.setStyleSheet("""
            QFrame {
                background-color: transparent;  /* No background */
                border: none;  /* No border */
                padding: 0px;
                margin: 0px 0px 25px 0px;
            }
        """)
        
        # Logo container layout
        logo_layout = QHBoxLayout(logo_container)
        logo_layout.setContentsMargins(0, 0, 0, 0)  # Zero margins
        logo_layout.setSpacing(8)  # Small spacing between logo and text
        logo_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        # Logo image
        logo_label = QLabel()
        from logic.utils import get_project_root
        logo_path = os.path.join(get_project_root(), "ui", "assets", "logo.png")
        
        logo_pixmap = QPixmap(logo_path)
        
        if not logo_pixmap.isNull():
            # HiDPI-aware scaling for crisp logo
            try:
                screen = self.window().windowHandle().screen() if self.window() and self.window().windowHandle() else None
                if screen is None:
                    from PyQt6.QtGui import QGuiApplication
                    screen = QGuiApplication.primaryScreen()
                dpr = float(screen.devicePixelRatio()) if screen else 1.0
                if dpr <= 0:
                    dpr = 1.0
            except Exception:
                dpr = 1.0
            target_w, target_h = int(32 * dpr), int(32 * dpr)
            scaled_pixmap = logo_pixmap.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            try:
                scaled_pixmap.setDevicePixelRatio(dpr)
            except Exception:
                pass
            logo_label.setPixmap(scaled_pixmap)
            logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logo_label.setStyleSheet("""
                QLabel {
                    padding: 0px;
                    margin: 0px;
                }
            """)
        else:
            # Fallback to text if image loading fails
            logo_label.setText("✨STUCK AI")
            try:
                main_window = self.parent()
                while main_window and not isinstance(main_window, MainWindow):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
                    logo_label.setFont(QFont("Inter 24pt", 18, QFont.Weight.Bold))
                else:
                    logo_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
            except:
                logo_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
            logo_label.setStyleSheet("""
                QLabel {
                    color: white;
                    padding: 0px;
                    margin: 0px;
                }
            """)
        
        # STUCK AI text
        text_label = QLabel("STUCK AI")
        try:
            main_window = self.parent()
            while main_window and not isinstance(main_window, MainWindow):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
                text_label.setFont(QFont("Inter 24pt", 16, QFont.Weight.Bold))
            else:
                text_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        except:
            text_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        text_label.setStyleSheet("""
            QLabel {
                color: white;
                padding: 0px;
                margin: 0px;
            }
        """)
        
        logo_layout.addWidget(logo_label)
        logo_layout.addWidget(text_label)
        layout.addWidget(logo_container)
        
        # Create button
        create_btn = QPushButton("  Create")
        # Use Poppins SemiBold for create button
        try:
            main_window = self.parent()
            while main_window and not isinstance(main_window, MainWindow):
                main_window = main_window.parent()
            if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
                create_btn.setFont(QFont("Poppins SemiBold", 14, QFont.Weight.Medium))
            elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
                create_btn.setFont(QFont("Poppins", 14, QFont.Weight.Medium))
            else:
                create_btn.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        except:
            create_btn.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        create_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        create_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        
        # Set icon for Create button
        create_icon = self.create_icon(ICONS["create"], QSize(24, 24), "white")
        create_btn.setIcon(create_icon)
        create_btn.setIconSize(QSize(24, 24))
        create_btn.setText("Create")
        
        create_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #60A5FA, stop:1 #3B82F6);
                color: white;
                border: none;
                border-radius: 25px;
                padding: 12px 0px;
                margin-bottom: 20px;
                font-weight: 600;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                text-align: center;
                min-height: 44px;
                outline: none;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3B82F6, stop:1 #2563EB);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #2563EB, stop:1 #1D4ED8);
            }
            QPushButton:focus {
                outline: none;
                border: none;
            }
        """)
        create_btn.clicked.connect(lambda: self.navigation_clicked.emit("create"))
        layout.addWidget(create_btn)
        
        # Navigation items
        nav_items = [
            ("home", "Home", True),
            ("ai_review", "AI Review", False),
            ("downloads", "Downloads", False),
            ("history", "History", False),
        ]
        
        self.nav_buttons = {}
        for item_id, text, is_selected in nav_items:
            # Create button with icon
            nav_btn = QPushButton(f" {text}")
            if item_id in ICONS:
                nav_icon = self.create_icon(ICONS[item_id], QSize(48, 48), "#8B91B5" if not is_selected else "white")
                nav_btn.setIcon(nav_icon)
                nav_btn.setIconSize(QSize(48, 48))
                nav_btn.setText(f"{text}")
            # Use Poppins SemiBold for navigation buttons
            try:
                main_window = self.parent()
                while main_window and not isinstance(main_window, MainWindow):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
                    nav_btn.setFont(QFont("Poppins SemiBold", 14, QFont.Weight.DemiBold))
                elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
                    nav_btn.setFont(QFont("Poppins", 14, QFont.Weight.DemiBold))
                else:
                    nav_btn.setFont(QFont("Arial", 14))
            except:
                nav_btn.setFont(QFont("Arial", 14))
            nav_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            nav_btn.setCheckable(True)
            nav_btn.setChecked(is_selected)
            
            if is_selected:
                self.current_page = item_id
                nav_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3A3F5C;
                        color: white;
                        border: none;
                        padding: 12px 8px;
                        text-align: left;
                        border-radius: 10px;
                        margin-bottom: 3px;
                        font-weight: 600;
                        font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                    }
                """)
            else:
                nav_btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #8B91B5;
                        border: none;
                        padding: 12px 8px;
                        text-align: left;
                        border-radius: 10px;
                        margin-bottom: 3px;
                        font-weight: 600;
                        font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                    }
                    QPushButton:hover {
                        background-color: rgba(58, 63, 92, 0.5);
                        color: white;
                    }
                """)
            
            nav_btn.clicked.connect(lambda checked, btn_id=item_id: self.on_nav_clicked(btn_id))
            self.nav_buttons[item_id] = nav_btn
            layout.addWidget(nav_btn)
        
        layout.addStretch()
        
        # Remove user info and logout UI from sidebar per request
        
        # Plan display section
        self.plan_section = QWidget()
        self.plan_section.setVisible(True)  # Always visible
        plan_layout = QVBoxLayout()
        plan_layout.setContentsMargins(0, 10, 0, 10)
        plan_layout.setSpacing(8)
        self.plan_section.setLayout(plan_layout)
        
        # Plan info label
        self.plan_info_label = QLabel("Your Plan: Free")
        self.plan_info_label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        self.plan_info_label.setStyleSheet("""
            QLabel {
                color: #8B91B5;
                background: rgba(58, 63, 92, 0.3);
                padding: 12px 20px;
                border-radius: 10px;
                border: 1px solid #3A3F5C;
                margin: 5px 0px;
            }
        """)
        self.plan_info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        plan_layout.addWidget(self.plan_info_label)
        
        layout.addWidget(self.plan_section)
        
        # Add some spacing before bottom section
        self.plan_spacer = QWidget()
        self.plan_spacer.setFixedHeight(10)
        self.plan_spacer.setVisible(True)
        layout.addWidget(self.plan_spacer)
        
        # Bottom section
        bottom_items = [
            ("settings", "Settings"),
            ("info", "Info"),
        ]
        
        for item_id, text in bottom_items:
            # Create button with icon
            bottom_btn = QPushButton(f" {text}")
            if item_id in ICONS:
                bottom_icon = self.create_icon(ICONS[item_id], QSize(48, 48), "#8B91B5")
                bottom_btn.setIcon(bottom_icon)
                bottom_btn.setIconSize(QSize(48, 48))
                bottom_btn.setText(f"{text}")
            # Use Poppins SemiBold for bottom buttons
            try:
                main_window = self.parent()
                while main_window and not isinstance(main_window, MainWindow):
                    main_window = main_window.parent()
                if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
                    bottom_btn.setFont(QFont("Poppins SemiBold", 14, QFont.Weight.DemiBold))
                elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
                    bottom_btn.setFont(QFont("Poppins", 14, QFont.Weight.DemiBold))
                else:
                    bottom_btn.setFont(QFont("Arial", 14))
            except:
                bottom_btn.setFont(QFont("Arial", 14))
            bottom_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            bottom_btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #8B91B5;
                    border: none;
                    padding: 12px 8px;
                    text-align: left;
                    border-radius: 10px;
                    margin-bottom: 3px;
                    font-weight: 600;
                    font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                }
                QPushButton:hover {
                    background-color: rgba(58, 63, 92, 0.5);
                    color: white;
                }
            """)
            bottom_btn.clicked.connect(lambda checked, btn_id=item_id: self.navigation_clicked.emit(btn_id))
            layout.addWidget(bottom_btn)
        
    def on_nav_clicked(self, item_id: str):
        """Handle navigation item click"""
        # Update button styles and text
        nav_items = [
            ("home", "Home"),
            ("ai_review", "AI Review"),
            ("downloads", "Downloads"),
            ("history", "History"),
        ]
        
        for btn_id, btn in self.nav_buttons.items():
            # Find the text for this button
            text = next((text for nav_id, text in nav_items if nav_id == btn_id), btn_id.title())
            
            if btn_id == item_id:
                btn.setChecked(True)
                
                # Set only the text, SVG icon is already set with setIcon()
                btn.setText(f"{text}")
                
                # Update icon color for selected state
                if btn_id in ICONS:
                    selected_icon = self.create_icon(ICONS[btn_id], QSize(48, 48), "white")
                    btn.setIcon(selected_icon)
                
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #3A3F5C;
                        color: white;
                        border: none;
                        padding: 12px 8px;
                        text-align: left;
                        border-radius: 10px;
                        margin-bottom: 3px;
                        font-weight: 600;
                        font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                    }
                """)
            else:
                btn.setChecked(False)
                
                # Set only the text, SVG icon is already set with setIcon()
                btn.setText(f"{text}")
                
                # Update icon color for unselected state
                if btn_id in ICONS:
                    unselected_icon = self.create_icon(ICONS[btn_id], QSize(48, 48), "#8B91B5")
                    btn.setIcon(unselected_icon)
                
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: transparent;
                        color: #8B91B5;
                        border: none;
                        padding: 12px 8px;
                        text-align: left;
                        border-radius: 10px;
                        margin-bottom: 3px;
                        font-weight: 600;
                        font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                    }
                    QPushButton:hover {
                        background-color: rgba(58, 63, 92, 0.5);
                        color: white;
                    }
                """)
        
        self.current_page = item_id
        self.navigation_clicked.emit(item_id)
    

    
    # Logout UI removed; keep method stub if referenced elsewhere
    def on_logout(self):
        return
    
    def find_main_window(self):
        """Find the main window instance"""
        main_window = self.parent()
        while main_window and not isinstance(main_window, MainWindow):
            main_window = main_window.parent()
        return main_window
    
    def update_user_display(self, user=None):
        """Update user display in sidebar"""
        # Find main window to get current user info
        main_window = self.find_main_window()
        
        # Only update plan badge; user name and logout are removed
        if main_window and main_window.current_user:
            plan_info = main_window.get_user_plan_info()
            plan_type = plan_info.get('plan_type', 'Free')
            self.plan_info_label.setText(f"Your Plan: {plan_type}")
            self.apply_plan_styling(plan_type)
            self.plan_section.setVisible(True)
            self.plan_spacer.setVisible(True)
        else:
            self.plan_info_label.setText("Your Plan: Free")
            self.apply_plan_styling("Free")
            self.plan_section.setVisible(True)
            self.plan_spacer.setVisible(True)
    
    def update_plan_display(self):
        """Update only the plan display"""
        main_window = self.find_main_window()
        
        if main_window and main_window.current_user:
            plan_info = main_window.get_user_plan_info()
            plan_type = plan_info.get('plan_type', 'Free')
            
            # Update plan info label
            self.plan_info_label.setText(f"Your Plan: {plan_type}")
            
            # Apply plan-specific styling
            self.apply_plan_styling(plan_type)
            
            self.plan_section.setVisible(True)
            self.plan_spacer.setVisible(True)
        else:
            self.plan_info_label.setText("Your Plan: Free")
            self.apply_plan_styling("Free")
            self.plan_section.setVisible(True)
            self.plan_spacer.setVisible(True)
    def apply_plan_styling(self, plan_type: str):
        """Apply styling based on plan type"""
        if plan_type == "Essential":
            # Essential plan: Blue gradient text with blue border
            self.plan_info_label.setStyleSheet("""
                QLabel {
                    background: rgba(58, 63, 92, 0.3);
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 2px solid #3B82F6;
                    margin: 5px 0px;
                    color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3B82F6,
                        stop:0.5 #60A5FA,
                        stop:1 #93C5FD);
                    font-weight: bold;
                }
            """)
        elif plan_type == "Plus":
            # Plus plan: Purple gradient text with purple border
            self.plan_info_label.setStyleSheet("""
                QLabel {
                    background: rgba(58, 63, 92, 0.3);
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 2px solid #8B5CF6;
                    margin: 5px 0px;
                    color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #8B5CF6,
                        stop:0.5 #A78BFA,
                        stop:1 #C4B5FD);
                    font-weight: bold;
                }
            """)
        elif plan_type == "Elite":
            # Elite plan: Enhanced green gradient text with green border
            self.plan_info_label.setStyleSheet("""
                QLabel {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 rgba(16, 185, 129, 0.1),
                        stop:1 rgba(52, 211, 153, 0.1));
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #10B981,
                        stop:1 #34D399);
                    margin: 5px 0px;
                    color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #059669,
                        stop:0.3 #10B981,
                        stop:0.7 #34D399,
                        stop:1 #6EE7B7);
                    font-weight: bold;
                }
            """)
        else:
            # Free plan: Default styling
            self.plan_info_label.setStyleSheet("""
                QLabel {
                    color: #8B91B5;
                    background: rgba(58, 63, 92, 0.3);
                    padding: 12px 20px;
                    border-radius: 10px;
                    border: 1px solid #3A3F5C;
                    margin: 5px 0px;
                }
            """)


class ValidationThread(QThread):
    """Background thread for validation checks"""
    validation_complete = pyqtSignal(dict)
    validation_error = pyqtSignal(str, str)  # error_type, message
    
    def __init__(self, auth_service, user_id: str, text: str, settings: dict):
        super().__init__()
        self.auth_service = auth_service
        self.current_user = None
        self.current_profile = None
        
        # Initialize cost tracking service (only for admin)
        self.cost_tracking_service = None
        self.scene_cost_tracking_service = None
        if self.auth_service and self.auth_service.get_current_user():
            # Only initialize if user is authenticated
            try:
                self.cost_tracking_service = CostTrackingService(self.auth_service)
                self.scene_cost_tracking_service = SceneCostTrackingService(self.auth_service)
                print("💰 Cost tracking service initialized")
                print("💰 Scene cost tracking service initialized")
            except Exception as e:
                print(f"⚠️ Could not initialize cost tracking service: {e}")
        self.user_id = user_id
        self.text = text
        self.settings = settings
    
    def run(self):
        try:
            # Check analysis credits
            analysis_count = self.auth_service.get_user_analysis_count(self.user_id)
            
            if analysis_count <= 0:
                self.validation_error.emit("credits", "No analysis credits remaining")
                return
            
            # Decrement analysis count with device restriction check
            result = self.auth_service.decrement_analysis_count_with_device_check(self.user_id)
            
            if not result["success"]:
                if result.get("restricted", False):
                    self.validation_error.emit("device_restriction", result["message"])
                else:
                    self.validation_error.emit("error", result["message"])
                return
            
            # Return success result
            self.validation_complete.emit({
                'text': self.text,
                'settings': self.settings,
                'analysis_count': analysis_count,
                'remaining_count': result.get("remaining_count", analysis_count - 1)
            })
            
        except Exception as e:
            self.validation_error.emit("error", f"Validation failed: {str(e)}")


class AnalysisThread(QThread):
    """Background thread for analysis"""
    progress_updated = pyqtSignal(float, str)
    analysis_complete = pyqtSignal(list)
    analysis_error = pyqtSignal(str)
    
    def __init__(self, text: str, settings: Dict[str, Any], user_id: str = None, cost_tracking_service = None, scene_cost_tracking_service = None):
        super().__init__()
        self.text = text
        self.settings = settings
        self.user_id = user_id
        self.cost_tracking_service = cost_tracking_service
        self.scene_cost_tracking_service = scene_cost_tracking_service
        
    def run(self):
        try:
            def progress_callback(current, total, scene_text):
                progress = current / total
                self.progress_updated.emit(progress, f"Analyzing scene {current}/{total}...")
                
            scenes_data = process_text(self.text, progress_callback, self.settings, self.user_id, self.cost_tracking_service)
            
            # Save results
            write_json_output(scenes_data)
            
            self.analysis_complete.emit(scenes_data)
            
        except Exception as e:
            self.analysis_error.emit(str(e))


class LazyLoadingThread(QThread):
    """Background thread for lazy loading scene media"""
    scene_media_ready = pyqtSignal(int, dict)  # scene_index, media_data
    scene_media_error = pyqtSignal(int, str)   # scene_index, error_message
    
    def __init__(self, scene_data: Dict[str, Any], scene_index: int, settings: Dict[str, Any]):
        super().__init__()
        self.scene_data = scene_data
        self.scene_index = scene_index
        self.settings = settings
        
    def run(self):
        try:
            from logic.scene_analysis import generate_visual_suggestions
            
            # Generate media suggestions for this scene
            suggestions = generate_visual_suggestions(self.scene_data, self.settings)
            
            # Emit success signal with media data
            self.scene_media_ready.emit(self.scene_index, suggestions)
            
        except Exception as e:
            # Emit error signal
            self.scene_media_error.emit(self.scene_index, str(e))


class VideoAnalysisThread(QThread):
    """Background thread for AI video analysis with timeout"""
    analysis_complete = pyqtSignal(dict)
    analysis_error = pyqtSignal(str)
    
    def __init__(self, file_path: str, auth_service=None, timeout_seconds: int = 300):  # 5 minutes timeout
        super().__init__()
        self.file_path = file_path
        self.auth_service = auth_service
        self.timeout_seconds = timeout_seconds
        self.is_running = False
        
    def run(self):
        self.is_running = True
        try:
            from logic.video_analysis import analyze_video
            import time
            import threading
            
            # Create a flag to track if analysis is complete
            analysis_complete = threading.Event()
            result = None
            error = None
            
            def run_analysis():
                nonlocal result, error
                try:
                    # Perform real AI video analysis
                    result = analyze_video(self.file_path, self.auth_service)
                    analysis_complete.set()
                except Exception as e:
                    error = e
                    analysis_complete.set()
            
            # Start analysis in a separate thread
            analysis_thread = threading.Thread(target=run_analysis)
            analysis_thread.daemon = True
            analysis_thread.start()
            
            # Wait for analysis to complete or timeout
            if analysis_complete.wait(timeout=self.timeout_seconds):
                if error:
                    self.analysis_error.emit(f"Video analysis failed: {str(error)}")
                elif result and result.get("analysis_complete"):
                    self.analysis_complete.emit(result)
                else:
                    error_msg = result.get("error", "Unknown analysis error") if result else "Analysis failed"
                    self.analysis_error.emit(error_msg)
            else:
                # Timeout occurred
                self.analysis_error.emit("Video analysis timed out. Please try again with a shorter video or check your internet connection.")
                
        except ImportError as e:
            self.analysis_error.emit(f"Video analysis module not available: {str(e)}")
        except Exception as e:
            self.analysis_error.emit(f"Video analysis failed: {str(e)}")
        finally:
            self.is_running = False
    
    def stop_analysis(self):
        """Stop the analysis if it's running"""
        self.is_running = False
        self.terminate()
        self.wait(5000)  # Wait up to 5 seconds for thread to terminate


class AIImageGenerationThread(QThread):
    """Background thread for AI image generation"""
    generation_complete = pyqtSignal(str, str)  # image_url, prompt
    generation_error = pyqtSignal(str)
    generation_progress = pyqtSignal(str)
    
    def __init__(self, leonardo_service, prompt: str, aspect_ratio: str = "1:1"):
        super().__init__()
        self.leonardo_service = leonardo_service
        self.prompt = prompt
        self.aspect_ratio = aspect_ratio
        self._stop_flag = False
    
    def run(self):
        try:
            self.generation_progress.emit("Starting AI image generation...")
            
            # Generate image using Leonardo AI with progress updates
            def progress_callback(message):
                if not self._stop_flag:
                    self.generation_progress.emit(message)
            
            # Add progress callback to Leonardo service
            if hasattr(self.leonardo_service, 'set_progress_callback'):
                self.leonardo_service.set_progress_callback(progress_callback)
            
            # Generate image using Leonardo AI
            image_urls = self.leonardo_service.create_image_from_prompt(self.prompt, self.aspect_ratio)
            
            if image_urls and len(image_urls) > 0:
                if not self._stop_flag:
                    self.generation_complete.emit(image_urls[0], self.prompt)
            else:
                if not self._stop_flag:
                    self.generation_error.emit("Failed to generate AI image")
                    
        except Exception as e:
            if not self._stop_flag:
                self.generation_error.emit(f"AI image generation error: {str(e)}")
    
    def stop_generation(self):
        """Stop the generation"""
        self._stop_flag = True


class ModernButton(QPushButton):
    """Modern styled button"""
    def __init__(self, text: str, button_type: str = "secondary"):
        super().__init__(text)
        self.button_type = button_type
        self.setup_style()
        
    def setup_style(self):
        """Setup button styling"""
        if self.button_type == "primary":
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                              stop:0 #3B82F6, stop:1 #2563EB);
                    color: white;
                    border: none;
                    border-radius: 10px;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 500;
                    font-family: 'Poppins', 'Arial', sans-serif;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                              stop:0 #2563EB, stop:1 #1D4ED8);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                                              stop:0 #1D4ED8, stop:1 #1E40AF);
                }
                QPushButton:disabled {
                    background: #9CA3AF;
                    color: #F9FAFB;
                }
            """)
        else:
            self.setStyleSheet("""
                QPushButton {
                    background: white;
                    color: #111827;
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-size: 14px;
                    font-weight: 500;
                    font-family: 'Poppins', 'Arial', sans-serif;
                }
                QPushButton:hover {
                    border-color: #3B82F6;
                    background: #F8FAFC;
                }
                QPushButton:pressed {
                    background: #F1F5F9;
                    border-color: #2563EB;
                }
                QPushButton:disabled {
                    color: #9CA3AF;
                    background: #F9FAFB;
                    border-color: #E5E7EB;
                }
            """)


class ModernTabWidget(QTabWidget):
    """Modern styled tab widget"""
    def __init__(self):
        super().__init__()
        self.setup_style()
        
    def setup_style(self):
        """Setup tab styling"""
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: white;
                border-radius: 12px;
            }
            QTabBar::tab {
                background: #F8F9FA;
                color: #374151;
                border: none;
                padding: 12px 20px;
                margin-right: 4px;
                border-radius: 0px;
                font-size: 16px;
                font-weight: 500;
                font-family: 'Poppins', 'Inter', 'Segoe UI', 'Roboto', sans-serif;
                min-width: 120px;
            }
            QTabBar::tab:selected {
                background: #F8F9FA;
                color: #3B82F6;
                border: none;
                border-bottom: 2px solid #3B82F6;
                border-radius: 0px;
            }
            QTabBar::tab:hover:!selected {
                background: #F1F3F4;
                color: #3B82F6;
                border: none;
            }
        """)
    
    def setTabTextColor(self, index: int, color: QColor):
        """Set text color for a specific tab"""
        try:
            # Get the tab bar
            tab_bar = self.tabBar()
            if tab_bar and 0 <= index < tab_bar.count():
                # Set the text color using stylesheet
                tab_bar.setTabTextColor(index, color)
        except Exception as e:
            print(f"Error setting tab text color: {e}")
    
    def setTabIcon(self, index: int, icon: QIcon):
        """Set icon for a specific tab"""
        try:
            # Get the tab bar
            tab_bar = self.tabBar()
            if tab_bar and 0 <= index < tab_bar.count():
                tab_bar.setTabIcon(index, icon)
        except Exception as e:
            print(f"Error setting tab icon: {e}")
class MediaCard(QFrame):
    """Modern media card widget"""
    selection_changed = pyqtSignal(dict, bool, str)
    
    def __init__(self, suggestion: Dict[str, Any], media_type: str, card_index: int = 0):
        super().__init__()
        self.suggestion = suggestion
        self.media_type = media_type
        self.card_index = card_index  # Add card index for numbering
        self.is_selected = False
        # Network manager with parent to auto-clean on widget deletion
        self.network_manager = QNetworkAccessManager(self)
        # Track in-flight replies to abort on destruction
        self._pending_replies = []
        self._is_destroyed = False
        
        # Video player for hover autoplay
        self.video_player = None
        self.video_widget = None
        self.is_hovering = False
        self.hover_timer = QTimer()
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self.start_video_playback)
        
        # Video loading timeout timer
        self.video_timeout_timer = QTimer()
        self.video_timeout_timer.setSingleShot(True)
        self.video_timeout_timer.timeout.connect(self.on_video_timeout)
        
        # Video loading state tracking
        self.video_loading_started = False
        self.video_loading_timeout = 15000  # 15 seconds timeout for problematic videos
        
        # Video retry counter
        self.video_retry_count = 0
        self.max_video_retries = 2
        
        self.setup_ui()
        self.setup_style()
        # Only load thumbnail for non-AI images
        if self.media_type != "ai_images":
            self.load_thumbnail()
        
        # Always register AI image card with MainWindow for state sync (creating/completed)
        if self.media_type == "ai_images":
            main_window = self.find_main_window()
            if main_window:
                prompt_key = self.suggestion.get('prompt', self.suggestion.get('title', 'Beautiful landscape'))
                main_window.register_ai_generation_card(prompt_key, self)
        
        # Enable mouse tracking for hover events (only for stock videos)
        if self.media_type == "stock_videos":
            self.setMouseTracking(True)

        # Ensure cleanup when this card is destroyed
        try:
            self.destroyed.connect(self.on_destroyed)
        except Exception:
            pass
        
        # Track whether final AI image is already displayed to avoid duplicate loads
        self.has_final_image = False

        # Per-card download button (top-right)
        try:
            from PyQt6.QtGui import QIcon
            from PyQt6.QtCore import QSize
            self.download_btn = QPushButton("", self)
            icon_path = get_asset_path("download_button.png")
            if icon_path:
                self.download_btn.setIcon(QIcon(icon_path))
                self.download_btn.setIconSize(QSize(28, 28))
            self.download_btn.setToolTip("Download this item")
            self.download_btn.setFixedSize(36, 36)
            self.download_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self.download_btn.setStyleSheet(
                """
                QPushButton {
                    background: rgba(209, 213, 219, 0.52); /* gray-300 with slight whiteness */
                    border: none;
                    border-radius: 18px;
                }
                QPushButton:hover {
                    background: rgba(190, 194, 203, 0.56); /* slightly darker on hover */
                }
                """
            )
            self.download_btn.clicked.connect(self.on_download_clicked)
            self.download_btn.raise_()
        except Exception as _e:
            self.download_btn = None

        # Single-item download thread holder
        self._single_download_thread = None
    
    def closeEvent(self, event):
        """Handle widget close event - stop any running threads"""
        # Do NOT stop AI image generation thread on card close.
        # Threads are managed by MainWindow to persist across tab/scene changes.
        
        # Stop video playback if running
        if hasattr(self, 'video_player') and self.video_player:
            self.stop_video_playback()
        
        # Stop timers
        if hasattr(self, 'hover_timer'):
            self.hover_timer.stop()
        if hasattr(self, 'video_timeout_timer'):
            self.video_timeout_timer.stop()
        
        # Detach any ongoing download thread to prevent 'QThread destroyed while thread is still running'
        try:
            if hasattr(self, 'download_thread') and self.download_thread:
                if self.download_thread.isRunning():
                    # Remove parent to avoid cleanup crash on widget destruction
                    self.download_thread.setParent(None)
                self.download_thread = None
        except Exception as e:
            print(f"Warning: could not cleanup download thread: {e}")
        
        event.accept()
    
    def hideEvent(self, event):
        """Handle widget hide event - stop video playback"""
        # Stop video playback when widget is hidden
        if hasattr(self, 'video_player') and self.video_player:
            self.stop_video_playback()
        super().hideEvent(event)
    
    def truncate_at_sentence_end(self, text: str, max_length: int = 200) -> str:
        """Truncate text at the end of the current sentence"""
        if len(text) <= max_length:
            return text
        
        # Find the last sentence ending within max_length
        truncated = text[:max_length]
        
        # Look for sentence endings (., !, ?) in the truncated text
        sentence_endings = ['.', '!', '?']
        last_ending = -1
        
        for ending in sentence_endings:
            pos = truncated.rfind(ending)
            if pos > last_ending:
                last_ending = pos
        
        # If we found a sentence ending, truncate there
        if last_ending > 0:
            return text[:last_ending + 1]
        
        # If no sentence ending found, look for word boundaries
        last_space = truncated.rfind(' ')
        if last_space > 0:
            return text[:last_space] + "..."
        
        # If no word boundary found, just truncate and add ellipsis
        return truncated + "..."
        
    def setup_ui(self):
        """Setup card UI"""
        self.setFixedSize(280, 320)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Selection checkbox
        self.checkbox = QCheckBox("Select")
        self.checkbox.setFont(QFont("Inter", 12))
        self.checkbox.setStyleSheet("""
            QCheckBox {
                color: #111827;
                font-weight: 500;
                background: transparent;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 2px solid #D1D5DB;
                border-radius: 3px;
                background: transparent; /* transparent to avoid white rectangle */
            }
            QCheckBox::indicator:checked {
                background: #3B82F6;
                border-color: #3B82F6;
            }
            QCheckBox::indicator:hover {
                border-color: #3B82F6;
            }
            QCheckBox::indicator:unchecked {
                background: transparent;
            }
        """)
        self.checkbox.stateChanged.connect(self.on_selection_changed)
        
        # Ensure the checkbox inherits parent background
        self.checkbox.setAutoFillBackground(False)
        
        layout.addWidget(self.checkbox)
        
        # Thumbnail area with overlay
        self.thumbnail_frame = QFrame()
        self.thumbnail_frame.setFixedSize(248, 140)
        self.thumbnail_frame.setStyleSheet("""
            QFrame {
                background: transparent;
                border: none;
                border-radius: 25px;
                position: relative;
                margin-left: -8px;
            }
        """)
        
        # Create thumbnail area based on media type
        if self.media_type == "ai_images":
            # AI Images: If generation already completed for this prompt, show final image immediately
            thumbnail_layout = QVBoxLayout()
            thumbnail_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # PNG Label (static only) - 16:9 format for AI Images
            self.thumbnail_label = QLabel()
            self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumbnail_label.setFixedSize(248, 140)  # 16:9 aspect ratio
            self.thumbnail_label.setStyleSheet("border: none; border-radius: 25px;")
            self.thumbnail_label.setScaledContents(False)
            
            # Decide initial image
            show_final = False
            try:
                main_window = self.find_main_window()
                prompt_key = self.suggestion.get('prompt', self.suggestion.get('title', 'Beautiful landscape'))
                if main_window and hasattr(main_window, 'get_ai_generation_status'):
                    status = main_window.get_ai_generation_status(prompt_key)
                    if status == 'completed' and hasattr(main_window, 'get_ai_generation_result'):
                        image_url = main_window.get_ai_generation_result(prompt_key)
                        if image_url:
                            show_final = True
                            self.has_final_image = True
                            # Render final image immediately
                            self.load_generated_ai_image(image_url)
            except Exception:
                show_final = False

            if not show_final:
                # Load loading.png as static background with proper centering
                try:
                    png_path = os.path.abspath("ui/assets/loading.png")
                    if os.path.exists(png_path):
                        pixmap = QPixmap(png_path)
                        if not pixmap.isNull():
                            # Fill and center-crop to avoid side paddings
                            target_w, target_h = 248, 140
                            crop = pixmap.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                            # Center crop
                            x = (crop.width() - target_w) // 2
                            y = (crop.height() - target_h) // 2
                            cropped = crop.copy(x, y, target_w, target_h)
                            self.thumbnail_label.setPixmap(cropped)
                except Exception:
                    pass
            
            # Add only PNG widget to layout
            thumbnail_layout.addWidget(self.thumbnail_label)
            
            self.thumbnail_frame.setLayout(thumbnail_layout)
        else:
            # Stock Images and Videos: Use simple thumbnail layout
            thumbnail_layout = QVBoxLayout()
            thumbnail_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            self.thumbnail_label = QLabel()
            self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.thumbnail_label.setStyleSheet("border: none; border-radius: 25px;")
            self.thumbnail_label.setFixedSize(248, 140)
            self.thumbnail_label.setScaledContents(False)
                
            thumbnail_layout.addWidget(self.thumbnail_label)
            self.thumbnail_frame.setLayout(thumbnail_layout)
        
        layout.addWidget(self.thumbnail_frame)
        
        # Title - For stock media, show "Video/Image Suggestion X", for AI show "AI Suggestion X"
        original_title = self.suggestion.get('title', 'Untitled')
        
        if self.media_type == "ai_images":
            title = f"AI Suggestion {self.card_index + 1}"
        elif self.media_type == "stock_videos":
            title = f"Video Suggestion {self.card_index + 1}"
        elif self.media_type == "stock_images":
            title = f"Image Suggestion {self.card_index + 1}"
        else:
            title = original_title
            if len(title) > 25:
                title = title[:25] + "..."
            
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        self.title_label.setStyleSheet("color: #111827; border: none;")
        self.title_label.setWordWrap(True)
        
        # Add tooltip for full title
        if len(original_title) > 25:
            self.title_label.setToolTip(original_title)
        
        layout.addWidget(self.title_label)
        
        # Description - For stock media, show description as subtitle
        if self.media_type == "stock_videos":
            # For stock videos, show description as subtitle
            description = self.suggestion.get('description', '')
            # If description is empty or same as title, try other fields
            if not description or description == original_title:
                description = self.suggestion.get('alt_text', self.suggestion.get('caption', 'No description available'))
            subtitle = description
            if len(subtitle) > 60:
                subtitle = subtitle[:60] + "..."
        elif self.media_type == "stock_images":
            # For stock images, show description as subtitle (consistent with videos)
            description = self.suggestion.get('description', '')
            # If description is empty or same as title, try other fields
            if not description or description == original_title:
                description = self.suggestion.get('alt_text', self.suggestion.get('caption', original_title))
            subtitle = description
            if len(subtitle) > 60:
                subtitle = subtitle[:60] + "..."
        else:
            # For AI images, show description/prompt
            subtitle = self.suggestion.get('description', self.suggestion.get('prompt', ''))
            if len(subtitle) > 60:
                subtitle = subtitle[:60] + "..."
            
        self.desc_label = QLabel(subtitle)
        self.desc_label.setFont(QFont("Inter", 12))
        self.desc_label.setStyleSheet("color: #6B7280; border: none;")
        self.desc_label.setWordWrap(True)
        
        # Add tooltip for full description
        if self.media_type == "ai_images":
            # For AI images, always show full prompt in tooltip
            full_prompt = self.suggestion.get('description', self.suggestion.get('prompt', ''))
            self.desc_label.setToolTip(full_prompt)
        elif len(original_title) > 60:
            # For stock media, show full title if truncated
            self.desc_label.setToolTip(original_title)
        
        layout.addWidget(self.desc_label)
        
        # Badge for stock media - HD Video/Image badge
        if self.media_type in ["stock_videos", "stock_images"]:
            if self.media_type == "stock_videos":
                badge_text = "▶️ HD Video"
                badge_color = "#3B82F6"  # Blue for videos
            else:  # stock_images
                badge_text = "📸 HD Image"
                badge_color = "#10B981"  # Green for images
            
            self.badge_label = QLabel(badge_text)
            self.badge_label.setFont(QFont("Poppins", 10, QFont.Weight.Medium))
            self.badge_label.setStyleSheet(f"""
                QLabel {{
                    background: transparent;
                    color: {badge_color};
                    border: none;
                    padding: 4px 8px;
                    font-weight: 500;
                }}
            """)
            layout.addWidget(self.badge_label)
        
        # Tags - Only show for AI images, hide for stock media
        if self.media_type == "ai_images" and 'search_keywords' in self.suggestion:
            keywords = self.suggestion['search_keywords'][:3]
            tags_text = ", ".join(keywords)
            if len(tags_text) > 35:
                tags_text = tags_text[:35] + "..."
                
            self.tags_label = QLabel(tags_text)
            self.tags_label.setFont(QFont("Inter", 10))
            self.tags_label.setStyleSheet("color: #9CA3AF; border: none;")
            self.tags_label.setWordWrap(True)
            layout.addWidget(self.tags_label)
        
        # Show Create button only for AI Images
        if self.media_type == "ai_images":
            # Create button for AI Images
            self.create_btn = QPushButton("Create")
            self.create_btn.setFont(QFont("Poppins Medium", 10))
            
            self.create_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5170ff, stop:1 #ff66c4);
                    color: white;
                    border: none;
                    border-radius: 5px;
                    padding: 5px 10px;
                    font-weight: 500;
                    font-family: 'Poppins Medium', 'Poppins', 'Arial', sans-serif;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3B82F6, stop:1 #8B5CF6);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2563EB, stop:1 #7C3AED);
                }
            """)
            self.create_btn.clicked.connect(self.on_create_clicked)
            
            # Check if AI image was already generated
            if self.suggestion.get('ai_generated', False) and (
                self.suggestion.get('download_url') or self.suggestion.get('url')
            ):
                self.create_btn.setText("Created ✅")
                self.create_btn.setStyleSheet("""
                    QPushButton {
                        background: #10B981;
                        color: white;
                        border: none;
                        border-radius: 5px;
                        padding: 5px 10px;
                        font-weight: 500;
                        font-family: 'Poppins Medium', 'Poppins', 'Arial', sans-serif;
                    }
                """)
                self.create_btn.setEnabled(False)
                
                # Load the generated image
                url_to_load = self.suggestion.get('download_url') or self.suggestion.get('url')
                if url_to_load:
                    self.load_generated_ai_image(url_to_load)
            
            layout.addWidget(self.create_btn)

        
        layout.addStretch()
        self.setLayout(layout)
        
    def setup_style(self):
        """Setup card styling"""
        self.setStyleSheet("""
            QFrame {
                background: #F8F9FA;
                border: 1px solid #E5E7EB;
                border-radius: 25px;
            }
            QFrame:hover {
                border-color: #3B82F6;
                background-color: #F1F3F4;
            }
        """)
        
    def on_selection_changed(self, state):
        """Handle selection change"""
        self.is_selected = state == Qt.CheckState.Checked.value
        self.selection_changed.emit(self.suggestion, self.is_selected, self.media_type)
        
        # Update visual style
        if self.is_selected:
            self.setStyleSheet("""
                QFrame {
                    background: #F8F9FA;
                    border: 2px solid #3B82F6;
                    border-radius: 25px;
                }
            """)
        else:
            self.setup_style()
            
    def enterEvent(self, event):
        """Handle mouse enter event for video autoplay"""
        super().enterEvent(event)
        # Only enable hover for stock videos, not AI images
        if self.media_type == "stock_videos" and 'download_url' in self.suggestion:
            self.is_hovering = True
            # Start timer to delay video playback (500ms delay)
            self.hover_timer.start(500)
    
    def leaveEvent(self, event):
        """Handle mouse leave event to stop video playback"""
        super().leaveEvent(event)
        # Only handle hover for stock videos, not AI images
        if self.media_type == "stock_videos":
            self.is_hovering = False
            self.hover_timer.stop()
            # Stop timeout timer if video is loading
            if self.video_loading_started:
                self.video_timeout_timer.stop()
                self.video_loading_started = False
            # Mouse left video area
            self.stop_video_playback()
    
    def start_video_playback(self):
        """Start video playback when hovering"""
        if not self.is_hovering or self.media_type != "stock_videos":
            return
            
        if not MULTIMEDIA_AVAILABLE:
            print("PyQt6 Multimedia module not available for video playback")
            return
            
        try:
            # Create video player if not exists
            if self.video_player is None:
                self.video_player = QMediaPlayer()
                self.video_widget = QVideoWidget()
                self.video_player.setVideoOutput(self.video_widget)
                
                # Set video source
                video_url = self.suggestion.get('download_url')
                if video_url:
                    # Validate URL before setting source
                    if not video_url.startswith(('http://', 'https://')):
                        print(f"Invalid video URL: {video_url}")
                        return
                    
                    print(f"Loading video from: {video_url}")
                    self.video_player.setSource(QUrl(video_url))
                    self.video_player.setLoops(QMediaPlayer.Loops.Infinite)  # Loop video
                    
                    # Connect signals for better control
                    self.video_player.mediaStatusChanged.connect(self.on_media_status_changed)
                    self.video_player.errorOccurred.connect(self.on_video_error)
                    
                    # Add playback state change signal
                    self.video_player.playbackStateChanged.connect(self.on_playback_state_changed)
                else:
                    print("No video URL available")
                    return
            
            # Replace thumbnail with video widget immediately
            if self.video_player and self.video_widget:
                # Clear thumbnail layout and add video widget
                thumbnail_layout = self.thumbnail_frame.layout()
                if thumbnail_layout:
                    # Remove thumbnail label
                    thumbnail_layout.removeWidget(self.thumbnail_label)
                    self.thumbnail_label.hide()
                    
                    # Add video widget
                    thumbnail_layout.addWidget(self.video_widget)
                    self.video_widget.setFixedSize(248, 140)
                    self.video_widget.show()
                    
                    # Set video widget background to match thumbnail and add loading style
                    self.video_widget.setStyleSheet("""
                        QVideoWidget {
                            background-color: #F9FAFB; 
                            border: 1px solid #E5E7EB; 
                            border-radius: 25px;
                        }
                    """)
                    
                    # Start timeout timer
                    self.video_loading_started = True
                    self.video_timeout_timer.start(self.video_loading_timeout)
                    
                    # Start playing
                    self.video_player.play()
                    
        except Exception as e:
            print(f"Error starting video playback: {e}")
    
    
    def on_media_status_changed(self, status):
        """Handle media status changes"""
        print(f"Media status changed: {status}")
        
        if status == QMediaPlayer.MediaStatus.LoadedMedia:
            # Video loaded successfully, ensure it's playing
            print("Video loaded successfully")
            self.video_timeout_timer.stop()
            self.video_loading_started = False
            
            if self.video_player and self.is_hovering:
                self.video_player.play()
                
        elif status == QMediaPlayer.MediaStatus.LoadingMedia:
            # Video is loading, show loading indicator
            print("Video loading...")
            
        elif status == QMediaPlayer.MediaStatus.BufferingMedia:
            # Video is buffering, keep loading indicator
            print("Video buffering...")
            
        elif status == QMediaPlayer.MediaStatus.StalledMedia:
            # Video is stalled, keep loading indicator
            print("Video stalled...")
            
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            # Video ended, restore thumbnail
            print("Video ended - restoring thumbnail")
            self.video_timeout_timer.stop()
            self.video_loading_started = False
            self.stop_video_playback()
            
        elif status == QMediaPlayer.MediaStatus.InvalidMedia:
            # Invalid media, restore thumbnail
            print("Invalid media - restoring thumbnail")
            self.video_timeout_timer.stop()
            self.video_loading_started = False
            self.stop_video_playback()
            
        elif status == QMediaPlayer.MediaStatus.NoMedia:
            # No media, restore thumbnail
            print("No media - restoring thumbnail")
            self.video_timeout_timer.stop()
            self.video_loading_started = False
            self.stop_video_playback()
    
    def on_playback_state_changed(self, state):
        """Handle playback state changes"""
        print(f"Playback state changed: {state}")
        
        if state == QMediaPlayer.PlaybackState.PlayingState:
            # Video is playing
            print("Video is playing")
            
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            # Video stopped, restore thumbnail
            print("Video stopped - restoring thumbnail")
            self.stop_video_playback()
            
        elif state == QMediaPlayer.PlaybackState.PausedState:
            # Video paused
            print("Video paused")
    
    def try_alternative_video_loading(self):
        """Try alternative method to load video when demuxing fails"""
        try:
            print("Attempting alternative video loading method")
            
            # Clean up existing video player
            if self.video_player:
                self.video_player.stop()
                self.video_player.deleteLater()
                self.video_player = None
            
            if self.video_widget:
                self.video_widget.deleteLater()
                self.video_widget = None
            
            # Create new video player with different settings
            self.video_player = QMediaPlayer()
            self.video_widget = QVideoWidget()
            self.video_player.setVideoOutput(self.video_widget)
            
            # Set different media settings for better compatibility
            video_url = self.suggestion.get('download_url')
            if video_url:
                # Try with different media settings
                self.video_player.setSource(QUrl(video_url))
                self.video_player.setLoops(QMediaPlayer.Loops.Infinite)
                
                # Connect signals
                self.video_player.mediaStatusChanged.connect(self.on_media_status_changed)
                self.video_player.errorOccurred.connect(self.on_video_error_final)
                self.video_player.playbackStateChanged.connect(self.on_playback_state_changed)
                
                # Try to play with a delay
                QTimer.singleShot(500, lambda: self.video_player.play() if self.video_player else None)
                
                print("Alternative video loading method completed")
            else:
                print("No video URL available for alternative loading")
                self.stop_video_playback()
                
        except Exception as e:
            print(f"Error in alternative video loading: {e}")
            self.stop_video_playback()
    
    def on_video_error_final(self, error, error_string):
        """Final error handler when alternative loading also fails"""
        print(f"Final video error: {error_string}")
        print(f"Error code: {error}")
        
        # Show user-friendly error message
        self.show_video_error_message(error_string)
        
        # Restore thumbnail
        self.stop_video_playback()
    
    def show_video_error_message(self, error_string):
        """Show user-friendly error message for video loading failures"""
        try:
            # Create error message widget
            error_widget = QWidget(self.video_widget if hasattr(self, 'video_widget') and self.video_widget else self)
            error_layout = QVBoxLayout(error_widget)
            error_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            
            # Error icon
            error_icon = QLabel("⚠️")
            error_icon.setFont(QFont("Arial", 24))
            error_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_icon.setStyleSheet("color: #EF4444; background: transparent; border: none;")
            error_layout.addWidget(error_icon)
            
            # Error text
            error_text = QLabel("Video yüklenemedi")
            error_text.setFont(QFont("Inter", 12, QFont.Weight.Medium))
            error_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_text.setStyleSheet("color: #6B7280; background: transparent; border: none;")
            error_layout.addWidget(error_text)
            
            # Subtitle
            subtitle = QLabel("Bu video formatı desteklenmiyor")
            subtitle.setFont(QFont("Inter", 10))
            subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
            error_layout.addWidget(subtitle)
            
            # Style the error widget
            error_widget.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 255, 255, 0.95);
                    border: 1px solid #E5E7EB;
                    border-radius: 8px;
                }
            """)
            
            # Replace video widget with error widget temporarily
            if hasattr(self, 'video_widget') and self.video_widget:
                thumbnail_layout = self.thumbnail_frame.layout()
                if thumbnail_layout:
                    # Remove video widget
                    thumbnail_layout.removeWidget(self.video_widget)
                    self.video_widget.hide()
                    
                    # Add error widget
                    thumbnail_layout.addWidget(error_widget)
                    error_widget.setFixedSize(248, 140)
                    error_widget.show()
                    
                    # Auto-restore thumbnail after 3 seconds
                    QTimer.singleShot(3000, lambda: self.restore_thumbnail_from_error())
                    
        except Exception as e:
            print(f"Error showing video error message: {e}")
    
    def restore_thumbnail_from_error(self):
        """Restore thumbnail after showing error message"""
        try:
            thumbnail_layout = self.thumbnail_frame.layout()
            if thumbnail_layout:
                # Remove error widget if it exists
                for i in range(thumbnail_layout.count()):
                    child = thumbnail_layout.itemAt(i).widget()
                    if child and child != self.thumbnail_label:
                        thumbnail_layout.removeWidget(child)
                        child.deleteLater()
                
                # Add back thumbnail label
                thumbnail_layout.addWidget(self.thumbnail_label)
                self.thumbnail_label.show()
                
        except Exception as e:
            print(f"Error restoring thumbnail from error: {e}")
    
    def on_video_error(self, error, error_string):
        """Handle video playback errors"""
        print(f"Video error: {error_string}")
        print(f"Error code: {error}")
        
        # Stop timeout timer
        self.video_timeout_timer.stop()
        self.video_loading_started = False
        
        # Check if it's a demuxing error and try alternative approach
        if "Demuxing failed" in error_string or "I/O error" in error_string:
            print("Detected demuxing error - trying alternative video loading method")
            self.try_alternative_video_loading()
        else:
            # Restore thumbnail on error
            self.stop_video_playback()
    
    def on_video_timeout(self):
        """Handle video loading timeout"""
        print("Video loading timeout - attempting retry")
        self.video_loading_started = False
        
        # Try alternative loading method if retries available
        if self.video_retry_count < self.max_video_retries:
            self.video_retry_count += 1
            print(f"Retry attempt {self.video_retry_count}/{self.max_video_retries}")
            self.try_alternative_video_loading()
        else:
            print("Max retries reached - restoring thumbnail")
            self.video_retry_count = 0  # Reset for next time
            # Restore thumbnail on timeout
            self.stop_video_playback()
    
    def stop_video_playback(self):
        """Stop video playback and restore thumbnail"""
        try:
            print("Stopping video playback")
            
            # Stop timeout timer
            self.video_timeout_timer.stop()
            self.video_loading_started = False
            
            # Reset retry counter
            self.video_retry_count = 0
            
            # Stop video playback
            
            if self.video_player:
                self.video_player.stop()
                
            # Restore thumbnail
            thumbnail_layout = self.thumbnail_frame.layout()
            if thumbnail_layout and hasattr(self, 'video_widget') and self.video_widget:
                # Remove video widget
                thumbnail_layout.removeWidget(self.video_widget)
                self.video_widget.hide()
                
                # Add back thumbnail label
                thumbnail_layout.addWidget(self.thumbnail_label)
                self.thumbnail_label.show()
                
        except Exception as e:
            print(f"Error stopping video playback: {e}")
    
    def mousePressEvent(self, event):
        """Handle mouse click"""
        if event.button() == Qt.MouseButton.LeftButton:
            # For AI Images, only toggle checkbox (no generation on click)
            if self.media_type == "ai_images":
                # Only allow selection if AI image has been generated
                if not self.suggestion.get('ai_generated', False):
                    try:
                        from PyQt6.QtWidgets import QMessageBox
                        box = QMessageBox(self)
                        box.setIcon(QMessageBox.Icon.Information)
                        box.setWindowTitle("AI Image")
                        box.setText("Please create the AI image first before selecting it.")
                        box.setStyleSheet(
                            "QMessageBox { background-color: #111111; color: #ffffff; }\n"
                            "QWidget { color: #ffffff; }\n"
                            "QLabel { color: #ffffff; background-color: transparent; border: none; }\n"
                            "QFrame { background-color: transparent; border: none; }\n"
                            "QTextEdit, QTextBrowser { background-color: transparent; color: #ffffff; border: none; }\n"
                            "QPushButton { background: #2b2b2b; color: #ffffff; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 6px; }\n"
                            "QPushButton:hover { background: #3a3a3a; }"
                        )
                        box.exec()
                    except Exception:
                        pass
                    return
                # Toggle selection when created
                self.checkbox.setChecked(not self.checkbox.isChecked())
            else:
                # For other media types, toggle checkbox
                self.checkbox.setChecked(not self.checkbox.isChecked())
        super().mousePressEvent(event)
    
    def load_thumbnail(self):
        """Load thumbnail image with preference for higher quality URLs and better error handling"""
        # Check if the label still exists before proceeding
        if not hasattr(self, 'thumbnail_label') or self.thumbnail_label is None:
            return
        
        # Check if thumbnail is already loaded (cache check)
        if hasattr(self, 'thumbnail_loaded') and self.thumbnail_loaded:
            print(f"📋 Thumbnail already loaded for {self.media_type}, skipping...")
            return
            
        # Try multiple URL sources in order of preference
        thumbnail_urls = []
        
        # First try preview_url if it's available and looks like a valid image URL
        if 'preview_url' in self.suggestion and self.suggestion['preview_url']:
            preview_url = self.suggestion['preview_url']
            # More comprehensive validation for video thumbnails
            if (any(ext in preview_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp', '.gif']) or 
                'images.' in preview_url or 'thumbnails.' in preview_url or 'cdn.' in preview_url):
                thumbnail_urls.append(preview_url)
        
        # Then try thumbnail_url as fallback
        if 'thumbnail_url' in self.suggestion and self.suggestion['thumbnail_url']:
            thumbnail_url = self.suggestion['thumbnail_url']
            if thumbnail_url not in thumbnail_urls:  # Avoid duplicates
                thumbnail_urls.append(thumbnail_url)
        
        # For videos, also try download_url as it might contain thumbnail info
        if ('download_url' in self.suggestion and self.suggestion['download_url']):
            download_url = self.suggestion['download_url']
            if download_url not in thumbnail_urls:
                thumbnail_urls.append(download_url)
        
        # Add fallback URLs for videos if no valid URLs found
        if not thumbnail_urls and self.media_type == "stock_videos":
            # Create a fallback thumbnail URL for videos
            title = self.suggestion.get('title', 'Video')
            # Try to create a more reliable fallback
            if 'download_url' in self.suggestion and self.suggestion['download_url']:
                # Use download URL as fallback for video thumbnails
                thumbnail_urls.append(self.suggestion['download_url'])
            else:
                # Create SVG fallback
                fallback_url = f"data:image/svg+xml,%3csvg width='400' height='300' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='%2310B981'/%3e%3ctext x='50%25' y='50%25' font-size='16' fill='white' text-anchor='middle' dy='.3em'%3e{title[:20]}%3c/text%3e%3c/svg%3e"
                thumbnail_urls.append(fallback_url)
        
        if thumbnail_urls:
            self.current_url_index = 0
            self.thumbnail_urls = thumbnail_urls
            self.try_load_thumbnail()
        else:
            # Use placeholder image if no URLs available
            self.create_placeholder_image()
            
    def try_load_thumbnail(self):
        """Try to load thumbnail from current URL with retry logic"""
        # Check if the label still exists before proceeding
        if not hasattr(self, 'thumbnail_label') or self.thumbnail_label is None:
            return
            
        if self.current_url_index >= len(self.thumbnail_urls):
            # All URLs failed, use placeholder
            print(f"❌ All thumbnail URLs failed for {self.media_type}, creating placeholder...")
            self.create_placeholder_image()
            return
            
        thumbnail_url = self.thumbnail_urls[self.current_url_index]
        
        # Loading thumbnail
        
        try:
            # Load thumbnail from URL
            request = QNetworkRequest(QUrl(thumbnail_url))
            request.setRawHeader(b"User-Agent", b"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            # Set shorter timeout to avoid hanging
            request.setTransferTimeout(12000)  # 12 seconds - increased for video thumbnails
            # Add headers to improve compatibility
            request.setRawHeader(b"Accept", b"image/webp,image/apng,image/*,*/*;q=0.8")
            request.setRawHeader(b"Accept-Language", b"en-US,en;q=0.9")
            
            reply = self.network_manager.get(request)
            if reply:
                try:
                    # Parent reply to this widget and track it for cleanup
                    reply.setParent(self)
                except Exception:
                    pass
                self._pending_replies.append(reply)
                reply.finished.connect(lambda: self.handle_thumbnail_reply(reply))
            else:
                print(f"❌ Failed to create network request for {self.media_type}")
                self.try_next_url()
        except Exception as e:
            self.try_next_url()
    

    
    def safe_set_pixmap(self, pixmap, scaled_contents):
        """Safely set pixmap from main thread"""
        try:
            if hasattr(self, 'thumbnail_label') and self.thumbnail_label is not None:
                self.thumbnail_label.setPixmap(pixmap)
                self.thumbnail_label.setScaledContents(scaled_contents)
        except RuntimeError as e:
            print(f"Warning: Could not set thumbnail pixmap - label may have been deleted: {e}")
        except Exception as e:
            print(f"Error setting pixmap: {e}")
            self.try_next_url()
            
    def try_next_url(self):
        """Try the next URL in the list"""
        # Check if the label still exists before proceeding
        if not hasattr(self, 'thumbnail_label') or self.thumbnail_label is None:
            return
            
        self.current_url_index += 1
        
        # If we've tried all URLs, create a placeholder
        if self.current_url_index >= len(self.thumbnail_urls):
            print(f"🔄 All thumbnail URLs failed for {self.media_type}, creating placeholder...")
            self.create_placeholder_image()
            return
            
        # Try the next URL
        print(f"🔄 Trying next thumbnail URL ({self.current_url_index + 1}/{len(self.thumbnail_urls)}) for {self.media_type}")
        self.try_load_thumbnail()
    

    def try_alternative_video_thumbnail_loading(self):
        """Try alternative method for loading video thumbnails"""
        try:
            if not hasattr(self, 'thumbnail_label') or self.thumbnail_label is None:
                return
                
            # Try to create a simple colored placeholder with video icon
            title = self.suggestion.get('title', 'Video')
            
            # Create a more attractive fallback thumbnail
            fallback_url = f"data:image/svg+xml,%3csvg width='400' height='300' xmlns='http://www.w3.org/2000/svg'%3e%3crect width='100%25' height='100%25' fill='%2310B981'/%3e%3crect x='10%25' y='10%25' width='80%25' height='80%25' fill='rgba(255,255,255,0.1)' rx='10'/%3e%3cpolygon points='35%25,25%25 35%25,75%25 75%25,50%25' fill='white'/%3e%3ctext x='50%25' y='85%25' font-size='12' fill='white' text-anchor='middle'%3e{title[:15]}%3c/text%3e%3c/svg%3e"
            
            # Create pixmap from SVG data
            pixmap = QPixmap()
            if pixmap.loadFromData(fallback_url.encode()):
                # Scale to fit thumbnail frame
                target_width = 248
                target_height = 140
                scaled_pixmap = pixmap.scaled(
                    target_width, 
                    target_height, 
                    Qt.AspectRatioMode.KeepAspectRatio, 
                    Qt.TransformationMode.SmoothTransformation
                )
                
                # Center-crop (no side paddings)
                crop = pixmap.scaled(target_width, target_height, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                cx = (crop.width() - target_width) // 2
                cy = (crop.height() - target_height) // 2
                cropped = crop.copy(cx, cy, target_width, target_height)
                QTimer.singleShot(0, lambda: self.safe_set_pixmap(cropped, False))
                print(f"✅ Alternative video thumbnail loaded for: {title}")
            else:
                # Fallback to simple placeholder
                self.create_placeholder_image()
                
        except Exception as e:
            print(f"❌ Error in alternative video thumbnail loading: {e}")
            self.create_placeholder_image()

    def resizeEvent(self, event):
        try:
            super().resizeEvent(event)
        except Exception:
            pass
        # Keep loading overlay covering the window and center its card
        try:
            if hasattr(self, '_loading_overlay') and self._loading_overlay and self._loading_overlay.isVisible():
                self._loading_overlay.setGeometry(0, 0, self.width(), self.height())
                card = None
                # Find the card child (first child widget inside overlay)
                for child in self._loading_overlay.findChildren(QWidget):
                    if child.parent() is self._loading_overlay:
                        card = child
                        break
                if card:
                    ow = self._loading_overlay.width()
                    oh = self._loading_overlay.height()
                    cw = card.width()
                    ch = card.height()
                    offset_x = 96
                    card.move(max(0, (ow - cw) // 2 + offset_x), max(0, (oh - ch) // 2))
        except Exception:
            pass
        # Position the download button at the top-right of the card
        try:
            if hasattr(self, 'download_btn') and self.download_btn:
                margin = 8
                self.download_btn.move(self.width() - self.download_btn.width() - margin, margin)
            # Resize overlay to cover the card
            if hasattr(self, '_download_overlay') and self._download_overlay:
                self._download_overlay.setGeometry(0, 0, self.width(), self.height())
        except Exception:
            pass

    def _ensure_download_overlay(self):
        try:
            if getattr(self, '_download_overlay', None) is None:
                overlay = QWidget(self)
                overlay.setGeometry(0, 0, self.width(), self.height())
                overlay.setStyleSheet("background: rgba(17, 24, 39, 0.5);")
                overlay.setVisible(False)
                layout = QVBoxLayout(overlay)
                layout.setContentsMargins(0, 0, 0, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label = QLabel("Downloading...")
                label.setStyleSheet("color: white; background: transparent;")
                label.setFont(QFont("Arial", 12, QFont.Weight.Bold))
                layout.addWidget(label)
                overlay._label = label  # attach for updates
                self._download_overlay = overlay
        except Exception:
            self._download_overlay = None

    def _show_download_overlay(self, text: str = "Downloading..."):
        try:
            self._ensure_download_overlay()
            if self._download_overlay and hasattr(self._download_overlay, '_label'):
                self._download_overlay._label.setText(text)
                self._download_overlay.show()
                self._download_overlay.raise_()
        except Exception:
            pass

    def _hide_download_overlay(self):
        try:
            if hasattr(self, '_download_overlay') and self._download_overlay:
                self._download_overlay.hide()
        except Exception:
            pass

    def create_placeholder_image(self):
        """Create a placeholder image for the thumbnail"""
        # Check if the label still exists before trying to set pixmap
        if not hasattr(self, 'thumbnail_label') or self.thumbnail_label is None:
            return
            
        try:
            # Create a 248x140 placeholder image
            pixmap = QPixmap(248, 140)
            
            # Check if this is a placeholder from missing API keys
            source = self.suggestion.get('source', '')
            if source == 'placeholder':
                # Use a different style for API key missing placeholders
                pixmap.fill(QColor("#F3F4F6"))  # Light gray background
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Set up gray text
                painter.setPen(QPen(QColor("#6B7280")))
                painter.setFont(QFont("Inter", 10, QFont.Weight.Bold))
                
                # Draw the message
                title = self.suggestion.get('title', 'Untitled')[:20]
                if self.media_type == "stock_images":
                    text = f"📸 {title}\n\n⚠️ API Key Missing\nAdd stock API keys\nto see real images"
                elif self.media_type == "stock_videos":
                    text = f"🎬 {title}\n\n⚠️ API Key Missing\nAdd stock API keys\nto see real videos"
                else:
                    text = f"🎨 {title}\n\n⚠️ API Key Missing"
                
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
                painter.end()
            else:
                # Use different colors for different media types (original behavior)
                if self.media_type == "stock_images":
                    pixmap.fill(QColor("#3B82F6"))  # Blue
                elif self.media_type == "stock_videos":
                    pixmap.fill(QColor("#10B981"))  # Green
                else:
                    pixmap.fill(QColor("#F59E0B"))  # Orange
                
                painter = QPainter(pixmap)
                painter.setRenderHint(QPainter.RenderHint.Antialiasing)
                
                # Set up white text
                painter.setPen(QPen(QColor("#FFFFFF")))
                painter.setFont(QFont("Inter", 14, QFont.Weight.Bold))
                
                # Draw the media type and title
                title = self.suggestion.get('title', 'Untitled')[:30]
                if self.media_type == "stock_images":
                    text = f"📸 IMAGE\n{title}"
                elif self.media_type == "stock_videos":
                    text = f"🎬 VIDEO\n{title}"
                else:
                    text = f"🎨 AI\n{title}"
                
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)
                painter.end()
            
            # Set the pixmap to the label using main thread
            QTimer.singleShot(0, lambda: self.safe_set_pixmap(pixmap, True))
            
            # Mark thumbnail as loaded (cache flag)
            self.thumbnail_loaded = True
            
            # Log successful placeholder creation for debugging
            print(f"✅ Created placeholder thumbnail for {self.media_type}: {self.suggestion.get('title', 'Untitled')}")
            
        except RuntimeError as e:
            # Handle the case where the QLabel has been deleted
            print(f"Warning: Could not set thumbnail pixmap - label may have been deleted: {e}")
        except Exception as e:
            print(f"Error creating placeholder image ({self.media_type}): {e}")
    def handle_thumbnail_reply(self, reply: QNetworkReply):
        """Handle thumbnail download response with improved aspect ratio handling and retry logic"""
        try:
            # If widget is being destroyed, abort safely
            if getattr(self, '_is_destroyed', False):
                try:
                    reply.abort()
                except Exception:
                    pass
                return
            # Check if the label still exists before trying to set pixmap
            if not hasattr(self, 'thumbnail_label') or self.thumbnail_label is None:
                reply.deleteLater()
                return
                
            if reply.error() == QNetworkReply.NetworkError.NoError:
                data = reply.readAll()
                pixmap = QPixmap()
                if pixmap.loadFromData(data) and not pixmap.isNull():
                    # Get original image dimensions
                    original_width = pixmap.width()
                    original_height = pixmap.height()
                    
                    # Target dimensions for thumbnail frame
                    target_width = 248
                    target_height = 140
                    
                    # Check if image is too low resolution - avoid stretching
                    if original_width < target_width * 0.5 or original_height < target_height * 0.5:
                        # For very low resolution images, center them without stretching
                        scaled_pixmap = pixmap.scaled(
                            min(original_width, target_width), 
                            min(original_height, target_height), 
                            Qt.AspectRatioMode.KeepAspectRatio, 
                            Qt.TransformationMode.SmoothTransformation
                        )
                    else:
                        # For adequate resolution, scale to fit while maintaining aspect ratio
                        scaled_pixmap = pixmap.scaled(
                            target_width, 
                            target_height, 
                            Qt.AspectRatioMode.KeepAspectRatio, 
                            Qt.TransformationMode.SmoothTransformation
                        )
                    
                    # Center-crop to remove side paddings
                    crop = pixmap.scaled(
                        target_width,
                        target_height,
                        Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    cx = (crop.width() - target_width) // 2
                    cy = (crop.height() - target_height) // 2
                    cropped = crop.copy(cx, cy, target_width, target_height)
                    
                    try:
                        # Set the pixmap to the label using main thread
                        QTimer.singleShot(0, lambda: self.safe_set_pixmap(cropped, False))
                        
                        # Mark thumbnail as loaded (cache flag)
                        self.thumbnail_loaded = True
                        # Thumbnail loaded successfully
                        
                    except RuntimeError as e:
                        # Handle the case where the QLabel has been deleted
                        print(f"Warning: Could not set thumbnail pixmap - label may have been deleted: {e}")
                else:
                    # Invalid image data, try next URL
                    print(f"Invalid image data for thumbnail, trying next URL...")
                    self.try_next_url()
            else:
                # Network error, try next URL
                current_url = self.thumbnail_urls[self.current_url_index]
                error_msg = reply.errorString()
                
                # Only log errors for non-placeholder URLs to reduce spam
                if not any(placeholder in current_url for placeholder in ["data:image/svg+xml", "via.placeholder.com", "vimeocdn"]):
                    print(f"Network error loading thumbnail ({self.media_type}): {error_msg}")
                    print(f"URL: {current_url}")
                    # For video thumbnails, try alternative loading method
                    if self.media_type == "stock_videos" and self.current_url_index == 0:
                        print(f"🔄 Trying alternative loading for video thumbnail...")
                        QTimer.singleShot(1000, self.try_alternative_video_thumbnail_loading)
                
                self.try_next_url()
        except Exception as e:
            print(f"Exception in handle_thumbnail_reply ({self.media_type}): {e}")
            self.try_next_url()
        finally:
            try:
                if reply in getattr(self, '_pending_replies', []):
                    self._pending_replies.remove(reply)
            except Exception:
                pass
            reply.deleteLater()

    def cancel_thumbnail_requests(self):
        """Abort and delete all in-flight thumbnail requests."""
        try:
            for r in list(getattr(self, '_pending_replies', [])):
                try:
                    r.finished.disconnect()
                except Exception:
                    pass
                try:
                    r.abort()
                except Exception:
                    pass
                try:
                    r.deleteLater()
                except Exception:
                    pass
            self._pending_replies.clear()
        except Exception:
            pass

    def on_destroyed(self, *args, **kwargs):
        """Cleanup resources when the card is destroyed to avoid crashes on rapid navigation."""
        self._is_destroyed = True
        # Stop timers
        try:
            if hasattr(self, 'hover_timer') and self.hover_timer:
                self.hover_timer.stop()
        except Exception:
            pass
        try:
            if hasattr(self, 'video_timeout_timer') and self.video_timeout_timer:
                self.video_timeout_timer.stop()
        except Exception:
            pass
        # Release video player
        try:
            if hasattr(self, 'video_player') and self.video_player:
                self.video_player.stop()
                self.video_player = None
        except Exception:
            pass
        # Cancel any pending network replies
        self.cancel_thumbnail_requests()
    
    def on_create_clicked(self):
        """Handle create button click - only for AI Images"""
        if self.media_type == "ai_images":
            print(f"🎨 Create button clicked for AI Image: {self.suggestion.get('title', 'Unknown')}")
            
            # Get main window to access auth service
            main_window = self.find_main_window()
            
            # Check AI credits BEFORE disabling the button
            credits_available = False
            if main_window and hasattr(main_window, 'auth_service') and main_window.auth_service:
                try:
                    # Check current AI image credits first
                    current_user = main_window.auth_service.get_current_user()
                    if current_user and current_user.get("user"):
                        user_id = current_user["user"].id
                        ai_image_count = main_window.auth_service.get_user_ai_image_count(user_id)
                        
                        if ai_image_count <= 0:
                            # Show popup immediately and return
                            root_parent = main_window or self.parent()
                            credits_dialog = ModernCreditsDialog(
                                root_parent,
                                title="AI Image Credits",
                                message="Your AI image credits have run out",
                                subtitle="Upgrade your plan to continue generating AI images"
                            )
                            credits_dialog.exec()
                            return
                        else:
                            credits_available = True
                except Exception as e:
                    print(f"Error checking AI credits: {e}")
                    # If we can't check credits, show error dialog
                    root_parent = main_window or self.parent()
                    credits_dialog = ModernCreditsDialog(
                        root_parent,
                        title="AI Image Credits",
                        message="Unable to check your AI image credits",
                        subtitle="Please try again later"
                    )
                    credits_dialog.exec()
                    return
            else:
                # No main window or auth service available - show credits dialog
                root_parent = main_window or self.parent()
                credits_dialog = ModernCreditsDialog(
                    root_parent,
                    title="AI Image Credits",
                    message="Your AI image credits have run out",
                    subtitle="Upgrade your plan to continue generating AI images"
                )
                credits_dialog.exec()
                return
            
            # Only proceed if credits are available
            if not credits_available:
                return
            
            # Disable create button immediately (only after credit check passes)
            if hasattr(self, 'create_btn'):
                self.create_btn.setEnabled(False)
                self.create_btn.setText("Creating...")
                self.create_btn.setStyleSheet("""
                    QPushButton {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                            stop:0 #4B5563, stop:1 #6B7280);
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-weight: 500;
                    }
                """)
            
            # Guard: if a thread already exists and is running for this prompt, don't decrement credits
            if main_window:
                prompt_key = self.suggestion.get('prompt', self.suggestion.get('title', 'Beautiful landscape'))
                existing_thread = main_window.ai_generation_threads.get(prompt_key) if hasattr(main_window, 'ai_generation_threads') else None
                if existing_thread and existing_thread.isRunning():
                    print(f"🔄 AI generation already running for prompt, skipping credit decrement: {prompt_key}")
                    self.show_ai_generation_loading()
                    return
            
            # Since we already checked credits above, we can proceed directly to generation
            if main_window and hasattr(main_window, 'auth_service') and main_window.auth_service:
                try:
                    # Decrement credits synchronously since we already verified they exist
                    current_user = main_window.auth_service.get_current_user()
                    if current_user and current_user.get("user"):
                        user_id = current_user["user"].id
                        result = main_window.auth_service.decrement_ai_image_count(user_id)
                        
                        if result and result.get("success"):
                            # Credits decremented successfully, proceed to generation
                            self.start_ai_image_generation(main_window)
                        else:
                            # Credit decrement failed, show error and restore button
                            self._on_ai_credit_error(main_window, result.get("message", "Failed to decrement credits"))
                    else:
                        self._on_ai_credit_error(main_window, "User not authenticated")
                except Exception as _e:
                    self._on_ai_credit_error(main_window, str(_e))
            else:
                # Re-enable button if failed
                if hasattr(self, 'create_btn'):
                    self.create_btn.setEnabled(True)
                    self.create_btn.setText("Create")
                # Use modern dialog customized for AI Image credits
                root_parent = self.find_main_window() or self.parent()
                credits_dialog = ModernCreditsDialog(
                    root_parent,
                    title="AI Image Credits",
                    message="Your AI image credits have run out",
                    subtitle="Upgrade your plan to continue generating AI images"
                )
                credits_dialog.exec()
            
        else:
            print(f"⚠️ Create button clicked for non-AI media: {self.media_type}")


    def _on_ai_credit_error(self, main_window, message: str):
        """No credits or error; show popup and restore button."""
        try:
            if hasattr(self, 'create_btn'):
                self.create_btn.setEnabled(True)
                self.create_btn.setText("Create")
                self.create_btn.setStyleSheet("""
                    QPushButton {
                        background: #3B82F6;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-weight: 500;
                    }
                    QPushButton:hover { background: #2563EB; }
                    QPushButton:pressed { background: #1D4ED8; }
                """)
            parent_window = main_window if main_window is not None else self.parent()
            try:
                credits_dialog = ModernCreditsDialog(
                    parent_window,
                    title="AI Image Credits",
                    message="Your AI image credits have run out",
                    subtitle="Upgrade your plan to continue generating AI images"
                )
                credits_dialog.exec()
            except Exception:
                from PyQt6.QtWidgets import QMessageBox
                QMessageBox.warning(parent_window, "AI Image Credits", "Your AI image credits have run out")
        except Exception:
            pass

    def on_download_clicked(self):
        """Download only this card's media item to default directory."""
        try:
            # Guard: For AI Images, require that the image is created
            if self.media_type == 'ai_images' and not self.suggestion.get('ai_generated', False):
                try:
                    from PyQt6.QtWidgets import QMessageBox
                    box = QMessageBox(self)
                    box.setIcon(QMessageBox.Icon.Information)
                    box.setWindowTitle("AI Image")
                    box.setText("Please create the AI image first before downloading it.")
                    box.setStyleSheet(
                        "QMessageBox { background-color: #111111; color: #ffffff; }\n"
                        "QWidget { color: #ffffff; }\n"
                        "QLabel { color: #ffffff; background-color: transparent; border: none; }\n"
                        "QFrame { background-color: transparent; border: none; }\n"
                        "QTextEdit, QTextBrowser { background-color: transparent; color: #ffffff; border: none; }\n"
                        "QPushButton { background: #2b2b2b; color: #ffffff; border: 1px solid #3a3a3a; padding: 6px 12px; border-radius: 6px; }\n"
                        "QPushButton:hover { background: #3a3a3a; }"
                    )
                    box.exec()
                except Exception:
                    pass
                return
            if getattr(self, '_single_download_thread', None) and self._single_download_thread.isRunning():
                return
            # Determine save directory
            main_window = self.find_main_window()
            save_dir = None
            try:
                if main_window and hasattr(main_window, 'settings'):
                    save_dir = main_window.settings.get('default_save_path')
            except Exception:
                save_dir = None
            if not save_dir:
                save_dir = get_default_download_path()
            try:
                os.makedirs(save_dir, exist_ok=True)
            except Exception:
                pass
            # Build single media payload
            media_type_val = 'video' if self.media_type == 'stock_videos' else 'image'
            download_url = self.suggestion.get('download_url') or self.suggestion.get('preview_url') or self.suggestion.get('thumbnail_url')
            if not download_url:
                print("⚠️ No downloadable URL for this item")
                return
            media_item = {
                'download_url': download_url,
                'title': self.suggestion.get('title', 'Untitled'),
                'chapter': self.suggestion.get('chapter', ''),
                'scene': self.suggestion.get('scene', ''),
                'media_type': media_type_val
            }
            # Start download thread
            self.download_btn.setEnabled(False)
            self._show_download_overlay("Preparing download...")
            self._single_download_thread = DownloadThread([media_item], save_dir)
            self._single_download_thread.download_progress.connect(self._on_single_download_progress)
            self._single_download_thread.download_complete.connect(lambda d, f: self._on_single_download_done(d, f))
            self._single_download_thread.download_error.connect(lambda msg: self._on_single_download_error(msg))
            self._single_download_thread.start()
        except Exception as e:
            print(f"❌ Single download error: {e}")

    def _on_single_download_done(self, downloaded: int, failed: int):
        try:
            if hasattr(self, 'download_btn') and self.download_btn:
                self.download_btn.setEnabled(True)
        except Exception:
            pass
        self._hide_download_overlay()
        # Capture downloaded files before clearing the thread reference
        downloaded_files = []
        try:
            if getattr(self, '_single_download_thread', None):
                downloaded_files = getattr(self._single_download_thread, 'downloaded_files', []) or []
        except Exception:
            downloaded_files = []
        self._single_download_thread = None
        if downloaded > 0 and failed == 0:
            print("✅ Item downloaded successfully")
            self._show_temporary_toast("Download completed ✅")
            # Add to Downloads page/history
            try:
                main_window = self.find_main_window()
                if main_window:
                    from datetime import datetime
                    for f in downloaded_files:
                        file_path = f.get('file_path')
                        file_type = 'video' if f.get('media_type') == 'video' else 'image'
                        filename = os.path.basename(file_path) if file_path else ''
                        # Estimate size
                        size_str = ""
                        try:
                            if file_path and os.path.exists(file_path):
                                size_bytes = os.path.getsize(file_path)
                                size_str = f"{size_bytes / (1024*1024):.1f} MB"
                        except Exception:
                            pass
                        # Create DownloadItem and push to downloads page
                        try:
                            item_id = str(uuid.uuid4())
                        except Exception:
                            item_id = filename
                        from datetime import datetime as _dt
                        download_date = _dt.now().strftime("%Y-%m-%d %H:%M")
                        download_item = DownloadItem(
                            id=item_id,
                            filename=filename,
                            file_path=file_path,
                            file_type=file_type,
                            download_date=download_date,
                            file_size=size_str,
                            thumbnail_path=file_path if file_type == 'image' else "",
                            original_url=f.get('original_url', ''),
                            chapter=f.get('chapter', ''),
                            scene=f.get('scene', '')
                        )
                        # Append to UI list
                        if hasattr(main_window, 'downloads_page') and hasattr(main_window.downloads_page, 'download_items'):
                            main_window.downloads_page.download_items.append(download_item)
                            # Refresh the downloads UI if available
                            try:
                                if hasattr(main_window.downloads_page, 'populate_downloads'):
                                    main_window.downloads_page.populate_downloads()
                            except Exception:
                                pass
                        # Append to persisted history model if present
                        if hasattr(main_window, 'downloads_history'):
                            main_window.downloads_history.append(download_item)
                        # Save to file if method exists
                        if hasattr(main_window, 'save_downloads_history_to_file'):
                            main_window.save_downloads_history_to_file()
                        # If video, kick off thumbnail generation for nicer list
                        try:
                            if file_type == 'video' and hasattr(main_window, 'create_video_thumbnail'):
                                thumb = main_window.create_video_thumbnail(file_path)
                                if thumb and hasattr(main_window.downloads_page, 'download_items'):
                                    download_item.thumbnail_path = thumb
                        except Exception:
                            pass
            except Exception as e:
                print(f"⚠️ Could not add single download to history: {e}")
        elif downloaded > 0 and failed > 0:
            print("⚠️ Item downloaded with errors")
            self._show_temporary_toast("Downloaded with errors ⚠️")
        else:
            print("❌ Item download failed")
            self._show_temporary_toast("Download failed ❌")

    def _on_single_download_error(self, message: str):
        try:
            if hasattr(self, 'download_btn') and self.download_btn:
                self.download_btn.setEnabled(True)
        except Exception:
            pass
        self._hide_download_overlay()
        self._single_download_thread = None
        print(f"❌ Item download error: {message}")

    def _on_single_download_progress(self, current: int, total: int):
        try:
            self._show_download_overlay(f"Downloading {current}/{total}...")
        except Exception:
            pass

    def _show_temporary_toast(self, text: str, duration_ms: int = 1800):
        try:
            toast = QLabel(text, self)
            toast.setStyleSheet("background: rgba(17,24,39,0.9); color: white; padding: 8px 12px; border-radius: 10px;")
            toast.setFont(QFont("Arial", 11, QFont.Weight.DemiBold))
            toast.adjustSize()
            # Position center inside the card
            x = (self.width() - toast.width()) // 2
            y = (self.height() - toast.height()) // 2
            toast.move(x, y)
            toast.show()
            toast.raise_()
            QTimer.singleShot(duration_ms, toast.deleteLater)
        except Exception:
            pass
    
    def start_ai_image_generation(self, main_window):
        """Start AI image generation process"""
        try:
            # Get prompt from suggestion
            prompt = self.suggestion.get('prompt', self.suggestion.get('title', 'Beautiful landscape'))
            
            # Register this MediaCard with MainWindow for status tracking
            main_window.register_ai_generation_card(prompt, self)
            
            # Check if generation is already in progress for this prompt
            current_status = main_window.get_ai_generation_status(prompt)
            if current_status == 'creating':
                print(f"🔄 AI image generation already in progress for: {prompt}")
                # Update this card to show loading state
                self.show_ai_generation_loading()
                return
            
            # Update status to creating (persist) and mark in scene data
            main_window.update_ai_generation_status(prompt, 'creating')
            try:
                main_window.mark_ai_image_generating_by_prompt(prompt)
            except Exception:
                pass
            
            # Create and start generation thread (only if not already running for this prompt)
            existing_thread = main_window.ai_generation_threads.get(prompt)
            if existing_thread and existing_thread.isRunning():
                # Already generating; just show loading state
                self.show_ai_generation_loading()
                return

            self.generation_thread = AIImageGenerationThread(
                main_window.leonardo_ai_service,
                prompt,
                "16:9"  # 16:9 aspect ratio for better UI fit
            )
            
            # Connect signals only to MainWindow (to persist across UI rebuilds)
            # Persist in MainWindow
            main_window.ai_generation_threads[prompt] = self.generation_thread
            self.generation_thread.generation_complete.connect(
                lambda url, p=prompt: main_window.update_ai_generation_status(p, 'completed', url)
            )
            self.generation_thread.generation_error.connect(
                lambda err, p=prompt: main_window.update_ai_generation_status(p, 'error')
            )
            # No direct connections to this card; MainWindow will propagate state to live cards
            
            # Show loading state
            self.show_ai_generation_loading()
            
            # Start generation
            self.generation_thread.start()
            
        except Exception as e:
            print(f"❌ Error starting AI image generation: {e}")
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "AI Image Generation",
                "We couldn't start image generation. Please try again."
            )
    
    def show_ai_generation_loading(self):
        """Show loading state for AI image generation"""
        # Update create button to show creating state
        if hasattr(self, 'create_btn'):
            self.create_btn.setText("Creating...")
            self.create_btn.setEnabled(False)
            self.create_btn.setStyleSheet("""
                QPushButton {
                    background: #6B7280;
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-weight: 500;
                }
            """)
    
    def update_created_button_state(self):
        """Ensure the Create button reflects a completed state without triggering downloads.

        Safe to call multiple times and when the card is re-created after navigation.
        """
        try:
            if hasattr(self, 'create_btn'):
                self.create_btn.setText("Created ✅")
                self.create_btn.setEnabled(False)
                self.create_btn.setStyleSheet("""
                    QPushButton {
                        background: #10B981;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-weight: 500;
                    }
                """)
        except Exception:
            pass

    def on_ai_image_generated(self, image_url: str, prompt: str):
        """Handle successful AI image generation"""
        try:
            print(f"✅ AI Image generated successfully: {image_url}")
            
            # Update suggestion with new image URL and generation status
            self.suggestion['download_url'] = image_url
            # Don't override the original title if prompt was used as key
            if 'prompt' not in self.suggestion or not self.suggestion.get('prompt'):
                self.suggestion['title'] = f"AI Generated: {prompt}"
            self.suggestion['ai_generated'] = True  # Flag to indicate this image was generated
            
            # Load the generated image only if we haven't already displayed final image
            if not getattr(self, 'has_final_image', False):
                self.load_generated_ai_image(image_url)
                self.has_final_image = True
            
            # Update create button to show success
            if hasattr(self, 'create_btn'):
                self.create_btn.setText("Created ✅")
                self.create_btn.setStyleSheet("""
                    QPushButton {
                        background: #10B981;
                        color: white;
                        border: none;
                        border-radius: 6px;
                        padding: 6px 12px;
                        font-weight: 500;
                    }
                """)
                # Keep button disabled permanently
                self.create_btn.setEnabled(False)
            
            # Update scene data to persist the generated image
            main_window = self.find_main_window()
            if main_window:
                main_window.update_ai_image_in_scene_data(self.suggestion)
                # Do not call update_ai_generation_status here to avoid re-entrant loops
            
            # Success message removed - no popup shown
            
        except Exception as e:
            print(f"❌ Error handling AI image generation: {e}")
            self.on_ai_image_error(f"Error displaying generated image: {str(e)}")
    
    def load_generated_ai_image(self, image_url: str):
        """Load the generated AI image using requests"""
        try:
            print(f"🎨 Loading AI image from URL: {image_url}")
            import requests
            from PyQt6.QtCore import QThread, pyqtSignal
            
            # Create a thread for downloading
            class ImageDownloadThread(QThread):
                download_complete = pyqtSignal(bytes)
                download_error = pyqtSignal(str)
                
                def __init__(self, url):
                    super().__init__()
                    self.url = url
                
                def run(self):
                    try:
                        print(f"📥 Downloading image from: {self.url}")
                        headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                        }
                        response = requests.get(self.url, timeout=30, headers=headers)
                        
                        if response.status_code == 200:
                            print(f"✅ Image downloaded successfully: {len(response.content)} bytes")
                            self.download_complete.emit(response.content)
                        else:
                            error_msg = f"HTTP {response.status_code}"
                            print(f"❌ Download failed: {error_msg}")
                            self.download_error.emit(error_msg)
                            
                    except Exception as e:
                        print(f"❌ Download error: {e}")
                        self.download_error.emit(str(e))
            
            # If we already have this image cached on disk, load from file instead of network
            try:
                cache_dir = os.path.join(self.get_project_root(), "downloads")
                if not os.path.exists(cache_dir):
                    os.makedirs(cache_dir, exist_ok=True)
                import hashlib
                url_hash = hashlib.md5(image_url.encode()).hexdigest()
                cache_path = os.path.join(cache_dir, f"ai_{url_hash}.jpg")
                print(f"🔍 Checking cache for: {cache_path}")
                if os.path.exists(cache_path):
                    print(f"📁 Found cached image: {cache_path}")
                    pixmap = QPixmap(cache_path)
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(self.thumbnail_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        self.thumbnail_label.setPixmap(scaled_pixmap)
                        self.thumbnail_label.setStyleSheet("")
                        print(f"✅ Loaded AI image from cache: {cache_path}")
                        return
                    else:
                        print(f"❌ Cached image is corrupted, will re-download")
                        os.remove(cache_path)  # Remove corrupted cache
                else:
                    print(f"📁 No cached image found, will download")
            except Exception as e:
                print(f"⚠️ Cache check error: {e}")

            # Start download thread (reuse existing if same URL already downloading)
            try:
                if hasattr(self, 'download_thread') and self.download_thread and self.download_thread.isRunning():
                    if getattr(self.download_thread, 'url', None) == image_url:
                        print("🔄 Reusing in-flight image download thread")
                        return
            except Exception:
                pass

            self.download_thread = ImageDownloadThread(image_url)
            self.download_thread.download_complete.connect(self.handle_downloaded_image_data)
            self.download_thread.download_error.connect(self.on_ai_image_error)
            # Reparent to MainWindow so it isn't destroyed with this card
            try:
                main_window = self.find_main_window()
                if main_window is not None:
                    self.download_thread.setParent(main_window)
            except Exception:
                pass
            # Ensure we drop the reference when finished to avoid dangling threads on widget destruction
            try:
                self.download_thread.finished.connect(lambda: setattr(self, 'download_thread', None))
            except Exception:
                pass
            self.download_thread.start()
            
        except Exception as e:
            print(f"❌ Error starting image download: {e}")
            self.on_ai_image_error(f"Error starting download: {str(e)}")
    
    def handle_downloaded_image_data(self, image_data: bytes):
        """Handle downloaded image data"""
        try:
            print(f"🔍 Processing downloaded image data: {len(image_data)} bytes")
            
            if len(image_data) == 0:
                print(f"❌ Empty image data received")
                self.on_ai_image_error("Empty image data received")
                return
            
            pixmap = QPixmap()
            success = pixmap.loadFromData(image_data)
            print(f"🔍 Pixmap load success: {success}, size: {pixmap.width()}x{pixmap.height()}")
            
            if not pixmap.isNull():
                # Scale and display the image
                scaled_pixmap = pixmap.scaled(
                    self.thumbnail_label.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self.thumbnail_label.setPixmap(scaled_pixmap)
                self.thumbnail_label.setStyleSheet("")
                print(f"✅ Generated AI image displayed successfully")

                # Persist to local cache for instant reuse on future tab switches
                try:
                    cache_dir = os.path.join(self.get_project_root(), "downloads")
                    if not os.path.exists(cache_dir):
                        os.makedirs(cache_dir, exist_ok=True)
                    # Use the URL from the active download thread if available
                    url = getattr(getattr(self, 'download_thread', None), 'url', None)
                    if url:
                        import hashlib
                        url_hash = hashlib.md5(url.encode()).hexdigest()
                        cache_path = os.path.join(cache_dir, f"ai_{url_hash}.jpg")
                        with open(cache_path, 'wb') as f:
                            f.write(image_data)
                        print(f"💾 Cached AI image: {cache_path}")
                    else:
                        print(f"⚠️ No URL available for caching")
                except Exception as e:
                    print(f"⚠️ Could not cache AI image: {e}")
            else:
                print(f"❌ Pixmap is null after loading data")
                self.on_ai_image_error("Failed to load generated image data")
                
        except Exception as e:
            print(f"❌ Error processing downloaded image data: {e}")
            import traceback
            traceback.print_exc()
            self.on_ai_image_error(f"Error processing image: {str(e)}")
    
    def on_ai_image_error(self, error_message: str):
        """Handle AI image generation error"""
        print(f"❌ AI Image generation error: {error_message}")
        
        # Show error placeholder in thumbnail
        try:
            if hasattr(self, 'thumbnail_label'):
                self.thumbnail_label.setText(f"❌ Error\n{error_message[:20]}...")
                self.thumbnail_label.setStyleSheet("""
                    QLabel {
                        background: #FEF2F2;
                        color: #DC2626;
                        border: 2px dashed #FCA5A5;
                        border-radius: 8px;
                        font-size: 10px;
                        text-align: center;
                    }
                """)
        except Exception as e:
            print(f"⚠️ Could not show error placeholder: {e}")
        
        # Just restore the button state
        
        # Re-enable create button on error
        if hasattr(self, 'create_btn'):
            self.create_btn.setEnabled(True)
            self.create_btn.setText("🎨 Create")
            self.create_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5170ff, stop:1 #ff66c4);
                    color: white;
                    border: none;
                    border-radius: 6px;
                    padding: 6px 12px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3B82F6, stop:1 #8B5CF6);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2563EB, stop:1 #7C3AED);
                }
            """)
        
        # Update MainWindow status
        main_window = self.find_main_window()
        if main_window:
            prompt = self.suggestion.get('prompt', self.suggestion.get('title', 'Beautiful landscape'))
            main_window.update_ai_generation_status(prompt, 'error')
        
        # Show error message (guard; UI may be gone)
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "AI Image Generation Error", error_message)
        except Exception:
            pass
    
    def on_ai_image_progress(self, message: str):
        """Handle AI image generation progress (safe if UI disposed)"""
        print(f"🎨 AI Image Generation: {message}")
        label = getattr(self, 'thumbnail_label', None)
        if not label:
            return
        try:
            if "Starting" in message:
                label.setText("🎨 Starting AI Generation...")
            elif "Checking" in message:
                if "elapsed" in message:
                    try:
                        elapsed = message.split("elapsed")[0].split(",")[-1].strip()
                        label.setText(f"🎨 Generating... ({elapsed})")
                    except Exception:
                        label.setText("🎨 Generating AI Image...")
                else:
                    label.setText("🎨 Generating AI Image...")
            elif "completed" in message:
                label.setText("🎨 Generation Complete!")
            elif "timeout" in message:
                label.setText("🎨 Generation Timeout")
            else:
                label.setText(f"🎨 {message}")
        except Exception:
            pass
    

        
    def open_in_browser(self):
        """Open media file in browser"""
        if 'download_url' not in self.suggestion:
            return
        
        import webbrowser
        download_url = self.suggestion['download_url']
        webbrowser.open(download_url)
        print(f"🔗 Opened in browser: {download_url}")
    
    def find_main_window(self):
        """Find the main window instance"""
        parent = self.parent()
        while parent:
            if hasattr(parent, 'auth_service'):
                return parent
            parent = parent.parent()
        return None
    



class SettingsDialog(QDialog):
    """Modern minimalist settings dialog"""
    def __init__(self, parent=None, current_settings=None):
        try:
            super().__init__(parent)
            self.setWindowTitle("Settings")
            self.setFixedSize(600, 650)
            # Use proper window flags for modal dialog without system close button
            self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            # Load current settings
            self.settings = current_settings or {
                'stock_images_count': 3,
                'stock_videos_count': 3,
                'ai_images_count': 3,
                'image_aspect_ratio': 'all',
                'video_aspect_ratio': 'all',
                'default_save_path': get_default_download_path()
            }
            
            print("🔧 SettingsDialog: Initializing UI...")
            self.setup_ui()
            print("🔧 SettingsDialog: Centering dialog...")
            self.center_dialog()
            
            # Add keyboard shortcut for closing dialog
            from PyQt6.QtGui import QKeySequence, QShortcut
            escape_shortcut = QShortcut(QKeySequence("Esc"), self)
            escape_shortcut.activated.connect(self.reject)
            
            print("🔧 SettingsDialog: Initialization complete")
            
        except Exception as e:
            print(f"❌ Error initializing SettingsDialog: {e}")
            raise
    
    def center_dialog(self):
        """Center the dialog on the parent window"""
        if self.parent():
            parent_rect = self.parent().geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            self.move(x, y)
    
    def setup_ui(self):
        """Setup modern UI"""
        try:
            print("🔧 SettingsDialog: Setting up layout...")
            layout = QVBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            self.setLayout(layout)
        except Exception as e:
            print(f"❌ Error setting up SettingsDialog UI: {e}")
            raise
        
        # Main container
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 20px;
                border: 2px solid #E5E7EB;
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(32, 24, 32, 24)
        container_layout.setSpacing(24)
        container.setLayout(container_layout)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # Settings icon
        icon_label = QLabel("⚙️")
        icon_label.setFont(QFont("Arial", 20))
        icon_label.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
        header_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Settings")
        title_label.setFont(QFont("Poppins", 24, QFont.Weight.DemiBold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                border: none;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Close button
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(28, 28)
        close_btn.setStyleSheet("""
            QPushButton {
                background: #F3F4F6;
                color: #6B7280;
                border: none;
                border-radius: 14px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #EF4444;
                color: white;
                border: none;
            }
        """)
        close_btn.clicked.connect(self.reject)
        close_btn.setToolTip("Close Settings")
        header_layout.addWidget(close_btn)
        
        container_layout.addLayout(header_layout)
        
        # Content Count Settings
        content_section = QWidget()
        content_section.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border-radius: 12px;
                border: 1px solid #E5E7EB;
            }
        """)
        
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(20, 16, 20, 16)
        content_layout.setSpacing(16)
        content_section.setLayout(content_layout)
        
        # Section title
        content_title = QLabel("Content Count")
        content_title.setFont(QFont("Poppins", 16, QFont.Weight.DemiBold))
        content_title.setStyleSheet("""
            QLabel {
                color: #1F2937;
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                border: none;
            }
        """)
        content_layout.addWidget(content_title)
        
        # Content count controls
        count_controls_layout = QHBoxLayout()
        count_controls_layout.setSpacing(20)
        
        # Stock Images
        stock_images_container = self.create_count_control("Stock Images", "stock_images_count")
        count_controls_layout.addWidget(stock_images_container)
        
        # Stock Videos
        stock_videos_container = self.create_count_control("Stock Videos", "stock_videos_count")
        count_controls_layout.addWidget(stock_videos_container)
        
        # AI Images
        ai_images_container = self.create_count_control("AI Images", "ai_images_count")
        count_controls_layout.addWidget(ai_images_container)
        
        content_layout.addLayout(count_controls_layout)
        container_layout.addWidget(content_section)
        
        # Highlight Color Settings
        highlight_section = QWidget()
        highlight_section.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border-radius: 12px;
                border: 1px solid #E5E7EB;
            }
        """)
        
        highlight_layout = QVBoxLayout()
        highlight_layout.setContentsMargins(20, 16, 20, 16)
        highlight_layout.setSpacing(16)
        highlight_section.setLayout(highlight_layout)
        
        # Section title
        highlight_title = QLabel("Highlight Color")
        highlight_title.setFont(QFont("Poppins", 16, QFont.Weight.DemiBold))
        highlight_title.setStyleSheet("""
            QLabel {
                color: #1F2937;
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                border: none;
            }
        """)
        highlight_layout.addWidget(highlight_title)
        
        # Highlight color controls
        highlight_controls_layout = QHBoxLayout()
        highlight_controls_layout.setSpacing(20)
        
        # Color options
        self.highlight_colors = {
            "Blue": "#3B82F6",
            "Green": "#10B981", 
            "Purple": "#8B5CF6",
            "Red": "#EF4444",
            "Orange": "#F59E0B",
            "Pink": "#EC4899"
        }
        
        self.selected_highlight_color = self.settings.get('highlight_color', 'Blue')
        self.highlight_buttons = {}
        
        for color_name, color_code in self.highlight_colors.items():
            color_btn = QPushButton()
            color_btn.setFixedSize(50, 50)
            color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            
            # Style the color button
            is_selected = color_name == self.selected_highlight_color
            border_style = "border: 3px solid #1F2937;" if is_selected else "border: 2px solid #E5E7EB;"
            
            color_btn.setStyleSheet(f"""
                QPushButton {{
                    background: {color_code};
                    {border_style}
                    border-radius: 25px;
                }}
                QPushButton:hover {{
                    border: 3px solid #6B7280;
                }}
            """)
            
            color_btn.clicked.connect(lambda checked, name=color_name: self.select_highlight_color(name))
            self.highlight_buttons[color_name] = color_btn
            highlight_controls_layout.addWidget(color_btn)
        
        # Remove the color name label - no longer needed
        highlight_controls_layout.addStretch()
        highlight_layout.addLayout(highlight_controls_layout)
        container_layout.addWidget(highlight_section)
        
        # Save Path Settings
        path_section = QWidget()
        path_section.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border-radius: 12px;
                border: 1px solid #E5E7EB;
            }
        """)
        
        path_layout = QVBoxLayout()
        path_layout.setContentsMargins(20, 16, 20, 16)
        path_layout.setSpacing(16)
        path_section.setLayout(path_layout)
        
        # Section title
        path_title = QLabel("Save Path Settings")
        path_title.setFont(QFont("Poppins", 16, QFont.Weight.DemiBold))
        path_title.setStyleSheet("""
            QLabel {
                color: #1F2937;
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                border: none;
            }
        """)
        path_layout.addWidget(path_title)
        
        # Save path control
        path_control_layout = QVBoxLayout()
        path_control_layout.setSpacing(8)
        
        # Label
        path_label = QLabel("Default Save Location:")
        path_label.setFont(QFont("Inter", 12, QFont.Weight.Normal))
        path_label.setStyleSheet("""
            QLabel {
                color: #374151;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                border: none;
            }
        """)
        path_control_layout.addWidget(path_label)
        
        # Path input and browse button
        path_input_layout = QHBoxLayout()
        path_input_layout.setSpacing(12)
        
        # Path input
        self.path_input = QLineEdit()
        self.path_input.setText(self.settings.get('default_save_path', get_default_download_path()))
        self.path_input.setStyleSheet("""
            QLineEdit {
                background: white;
                border: none;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                color: #1F2937;
                font-family: 'Inter', 'Arial', sans-serif;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: none;
                outline: none;
            }
            QLineEdit:hover {
                border: none;
            }
        """)
        path_input_layout.addWidget(self.path_input, 1)
        
        # Browse button
        browse_btn = QPushButton("📁 Browse")
        browse_btn.setFixedSize(100, 40)
        browse_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 600;
                font-size: 13px;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #2563EB;
                border: none;
            }
            QPushButton:pressed {
                background: #1D4ED8;
                border: none;
            }
        """)
        browse_btn.clicked.connect(self.browse_save_path)
        path_input_layout.addWidget(browse_btn)
        
        path_control_layout.addLayout(path_input_layout)
        
        path_layout.addLayout(path_control_layout)
        container_layout.addWidget(path_section)
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(100, 40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F3F4F6;
                color: #374151;
                border: none;
                border-radius: 10px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #E5E7EB;
                border: none;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.setFixedSize(120, 40)
        save_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #2563EB;
                border: none;
            }
        """)
        save_btn.clicked.connect(self.save_settings)
        button_layout.addWidget(save_btn)
        
        container_layout.addLayout(button_layout)
        layout.addWidget(container)
    
    def select_highlight_color(self, color_name: str):
        """Handle highlight color selection"""
        self.selected_highlight_color = color_name
        
        # Update button styles
        for name, button in self.highlight_buttons.items():
            color_code = self.highlight_colors[name]
            is_selected = name == color_name
            border_style = "border: 3px solid #1F2937;" if is_selected else "border: 2px solid #E5E7EB;"
            
            button.setStyleSheet(f"""
                QPushButton {{
                    background: {color_code};
                    {border_style}
                    border-radius: 25px;
                }}
                QPushButton:hover {{
                    border: 3px solid #6B7280;
                }}
            """)
    
    def create_count_control(self, label_text: str, setting_key: str) -> QWidget:
        """Create a modern count control widget"""
        container = QWidget()
        container.setFixedWidth(150)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        container.setLayout(layout)
        
        # Label
        label = QLabel(label_text)
        label.setFont(QFont("Inter", 12, QFont.Weight.Normal))
        label.setStyleSheet("""
            QLabel {
                color: #374151;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                border: none;
            }
        """)
        layout.addWidget(label)
        
        # Combo box for count selection
        combo = QComboBox()
        combo.addItems(["0", "1", "2", "3"])
        combo.setCurrentText(str(self.settings.get(setting_key, 3)))
        combo.setStyleSheet("""
            QComboBox {
                background: white;
                border: 0px;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                font-weight: 600;
                color: #1F2937;
                font-family: 'Inter', 'Arial', sans-serif;
                min-height: 20px;
            }
            QComboBox:focus {
                border: 0px;
                outline: none;
            }
            QComboBox:hover {
                border: 0px;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 0px;
                border-left: none;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
                background: transparent;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
            }
            QComboBox QAbstractItemView {
                border: 0px;
                border-radius: 8px;
                background: white;
                color: #1F2937;
                selection-background-color: #EBF8FF;
                selection-color: #1F2937;
            }
        """)
        setattr(self, f"{setting_key}_combo", combo)
        layout.addWidget(combo)
        
        return container
    

    def get_settings(self):
        """Get current settings from UI controls"""
        try:
            return {
                'stock_images_count': int(self.stock_images_count_combo.currentText()),
                'stock_videos_count': int(self.stock_videos_count_combo.currentText()),
                'ai_images_count': int(self.ai_images_count_combo.currentText()),
                'highlight_color': self.selected_highlight_color,
                'default_save_path': self.path_input.text()
            }
        except Exception as e:
            print(f"Get settings error: {e}")
            return self.settings
    

    def browse_save_path(self):
        """Browse for save path"""
        from PyQt6.QtWidgets import QFileDialog
        folder_path = QFileDialog.getExistingDirectory(
            self, 
            "Select Default Save Folder",
            self.path_input.text()
        )
        if folder_path:
            self.path_input.setText(folder_path)
    
    def save_settings(self):
        """Save settings and close dialog"""
        try:
            # Update settings with current values
            self.settings.update({
                'stock_images_count': int(self.stock_images_count_combo.currentText()),
                'stock_videos_count': int(self.stock_videos_count_combo.currentText()),
                'ai_images_count': int(self.ai_images_count_combo.currentText()),
                'highlight_color': self.selected_highlight_color,
                'default_save_path': self.path_input.text()
            })
            print(f"✅ Settings saved in dialog: {self.settings}")
            self.accept()  # Close dialog with Accepted result
        except Exception as e:
            print(f"❌ Settings save error: {e}")
            QMessageBox.warning(
                self,
                "Settings",
                "We couldn't save your settings. Please try again."
            )
    
    def closeEvent(self, event):
        """Handle close event to ensure proper cleanup"""
        try:
            print("🔧 SettingsDialog: Close event triggered")
            self.reject()  # Ensure dialog closes properly
            event.accept()
        except Exception as e:
            print(f"❌ Error in settings dialog close event: {e}")
            event.accept()
    
    # Removed duplicate get_settings method - the first one reads from UI controls


class VideoQualityDialog(QDialog):
    """Video quality analysis dialog"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Video Quality Analysis")
        self.setFixedSize(800, 600)
        self.setModal(True)
        
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("📊 Video Quality Analysis")
        title_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #111827;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)
        
        layout.addStretch()
        
        # Upload button
        upload_button = ModernButton("📤 Select Video File", "primary")
        upload_button.setFixedSize(200, 50)
        upload_button.clicked.connect(self.select_video_file)
        layout.addWidget(upload_button, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addStretch()
        
        self.setLayout(layout)
        self.setStyleSheet("background: #F9FAFB;")
        
    def select_video_file(self):
        """Select video file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv);;All Files (*)"
        )
        
        if file_path:
            QMessageBox.information(self, "Success", f"Selected: {os.path.basename(file_path)}")


class HistoryItem:
    """Represents a single history item"""
    def __init__(self, id: str, title: str, content_type: str, output_count: int, 
                 date: str, status: str = "completed", file_path: str = "", original_text: str = ""):
        self.id = id
        self.title = title
        self.content_type = content_type  # "AI Images", "Stock Video", "Stock Images"
        self.output_count = output_count
        self.date = date
        self.status = status  # "completed", "pending", "failed"
        self.file_path = file_path
        self.original_text = original_text
class HistoryCard(QFrame):
    """Modern history card widget"""
    re_analyze_clicked = pyqtSignal(str)
    show_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    
    def __init__(self, history_item: HistoryItem):
        super().__init__()
        self.history_item = history_item
        self.setup_ui()
        self.setup_style()
    
    def setup_ui(self):
        """Setup the card UI"""
        self.setFixedSize(400, 180)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        self.setLayout(layout)
        
        # Header row with title and status
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        
        # Title and icon
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        
        # Icon based on content type
        icon_map = {
            "AI Images": "🎨",
            "Stock Video": "🎬", 
            "Stock Images": "🖼️"
        }
        icon = QLabel(icon_map.get(self.history_item.content_type, "📄"))
        icon.setFont(QFont("Arial", 16))
        icon.setStyleSheet("background: transparent;")
        title_layout.addWidget(icon)
        
        # Title
        title_label = QLabel(self.history_item.title)
        title_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #1F2937; background: transparent;")
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        
        header_layout.addLayout(title_layout)
        
        # Status badge
        status_badge = self.create_status_badge()
        header_layout.addWidget(status_badge)
        
        layout.addLayout(header_layout)
        
        # Content details
        details_layout = QVBoxLayout()
        details_layout.setSpacing(8)
        
        # Type and results
        type_results_layout = QHBoxLayout()
        type_results_layout.setSpacing(20)
        
        # Type
        type_label = QLabel(f"Type: {self.history_item.content_type}")
        type_label.setFont(QFont("Arial", 12))
        type_label.setStyleSheet("color: #6B7280; background: transparent;")
        type_results_layout.addWidget(type_label)
        
        # Results
        results_label = QLabel(f"Results: {self.history_item.output_count} items")
        results_label.setFont(QFont("Arial", 12))
        results_label.setStyleSheet("color: #6B7280; background: transparent;")
        type_results_layout.addWidget(results_label)
        type_results_layout.addStretch()
        
        details_layout.addLayout(type_results_layout)
        
        # Date
        date_label = QLabel(f"Date: {self.history_item.date}")
        date_label.setFont(QFont("Arial", 12))
        date_label.setStyleSheet("color: #6B7280; background: transparent;")
        details_layout.addWidget(date_label)
        
        layout.addLayout(details_layout)
        layout.addStretch()
        
        # Action buttons
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)
        buttons_layout.addStretch()
        

        
        # Show button
        show_btn = QPushButton("Show")
        # Use Poppins Medium for buttons
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            show_btn.setFont(QFont("Poppins", 11, QFont.Weight.Medium))
        else:
            show_btn.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        show_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        show_btn.setFixedSize(80, 32)
        show_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #2563EB;
            }
            QPushButton:pressed {
                background: #1D4ED8;
            }
        """)
        show_btn.clicked.connect(lambda: self._on_show_clicked())
        buttons_layout.addWidget(show_btn)
        
        # Re-analyze button
        re_analyze_btn = QPushButton("Re-Analyze")
        # Use Poppins Medium for buttons
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            re_analyze_btn.setFont(QFont("Poppins", 11, QFont.Weight.Medium))
        else:
            re_analyze_btn.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        re_analyze_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        re_analyze_btn.setFixedSize(110, 32)
        re_analyze_btn.setStyleSheet("""
            QPushButton {
                background: #10B981;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #059669;
            }
            QPushButton:pressed {
                background: #047857;
            }
        """)
        re_analyze_btn.clicked.connect(lambda: self._on_re_analyze_clicked())
        buttons_layout.addWidget(re_analyze_btn)
        
        # Delete button
        delete_btn = QPushButton("Delete")
        # Use Poppins Medium for buttons
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            delete_btn.setFont(QFont("Poppins", 11, QFont.Weight.Medium))
        else:
            delete_btn.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        delete_btn.setFixedSize(70, 32)
        delete_btn.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #DC2626;
            }
            QPushButton:pressed {
                background: #B91C1C;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.history_item.id))
        buttons_layout.addWidget(delete_btn)
        
        layout.addLayout(buttons_layout)
    
    def _on_re_analyze_clicked(self):
        """Handle re-analyze button click with debug"""
        print(f"HistoryCard._on_re_analyze_clicked called for item: {self.history_item.id}")
        self.re_analyze_clicked.emit(self.history_item.id)
    
    def _on_show_clicked(self):
        """Handle show button click"""
        print(f"HistoryCard._on_show_clicked called for item: {self.history_item.id}")
        self.show_clicked.emit(self.history_item.id)
    
    def create_status_badge(self) -> QLabel:
        """Create status badge based on item status"""
        status_config = {
            "completed": {"text": "✅ Completed", "color": "#10B981", "bg": "#D1FAE5"},
            "pending": {"text": "🕑 Pending", "color": "#F59E0B", "bg": "#FEF3C7"},
            "failed": {"text": "❌ Failed", "color": "#EF4444", "bg": "#FEE2E2"}
        }
        
        config = status_config.get(self.history_item.status, status_config["completed"])
        
        badge = QLabel(config["text"])
        badge.setFont(QFont("Arial", 10, QFont.Weight.Medium))
        badge.setStyleSheet(f"""
            QLabel {{
                background: {config["bg"]};
                color: {config["color"]};
                border-radius: 12px;
                padding: 4px 8px;
                border: 1px solid {config["color"]}20;
            }}
        """)
        return badge
    
    def find_main_window(self):
        """Find MainWindow in widget hierarchy"""
        current = self.parent()
        while current:
            if hasattr(current, 're_analyze_from_history'):
                return current
            current = current.parent()
        return None
    
    def setup_style(self):
        """Setup card styling"""
        self.setStyleSheet("""
            HistoryCard {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                /* box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1); */
            }
            HistoryCard:hover {
                border-color: #3B82F6;
                /* box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15); */
            }
        """)

class DownloadItem:
    """Download item data class"""
    def __init__(self, id: str, filename: str, file_path: str, file_type: str, 
                 download_date: str, file_size: str = "", thumbnail_path: str = "", 
                 original_url: str = "", chapter: str = "", scene: str = ""):
        self.id = id
        self.filename = filename
        self.file_path = file_path
        self.file_type = file_type  # "image" or "video"
        self.download_date = download_date
        self.file_size = file_size
        self.thumbnail_path = thumbnail_path
        self.original_url = original_url
        self.chapter = chapter
        self.scene = scene

class ThumbnailGeneratorThread(QThread):
    """Thread for generating video thumbnails asynchronously"""
    thumbnail_created = pyqtSignal(str, str)  # file_path, thumbnail_path
    
    def __init__(self, video_path: str):
        super().__init__()
        self.video_path = video_path
    
    def run(self):
        """Generate thumbnail for video file"""
        try:
            # Create thumbnails directory if it doesn't exist
            thumbnails_dir = os.path.join(self.get_project_root(), "thumbnails")
            if not os.path.exists(thumbnails_dir):
                os.makedirs(thumbnails_dir)
            
            # Generate unique thumbnail filename using file path hash
            import hashlib
            video_hash = hashlib.md5(self.video_path.encode()).hexdigest()[:8]
            video_name = os.path.splitext(os.path.basename(self.video_path))[0]
            thumbnail_path = os.path.join(thumbnails_dir, f"{video_name}_{video_hash}_thumb.jpg")
            
            # Check if thumbnail already exists
            if os.path.exists(thumbnail_path):
                self.thumbnail_created.emit(self.video_path, thumbnail_path)
                return
            
            # Use ffmpeg to extract thumbnail
            import subprocess
            cmd = [
                'ffmpeg', '-i', self.video_path, 
                '-ss', '00:00:01',  # Extract frame at 1 second
                '-vframes', '1',    # Extract only 1 frame
                '-vf', 'scale=640:360',  # Scale to 640x360 (HD quality)
                '-q:v', '2',  # High quality JPEG
                '-y',  # Overwrite output file
                thumbnail_path
            ]
            
            # Suppress flashing console window on Windows
            import sys
            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                try:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags = subprocess.CREATE_NO_WINDOW
                except Exception:
                    startupinfo = None
                    creationflags = 0

            result = run_hidden(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            if result.returncode == 0 and os.path.exists(thumbnail_path):
                print(f"✅ Video thumbnail created asynchronously: {thumbnail_path}")
                self.thumbnail_created.emit(self.video_path, thumbnail_path)
            else:
                print(f"❌ Failed to create video thumbnail: {result.stderr}")
                self.thumbnail_created.emit(self.video_path, "")
                
        except Exception as e:
            print(f"❌ Error creating video thumbnail: {e}")
            self.thumbnail_created.emit(self.video_path, "")


class DownloadListItem(QFrame):
    """Modern download list item widget"""
    open_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    
    def __init__(self, download_item: DownloadItem):
        super().__init__()
        self.download_item = download_item
        self.setup_ui()
        
    def setup_ui(self):
        """Setup download list item UI"""
        self.setFixedHeight(80)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            QFrame:hover {
                border-color: #3B82F6;
                /* box-shadow: 0 2px 8px rgba(59, 130, 246, 0.1); */
            }
        """)
        
        layout = QHBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Center vertically
        self.setLayout(layout)
        
        # Set fixed height to prevent layout issues
        self.setFixedHeight(80)
        
        # Thumbnail container - smaller and centered
        thumbnail_container = QWidget()
        thumbnail_container.setFixedSize(84, 84)  # Larger size for better quality
        thumbnail_container.setStyleSheet("""
            QWidget {
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)
        
        # Thumbnail image - properly positioned in smaller container with clipping
        self.thumbnail_label = QLabel(thumbnail_container)
        self.thumbnail_label.setGeometry(2, 2, 80, 80)  # 2px margin on all sides
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                border-radius: 8px;
            }
        """)
        # Enable clipping to keep image within rounded bounds
        self.thumbnail_label.setScaledContents(False)
        # Set mask for rounded clipping
        from PyQt6.QtGui import QPainterPath, QRegion
        path = QPainterPath()
        path.addRoundedRect(0, 0, 80, 80, 8, 8)
        self.thumbnail_label.setMask(QRegion(path.toFillPolygon().toPolygon()))
        
        # Thumbnail container is properly positioned
        
        # Zoom button - positioned absolutely in top-right, circular
        self.zoom_button = QPushButton("🔍", thumbnail_container)
        self.zoom_button.setGeometry(36, 0, 20, 20)  # Top-right corner of smaller container
        self.zoom_button.raise_()  # Bring to front
        # Use Poppins Medium for zoom button
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            self.zoom_button.setFont(QFont("Poppins", 8, QFont.Weight.Medium))  # Smaller font
        else:
            self.zoom_button.setFont(QFont("Arial", 8, QFont.Weight.Medium))  # Smaller font
        self.zoom_button.setStyleSheet("""
            QPushButton {
                background: rgba(59, 130, 246, 0.9);
                color: white;
                border: none;
                border-radius: 10px;  /* Perfect circle */
                font-size: 8px;
                font-weight: bold;
                font-family: 'Poppins', 'Arial', sans-serif;
                min-width: 20px;
                max-width: 20px;
                min-height: 20px;
                max-height: 20px;
            }
            QPushButton:hover {
                background: rgba(59, 130, 246, 1.0);
            }
        """)
        self.zoom_button.clicked.connect(self.zoom_image)
        
        # Load thumbnail
        self.load_thumbnail()
        layout.addWidget(thumbnail_container)
        
        # File info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)  # Center vertically
        
        # Check if file exists
        file_exists = os.path.exists(self.download_item.file_path)
        
        # Filename (cleaned from source information)
        cleaned_filename = self.clean_filename(self.download_item.filename)
        filename_label = QLabel(cleaned_filename)
        filename_label.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        
        # Style based on file existence
        if file_exists:
            filename_label.setStyleSheet("color: #111827; background: transparent; border: none; outline: none;")
        else:
            filename_label.setStyleSheet("color: #9CA3AF; background: transparent; border: none; outline: none; text-decoration: line-through;")
        
        filename_label.setWordWrap(True)
        info_layout.addWidget(filename_label)
        
        # File details
        details_layout = QHBoxLayout()
        details_layout.setSpacing(12)
        
        # File type badge with AI Image support (detect via original_url domain or explicit markers)
        original_url_lc = (self.download_item.original_url or "").lower()
        is_ai_image = (
            self.download_item.file_type == "image" and (
                "leonardo.ai" in original_url_lc or "cdn.leonardo.ai" in original_url_lc or
                any(keyword in self.download_item.filename.lower() for keyword in ["ai_generated", "ai image"])
            )
        )

        if is_ai_image:
            badge_text = "AI IMAGE"
            badge_color = "#8B5CF6"  # Purple for AI Images
        else:
            badge_text = self.download_item.file_type.upper()
            badge_color = "#3B82F6"  # Blue for regular images/videos
        
        type_badge = QLabel(badge_text)
        type_badge.setFont(QFont("Arial", 9, QFont.Weight.Bold))
        type_badge.setStyleSheet(f"""
            QLabel {{
                background: {badge_color};
                color: white;
                border-radius: 4px;
                padding: 2px 6px;
            }}
        """)
        details_layout.addWidget(type_badge)
        
        # File size
        if self.download_item.file_size:
            size_label = QLabel(self.download_item.file_size)
            size_label.setFont(QFont("Arial", 11))
            size_label.setStyleSheet("color: #6B7280; background: transparent; border: none; outline: none;")
            details_layout.addWidget(size_label)
        
        # Download date
        date_label = QLabel(self.download_item.download_date)
        date_label.setFont(QFont("Arial", 11))
        date_label.setStyleSheet("color: #6B7280; background: transparent; border: none; outline: none;")
        details_layout.addWidget(date_label)
        
        details_layout.addStretch()
        info_layout.addLayout(details_layout)
        layout.addLayout(info_layout)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # Open button
        open_btn = QPushButton("Open")
        # Use Poppins Medium for buttons
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            open_btn.setFont(QFont("Poppins", 11, QFont.Weight.Medium))
        else:
            open_btn.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        open_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #2563EB;
            }
        """)
        open_btn.clicked.connect(lambda: self.open_clicked.emit(self.download_item.file_path))
        button_layout.addWidget(open_btn)
        
        # Delete button
        delete_btn = QPushButton("Delete")
        # Use Poppins Medium for buttons
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            delete_btn.setFont(QFont("Poppins", 11, QFont.Weight.Medium))
        else:
            delete_btn.setFont(QFont("Arial", 11, QFont.Weight.Medium))
        delete_btn.setFixedSize(60, 36)
        delete_btn.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #DC2626;
            }
        """)
        delete_btn.clicked.connect(lambda: self.delete_clicked.emit(self.download_item.id))
        button_layout.addWidget(delete_btn)
        
        layout.addLayout(button_layout)
        
    def start_async_thumbnail_generation(self):
        """Start asynchronous thumbnail generation for video files"""
        if self.download_item.file_type == "video":
            self.thumbnail_thread = ThumbnailGeneratorThread(self.download_item.file_path)
            self.thumbnail_thread.thumbnail_created.connect(self.on_thumbnail_created)
            self.thumbnail_thread.start()
    
    def on_thumbnail_created(self, file_path: str, thumbnail_path: str):
        """Handle thumbnail creation completion"""
        if file_path == self.download_item.file_path and thumbnail_path:
            # Update the download item's thumbnail path
            self.download_item.thumbnail_path = thumbnail_path
            
            # Load the newly created thumbnail
            try:
                pixmap = QPixmap(thumbnail_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    self.thumbnail_label.setPixmap(scaled_pixmap)
                    self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    print(f"✅ Async thumbnail loaded: {thumbnail_path}")
                else:
                    print(f"❌ Failed to load async thumbnail: {thumbnail_path}")
            except Exception as e:
                print(f"❌ Error loading async thumbnail: {e}")
        
    def load_thumbnail(self):
        """Load thumbnail for the download item"""
        # Check if this is an AI Image (check filename for AI indicators)
        is_ai_image = any(keyword in self.download_item.filename.lower() for keyword in ['ai', 'leonardo', 'generated'])
        
        # For AI Images, try to load from the actual file path first
        if is_ai_image and self.download_item.file_path:
            try:
                if os.path.exists(self.download_item.file_path):
                    print(f"🎨 Loading AI image thumbnail from: {self.download_item.file_path}")
                    pixmap = QPixmap(self.download_item.file_path)
                    if not pixmap.isNull():
                        # Scale to fit within the 80x80 container while maintaining aspect ratio
                        scaled_pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                        # Set pixmap directly instead of using QTimer
                        self.thumbnail_label.setPixmap(scaled_pixmap)
                        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        # AI image thumbnail loaded successfully
                        return
                    else:
                        print(f"❌ Failed to load AI image thumbnail: pixmap is null")
                else:
                    print(f"❌ AI image file not found: {self.download_item.file_path}")
            except Exception as e:
                print(f"❌ Error loading AI image thumbnail from file path: {e}")
        
        # Try thumbnail_path if available
        if self.download_item.thumbnail_path and os.path.exists(self.download_item.thumbnail_path):
            try:
                # Load actual thumbnail with absolute path
                absolute_path = os.path.abspath(self.download_item.thumbnail_path)
                pixmap = QPixmap(absolute_path)
                
                if not pixmap.isNull():
                    # Scale to fit within the 80x80 container while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                    # Set the pixmap directly
                    self.thumbnail_label.setPixmap(scaled_pixmap)
                    self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    # Thumbnail loaded successfully
                    return
                else:
                    # Try alternative loading method
                    pixmap = QPixmap()
                    if pixmap.load(absolute_path):
                        scaled_pixmap = pixmap.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                        self.thumbnail_label.setPixmap(scaled_pixmap)
                        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                        print(f"✅ Thumbnail loaded with alternative method: {absolute_path}")
                        return
                    else:
                        print(f"❌ Failed to load thumbnail: {absolute_path}")
            except Exception as e:
                print(f"❌ Error loading thumbnail: {e}")
        else:
            print(f"❌ Thumbnail path not found or doesn't exist: {self.download_item.thumbnail_path}")
        
        # For video files without thumbnail, start async generation
        if self.download_item.file_type == "video" and not self.download_item.thumbnail_path:
            self.start_async_thumbnail_generation()
        
        # Fallback to placeholder if image loading fails
        
        # Create placeholder based on file type and AI status
        if self.download_item.file_type == "image":
            if is_ai_image:
                # AI Image placeholder
                self.thumbnail_label.setText("🎨")
                self.thumbnail_label.setFont(QFont("Arial", 24))
                self.thumbnail_label.setStyleSheet("""
                    QLabel {
                        background: transparent;
                        color: #8B5CF6;
                        border: none;
                        border-radius: 8px;
                    }
                """)
            else:
                # Regular image placeholder
                self.thumbnail_label.setText("🖼️")
                self.thumbnail_label.setFont(QFont("Arial", 24))
                self.thumbnail_label.setStyleSheet("""
                    QLabel {
                        background: transparent;
                        color: #3B82F6;
                        border: none;
                        border-radius: 8px;
                    }
                """)
        else:  # video
            self.thumbnail_label.setText("🎬")
            self.thumbnail_label.setFont(QFont("Arial", 24))
            self.thumbnail_label.setStyleSheet("""
                QLabel {
                    background: transparent;
                    color: #F59E0B;
                    border: none;
                    border-radius: 8px;
                }
            """)
    
    def clean_filename(self, filename: str) -> str:
        """Clean filename by removing source information like pexels, unsplash, etc."""
        # Remove common source suffixes and prefixes
        sources_to_remove = [
            '_pexels', 'pexels_', '_unsplash', 'unsplash_', 
            '_pixabay', 'pixabay_', '_shutterstock', 'shutterstock_',
            '_istock', 'istock_', '_adobe', 'adobe_', '_getty', 'getty_'
        ]
        
        cleaned = filename
        for source in sources_to_remove:
            cleaned = cleaned.replace(source, '')
        
        # Remove file extension for display
        if '.' in cleaned:
            cleaned = cleaned.rsplit('.', 1)[0]
        
        # Clean up any remaining underscores and make it more readable
        cleaned = cleaned.replace('_', ' ').strip()
        
        # Capitalize first letter of each word
        cleaned = ' '.join(word.capitalize() for word in cleaned.split())
        
        return cleaned
    
    def find_main_window(self):
        """Find MainWindow in widget hierarchy"""
        current = self.parent()
        while current:
            if hasattr(current, 're_analyze_from_history'):
                return current
            current = current.parent()
        return None
    
    def zoom_image(self):
        """Zoom the image with soft animation"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
        
        # Create zoom dialog
        zoom_dialog = QDialog(self)
        zoom_dialog.setWindowTitle(f"Zoom - {self.download_item.filename}")
        zoom_dialog.setModal(True)
        zoom_dialog.setMinimumSize(600, 400)
        
        # Setup dialog layout
        dialog_layout = QVBoxLayout()
        zoom_dialog.setLayout(dialog_layout)
        
        # Image display area
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setStyleSheet("""
            QLabel {
                background: #F8FAFC;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)
        
        # Load and display the image
        if self.download_item.thumbnail_path and os.path.exists(self.download_item.thumbnail_path):
            try:
                pixmap = QPixmap(self.download_item.thumbnail_path)
                if not pixmap.isNull():
                    # Scale to fit dialog while maintaining aspect ratio
                    scaled_pixmap = pixmap.scaled(550, 350, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    image_label.setPixmap(scaled_pixmap)
                    print(f"Zoom dialog: Image loaded {scaled_pixmap.width()}x{scaled_pixmap.height()}")
                else:
                    image_label.setText("❌ Resim yüklenemedi")
                    image_label.setStyleSheet("color: #EF4444; font-size: 16px;")
            except Exception as e:
                image_label.setText(f"❌ Hata: {str(e)}")
                image_label.setStyleSheet("color: #EF4444; font-size: 16px;")
        else:
            # Show placeholder for videos or missing images
            if self.download_item.file_type == "image":
                image_label.setText("🖼️")
                image_label.setStyleSheet("""
                    QLabel {
                        background: #F0F9FF;
                        color: #3B82F6;
                        border: 1px solid #E5E7EB;
                        border-radius: 8px;
                        font-size: 48px;
                    }
                """)
            else:
                image_label.setText("🎬")
                image_label.setStyleSheet("""
                    QLabel {
                        background: #FEF3C7;
                        color: #F59E0B;
                        border: 1px solid #E5E7EB;
                        border-radius: 8px;
                        font-size: 48px;
                    }
                """)
        
        dialog_layout.addWidget(image_label)
        
        # File info
        info_label = QLabel(f"📁 {self.download_item.filename}\n📊 {self.download_item.file_size} • 📅 {self.download_item.download_date}")
        info_label.setStyleSheet("color: #6B7280; font-size: 12px; margin: 8px;")
        info_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        dialog_layout.addWidget(info_label)
        
        # Close button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Kapat")
        close_button.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: #2563EB;
            }
        """)
        close_button.clicked.connect(zoom_dialog.accept)
        button_layout.addWidget(close_button)
        
        dialog_layout.addLayout(button_layout)
        
        # Show dialog
        zoom_dialog.exec()
class DownloadsPage(QWidget):
    """Modern downloads page widget"""
    open_file_clicked = pyqtSignal(str)
    delete_file_clicked = pyqtSignal(str)
    
    def __init__(self, parent=None, download_items=None):
        super().__init__(parent)
        self.download_items = download_items or []
        self.setup_ui()
        
    def setup_ui(self):
        """Setup downloads page UI"""
        self.setStyleSheet("background: #F8F9FB;")
        
        layout = QVBoxLayout()
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)
        self.setLayout(layout)
        
        # Header section
        header_widget = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)
        header_widget.setLayout(header_layout)
        
        # Left side - Title and stats
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)
        
        title_label = QLabel("Downloads")
        # Use Poppins SemiBold for main title - same as AI Review
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 32, QFont.Weight.Bold))
        elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins", 32, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        title_layout.addWidget(title_label)
        
        subtitle_label = QLabel("Manage your downloaded files")
        # Use Inter Regular for subtitle
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
            subtitle_label.setFont(QFont("Inter 24pt", 14))
        else:
            subtitle_label.setFont(QFont("Arial", 14))
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        title_layout.addWidget(subtitle_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Right side - Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Open folder button
        open_folder_btn = QPushButton("Open Folder")
        # Use Poppins Medium for buttons
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            open_folder_btn.setFont(QFont("Poppins", 12, QFont.Weight.Medium))
        else:
            open_folder_btn.setFont(QFont("Arial", 12, QFont.Weight.Medium))
        open_folder_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #2563EB;
            }
        """)
        open_folder_btn.clicked.connect(self.open_downloads_folder)
        button_layout.addWidget(open_folder_btn)
        
        # Clear all button
        clear_btn = QPushButton("Clear All")
        # Use Poppins Medium for buttons
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            clear_btn.setFont(QFont("Poppins", 12, QFont.Weight.Medium))
        else:
            clear_btn.setFont(QFont("Arial", 12, QFont.Weight.Medium))
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #DC2626;
            }
        """)
        clear_btn.clicked.connect(self.clear_all_downloads)
        button_layout.addWidget(clear_btn)
        
        header_layout.addLayout(button_layout)
        layout.addWidget(header_widget)
        
        # Statistics cards
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        
        # Total downloads
        self.total_card = self.create_stat_card("Total Downloads", len(self.download_items), "#3B82F6")
        stats_layout.addWidget(self.total_card)
        
        # Images count
        images_count = len([item for item in self.download_items if item.file_type == "image"])
        self.images_card = self.create_stat_card("Images", images_count, "#10B981")
        stats_layout.addWidget(self.images_card)
        
        # Videos count
        videos_count = len([item for item in self.download_items if item.file_type == "video"])
        self.videos_card = self.create_stat_card("Videos", videos_count, "#F59E0B")
        stats_layout.addWidget(self.videos_card)
        
        stats_layout.addStretch()
        layout.addLayout(stats_layout)
        
        # Downloads list
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout()
        self.list_layout.setSpacing(12)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_widget.setLayout(self.list_layout)
        
        # Scroll area for downloads
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #F9FAFB;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9CA3AF;
            }
        """)
        
        scroll_area.setWidget(self.list_widget)
        layout.addWidget(scroll_area)
        
        # Populate downloads
        self.populate_downloads()
        
    def create_stat_card(self, title: str, count: int, color: str) -> QWidget:
        """Create statistics card"""
        card = QWidget()
        card.setFixedSize(160, 80)
        card.setStyleSheet(f"""
            QWidget {{
                background: white;
                border: none;
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        card.setLayout(layout)
        
        # Count
        count_label = QLabel(str(count))
        count_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        count_label.setStyleSheet(f"color: {color}; background: transparent;")
        count_label.setObjectName("count_label")  # Set object name for easy finding
        layout.addWidget(count_label)
        
        # Title
        title_label = QLabel(title)
        # Use Inter Regular for card titles
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
            title_label.setFont(QFont("Inter 24pt", 12))
        else:
            title_label.setFont(QFont("Arial", 12))
        title_label.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(title_label)
        
        return card
        
    def populate_downloads(self):
        """Populate downloads list"""
        # Clear existing items
        for i in reversed(range(self.list_layout.count())):
            item = self.list_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                self.list_layout.removeItem(item)
        
        if not self.download_items:
            # Show empty state
            empty_label = QLabel("📁 No downloads yet")
            empty_label.setFont(QFont("Arial", 16))
            empty_label.setStyleSheet("color: #9CA3AF; background: transparent;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.list_layout.addWidget(empty_label)
            return
        
        # Add download list items
        for download_item in self.download_items:
            list_item = DownloadListItem(download_item)
            list_item.open_clicked.connect(self.on_open_file)
            list_item.delete_clicked.connect(self.on_delete_file)
            
            self.list_layout.addWidget(list_item)
        
        # Add stretch to push items to the top
        self.list_layout.addStretch()
    
    def on_open_file(self, file_path: str):
        """Handle open file click"""
        self.open_file_clicked.emit(file_path)
    
    def on_delete_file(self, item_id: str):
        """Handle delete file click"""
        self.delete_file_clicked.emit(item_id)
    
    def clear_all_downloads(self):
        """Clear all downloads"""
        # Check if downloads list is empty
        if not self.download_items:
            # Show warning dialog for empty downloads
            warning_dialog = PremiumSuccessDialog(
                self, 
                "No Downloads", 
                "There are no downloaded files to clear.",
                "📁"
            )
            warning_dialog.exec()
            return
        
        dialog = PremiumConfirmDialog(
            self, 
            "Clear All Downloads", 
            "Are you sure you want to delete all downloaded files?",
            "🗑️",
            confirm_text="Delete",
            confirm_variant="danger"
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Make a copy of current items for history cleanup
            items_to_remove = list(self.download_items)

            # Delete all files from disk first
            deleted_count = 0
            missing_count = 0
            
            for item in items_to_remove:
                try:
                    if os.path.exists(item.file_path):
                        os.remove(item.file_path)
                        deleted_count += 1
                    else:
                        # File already missing on disk
                        missing_count += 1
                except Exception as e:
                    print(f"Failed to delete file {item.file_path}: {e}")
                    missing_count += 1
            
            # Clear all downloads from the page list
            self.download_items.clear()
            self.populate_downloads()

            # Also remove entries from MainWindow downloads history and persist
            try:
                main_window = self.find_main_window()
                if main_window and hasattr(main_window, 'downloads_history'):
                    to_remove_ids = {item.id for item in items_to_remove}
                    to_remove_paths = {os.path.normpath(item.file_path) for item in items_to_remove if item.file_path}
                    updated_history = []
                    for hist_item in main_window.downloads_history:
                        hist_id = getattr(hist_item, 'id', None)
                        hist_path = os.path.normpath(getattr(hist_item, 'file_path', '')) if getattr(hist_item, 'file_path', '') else ''
                        if hist_id in to_remove_ids or (hist_path and hist_path in to_remove_paths):
                            continue  # drop
                        updated_history.append(hist_item)
                    removed_from_history = len(main_window.downloads_history) - len(updated_history)
                    main_window.downloads_history = updated_history
                    if removed_from_history > 0 and hasattr(main_window, 'save_downloads_history_to_file'):
                        main_window.save_downloads_history_to_file()
            except Exception as e:
                print(f"⚠️ Error clearing downloads from history: {e}")
            
            # Update stats after clearing
            self.update_statistics()
            
            # Show success message with details (count disk deletes and missing entries)
            total_removed = len(items_to_remove)
            message = f"Removed {total_removed} downloads (deleted: {deleted_count}, missing on disk: {missing_count})."
            success_dialog = PremiumSuccessDialog(
                self, 
                "Success", 
                message,
                "✅"
            )
            success_dialog.exec()
    
    def open_downloads_folder(self):
        """Open downloads folder"""
        # Prefer opening the folder of the most recent downloaded item (wherever it was saved)
        target_path = None
        if self.download_items:
            recent_item = self.download_items[0]
            if recent_item and recent_item.file_path:
                candidate = os.path.dirname(os.path.normpath(recent_item.file_path))
                if os.path.isdir(candidate):
                    target_path = candidate
        
        # Fallback to user's default_save_path from settings
        if not target_path:
            main_window = self.find_main_window()
            if main_window and hasattr(main_window, 'settings'):
                candidate = main_window.settings.get('default_save_path')
                if candidate and os.path.isdir(candidate):
                    target_path = candidate
        
        # Final fallback to user's default downloads directory
        if not target_path:
            candidate = get_default_download_path()
            if os.path.isdir(candidate):
                target_path = candidate
        
        if target_path:
            if sys.platform == "win32":
                os.startfile(target_path)
            elif sys.platform == "darwin":
                run_hidden(["open", target_path])
            else:
                run_hidden(["xdg-open", target_path])
        else:
            QMessageBox.information(
                self,
                "Downloads",
                "We couldn't find a downloads folder. Please choose a location in Settings."
            )
    
    def find_main_window(self):
        """Find MainWindow in widget hierarchy"""
        current = self.parent()
        while current:
            if hasattr(current, 're_analyze_from_history'):
                return current
            current = current.parent()
        return None
    
    def update_downloads_data(self, download_items: List[DownloadItem]):
        """Update downloads data"""
        self.download_items = download_items
        self.update_statistics()
        self.populate_downloads()
    
    def update_statistics(self):
        """Update statistics cards with current data"""
        if hasattr(self, 'total_card') and hasattr(self, 'images_card') and hasattr(self, 'videos_card'):
            # Update total downloads
            total_count = len(self.download_items)
            total_count_label = self.total_card.findChild(QLabel, "count_label")
            if total_count_label:
                total_count_label.setText(str(total_count))
            
            # Update images count
            images_count = len([item for item in self.download_items if item.file_type == "image"])
            images_count_label = self.images_card.findChild(QLabel, "count_label")
            if images_count_label:
                images_count_label.setText(str(images_count))
            
            # Update videos count
            videos_count = len([item for item in self.download_items if item.file_type == "video"])
            videos_count_label = self.videos_card.findChild(QLabel, "count_label")
            if videos_count_label:
                videos_count_label.setText(str(videos_count))

class PremiumSuccessDialog(QDialog):
    """Premium success dialog with modern design"""
    def __init__(self, parent=None, title="", message="", icon="✅"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(450, 200)  # Increased size for better readability
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setup_ui(title, message, icon)
        self.center_dialog()
    
    def center_dialog(self):
        """Center the dialog on the parent window"""
        if self.parent():
            # Get the main window as the reference for centering
            main_window = self.find_main_window()
            if main_window:
                # Use main window geometry for centering
                main_rect = main_window.geometry()
                x = main_rect.x() + (main_rect.width() - self.width()) // 2
                y = main_rect.y() + (main_rect.height() - self.height()) // 2
            else:
                # Fallback to parent centering
                parent_rect = self.parent().geometry()
                x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
                y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            
            # Ensure dialog stays within screen bounds
            screen = QApplication.primaryScreen().geometry()
            x = max(screen.x(), min(x, screen.x() + screen.width() - self.width()))
            y = max(screen.y(), min(y, screen.y() + screen.height() - self.height()))
            
            # Move dialog to center
            self.move(x, y)
    
    def setup_ui(self, title, message, icon):
        """Setup the dialog UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Main container
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 16px;
                border: 2px solid #D1D5DB;
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(32, 24, 32, 24)
        container_layout.setSpacing(20)
        container.setLayout(container_layout)
        
        # Icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Arial", 24))
        icon_label.setStyleSheet("color: #3B82F6; background: transparent;")
        header_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        # Use Poppins SemiBold for title
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 18, QFont.Weight.Bold))
        elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins", 18, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                border: none;
                outline: none;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        container_layout.addLayout(header_layout)
        
        # Message
        message_label = QLabel(message)
        # Use Inter Regular for message
        if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
            message_label.setFont(QFont("Inter 24pt", 14))
        else:
            message_label.setFont(QFont("Arial", 14))
        message_label.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                line-height: 140%;
                border: none;
                outline: none;
            }
        """)
        message_label.setWordWrap(True)
        container_layout.addWidget(message_label)
        
        container_layout.addStretch()
        
        # OK button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_btn = QPushButton("OK")
        # Use Poppins Medium for buttons
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            ok_btn.setFont(QFont("Poppins", 12, QFont.Weight.Medium))
        else:
            ok_btn.setFont(QFont("Arial", 12, QFont.Weight.Medium))
        ok_btn.setFixedSize(100, 36)
        ok_btn.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 8px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #2563EB;
            }
        """)
        ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(ok_btn)
        
        container_layout.addLayout(button_layout)
        layout.addWidget(container)
    
    def find_main_window(self):
        """Find MainWindow in widget hierarchy"""
        current = self.parent()
        while current:
            if hasattr(current, 're_analyze_from_history'):
                return current
            current = current.parent()
        return None

class ModernCharLimitDialog(QDialog):
    """Modern character limit warning dialog"""
    
    def __init__(self, parent=None, char_count=0):
        super().__init__(parent)
        self.char_count = char_count
        self.setWindowTitle("")
        self.setFixedSize(480, 320)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
        self.center_dialog()
    
    def setup_ui(self):
        """Setup modern UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main container with rounded corners and shadow
        main_container = QWidget()
        main_container.setObjectName("mainContainer")
        main_container.setStyleSheet("""
            #mainContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8FAFC);
                border-radius: 20px;
                border: 1px solid #E2E8F0;
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(32, 32, 32, 32)
        container_layout.setSpacing(24)
        
        # Header with icon and title
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)
        
        # Warning icon
        icon_label = QLabel("⚠️")
        icon_label.setFont(QFont("Arial", 24))
        icon_label.setStyleSheet("background: transparent;")
        header_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel("Character Limit Exceeded")
        title_label.setFont(QFont("Poppins", 18, QFont.Weight.DemiBold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1E293B;
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        container_layout.addLayout(header_layout)
        
        # Message content
        message_layout = QVBoxLayout()
        message_layout.setSpacing(12)
        
        # Current count
        count_label = QLabel(f"Current: {self.char_count:,} characters")
        count_label.setFont(QFont("Inter", 14, QFont.Weight.Medium))
        count_label.setStyleSheet("""
            QLabel {
                color: #EF4444;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                min-width: 300px;
            }
        """)
        count_label.setWordWrap(True)
        message_layout.addWidget(count_label)
        
        # Limit info
        limit_label = QLabel("Maximum allowed: 10,000 characters")
        limit_label.setFont(QFont("Inter", 14))
        limit_label.setStyleSheet("""
            QLabel {
                color: #6B7280;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                min-width: 300px;
            }
        """)
        limit_label.setWordWrap(True)
        message_layout.addWidget(limit_label)
        
        # Action message
        action_label = QLabel("Please shorten your text and try again.")
        action_label.setFont(QFont("Inter", 14))
        action_label.setStyleSheet("""
            QLabel {
                color: #374151;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                min-width: 300px;
            }
        """)
        action_label.setWordWrap(True)
        message_layout.addWidget(action_label)
        
        container_layout.addLayout(message_layout)
        
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background: #E5E7EB; border: none; margin: 16px 0px;")
        divider.setFixedHeight(1)
        container_layout.addWidget(divider)
        
        # Button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        ok_button = QPushButton("Got it")
        ok_button.setFont(QFont("Poppins", 14, QFont.Weight.Medium))
        ok_button.setFixedSize(120, 40)
        ok_button.setCursor(Qt.CursorShape.PointingHandCursor)
        ok_button.setStyleSheet("""
            QPushButton {
                background: #3B82F6;
                color: white;
                border: none;
                border-radius: 10px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #2563EB;
            }
            QPushButton:pressed {
                background: #1D4ED8;
            }
        """)
        ok_button.clicked.connect(self.accept)
        button_layout.addWidget(ok_button)
        
        container_layout.addLayout(button_layout)
        
        main_container.setLayout(container_layout)
        layout.addWidget(main_container)
        self.setLayout(layout)
    
    def center_dialog(self):
        """Center the dialog on the parent window"""
        if self.parent():
            parent_rect = self.parent().geometry()
            dialog_rect = self.geometry()
            x = parent_rect.x() + (parent_rect.width() - dialog_rect.width()) // 2
            y = parent_rect.y() + (parent_rect.height() - dialog_rect.height()) // 2
            self.move(x, y)
class ModernDeviceRestrictionDialog(QDialog):
    """Modern device restriction dialog"""
    
    def __init__(self, parent=None, server_message: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Upgrade to Premium")
        self.setFixedSize(500, 400)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui(server_message)
        self.center_dialog()
    
    def center_dialog(self):
        """Center dialog on parent window with better positioning"""
        if self.parent():
            parent_rect = self.parent().geometry()
            x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
            # Position slightly higher (8vh equivalent)
            y = parent_rect.y() + (parent_rect.height() - self.height()) // 2 - 50
            self.move(x, y)
    
    def setup_ui(self, server_message: str):
        """Setup modern UI"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Main container with background and subtle gradient
        main_container = QWidget()
        main_container.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #FFFFFF, stop:1 #F9FAFB);
                border-radius: 20px;
                border: 2px solid #E5E7EB;
                backdrop-filter: blur(4px);
            }
        """)
        
        container_layout = QVBoxLayout(main_container)
        container_layout.setContentsMargins(40, 40, 40, 40)
        container_layout.setSpacing(25)
        
        # Title with better text wrapping and visual icon
        title_label = QLabel("Access limited for free accounts on this device")
        title_label.setStyleSheet("""
            QLabel {
                color: #111827;
                font-family: 'Poppins', 'Arial', sans-serif;
                font-size: 20px;
                font-weight: 600;
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
                line-height: 1.4;
            }
        """)
        title_label.setWordWrap(True)
        title_label.setMinimumHeight(80)  # Reduced height since font is smaller
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Use shorter text to prevent word breaking
        title_text = "Access limited for free accounts on this device"
        title_label.setText(title_text)
        
        # Close button - positioned absolutely in top right corner
        close_btn = QPushButton("×")
        close_btn.setFixedSize(32, 32)
        close_btn.setStyleSheet("""
            QPushButton {
                background: rgba(156, 163, 175, 0.1);
                border: none;
                color: #6B7280;
                font-size: 18px;
                font-weight: bold;
                border-radius: 16px;
                padding: 0px;
                text-align: center;
                line-height: 32px;
            }
            QPushButton:hover {
                background: rgba(156, 163, 175, 0.2);
                color: #374151;
            }
        """)
        close_btn.clicked.connect(self.close)
        
        # Subtitle
        subtitle_label = QLabel("Thanks for trying Stuck AI!")
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #6B7280;
                font-family: 'Inter', 'Arial', sans-serif;
                font-size: 19px;
                font-weight: 400;
                background: transparent;
                border: none;
                line-height: 1.5;
                margin-top: 4px;
            }
        """)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setWordWrap(True)
        
        # Description
        # Gentle, clear explanation
        human_msg = ""
        if isinstance(server_message, str) and server_message:
            if 'device_or_ip_already_used' in server_message:
                human_msg = "This device or network has already been used for a free account."
            elif 'device_ip_already_used' in server_message:
                human_msg = "This device or network has already been used for a free account."
            elif 'No analysis credits remaining' in server_message:
                human_msg = "You have no analysis credits left."
        if not human_msg:
            human_msg = "Free accounts are limited to one device or IP."

        desc_label = QLabel(human_msg + "\nUpgrade to continue without limits:")
        desc_label.setStyleSheet("""
            QLabel {
                color: #6B7280;
                font-family: 'Inter', 'Arial', sans-serif;
                font-size: 19px;
                font-weight: 400;
                background: transparent;
                border: none;
                line-height: 1.5;
            }
        """)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        
        # Upgrade button with more motivating text
        upgrade_btn = QPushButton("Upgrade Plan")
        upgrade_btn.setFixedSize(220, 50)
        upgrade_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #2563EB);
                border: none;
                color: white;
                font-family: 'Poppins', 'Arial', sans-serif;
                font-size: 16px;
                font-weight: 500;
                border-radius: 12px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #1D4ED8);
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1D4ED8, stop:1 #1E40AF);
                transform: translateY(1px);
            }
        """)
        upgrade_btn.clicked.connect(self.on_upgrade_clicked)
        
        # Removed bottom promo text per request
        
        # Add widgets to layout
        container_layout.addWidget(title_label)
        container_layout.addWidget(subtitle_label)
        container_layout.addWidget(desc_label)
        container_layout.addStretch()
        container_layout.addWidget(upgrade_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(main_container)
        
        # Add close button to main container and position it in top right corner
        main_container.layout().addWidget(close_btn)
        
        # Position close button in top right corner after layout is done
        def position_close_button():
            close_btn.setParent(main_container)
            close_btn.raise_()  # Bring to front
            close_btn.move(main_container.width() - 42, 10)
        
        # Use QTimer to position after layout is complete
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(0, position_close_button)
    
    def on_upgrade_clicked(self):
        """Handle upgrade button click"""
        try:
            webbrowser.open("https://dashboard.stuckai.net/pricing")
        finally:
            self.close()

class ModernCreditsDialog(QDialog):
    """Modern credits warning dialog.
    Can be customized via optional title/message/subtitle for different credit types.
    """
    
    def __init__(self, parent=None, title: str | None = None, message: str | None = None, subtitle: str | None = None):
        super().__init__(parent)
        self.setWindowTitle("")
        # Defaults for analysis credits; callers can override for AI Images, etc.
        self._title_text = title or "Analysis Credits"
        self._message_text = message or "Your analysis credits have run out"
        self._subtitle_text = subtitle or "Upgrade your plan to continue analyzing content"
        # Responsive min/max; başlangıçta orta boy
        self.setMinimumSize(360, 280)
        self.resize(480, 360)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setup_ui()
        self.center_dialog()
        # Resize/parent move olduğunda ortalamayı koru
        if parent:
            parent.installEventFilter(self)
        
    def setup_ui(self):
        """Setup modern UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main container with rounded corners and shadow
        main_container = QWidget()
        main_container.setObjectName("mainContainer")
        main_container.setStyleSheet("""
            #mainContainer {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FFFFFF, stop:1 #F8FAFC);
                border-radius: 20px;
                border: 1px solid #E2E8F0;
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(30, 30, 30, 30)
        container_layout.setSpacing(20)
        
        # Header with title only
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title
        title_label = QLabel(self._title_text)
        title_label.setStyleSheet("""
            QLabel {
                color: #1E293B;
                font-family: 'Poppins';
                font-size: 18px;
                font-weight: 600;
            }
        """)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Icon and message
        content_layout = QVBoxLayout()
        content_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        content_layout.setSpacing(20)
        
        # Icon: dart.png
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        icon_label.setFixedSize(56, 56)
        try:
            dart_path = os.path.abspath("ui/assets/dart.png")
            if os.path.exists(dart_path):
                pm = QPixmap(dart_path)
                if not pm.isNull():
                    scaled = pm.scaled(56, 56, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    icon_label.setPixmap(scaled)
        except Exception:
            pass
        
        # Message
        message_label = QLabel(self._message_text)
        message_label.setStyleSheet("""
            QLabel {
                color: #1E293B;
                font-family: 'Inter';
                font-size: 16px;
                font-weight: 400;
                text-align: left;
            }
        """)
        message_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        message_label.setWordWrap(True)
        
        # Subtitle
        subtitle_label = QLabel(self._subtitle_text)
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #64748B;
                font-family: 'Inter';
                font-size: 14px;
                text-align: left;
            }
        """)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        subtitle_label.setWordWrap(True)
        
        content_layout.addWidget(icon_label)
        content_layout.addWidget(message_label)
        content_layout.addWidget(subtitle_label)
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setFixedSize(120, 40)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: 1px solid #D1D5DB;
                color: #374151;
                font-family: 'Poppins Medium';
                font-size: 14px;
                font-weight: 500;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: #F9FAFB;
                border-color: #9CA3AF;
            }
        """)
        try:
            cancel_btn.setFont(QFont("Poppins Medium", 10))
        except Exception:
            pass
        cancel_btn.clicked.connect(self.reject)
        
        # Upgrade button
        upgrade_btn = QPushButton("Upgrade Plan")
        upgrade_btn.setFixedSize(120, 40)
        upgrade_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #2563EB);
                border: none;
                color: white;
                font-family: 'Poppins Medium';
                font-size: 14px;
                font-weight: 500;
                border-radius: 10px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #1D4ED8);
            }
        """)
        try:
            upgrade_btn.setFont(QFont("Poppins Medium", 10))
        except Exception:
            pass
        def open_pricing():
            try:
                webbrowser.open("https://dashboard.stuckai.net/pricing")
            except Exception:
                pass
            self.accept()
        upgrade_btn.clicked.connect(open_pricing)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(upgrade_btn)
        
        # Add all layouts to container
        container_layout.addLayout(header_layout)
        container_layout.addLayout(content_layout)
        container_layout.addStretch()
        container_layout.addLayout(button_layout)
        
        main_container.setLayout(container_layout)
        layout.addWidget(main_container)
        self.setLayout(layout)
        
    def center_dialog(self):
        """Center the dialog on the screen"""
        # Get the parent window (main window) geometry
        if self.parent():
            parent_geometry = self.parent().geometry()
            x = parent_geometry.x() + (parent_geometry.width() - self.width()) // 2
            y = parent_geometry.y() + (parent_geometry.height() - self.height()) // 2
        else:
            # Fallback to screen center if no parent
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - self.width()) // 2
            y = (screen.height() - self.height()) // 2
        
        self.move(x, y)

    def eventFilter(self, obj, event):
        # Parent taşınır/yeniden boyutlandırılırsa pop-up ortada kalsın
        if obj is self.parent() and event.type() in (QEvent.Type.Resize, QEvent.Type.Move):
            QTimer.singleShot(0, self.center_dialog)
        return super().eventFilter(obj, event)

class PremiumConfirmDialog(QDialog):
    """Premium confirmation dialog with modern design.

    Optional params:
    - confirm_text: override confirm button text (default depends on variant)
    - confirm_variant: 'danger' (red) or 'primary' (blue)
    - on_confirm: optional callable executed before closing
    """
    def __init__(self, parent=None, title="", message="", icon="❓", confirm_text=None, confirm_variant="danger", on_confirm=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        # store options
        self._confirm_text = confirm_text
        self._confirm_variant = confirm_variant or "danger"
        self._on_confirm = on_confirm
        # Responsive boyutlar
        self.setMinimumSize(320, 240)
        self.resize(440, 320)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground)
        self.setup_ui(title, message, icon)
        self.center_dialog()
    

    
    def center_dialog(self):
        """Center the dialog on the parent window"""
        if self.parent():
            # Get the main window as the reference for centering
            main_window = self.find_main_window()
            if main_window:
                # Use main window geometry for centering
                main_rect = main_window.geometry()
                x = main_rect.x() + (main_rect.width() - self.width()) // 2
                y = main_rect.y() + (main_rect.height() - self.height()) // 2
            else:
                # Fallback to parent centering
                parent_rect = self.parent().geometry()
                x = parent_rect.x() + (parent_rect.width() - self.width()) // 2
                y = parent_rect.y() + (parent_rect.height() - self.height()) // 2
            
            # Ensure dialog stays within screen bounds
            screen = QApplication.primaryScreen().geometry()
            x = max(screen.x(), min(x, screen.x() + screen.width() - self.width()))
            y = max(screen.y(), min(y, screen.y() + screen.height() - self.height()))
            
            # Move dialog to center
            self.move(x, y)
        
    def event(self, e):
        # Resize edildiğinde ortalamayı koru
        if e.type() == QEvent.Type.Resize:
            QTimer.singleShot(0, self.center_dialog)
        return super().event(e)
    
    def setup_ui(self, title, message, icon):
        """Setup the dialog UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Main container
        container = QWidget()
        container.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 16px;
                border: 2px solid #D1D5DB;
            }
        """)
        
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(32, 32, 32, 32)  # Padding'i artırdık
        container_layout.setSpacing(24)  # Spacing'i artırdık
        container.setLayout(container_layout)
        
        # Icon and title
        header_layout = QHBoxLayout()
        header_layout.setSpacing(16)
        
        # Icon
        icon_label = QLabel(icon)
        icon_label.setFont(QFont("Arial", 24))
        icon_label.setStyleSheet("color: #3B82F6; background: transparent;")
        header_layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        # Use Poppins SemiBold for title
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 18, QFont.Weight.Bold))
        elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins", 18, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
                border: none;
                outline: none;
            }
        """)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        container_layout.addLayout(header_layout)
        
        # Message
        message_label = QLabel(message)
        # Use Inter Regular for message
        if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
            message_label.setFont(QFont("Inter 24pt", 14))
        else:
            message_label.setFont(QFont("Arial", 14))
        message_label.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                line-height: 140%;
                border: none;
                outline: none;
                min-height: 80px;  /* Minimum yükseklik ekledik */
            }
        """)
        message_label.setWordWrap(True)
        container_layout.addWidget(message_label)
        
        container_layout.addStretch()
        
        # Buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        button_layout.addStretch()
        
        # Cancel button
        cancel_btn = QPushButton("Cancel")
        # Use Poppins Medium for buttons
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            cancel_btn.setFont(QFont("Poppins", 12, QFont.Weight.Medium))
        else:
            cancel_btn.setFont(QFont("Arial", 12, QFont.Weight.Medium))
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background: #F3F4F6;
                color: #374151;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #E5E7EB;
                border-color: #9CA3AF;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        # Confirm button (variant-aware)
        default_text = "Delete" if (self._confirm_variant == "danger") else "Confirm"
        confirm_btn = QPushButton(self._confirm_text or default_text)
        # Use Poppins Medium for buttons
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            confirm_btn.setFont(QFont("Poppins", 12, QFont.Weight.Medium))
        else:
            confirm_btn.setFont(QFont("Arial", 12, QFont.Weight.Medium))
        confirm_btn.setFixedSize(140, 36)
        if self._confirm_variant == "primary":
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3B82F6, stop:1 #2563EB);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                    font-family: 'Poppins', 'Arial', sans-serif;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2563EB, stop:1 #1D4ED8);
                }
            """)
        else:
            confirm_btn.setStyleSheet("""
                QPushButton {
                    background: #EF4444;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-weight: 500;
                    font-family: 'Poppins', 'Arial', sans-serif;
                }
                QPushButton:hover {
                    background: #DC2626;
                }
            """)
        def _handle_confirm():
            try:
                if callable(self._on_confirm):
                    self._on_confirm()
            except Exception:
                pass
            self.accept()
        confirm_btn.clicked.connect(_handle_confirm)
        button_layout.addWidget(confirm_btn)
        
        container_layout.addLayout(button_layout)
        layout.addWidget(container)
    
    def find_main_window(self):
        """Find MainWindow in widget hierarchy"""
        current = self.parent()
        while current:
            if hasattr(current, 're_analyze_from_history'):
                return current
            current = current.parent()
        return None
class HistoryPage(QWidget):
    """History page with modern card layout"""
    def __init__(self, parent=None, history_items=None):
        super().__init__(parent)
        self.history_items = history_items or []
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the history page UI"""
        layout = QVBoxLayout()
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(24)
        self.setLayout(layout)
        
        # Header section
        header_layout = QHBoxLayout()
        header_layout.setSpacing(20)
        
        # Title and subtitle
        title_layout = QVBoxLayout()
        title_layout.setSpacing(8)
        
        title_label = QLabel("Analysis History")
        # Use Poppins SemiBold for main title
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins SemiBold" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 28, QFont.Weight.Bold))
        elif main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            title_label.setFont(QFont("Poppins", 28, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 28, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        title_layout.addWidget(title_label)
        
        self.subtitle_label = QLabel("Track your previous analyses and results")
        # Use Inter Regular for subtitle
        if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
            self.subtitle_label.setFont(QFont("Inter 24pt", 14))
        else:
            self.subtitle_label.setFont(QFont("Arial", 14))
        self.subtitle_label.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        title_layout.addWidget(self.subtitle_label)
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Action buttons
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        
        # Clear all button
        clear_btn = QPushButton("Clear All")
        # Use Poppins Medium for buttons
        if main_window and hasattr(main_window, 'loaded_fonts') and "Poppins" in main_window.loaded_fonts:
            clear_btn.setFont(QFont("Poppins", 12, QFont.Weight.Medium))
        else:
            clear_btn.setFont(QFont("Arial", 12, QFont.Weight.Medium))
        clear_btn.setStyleSheet("""
            QPushButton {
                background: #EF4444;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: #DC2626;
            }
        """)
        clear_btn.clicked.connect(self.clear_all_history)
        actions_layout.addWidget(clear_btn)
        
        header_layout.addLayout(actions_layout)
        layout.addLayout(header_layout)
        
        # Statistics cards
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(16)
        
        # Calculate statistics
        completed_count = sum(1 for item in self.history_items if item.status == "completed")
        pending_count = sum(1 for item in self.history_items if item.status == "pending")
        failed_count = sum(1 for item in self.history_items if item.status == "failed")
        total_outputs = sum(item.output_count for item in self.history_items)
        
        stats_data = [
            ("✅ Completed", completed_count, "#10B981"),
            ("🕑 Pending", pending_count, "#F59E0B"),
            ("❌ Failed", failed_count, "#EF4444"),
            ("📊 Total Outputs", total_outputs, "#3B82F6")
        ]
        
        for title, count, color in stats_data:
            stat_card = self.create_stat_card(title, count, color)
            self.stats_layout.addWidget(stat_card)
        
        self.stats_layout.addStretch()
        layout.addLayout(self.stats_layout)
        
        # History cards list
        self.cards_widget = QWidget()
        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(20)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_widget.setLayout(self.cards_layout)
        
        # Scroll area for cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #F3F4F6;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9CA3AF;
            }
        """)
        
        scroll_area.setWidget(self.cards_widget)
        layout.addWidget(scroll_area)
        
        # Populate cards
        self.populate_cards()
    
    def create_stat_card(self, title: str, count: int, color: str) -> QWidget:
        """Create statistics card"""
        card = QWidget()
        card.setFixedSize(160, 80)
        card.setStyleSheet(f"""
            QWidget {{
                background: white;
                border: none;
                border-radius: 12px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        card.setLayout(layout)
        
        # Count
        count_label = QLabel(str(count))
        count_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        count_label.setStyleSheet(f"color: {color}; background: transparent;")
        count_label._is_count_label = True  # Mark this as the count label for updating
        layout.addWidget(count_label)
        
        # Title
        title_label = QLabel(title)
        # Use Inter Regular for card titles
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'loaded_fonts') and "Inter 24pt" in main_window.loaded_fonts:
            title_label.setFont(QFont("Inter 24pt", 12))
        else:
            title_label.setFont(QFont("Arial", 12))
        title_label.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(title_label)
        
        return card
    
    def populate_cards(self):
        """Populate the history cards grid"""
        # Clear existing cards
        for i in reversed(range(self.cards_layout.count())):
            item = self.cards_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()
            elif item.spacerItem():
                self.cards_layout.removeItem(item)
        
        if not self.history_items:
            # Show empty state
            empty_label = QLabel("📁 No history yet")
            empty_label.setFont(QFont("Arial", 16))
            empty_label.setStyleSheet("color: #9CA3AF; background: transparent;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards_layout.addWidget(empty_label, 0, 0)
            return
        
        # Add cards in grid layout (2 columns)
        for i, item in enumerate(self.history_items):
            card = HistoryCard(item)
            card.re_analyze_clicked.connect(self.on_re_analyze)
            card.show_clicked.connect(self.on_show_item)
            card.delete_clicked.connect(self.on_delete)
            
            # Calculate row and column for grid
            row = i // 2
            col = i % 2
            
            self.cards_layout.addWidget(card, row, col)
    
    def on_re_analyze(self, item_id: str):
        """Handle re-analyze button click"""
        print(f"HistoryPage.on_re_analyze called with item_id: {item_id}")
        
        # Call MainWindow's re-analyze function
        if hasattr(self.parent(), 're_analyze_from_history'):
            print("Found re_analyze_from_history method in parent")
            self.parent().re_analyze_from_history(item_id)
        else:
            print("re_analyze_from_history method NOT found in parent")
            print(f"Parent type: {type(self.parent())}")
            
            # Try to find MainWindow in the widget hierarchy
            main_window = self.find_main_window()
            if main_window and hasattr(main_window, 're_analyze_from_history'):
                print("Found MainWindow in hierarchy, calling re_analyze_from_history")
                main_window.re_analyze_from_history(item_id)
            else:
                print("MainWindow not found in hierarchy")
                QMessageBox.warning(
                    self,
                    "Re-Analyze",
                    "We couldn't prepare the window to re-analyze. Please try again."
                )
    
    def on_show_item(self, item_id: str):
        """Handle show button click to open saved analysis snapshot"""
        print(f"HistoryPage.on_show_item called with item_id: {item_id}")
        main_window = self.find_main_window()
        if main_window and hasattr(main_window, 'show_history_snapshot'):
            main_window.show_history_snapshot(item_id)
        else:
            QMessageBox.warning(
                self,
                "History",
                "We couldn't open the saved analysis. Please try again."
            )
    
    def find_main_window(self):
        """Find MainWindow in widget hierarchy"""
        current = self.parent()
        while current:
            if hasattr(current, 're_analyze_from_history'):
                return current
            current = current.parent()
        return None
    

    
    def on_delete(self, item_id: str):
        """Handle delete button click"""
        dialog = PremiumConfirmDialog(
            self, 
            "Delete Analysis", 
            "Are you sure you want to delete this analysis?",
            "🗑️",
            confirm_text="Delete",
            confirm_variant="danger"
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Remove item from local list
            self.history_items = [item for item in self.history_items if item.id != item_id]
            self.populate_cards()
            self.update_statistics()
            
            # Update main window history and save to file
            main_window = self.find_main_window()
            if main_window and hasattr(main_window, 'history_items'):
                main_window.history_items = [item for item in main_window.history_items if item.id != item_id]
                # Remove snapshot folder
                try:
                    snapshot_dir = os.path.join(main_window.get_project_root(), 'history', item_id)
                    if os.path.exists(snapshot_dir):
                        import shutil
                        shutil.rmtree(snapshot_dir, ignore_errors=True)
                except Exception as _e:
                    print(f"Warning: failed to remove snapshot for {item_id}: {_e}")
                main_window.save_history_to_file()
            
            # Ensure file is saved by calling save_history_to_file again
            if main_window and hasattr(main_window, 'save_history_to_file'):
                main_window.save_history_to_file()
            
            # Show success message
            success_dialog = PremiumSuccessDialog(
                self, 
                "Success", 
                "Analysis deleted successfully!",
                "✅"
            )
            success_dialog.exec()
    

    
    def update_history_data(self, history_items: List[HistoryItem]):
        """Update history data and refresh UI"""
        self.history_items = history_items
        self.populate_cards()
        self.update_statistics()
    
    def update_statistics(self):
        """Update statistics cards with current data"""
        # Calculate statistics
        completed_count = sum(1 for item in self.history_items if item.status == "completed")
        pending_count = sum(1 for item in self.history_items if item.status == "pending")
        failed_count = sum(1 for item in self.history_items if item.status == "failed")
        total_outputs = sum(item.output_count for item in self.history_items)
        
        # Update subtitle
        if hasattr(self, 'subtitle_label'):
            self.subtitle_label.setText(f"Track your {len(self.history_items)} previous analyses and results")
        
        # Update stat cards if they exist
        if hasattr(self, 'stats_layout'):
            # Store existing stat card widgets for updating instead of recreating
            stat_widgets = []
            for i in range(self.stats_layout.count()):
                item = self.stats_layout.itemAt(i)
                if item and item.widget():
                    stat_widgets.append(item.widget())
            
            # If we have exactly 4 stat cards, update them in place
            if len(stat_widgets) == 4:
                stats_data = [
                    ("✅ Completed", completed_count, "#10B981"),
                    ("🕑 Pending", pending_count, "#F59E0B"),
                    ("❌ Failed", failed_count, "#EF4444"),
                    ("📊 Total Outputs", total_outputs, "#3B82F6")
                ]
                
                for i, (title, count, color) in enumerate(stats_data):
                    if i < len(stat_widgets):
                        # Update the existing widget's content
                        widget = stat_widgets[i]
                        # Find the count label and update it
                        for child in widget.findChildren(QLabel):
                            if hasattr(child, '_is_count_label'):
                                child.setText(str(count))
                                break
            else:
                # Clear and recreate if the number doesn't match
                for i in reversed(range(self.stats_layout.count())):
                    item = self.stats_layout.itemAt(i)
                    if item.widget():
                        item.widget().deleteLater()
                    elif item.spacerItem():
                        self.stats_layout.removeItem(item)
                
                # Recreate stat cards
                stats_data = [
                    ("✅ Completed", completed_count, "#10B981"),
                    ("🕑 Pending", pending_count, "#F59E0B"),
                    ("❌ Failed", failed_count, "#EF4444"),
                    ("📊 Total Outputs", total_outputs, "#3B82F6")
                ]
                
                for title, count, color in stats_data:
                    stat_card = self.create_stat_card(title, count, color)
                    self.stats_layout.addWidget(stat_card)
    
    def clear_all_history(self):
        """Clear all history items"""
        # Check if history list is empty
        if not self.history_items:
            # Show warning dialog for empty history
            warning_dialog = PremiumSuccessDialog(
                self, 
                "No History", 
                "There are no analysis history items to clear.",
                "📁"
            )
            warning_dialog.exec()
            return
        
        dialog = PremiumConfirmDialog(
            self, 
            "Clear All History", 
            "Are you sure you want to clear all analysis history? This action cannot be undone.",
            "🗑️",
            confirm_text="Delete",
            confirm_variant="danger"
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.history_items = []
            self.populate_cards()
            self.update_statistics()
            
            # Clear history in MainWindow and save to file using find_main_window
            main_window = self.find_main_window()
            if main_window and hasattr(main_window, 'history_items'):
                main_window.history_items = []
                main_window.history_counter = 1
                main_window.save_history_to_file()
                # Also remove all saved snapshots under history/ root
                try:
                    history_root = os.path.join(main_window.get_project_root(), 'history')
                    if os.path.exists(history_root):
                        import shutil
                        shutil.rmtree(history_root, ignore_errors=True)
                        os.makedirs(history_root, exist_ok=True)
                except Exception as _e:
                    print(f"Warning: failed to clear history snapshots: {_e}")
            
            # Ensure file is saved by calling save_history_to_file again
            if main_window and hasattr(main_window, 'save_history_to_file'):
                main_window.save_history_to_file()
            
            # Show success message
            success_dialog = PremiumSuccessDialog(
                self, 
                "Success", 
                "All history cleared successfully!",
                "✅"
            )
            success_dialog.exec()
class WelcomeTooltipDialog(QDialog):
    """Deprecated: retained for compatibility, no longer used."""
    def __init__(self, *args, **kwargs):
        super().__init__(*(args or [None]), **kwargs)
        self._checkbox = QCheckBox()

    def get_do_not_show(self) -> bool:
        return False

class MainWindow(QMainWindow):
    """Main application window"""
    
    def __init__(self, auth_service: SupabaseAuthService = None):
        super().__init__()
        
        # Initialize authentication
        self.auth_service = auth_service
        self.current_user = None
        self.current_profile = None
        
        # Initialize cost tracking service (will be initialized after user login)
        self.cost_tracking_service = None
        self.scene_cost_tracking_service = None
        self.leonardo_ai_service = LeonardoAIService()
        self.current_user = None
        self.current_profile = None
        
        # Initialize user manager
        self.user_manager = UserManager()
        
        self.scenes_data = []
        self.current_scene_index = 0
        self.selected_media = {'images': [], 'videos': []}
        
        # Lazy loading state tracking
        self.scene_loading_states = {}  # scene_index -> 'loading', 'ready', 'error'
        self.lazy_loading_threads = {}  # scene_index -> thread
        self.scene_media_cache = {}     # scene_index -> media_data
        self.background_analysis_threads = {}  # scene_index -> background analysis thread
        self.settings = {
            'stock_images_count': 3,
            'stock_videos_count': 3,
            'ai_images_count': 3,
            'image_aspect_ratio': 'all',
            'video_aspect_ratio': 'all',
            'default_save_path': os.path.join(self.get_project_root(), "downloads"),
            'show_welcome_tooltip': True
        }
        
        # Initialize history system
        self.history_items = []
        self.history_counter = 1
        self.history_file = os.path.join(self.get_project_root(), "data", "analysis_history.json")
        print(f"🔍 DEBUG: History file path: {self.history_file}")
        # Snapshot viewing flag
        self._is_viewing_history_snapshot = False
        
        # Initialize downloads history system
        self.downloads_history = []
        self.downloads_history_file = os.path.join(self.get_project_root(), "data", "downloads_history.json")
        print(f"🔍 DEBUG: Downloads history file path: {self.downloads_history_file}")
        
        # AI Image Generation Status Tracking
        self.ai_generation_status = {}  # prompt -> status ('creating', 'completed', 'error')
        self.ai_generation_media_cards = {}  # prompt -> list of MediaCard instances
        self.ai_generation_threads = {}  # prompt -> AIImageGenerationThread
        self.ai_generation_results = {}  # prompt -> image_url
        # Navigation reentrancy/debounce controls
        self._nav_locked = False
        self._last_nav_at = 0.0
        self._highlight_token = 0
        
        # Load custom fonts
        self.load_custom_fonts()
        
        # Ensure required directories exist
        os.makedirs(os.path.join(self.get_project_root(), 'history'), exist_ok=True)
        os.makedirs(os.path.join(self.get_project_root(), 'data'), exist_ok=True)
        
        # Load settings from file
        self.load_settings_from_file()
        
        # Load history from file
        self.load_history_from_file()
        
        # Load downloads history from file
        self.load_downloads_history_from_file()
        
        self.setup_ui()
    
    def get_project_root(self):
        """Get the project root directory, always uses user data directory for compiled mode"""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable - always use user data directory
            exe_dir = os.path.dirname(os.path.abspath(sys.executable))
            user_data_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local", "StuckAI")
            os.makedirs(user_data_dir, exist_ok=True)
            project_root = user_data_dir
            print(f"🔍 DEBUG: get_project_root (installer mode): {project_root}")
            
            # Migrate data from exe directory if it exists and we have access
            self._migrate_data_from_exe_dir(exe_dir, project_root)
            
            print(f"🔍 DEBUG: sys.executable: {sys.executable}")
            return project_root
        else:
            # Running as script - get the directory containing this file (ui/main_window.py)
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            print(f"🔍 DEBUG: get_project_root (script): {project_root}")
            print(f"🔍 DEBUG: __file__: {__file__}")
            return project_root
    
    def _migrate_data_from_exe_dir(self, exe_dir: str, user_data_dir: str):
        """Migrate data from exe directory to user data directory if needed"""
        try:
            exe_data_dir = os.path.join(exe_dir, 'data')
            exe_history_dir = os.path.join(exe_dir, 'history')
            
            # Check if we can access the exe directory
            try:
                os.listdir(exe_dir)
            except PermissionError:
                print(f"🔍 DEBUG: No read access to exe directory: {exe_dir}")
                return
            
            if not os.path.exists(exe_data_dir) and not os.path.exists(exe_history_dir):
                return  # No data to migrate
            
            print(f"🔍 DEBUG: Migrating data from {exe_dir} to {user_data_dir}")
            
            # Create user data directories
            user_data_data_dir = os.path.join(user_data_dir, 'data')
            user_data_history_dir = os.path.join(user_data_dir, 'history')
            os.makedirs(user_data_data_dir, exist_ok=True)
            os.makedirs(user_data_history_dir, exist_ok=True)
            
            # Migrate data directory
            if os.path.exists(exe_data_dir):
                import shutil
                for item in os.listdir(exe_data_dir):
                    src = os.path.join(exe_data_dir, item)
                    dst = os.path.join(user_data_data_dir, item)
                    if os.path.isfile(src) and not os.path.exists(dst):
                        shutil.copy2(src, dst)
                        print(f"🔍 DEBUG: Migrated file: {item}")
            
            # Migrate history directory
            if os.path.exists(exe_history_dir):
                import shutil
                for item in os.listdir(exe_history_dir):
                    src = os.path.join(exe_history_dir, item)
                    dst = os.path.join(user_data_history_dir, item)
                    if os.path.isdir(src) and not os.path.exists(dst):
                        shutil.copytree(src, dst)
                        print(f"🔍 DEBUG: Migrated history folder: {item}")
            
            print(f"✅ Data migration completed")
            
        except Exception as e:
            print(f"⚠️ Error during data migration: {e}")
            # Don't raise the error, just log it
    
    def setup_ui(self):
        self.setup_style()
        self.load_default_text()

        # Background analysis finished handler is now properly defined as a method

        # Onboarding tooltips are shown after a successful login

    def maybe_show_welcome_tooltip(self):
        # Legacy tooltip disabled in favor of coachmark
        return

    def maybe_show_create_coachmark(self):
        try:
            if not self.settings.get('show_welcome_tooltip', True):
                # respect user's choice to not show onboarding; skip coachmark as well
                return
            # Find sidebar and its create button
            if hasattr(self, 'sidebar') and self.sidebar:
                # The first button after logo is Create; capture it by text
                btn = None
                for child in self.sidebar.findChildren(QPushButton):
                    if child.text().strip().lower() == 'create':
                        btn = child
                        break
                if not btn:
                    return

                # Dark overlay across the window with a clear hole over the Create button
                self._coach_overlay = QWidget(self)
                self._coach_overlay.setObjectName('coach_overlay')
                self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
                self._coach_overlay.setStyleSheet("background: rgba(0,0,0,0.55);")
                self._coach_overlay.show()
                self._coach_overlay.raise_()

                # Keep overlay full-size on resize
                def keep_overlay():
                    try:
                        if hasattr(self, '_coach_overlay') and self._coach_overlay:
                            self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
                            # Create transparent hole over the Create button
                            btn_pos = btn.mapTo(self, QPoint(0, 0))
                            hole_rect = QRect(btn_pos.x() - 8, btn_pos.y() - 6, btn.width() + 16, btn.height() + 12)
                            try:
                                from PyQt6.QtGui import QRegion
                                full = QRegion(self._coach_overlay.rect())
                                hole = QRegion(hole_rect)
                                self._coach_overlay.setMask(full.subtracted(hole))
                            except Exception:
                                pass
                    except Exception:
                        pass
                self.installEventFilter(self)
                QTimer.singleShot(0, keep_overlay)

                # Pointer GIF near Create button as a top-level transparent window (always above overlay)
                pointer_label = QLabel(None)
                pointer_label.setObjectName('coach_pointer')
                # Ensure label background is fully transparent
                try:
                    pointer_label.setAutoFillBackground(False)
                except Exception:
                    pass
                try:
                    pointer_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
                except Exception:
                    pass
                try:
                    pointer_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                except Exception:
                    pass
                pointer_label.setStyleSheet("background: transparent;")
                try:
                    pointer_label.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                    pointer_label.setWindowFlag(Qt.WindowType.Tool, True)
                    pointer_label.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                except Exception:
                    pass
                pointer_movie = QMovie(os.path.abspath('ui/assets/pointer.gif'))
                pointer_movie.setCacheMode(QMovie.CacheMode.CacheAll)
                pointer_movie.setSpeed(100)
                # Drive animation manually to allow white background removal
                def _update_pointer_frame():
                    try:
                        pix = pointer_movie.currentPixmap()
                        if pix.isNull():
                            return
                        img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                        w = img.width()
                        h = img.height()
                        # Make near-white pixels transparent
                        for y in range(h):
                            for x in range(w):
                                c = QColor(img.pixel(x, y))
                                if c.red() > 250 and c.green() > 250 and c.blue() > 250:
                                    img.setPixelColor(x, y, QColor(255, 255, 255, 0))
                        scaled = QPixmap.fromImage(img).scaled(pointer_label.width() or 64, pointer_label.height() or 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        pointer_label.setPixmap(scaled)
                    except Exception:
                        pass
                try:
                    pointer_movie.frameChanged.connect(lambda _=None: _update_pointer_frame())
                except Exception:
                    pass
                pointer_movie.start()
                _update_pointer_frame()
                pointer_label.show()
                # Keep references to prevent garbage collection
                self._coach_pointer_movie = pointer_movie
                self._coach_pointer_label = pointer_label
                try:
                    pointer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                except Exception:
                    pass

                # Caption next to pointer as a top-level transparent window
                caption = QLabel("Click Create to analyze your content.", None)
                caption.setStyleSheet("color: white; background: transparent; font-size: 24px; font-weight: 700; font-family: 'Poppins', 'Arial', sans-serif;")
                try:
                    from PyQt6.QtGui import QFont
                    weight = QFont.Weight.DemiBold
                    caption.setFont(QFont("Poppins", 20, weight))
                except Exception:
                    pass
                self._coach_caption = caption
                try:
                    caption.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                    caption.setWindowFlag(Qt.WindowType.Tool, True)
                    caption.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                except Exception:
                    pass
                caption.show()
                try:
                    caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                except Exception:
                    pass
                # Add subtle shadow to improve readability over mixed backgrounds
                try:
                    shadow = QGraphicsDropShadowEffect(caption)
                    shadow.setBlurRadius(12)
                    shadow.setOffset(0, 2)
                    shadow.setColor(QColor(0, 0, 0, 180))
                    caption.setGraphicsEffect(shadow)
                except Exception:
                    pass

                # Top-level windows already above overlay; no stacking needed

                # Position pointer to the right of the button
                def position_pointer():
                    try:
                        btn_pos_global = btn.mapToGlobal(QPoint(0, 0))
                        btn_rect = QRectF(btn_pos_global.x(), btn_pos_global.y(), btn.width(), btn.height())
                        # Position pointer centered over the Create button and enlarge slightly
                        px = int(btn_rect.center().x() - 32)
                        offset_y = 32  # move further down
                        py = int(btn_rect.center().y() - 32 + offset_y)
                        pointer_movie.setScaledSize(QSize(64, 64))
                        pointer_label.setFixedSize(64, 64)
                        pointer_label.move(px, py)
                        # Place caption to the right of the pointer
                        caption.move(px + 72, py + 20)
                        # Keep z-order: pointer/caption above overlay
                        try:
                            caption.raise_()
                            pointer_label.raise_()
                        except Exception:
                            pass
                        # Rebuild the mask so the button remains visible and colored
                        keep_overlay()
                    except Exception:
                        pass
                position_pointer()
                QTimer.singleShot(0, position_pointer)

                # Helper to close create-step coachmark
                def close_coachmark():
                    try:
                        if hasattr(self, '_coach_overlay') and self._coach_overlay:
                            self._coach_overlay.hide()
                            self._coach_overlay.deleteLater()
                            self._coach_overlay = None
                            # Release refs
                            try:
                                if getattr(self, '_coach_pointer_label', None):
                                    self._coach_pointer_label.close()
                                    self._coach_pointer_label.deleteLater()
                            except Exception:
                                pass
                            try:
                                if getattr(self, '_coach_caption', None):
                                    self._coach_caption.close()
                                    self._coach_caption.deleteLater()
                            except Exception:
                                pass
                            self._coach_pointer_movie = None
                            self._coach_pointer_label = None
                            self._coach_caption = None
                    except Exception:
                        pass
                # Require pressing the Create button to advance
                def _proceed_from_create():
                    try:
                        close_coachmark()
                        if getattr(self, '_tour_active', False):
                            QTimer.singleShot(300, self.show_textbox_coachmark)
                    except Exception:
                        pass
                try:
                    btn.clicked.connect(_proceed_from_create)
                except Exception:
                    pass

                # Ignore overlay clicks (do not close or advance)
                try:
                    self._coach_overlay.mousePressEvent = lambda _e=None: None
                except Exception:
                    pass
        except Exception:
            pass

    def hide_coachmark(self):
        """Hide any active coachmark elements (overlay, pointer, caption)."""
        try:
            if hasattr(self, '_coach_overlay') and self._coach_overlay:
                try:
                    self._coach_overlay.hide()
                    self._coach_overlay.deleteLater()
                except Exception:
                    pass
                self._coach_overlay = None
            if hasattr(self, '_coach_pointer_label') and self._coach_pointer_label:
                try:
                    self._coach_pointer_label.close()
                    self._coach_pointer_label.deleteLater()
                except Exception:
                    pass
                self._coach_pointer_label = None
            if hasattr(self, '_coach_caption') and self._coach_caption:
                try:
                    self._coach_caption.close()
                    self._coach_caption.deleteLater()
                except Exception:
                    pass
                self._coach_caption = None
            self._coach_pointer_movie = None
        except Exception:
            pass

    def show_textbox_coachmark(self):
        """Show a coachmark pointing to the main text input box with a dark overlay that excludes the textbox area."""
        try:
            # Ensure text_input exists
            if not hasattr(self, 'text_input') or not self.text_input:
                return

            target = self.text_input
            # Create dark overlay over the whole window with a hole over the text box
            # Before creating a new textbox overlay, remove any previous remnants
            try:
                if getattr(self, '_coach_overlay', None) and getattr(self._coach_overlay, 'objectName', lambda: '')() == 'coach_overlay_text':
                    self._coach_overlay.hide()
                    self._coach_overlay.deleteLater()
                    self._coach_overlay = None
                if getattr(self, '_coach_pointer_label', None):
                    self._coach_pointer_label.close()
                    self._coach_pointer_label.deleteLater()
                    self._coach_pointer_label = None
                if getattr(self, '_coach_caption', None):
                    self._coach_caption.close()
                    self._coach_caption.deleteLater()
                    self._coach_caption = None
                self._coach_pointer_movie = None
            except Exception:
                pass

            self._coach_overlay = QWidget(self)
            self._coach_overlay.setObjectName('coach_overlay_text')
            self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
            self._coach_overlay.setStyleSheet("background: rgba(0,0,0,0.55);")
            self._coach_overlay.show()
            self._coach_overlay.raise_()

            def update_mask():
                try:
                    if not (hasattr(self, '_coach_overlay') and self._coach_overlay):
                        return
                    self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
                    wpos = target.mapTo(self, QPoint(0, 0))
                    padding = 8
                    hole_rect = QRect(wpos.x() - padding, wpos.y() - padding, target.width() + padding * 2, target.height() + padding * 2)
                    from PyQt6.QtGui import QRegion
                    full = QRegion(self._coach_overlay.rect())
                    hole = QRegion(hole_rect)
                    self._coach_overlay.setMask(full.subtracted(hole))
                except Exception:
                    pass
            QTimer.singleShot(0, update_mask)

            # Pointer as top-level window, positioned near the text box
            pointer_label = QLabel(None)
            pointer_label.setObjectName('coach_pointer_text')
            try:
                pointer_label.setAutoFillBackground(False)
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
            except Exception:
                pass
            pointer_label.setStyleSheet("background: transparent;")
            try:
                pointer_label.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                pointer_label.setWindowFlag(Qt.WindowType.Tool, True)
                pointer_label.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            pointer_movie = QMovie(os.path.abspath('ui/assets/pointer2.gif'))
            pointer_movie.setCacheMode(QMovie.CacheMode.CacheAll)
            pointer_movie.setSpeed(100)
            def _update_pointer_frame2():
                try:
                    pix = pointer_movie.currentPixmap()
                    if pix.isNull():
                        return
                    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                    w = img.width()
                    h = img.height()
                    for y in range(h):
                        for x in range(w):
                            c = QColor(img.pixel(x, y))
                            if c.red() > 250 and c.green() > 250 and c.blue() > 250:
                                img.setPixelColor(x, y, QColor(255, 255, 255, 0))
                    scaled = QPixmap.fromImage(img).scaled(pointer_label.width() or 64, pointer_label.height() or 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    pointer_label.setPixmap(scaled)
                except Exception:
                    pass
            try:
                pointer_movie.frameChanged.connect(lambda _=None: _update_pointer_frame2())
            except Exception:
                pass
            pointer_movie.start()
            pointer_label.show()
            self._coach_pointer_movie = pointer_movie
            self._coach_pointer_label = pointer_label
            try:
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            except Exception:
                pass

            # Caption as top-level near the text box
            caption = QLabel("Enter your text here to analyze.", None)
            try:
                caption.setObjectName('coach_caption_text')
            except Exception:
                pass
            caption.setStyleSheet("color: white; background: transparent; font-size: 24px; font-weight: 700; font-family: 'Poppins', 'Arial', sans-serif;")
            try:
                from PyQt6.QtGui import QFont
                weight = QFont.Weight.DemiBold
                caption.setFont(QFont("Poppins", 20, weight))
            except Exception:
                pass
            try:
                caption.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                caption.setWindowFlag(Qt.WindowType.Tool, True)
                caption.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            caption.show()
            self._coach_caption = caption
            try:
                caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                shadow = QGraphicsDropShadowEffect(caption)
                shadow.setBlurRadius(12)
                shadow.setOffset(0, 2)
                shadow.setColor(QColor(0, 0, 0, 180))
                caption.setGraphicsEffect(shadow)
            except Exception:
                pass

            def position_text_pointer():
                try:
                    gpos = target.mapToGlobal(QPoint(0, 0))
                    rect = QRectF(gpos.x(), gpos.y(), target.width(), target.height())
                    pointer_movie.setScaledSize(QSize(64, 64))
                    pointer_label.setFixedSize(64, 64)
                    # Keep caption above textbox
                    caption.move(int(rect.left()), int(rect.top() - 40))  # above textbox
                    try:
                        caption.adjustSize()
                    except Exception:
                        pass
                    # Place pointer GIF under the caption, centered
                    pcx = int(caption.x() + caption.width() / 2 - 32)
                    pcy = int(caption.y() + caption.height() + 8)
                    pointer_label.move(pcx, pcy)
                    caption.raise_()
                    pointer_label.raise_()
                    update_mask()
                except Exception:
                    pass
            position_text_pointer()
            QTimer.singleShot(0, position_text_pointer)

            # Clicking overlay closes this coachmark and fully cleans up
            def close_text_coach():
                try:
                    if hasattr(self, '_coach_overlay') and self._coach_overlay:
                        self._coach_overlay.hide()
                        self._coach_overlay.deleteLater()
                        self._coach_overlay = None
                    if hasattr(self, '_coach_pointer_label') and self._coach_pointer_label:
                        self._coach_pointer_label.close()
                        self._coach_pointer_label.deleteLater()
                        self._coach_pointer_label = None
                    if hasattr(self, '_coach_caption') and self._coach_caption:
                        self._coach_caption.close()
                        self._coach_caption.deleteLater()
                        self._coach_caption = None
                    self._coach_pointer_movie = None
                    # Ensure any stray text coachmark caption/pointer are removed
                    try:
                        if getattr(self, '_coach_pointer_label', None):
                            self._coach_pointer_label.close()
                            self._coach_pointer_label.deleteLater()
                            self._coach_pointer_label = None
                    except Exception:
                        pass
                    try:
                        if getattr(self, '_coach_caption', None):
                            self._coach_caption.close()
                            self._coach_caption.deleteLater()
                            self._coach_caption = None
                    except Exception:
                        pass
                    # After closing textbox coachmark, if tour active, proceed to Start Analysis step
                    if getattr(self, '_tour_active', False):
                        try:
                            self._start_coachmark_triggered = False
                            self._start_coachmark_shown = False
                        except Exception:
                            pass
                        QTimer.singleShot(0, self._try_show_start_button_coachmark_once)
                except Exception:
                    pass
            self._coach_overlay.mousePressEvent = lambda e: close_text_coach()
        except Exception:
            pass

    def _try_show_start_button_coachmark_once(self):
        """Attempt to show the Start Analysis coachmark when the button exists; retry if needed."""
        try:
            if getattr(self, '_start_coachmark_shown', False):
                return
            if hasattr(self, 'analyze_btn') and self.analyze_btn and self.analyze_btn.isVisible() and self.analyze_btn.width() > 0:
                self._start_coachmark_shown = True
                self.show_start_button_coachmark()
            else:
                # Retry shortly until UI is fully built
                QTimer.singleShot(500, self._try_show_start_button_coachmark_once)
        except Exception:
            pass

    def show_start_button_coachmark(self):
        """Show a coachmark for the Start Analysis button with dark overlay and pointer.gif."""
        try:
            if not hasattr(self, 'analyze_btn') or not self.analyze_btn:
                return
            btn = self.analyze_btn
            # Create dark overlay with a clear hole over the Start Analysis button
            self._coach_overlay = QWidget(self)
            self._coach_overlay.setObjectName('coach_overlay_start')
            self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
            self._coach_overlay.setStyleSheet("background: rgba(0,0,0,0.55);")
            self._coach_overlay.show()
            self._coach_overlay.raise_()

            def update_mask():
                try:
                    if not (hasattr(self, '_coach_overlay') and self._coach_overlay):
                        return
                    self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
                    wpos = btn.mapTo(self, QPoint(0, 0))
                    padding = 8
                    hole_rect = QRect(wpos.x() - padding, wpos.y() - padding, btn.width() + padding * 2, btn.height() + padding * 2)
                    from PyQt6.QtGui import QRegion
                    full = QRegion(self._coach_overlay.rect())
                    hole = QRegion(hole_rect)
                    self._coach_overlay.setMask(full.subtracted(hole))
                except Exception:
                    pass
            QTimer.singleShot(0, update_mask)

            # Pointer GIF near Start Analysis button
            pointer_label = QLabel(None)
            pointer_label.setObjectName('coach_pointer_start')
            try:
                pointer_label.setAutoFillBackground(False)
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                pointer_label.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                pointer_label.setWindowFlag(Qt.WindowType.Tool, True)
                pointer_label.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            pointer_label.setStyleSheet("background: transparent;")

            pointer_movie = QMovie(os.path.abspath('ui/assets/pointer.gif'))
            pointer_movie.setCacheMode(QMovie.CacheMode.CacheAll)
            pointer_movie.setSpeed(100)

            def _update_pointer_frame3():
                try:
                    pix = pointer_movie.currentPixmap()
                    if pix.isNull():
                        return
                    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                    w = img.width()
                    h = img.height()
                    for y in range(h):
                        for x in range(w):
                            c = QColor(img.pixel(x, y))
                            if c.red() > 250 and c.green() > 250 and c.blue() > 250:
                                img.setPixelColor(x, y, QColor(255, 255, 255, 0))
                    scaled = QPixmap.fromImage(img).scaled(pointer_label.width() or 64, pointer_label.height() or 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    pointer_label.setPixmap(scaled)
                except Exception:
                    pass
            try:
                pointer_movie.frameChanged.connect(lambda _=None: _update_pointer_frame3())
            except Exception:
                pass
            pointer_movie.start()
            pointer_label.show()
            self._coach_pointer_movie = pointer_movie
            self._coach_pointer_label = pointer_label
            try:
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            except Exception:
                pass

            # Caption under the pointer with same visual style as other coachmarks
            caption = QLabel("Press Start Analysis to start the analysis.\nNote: This will use 1 of your analysis credits. Click anywhere to skip the tour.", None)
            caption.setStyleSheet("color: white; background: transparent; font-size: 24px; font-weight: 700; font-family: 'Poppins', 'Arial', sans-serif;")
            try:
                from PyQt6.QtGui import QFont
                weight = QFont.Weight.DemiBold
                caption.setFont(QFont("Poppins", 20, weight))
            except Exception:
                pass
            # Constrain caption width and enable wrapping so it doesn't overflow the screen
            try:
                caption.setWordWrap(True)
                max_caption_width = min(700, int(self.width() * 0.75))
                caption.setFixedWidth(max_caption_width)
            except Exception:
                pass
            try:
                caption.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                caption.setWindowFlag(Qt.WindowType.Tool, True)
                caption.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            caption.show()
            self._coach_caption = caption
            try:
                caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                shadow = QGraphicsDropShadowEffect(caption)
                shadow.setBlurRadius(12)
                shadow.setOffset(0, 2)
                shadow.setColor(QColor(0, 0, 0, 180))
                caption.setGraphicsEffect(shadow)
            except Exception:
                pass

            def position_start_pointer():
                try:
                    if not btn.isVisible() or btn.width() <= 0:
                        return
                    gpos = btn.mapToGlobal(QPoint(0, 0))
                    rect = QRectF(gpos.x(), gpos.y(), btn.width(), btn.height())
                    pointer_movie.setScaledSize(QSize(64, 64))
                    pointer_label.setFixedSize(64, 64)
                    # Place pointer above the Start Analysis button
                    px = int(rect.center().x() - 32)
                    py = int(rect.bottom() + 8)
                    pointer_label.move(px, py)
                    # Place caption under the pointer, centered
                    try:
                        caption.adjustSize()
                    except Exception:
                        pass
                    cx = int(px + 32 - (caption.width() // 2) - 24)
                    cy = int(py + 64 + 8)
                    # Clamp caption position to stay within the window bounds
                    try:
                        cx = max(8, min(cx, self.width() - caption.width() - 8))
                        cy = max(8, min(cy, self.height() - caption.height() - 8))
                    except Exception:
                        pass
                    caption.move(cx, cy)
                    try:
                        caption.raise_()
                    except Exception:
                        pass
                    pointer_label.raise_()
                except Exception:
                    pass
            position_start_pointer()
            QTimer.singleShot(0, position_start_pointer)
            QTimer.singleShot(300, position_start_pointer)
            QTimer.singleShot(800, position_start_pointer)
            QTimer.singleShot(0, update_mask)
            QTimer.singleShot(300, update_mask)
            QTimer.singleShot(800, update_mask)

            # Clicking anywhere on the overlay should end the tour immediately
            def _end_tour_from_start_coachmark():
                try:
                    if hasattr(self, '_coach_pointer_label') and self._coach_pointer_label:
                        self._coach_pointer_label.close()
                        self._coach_pointer_label.deleteLater()
                        self._coach_pointer_label = None
                    self._coach_pointer_movie = None
                    if hasattr(self, '_coach_caption') and self._coach_caption:
                        try:
                            self._coach_caption.close()
                            self._coach_caption.deleteLater()
                        except Exception:
                            pass
                        self._coach_caption = None
                    if hasattr(self, '_coach_overlay') and self._coach_overlay:
                        self._coach_overlay.hide()
                        self._coach_overlay.deleteLater()
                        self._coach_overlay = None
                    # End the tour and prevent proceeding to results coachmark
                    try:
                        self._tour_active = False
                    except Exception:
                        pass
                except Exception:
                    pass

            try:
                self._coach_overlay.mousePressEvent = lambda e: _end_tour_from_start_coachmark()
            except Exception:
                pass

            # Auto-hide when Start Analysis is clicked, or after 6 seconds
            def _hide_pointer_only():
                try:
                    if hasattr(self, '_coach_pointer_label') and self._coach_pointer_label:
                        self._coach_pointer_label.close()
                        self._coach_pointer_label.deleteLater()
                        self._coach_pointer_label = None
                    self._coach_pointer_movie = None
                    if hasattr(self, '_coach_caption') and self._coach_caption:
                        try:
                            self._coach_caption.close()
                            self._coach_caption.deleteLater()
                        except Exception:
                            pass
                        self._coach_caption = None
                    if hasattr(self, '_coach_overlay') and self._coach_overlay:
                        self._coach_overlay.hide()
                        self._coach_overlay.deleteLater()
                        self._coach_overlay = None
                    # Proceed to results coachmark if tour is active
                    if getattr(self, '_tour_active', False):
                        try:
                            QTimer.singleShot(300, self.show_results_coachmark)
                        except Exception:
                            pass
                except Exception:
                    pass

            try:
                self.analyze_btn.clicked.connect(_hide_pointer_only)
            except Exception:
                pass
        except Exception:
            pass

    def show_results_coachmark(self):
        """Show a coachmark using pointer2.gif pointing to the Analysis Results area after starting analysis."""
        try:
            # Guard: only during tour
            if not getattr(self, '_tour_active', False):
                return
            # Determine the current results content box (the whole grid area, not just the label)
            if not hasattr(self, 'tab_widget'):
                return
            tab_index = self.tab_widget.currentIndex()
            if tab_index == 0 and hasattr(self, 'stock_images_tab'):
                tab_widget = self.stock_images_tab
            elif tab_index == 1 and hasattr(self, 'stock_videos_tab'):
                tab_widget = self.stock_videos_tab
            else:
                tab_widget = getattr(self, 'ai_images_tab', None)
            if not tab_widget:
                return
            scroll_area = tab_widget.findChild(QScrollArea)
            if not scroll_area:
                return
            # Use the viewport so the hole matches the visible results box
            target = scroll_area.viewport()

            # Create dark overlay focusing the results header area
            self._coach_overlay = QWidget(self)
            self._coach_overlay.setObjectName('coach_overlay_results')
            self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
            self._coach_overlay.setStyleSheet("background: rgba(0,0,0,0.55);")
            self._coach_overlay.show()
            self._coach_overlay.raise_()

            def update_mask():
                try:
                    if not (hasattr(self, '_coach_overlay') and self._coach_overlay):
                        return
                    self._coach_overlay.setGeometry(0, 0, self.width(), self.height())
                    wpos = target.mapTo(self, QPoint(0, 0))
                    padding = 10
                    hole_rect = QRect(wpos.x() - padding, wpos.y() - padding, target.width() + padding * 2, target.height() + padding * 2)
                    from PyQt6.QtGui import QRegion
                    full = QRegion(self._coach_overlay.rect())
                    hole = QRegion(hole_rect)
                    self._coach_overlay.setMask(full.subtracted(hole))
                except Exception:
                    pass
            QTimer.singleShot(0, update_mask)

            # Pointer2 gif near the results box
            pointer_label = QLabel(None)
            pointer_label.setObjectName('coach_pointer_results')
            try:
                pointer_label.setAutoFillBackground(False)
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
                pointer_label.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                pointer_label.setWindowFlag(Qt.WindowType.Tool, True)
                pointer_label.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            pointer_label.setStyleSheet("background: transparent;")

            pointer_movie = QMovie(os.path.abspath('ui/assets/pointer2.gif'))
            pointer_movie.setCacheMode(QMovie.CacheMode.CacheAll)
            pointer_movie.setSpeed(100)

            def _update_pointer_frame_results():
                try:
                    pix = pointer_movie.currentPixmap()
                    if pix.isNull():
                        return
                    img = pix.toImage().convertToFormat(QImage.Format.Format_ARGB32)
                    w = img.width()
                    h = img.height()
                    for y in range(h):
                        for x in range(w):
                            c = QColor(img.pixel(x, y))
                            if c.red() > 250 and c.green() > 250 and c.blue() > 250:
                                img.setPixelColor(x, y, QColor(255, 255, 255, 0))
                    scaled = QPixmap.fromImage(img).scaled(pointer_label.width() or 64, pointer_label.height() or 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    pointer_label.setPixmap(scaled)
                except Exception:
                    pass
            try:
                pointer_movie.frameChanged.connect(lambda _=None: _update_pointer_frame_results())
            except Exception:
                pass
            pointer_movie.start()
            pointer_label.show()
            self._coach_pointer_movie = pointer_movie
            self._coach_pointer_label = pointer_label
            try:
                pointer_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            except Exception:
                pass

            # Caption for results
            caption = QLabel("Your analysis results will be displayed here. After the process is complete, you may choose and download any suggestion you wish.", None)
            caption.setStyleSheet("color: white; background: transparent; font-size: 24px; font-weight: 700; font-family: 'Poppins', 'Arial', sans-serif;")
            try:
                from PyQt6.QtGui import QFont
                weight = QFont.Weight.DemiBold
                caption.setFont(QFont("Poppins", 20, weight))
            except Exception:
                pass
            # Constrain caption width and enable wrapping for long content
            try:
                caption.setWordWrap(True)
                max_caption_width = min(700, int(self.width() * 0.75))
                caption.setFixedWidth(max_caption_width)
            except Exception:
                pass
            try:
                caption.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
                caption.setWindowFlag(Qt.WindowType.Tool, True)
                caption.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            caption.show()
            self._coach_caption = caption
            try:
                caption.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                shadow = QGraphicsDropShadowEffect(caption)
                shadow.setBlurRadius(12)
                shadow.setOffset(0, 2)
                shadow.setColor(QColor(0, 0, 0, 180))
                caption.setGraphicsEffect(shadow)
            except Exception:
                pass

            def position_results_pointer():
                try:
                    if not target.isVisible() or target.width() <= 0:
                        return
                    gpos = target.mapToGlobal(QPoint(0, 0))
                    rect = QRectF(gpos.x(), gpos.y(), target.width(), target.height())
                    pointer_movie.setScaledSize(QSize(64, 64))
                    pointer_label.setFixedSize(64, 64)
                    # Place pointer ABOVE the results box, centered
                    px = int(rect.center().x() - 32)
                    py = int(rect.top() - 72)
                    pointer_label.move(px, py)
                    try:
                        caption.adjustSize()
                    except Exception:
                        pass
                    # Place caption ABOVE the pointer, centered
                    cx = int(rect.center().x() - (caption.width() // 2))
                    cy = int(py - caption.height() - 8)
                    # Clamp caption position within window bounds
                    try:
                        cx = max(8, min(cx, self.width() - caption.width() - 8))
                        cy = max(8, min(cy, self.height() - caption.height() - 8))
                    except Exception:
                        pass
                    caption.move(cx, cy)
                    try:
                        caption.raise_()
                        pointer_label.raise_()
                    except Exception:
                        pass
                    update_mask()
                except Exception:
                    pass
            position_results_pointer()
            QTimer.singleShot(0, position_results_pointer)
            QTimer.singleShot(300, position_results_pointer)
            QTimer.singleShot(800, position_results_pointer)
            QTimer.singleShot(0, update_mask)
            QTimer.singleShot(300, update_mask)
            QTimer.singleShot(800, update_mask)

            # Close results coachmark on any click to continue
            def close_results_coachmark():
                try:
                    if hasattr(self, '_coach_overlay') and self._coach_overlay:
                        self._coach_overlay.hide()
                        self._coach_overlay.deleteLater()
                        self._coach_overlay = None
                    if hasattr(self, '_coach_pointer_label') and self._coach_pointer_label:
                        self._coach_pointer_label.close()
                        self._coach_pointer_label.deleteLater()
                        self._coach_pointer_label = None
                    if hasattr(self, '_coach_caption') and self._coach_caption:
                        self._coach_caption.close()
                        self._coach_caption.deleteLater()
                        self._coach_caption = None
                    self._coach_pointer_movie = None
                    # End tour after results coachmark
                    try:
                        self._tour_active = False
                    except Exception:
                        pass
                except Exception:
                    pass
            try:
                self._coach_overlay.mousePressEvent = lambda e: close_results_coachmark()
            except Exception:
                pass
        except Exception:
            pass

    # -------------------------- Navigation helpers --------------------------
    def _is_scene_ready(self, index: int) -> bool:
        """Return True if scene analysis and lazy media are ready for the given index."""
        try:
            if not self.scenes_data or index < 0 or index >= len(self.scenes_data):
                return False
            analyzed = bool(self.scenes_data[index].get('analyzed', False))
            state = self.scene_loading_states.get(index, 'pending')
            return analyzed and state == 'ready'
        except Exception:
            return False

    def _is_scene_analyzing(self, index: int) -> bool:
        """Return True if scene ANALYSIS is not finished.

        We DO NOT block navigation for lazy media loading states; only for
        scenes whose textual analysis hasn't been produced yet.
        """
        try:
            if not self.scenes_data or index < 0 or index >= len(self.scenes_data):
                return False
            
            # Check if scene is analyzed
            analyzed = bool(self.scenes_data[index].get('analyzed', False))
            
            # Also check loading state - if it's 'loading', it's still analyzing
            loading_state = self.scene_loading_states.get(index, 'pending')
            
            # Scene is analyzing if either not analyzed OR currently loading
            return not analyzed or loading_state == 'loading'
        except Exception:
            return False

    def _update_navigation_buttons(self) -> None:
        """Enable/disable navigation according to current scene readiness.

        Requirement: If current scene shows "Analyzing...", user should not be able
        to progress forward. Background analysis continues.
        """
        try:
            # While a navigation update is in-flight, disable both buttons to avoid reentrancy
            if getattr(self, '_nav_locked', False):
                self.prev_btn.setEnabled(False)
                self.next_btn.setEnabled(False)
                return
            analyzing = self._is_scene_analyzing(self.current_scene_index)
            # Allow going back anytime; block forward while analyzing
            self.prev_btn.setEnabled(self.current_scene_index > 0)
            self.next_btn.setEnabled((self.current_scene_index < len(self.scenes_data) - 1) and (not analyzing))
        except Exception:
            # Fallback to original behavior
            self.prev_btn.setEnabled(self.current_scene_index > 0)
            self.next_btn.setEnabled(self.current_scene_index < len(self.scenes_data) - 1)

    def _debounce_navigation(self) -> bool:
        """Return True if enough time has passed since the last navigation action."""
        try:
            import time as _time
            now = _time.monotonic() if hasattr(_time, 'monotonic') else _time.time()
        except Exception:
            now = 0.0
        last = getattr(self, '_last_nav_at', 0.0) or 0.0
        # 150ms debounce window to absorb rapid clicks/keys
        if now and (now - last) < 0.15:
            return False
        self._last_nav_at = now
        return True
    
    def load_custom_fonts(self):
        """Load custom fonts safely"""
        from PyQt6.QtGui import QFontDatabase
        
    def maybe_show_welcome_tour(self):
        """Show welcome tour prompt if user hasn't disabled it (English content)."""
        try:
            # Respect setting if already opted out
            dont_show = False
            try:
                from logic.user_config import UserConfig
                cfg = UserConfig()
                dont_show = bool(cfg.get_setting('show_welcome_tour_disabled', False))
            except Exception:
                pass
            if dont_show:
                return

            # Prevent showing the welcome tour more than once per session
            try:
                if getattr(self, '_welcome_tour_shown', False):
                    return
                self._welcome_tour_shown = True
            except Exception:
                pass

            dlg = QDialog(self)
            dlg.setWindowTitle("Welcome")
            dlg.setModal(True)
            dlg.setWindowFlags(dlg.windowFlags() | Qt.WindowType.FramelessWindowHint)
            try:
                dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
            except Exception:
                pass
            dlg.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            try:
                dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
            except Exception:
                pass

            container = QWidget(dlg)
            container.setStyleSheet(
                """
                QWidget {
                    background: white;
                    border-radius: 16px;
                    border: none;
                }
                """
            )
            layout = QVBoxLayout(container)
            layout.setContentsMargins(24, 24, 24, 24)
            layout.setSpacing(16)

            title = QLabel("Welcome to StuckAI")
            try:
                if hasattr(self, 'loaded_fonts') and ("Poppins" in self.loaded_fonts or "Poppins SemiBold" in self.loaded_fonts):
                    title.setFont(QFont("Poppins", 22, QFont.Weight.DemiBold))
                else:
                    title.setFont(QFont("Arial", 22, QFont.Weight.DemiBold))
            except Exception:
                try:
                    title.setFont(QFont("Arial", 22, QFont.Weight.DemiBold))
                except Exception:
                    pass
            title.setStyleSheet("color: #111827;")
            try:
                title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            except Exception:
                pass
            layout.addWidget(title)

            desc = QLabel("Welcome! We'll show you a quick tour to help you learn the app faster. You can skip it if you prefer.")
            desc.setWordWrap(True)
            try:
                if hasattr(self, 'loaded_fonts') and ("Inter 24pt" in self.loaded_fonts or "Inter" in self.loaded_fonts):
                    desc.setFont(QFont("Inter 24pt", 15))
                else:
                    desc.setFont(QFont("Arial", 15))
            except Exception:
                try:
                    desc.setFont(QFont("Arial", 15))
                except Exception:
                    pass
            desc.setStyleSheet("color: #6B7280;")
            layout.addWidget(desc)

            # Buttons row
            buttons_row = QHBoxLayout()
            buttons_row.addStretch()

            start_btn = QPushButton("Start Tour")
            start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            start_btn.setFixedHeight(36)
            start_btn.setStyleSheet(
                """
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #6366F1, stop:1 #8B5CF6);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 0 16px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5B5BF7, stop:1 #7C3AED);
                }
                """
            )
            try:
                start_btn.setAutoDefault(False)
                start_btn.setDefault(False)
            except Exception:
                pass
            # (moved to bottom bar)

            skip_btn = QPushButton("Skip Tour")
            skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            skip_btn.setFixedHeight(36)
            skip_btn.setStyleSheet(
                """
                QPushButton {
                    background: transparent;
                    color: #374151;
                    border: 1px solid #D1D5DB;
                    border-radius: 8px;
                    padding: 0 16px;
                    font-weight: 600;
                }
                QPushButton:hover {
                    background: #F3F4F6;
                }
                """
            )
            try:
                skip_btn.setAutoDefault(False)
                skip_btn.setDefault(False)
            except Exception:
                pass
            # (moved to bottom bar)
            # Add a stretch to push bottom bar to the bottom; buttons will be placed in bottom bar later
            layout.addStretch()

            # Bottom bar: checkbox on the left, Start/Skip buttons on the right
            dont_show_again = QCheckBox("Don't show again")
            dont_show_again.setCursor(Qt.CursorShape.PointingHandCursor)
            try:
                dont_show_again.setTristate(False)
            except Exception:
                pass
            dont_show_again.setStyleSheet(
                """
                QCheckBox { 
                    color: #6B7280; 
                    spacing: 8px;
                    background: transparent;
                }
                QCheckBox::indicator {
                    width: 18px; height: 18px;
                    border-radius: 4px;
                    border: 1px solid #D1D5DB;
                    background: #FFFFFF;
                }
                QCheckBox::indicator:hover {
                    border-color: #9CA3AF;
                }
                QCheckBox::indicator:checked {
                    background-color: #6366F1;
                    border-color: #6366F1;
                    image: none;
                }
                """
            )
            bottom_bar = QHBoxLayout()
            bottom_bar.setContentsMargins(0, 0, 0, 0)
            bottom_bar.setSpacing(10)
            bottom_bar.addWidget(dont_show_again)
            bottom_bar.addStretch()
            bottom_bar.addWidget(start_btn)
            bottom_bar.addWidget(skip_btn)
            layout.addLayout(bottom_bar)

            # Dialog layout
            outer = QVBoxLayout(dlg)
            outer.setContentsMargins(0, 0, 0, 0)
            outer.addWidget(container)

            # Ensure tour starts only after dialog fully finishes
            try:
                self._welcome_tour_start_requested = False
            except Exception:
                pass

            def _on_dialog_finished(_result:int=0):
                try:
                    if getattr(self, '_welcome_tour_start_requested', False):
                        try:
                            self._welcome_tour_start_requested = False
                        except Exception:
                            pass
                        QTimer.singleShot(0, self.maybe_show_create_coachmark)
                except Exception:
                    pass
            try:
                dlg.finished.connect(_on_dialog_finished)
            except Exception:
                pass

            def _persist_disable(disable: bool):
                try:
                    from logic.user_config import UserConfig
                    cfg = UserConfig()
                    if disable:
                        cfg.set_setting('show_welcome_tour_disabled', True)
                except Exception:
                    pass

            def _start_tour():
                try:
                    checked = bool(dont_show_again.isChecked())
                except Exception:
                    checked = False
                _persist_disable(checked)
                try:
                    self._tour_active = True
                except Exception:
                    pass
                # Close dialog immediately and flush events, then start coachmark
                try:
                    start_btn.setEnabled(False)
                    skip_btn.setEnabled(False)
                except Exception:
                    pass
                try:
                    self._welcome_tour_start_requested = True
                except Exception:
                    pass
                # Close dialog immediately by accepting result; tour will start after dialog finishes
                try:
                    from PyQt6.QtWidgets import QDialog as _QDialog
                    dlg.done(int(_QDialog.DialogCode.Accepted))
                except Exception:
                    pass
                try:
                    dlg.accept()
                except Exception:
                    pass
                try:
                    dlg.hide()
                    dlg.close()
                except Exception:
                    pass

            def _skip():
                try:
                    checked = bool(dont_show_again.isChecked())
                except Exception:
                    checked = False
                _persist_disable(checked)
                # Close dialog immediately; ensure single-shot
                try:
                    start_btn.setEnabled(False)
                    skip_btn.setEnabled(False)
                except Exception:
                    pass
                try:
                    self._welcome_tour_start_requested = False
                except Exception:
                    pass
                try:
                    from PyQt6.QtWidgets import QDialog as _QDialog
                    dlg.done(int(_QDialog.DialogCode.Accepted))
                except Exception:
                    pass
                try:
                    dlg.accept()
                except Exception:
                    pass
                try:
                    dlg.hide()
                    dlg.close()
                except Exception:
                    pass

            start_btn.clicked.connect(_start_tour)
            skip_btn.clicked.connect(_skip)

            # Center and block input behind to ensure proper interaction
            dlg.resize(520, 220)
            try:
                dlg.setWindowModality(Qt.WindowModality.ApplicationModal)
            except Exception:
                pass
            try:
                dlg.raise_()
                dlg.activateWindow()
            except Exception:
                pass
            dlg.setFocus()
            dlg.exec()
        except Exception:
            pass
        self.loaded_fonts = []
        try:
            fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
            if os.path.exists(fonts_dir):
                for filename in os.listdir(fonts_dir):
                    if filename.lower().endswith(('.ttf', '.otf')):
                        font_path = os.path.join(fonts_dir, filename)
                        font_id = QFontDatabase.addApplicationFont(font_path)
                        if font_id != -1:
                            font_families = QFontDatabase.applicationFontFamilies(font_id)
                            self.loaded_fonts.extend(font_families)
        except Exception as e:
            self.loaded_fonts = []
    
    def load_settings_from_file(self):
        """Load settings from file"""
        try:
            import json
            settings_file = "data/settings.json"
            if os.path.exists(settings_file):
                with open(settings_file, 'r') as f:
                    loaded_settings = json.load(f)
                    # Update settings with loaded values, preserving defaults for missing keys
                    for key, value in loaded_settings.items():
                        self.settings[key] = value
                # Sanitize default_save_path: if file provided contains a path that doesn't
                # exist on this machine (e.g., another user's Desktop), replace with per-user default
                dsp = self.settings.get('default_save_path')
                if not dsp or not os.path.isdir(dsp):
                    self.settings['default_save_path'] = get_default_download_path()
        except Exception as e:
            pass
    
    def closeEvent(self, event):
        """Handle application close event - save history before closing"""
        try:
            # Clear all caches before closing
            if hasattr(self, 'scene_media_cache'):
                self.scene_media_cache.clear()
                print("Scene media cache cleared before closing")
            
            if hasattr(self, 'scene_loading_states'):
                self.scene_loading_states.clear()
                print("Scene loading states cleared before closing")
            
            if hasattr(self, 'background_analysis_threads'):
                self.background_analysis_threads.clear()
                print("Background analysis threads cleared before closing")
            
            # Clear credits cache
            if hasattr(self, '_credits_cache'):
                delattr(self, '_credits_cache')
            if hasattr(self, '_credits_cache_time'):
                delattr(self, '_credits_cache_time')
            
            self.save_history_to_file()
            self.save_downloads_history_to_file()
            print("History and downloads history saved before closing application")
        except Exception as e:
            print(f"Error saving history on close: {e}")
        
        event.accept()
        
    def setup_ui(self):
        """Setup main UI"""
        self.setWindowTitle("STUCK AI - Video Scene Creator")
        # Responsive sizing based on available screen geometry
        try:
            from PyQt6.QtGui import QGuiApplication
            available = QGuiApplication.primaryScreen().availableGeometry()
            screen_w = max(800, available.width())
            screen_h = max(600, available.height())
            # Cap minimum size to screen to avoid overflow on smaller displays
            min_w = min(1400, int(screen_w * 0.9))
            min_h = min(900, int(screen_h * 0.9))
            self.setMinimumSize(min_w, min_h)
            # Initial size scales with screen but never exceeds available area
            init_w = min(1750, int(screen_w * 0.95))
            init_h = min(950, int(screen_h * 0.95))
            self.resize(init_w, init_h)
        except Exception:
            # Fallback to previous defaults if screen info unavailable
            self.setMinimumSize(1400, 900)
            self.resize(1750, 950)
        
        # Set window icon
        icon_path = os.path.join(self.get_project_root(), "ui", "assets", "app.ico")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
        
        # Center window on screen
        self.center_window()
        
        # Central widget
        central_widget = QWidget()
        central_widget.setStyleSheet("""
            QWidget {
                background-color: #E5E7EB;
                border-radius: 20px;
            }
        """)
        self.setCentralWidget(central_widget)
        
        # Main horizontal layout with padding
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        central_widget.setLayout(main_layout)
        
        # Sidebar container with rounded corners
        sidebar_container = QWidget()
        sidebar_container.setStyleSheet("""
            QWidget {
                background-color: transparent;
            }
        """)
        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)
        sidebar_container.setLayout(sidebar_layout)
        
        # Add sidebar
        self.sidebar = Sidebar()
        self.sidebar.navigation_clicked.connect(self.on_sidebar_navigation)
        sidebar_layout.addWidget(self.sidebar)
        
        main_layout.addWidget(sidebar_container)
        
        # Content area with vertical layout and rounded corners
        content_widget = QWidget()
        content_widget.setStyleSheet("""
            QWidget {
                background-color: #F8F9FB;
                border-radius: 20px;
            }
        """)
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_widget.setLayout(content_layout)
        main_layout.addWidget(content_widget)
        
        # Top bar for content area (replaces header)
        self.create_top_bar(content_layout)
        
        # Main content area
        self.create_content_area(content_layout)
        
        # Status bar removed
        
        # Initialize with Home page
        self.show_page_content("home")
        
        # Delay plan display update to improve startup performance
        QTimer.singleShot(1000, self.delayed_plan_update)
    
    def delayed_plan_update(self):
        """Update plan display after startup delay"""
        if hasattr(self, 'sidebar'):
            QTimer.singleShot(100, self.sidebar.update_plan_display)
    
    def center_window(self):
        """Center the window on the screen"""
        # Use available geometry to respect taskbars/docks
        try:
            from PyQt6.QtGui import QGuiApplication
            ag = QGuiApplication.primaryScreen().availableGeometry()
            # Clamp current size to available area to prevent overflow
            clamped_w = min(self.width(), ag.width())
            clamped_h = min(self.height(), ag.height())
            if clamped_w != self.width() or clamped_h != self.height():
                self.resize(clamped_w, clamped_h)
            # Center within available rect
            x = ag.left() + max(0, (ag.width() - clamped_w) // 2)
            y = ag.top() + max(0, (ag.height() - clamped_h) // 2)
            self.move(x, y)
        except Exception:
            # Fallback using full screen geometry
            screen = QApplication.primaryScreen().geometry()
            window = self.geometry()
            x = (screen.width() - window.width()) // 2
            y = (screen.height() - window.height()) // 2
            self.move(x, y)
        
    def show_page_content(self, page_id: str):
        """Show different content based on selected page"""
        if page_id == "home":
            self.show_welcome_page()
        else:
            self.show_main_interface()
            
    def show_welcome_page(self):
        """Show AI POWERED STOCK FINDER welcome page"""
        # Hide top bar for Home page
        if hasattr(self, 'top_bar_widget'):
            self.top_bar_widget.hide()
            
        # Clear all existing widgets from content layout
        self.clear_content_layout()
        
        # Create and show welcome widget
        if not hasattr(self, 'welcome_widget') or self.welcome_widget is None:
            self.create_welcome_widget()
        
        # Start animation timer for welcome page
        if hasattr(self, 'animation_timer'):
            self.animation_timer.start(50)
            
        # Set main window background to match welcome gradient
        self.setStyleSheet("""
            MainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FFFFFF,
                    stop:0.2 #F0F9FF,
                    stop:0.4 #E0F2FE,
                    stop:0.6 #BAE6FD,
                    stop:0.8 #7DD3FC,
                    stop:1 #38BDF8);
            }
        """)
            
        # Make content widget transparent for welcome page
        if hasattr(self, 'content_widget'):
            self.content_widget.setStyleSheet("""
                QWidget {
                    background: transparent;
                    border: none;
                }
            """)
            # Set widget attributes to prevent gradient overflow
            self.content_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            self.content_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        
        # Remove margins for welcome page to fill entire content area
        if hasattr(self, 'content_layout'):
            self.content_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout.setSpacing(0)
        
        self.content_layout.addWidget(self.welcome_widget)
        self.welcome_widget.show()
        
    def show_main_interface(self):
        """Show main analysis interface"""
        # Stop animation timer when leaving welcome page
        if hasattr(self, 'animation_timer'):
            self.animation_timer.stop()
            
        # Show top bar for main interface
        if hasattr(self, 'top_bar_widget'):
            self.top_bar_widget.show()
            
        # Reset main window background to normal for non-welcome pages
        self.setStyleSheet("""
            MainWindow {
                background-color: #F8F9FB;
            }
        """)
            
        # Restore normal margins for main interface (consistent with welcome page)
        if hasattr(self, 'content_layout'):
            self.content_layout.setContentsMargins(32, 24, 32, 24)
            self.content_layout.setSpacing(32)
            
        # Reset content widget styling for main interface
        if hasattr(self, 'content_widget'):
            self.content_widget.setStyleSheet("""
                QWidget {
                    background-color: #F8F9FB;
                    border-radius: 20px;
                }
            """)
            
        # Clear all existing widgets from content layout
        self.clear_content_layout()
        
        # Update analysis credits when showing main interface
        self.load_user_analysis_credits()
        
        # Add and show main interface elements
        if hasattr(self, 'left_panel'):
            self.content_layout.addWidget(self.left_panel)
            self.left_panel.show()
        if hasattr(self, 'right_panel'):
            self.content_layout.addWidget(self.right_panel)
            self.right_panel.show()
    
    def show_ai_review_page(self):
        """Show AI Review page with video quality analysis"""
        # Show small centered loading overlay during page build
        try:
            self.show_loading_overlay("Opening AI Review…")
        except Exception:
            pass

        # Reset main window background
        self.setStyleSheet("""
            MainWindow {
                background-color: #F8F9FB;
            }
        """)
        
        # Hide header for premium full-screen experience
        if hasattr(self, 'top_bar_widget'):
            self.top_bar_widget.hide()
        
        # Keep consistent margins for all pages
        if hasattr(self, 'content_layout'):
            self.content_layout.setContentsMargins(32, 24, 32, 24)
            self.content_layout.setSpacing(32)
        
        # Clear all existing widgets from content layout
        self.clear_content_layout()
        
        # Update analysis credits when showing AI Review page
        self.load_user_analysis_credits()
        
        # Always create a fresh AI Review widget to avoid layout issues
        if hasattr(self, 'ai_review_widget') and self.ai_review_widget:
            self.ai_review_widget.deleteLater()
        
        self.create_premium_ai_review_widget()
        
        # Reset analysis content to initial state
        if hasattr(self, 'analysis_content'):
            self.analysis_content.setText("")
            self.analysis_content.setStyleSheet("""
                QLabel {
                    color: #6B7280;
                    background: transparent;
                    font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                    font-size: 14px;
                    padding: 20px;
                    border: none;
                    border-radius: 12px;
                    margin: 20px;
                }
            """)
            self.analysis_content.hide()
        
        # Remove dashboard if exists
        if hasattr(self, 'analysis_dashboard'):
            self.analysis_dashboard.hide()
            self.analysis_dashboard.deleteLater()
            delattr(self, 'analysis_dashboard')
        
        # Show upload container and features section when page is opened
        if hasattr(self, 'upload_container'):
            self.upload_container.show()
            print("📤 Upload container shown on page load")
        
        if hasattr(self, 'features_container'):
            self.features_container.show()
            print("📦 Features section shown on page load")
        
        self.content_layout.addWidget(self.ai_review_widget)
        self.ai_review_widget.show()

        # Hide loading overlay when ready
        try:
            QTimer.singleShot(1000, self.hide_loading_overlay)
        except Exception:
            try:
                self.hide_loading_overlay()
            except Exception:
                pass

    def _compute_loading_card_size(self) -> tuple[int, int]:
        """Compute a responsive loading card size based on window size."""
        try:
            w = max(320, self.width())
            h = max(240, self.height())
            # Target ~28% of width, clamp to sensible bounds
            target_w = int(w * 0.28)
            target_h = int(h * 0.18)
            card_w = min(520, max(280, target_w))
            card_h = min(260, max(160, target_h))
            return card_w, card_h
        except Exception:
            return 360, 200

    def show_loading_overlay(self, message: str = "Loading…"):
        """Show a modern full-window overlay with centered card."""
        try:
            # If already shown, just update text
            if hasattr(self, "_loading_overlay") and self._loading_overlay and self._loading_overlay.isVisible():
                label = self._loading_overlay.findChild(QLabel, "loading_message_label")
                if label:
                    label.setText(message)
                return

            # Full-window translucent overlay
            self._loading_overlay = QWidget(self)
            self._loading_overlay.setObjectName("loading_full_overlay")
            self._loading_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            self._loading_overlay.setGeometry(0, 0, self.width(), self.height())
            self._loading_overlay.setStyleSheet("background: rgba(17, 24, 39, 0.35);")

            # Center container (card)
            card = QWidget(self._loading_overlay)
            card.setObjectName("loading_card")
            cw, ch = self._compute_loading_card_size()
            card.resize(cw, ch)
            card.setStyleSheet(
                """
                QWidget {
                    background: white;
                    border-radius: 16px;
                    border: 1px solid rgba(229,231,235,0.8);
                }
                """
            )

            # Shadow effect
            try:
                shadow = QGraphicsDropShadowEffect(self._loading_overlay)
                shadow.setBlurRadius(30)
                shadow.setOffset(0, 10)
                shadow.setColor(QColor(0, 0, 0, 50))
                card.setGraphicsEffect(shadow)
            except Exception:
                pass

            # Layout for card
            layout = QVBoxLayout(card)
            layout.setContentsMargins(24, 20, 24, 20)
            layout.setSpacing(14)

            gif_label = QLabel()
            gif_label.setObjectName("loading_gif_label")
            gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            gif_label.setStyleSheet("background: transparent;")
            try:
                gif_path = os.path.abspath("ui/assets/Loading animation blue.gif")
                movie = QMovie(gif_path)
                # Use caching and scale down a bit to fit the card nicely
                movie.setCacheMode(QMovie.CacheMode.CacheAll)
                movie.setSpeed(100)
                gif_label.setMovie(movie)
                # Scale GIF to fit card while preserving aspect ratio
                try:
                    max_gif_w = min(360, max(120, cw - 96))
                    max_gif_h = min(120, max(80, ch - 90))
                    frame_rect = movie.frameRect()
                    orig_w = frame_rect.width() or 320
                    orig_h = frame_rect.height() or 320
                    scale_factor = min(max_gif_w / orig_w, max_gif_h / orig_h, 1.0)
                    target_w = max(64, int(orig_w * scale_factor))
                    target_h = max(64, int(orig_h * scale_factor))
                    movie.setScaledSize(QSize(target_w, target_h))
                    gif_label.setFixedSize(target_w, target_h)
                except Exception:
                    pass
                movie.start()
            except Exception:
                # Fallback to a static icon if GIF fails
                gif_label.setText("🔄")
                gif_label.setStyleSheet("color: #3B82F6; background: transparent;")
                gif_label.setFont(QFont("Arial", 28))
            layout.addWidget(gif_label, 0, Qt.AlignmentFlag.AlignHCenter)

            message_label = QLabel(message)
            message_label.setObjectName("loading_message_label")
            message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            message_label.setStyleSheet("color: #111827; background: transparent;")
            message_label.setFont(QFont("Inter", 13, QFont.Weight.Medium))
            layout.addWidget(message_label)

            progress = QProgressBar()
            progress.setRange(0, 0)
            progress.setFixedHeight(6)
            progress.setTextVisible(False)
            progress.setStyleSheet(
                """
                QProgressBar { border: none; background: #F3F4F6; border-radius: 4px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #60A5FA); border-radius: 4px; }
                """
            )
            layout.addWidget(progress)

            # Position card centered in overlay
            def center_card():
                try:
                    ow = self._loading_overlay.width()
                    oh = self._loading_overlay.height()
                    cw, ch = self._compute_loading_card_size()
                    card.resize(cw, ch)
                    # Slight right bias as requested
                    offset_x = 96
                    card.move(max(0, (ow - cw) // 2 + offset_x), max(0, (oh - ch) // 2))
                    # Rescale GIF if present to fit new card size
                    try:
                        lbl = self._loading_overlay.findChild(QLabel, "loading_gif_label")
                        if lbl is not None and lbl.movie() is not None:
                            movie = lbl.movie()
                            max_gif_w = min(360, max(120, cw - 96))
                            max_gif_h = min(120, max(80, ch - 90))
                            frame_rect = movie.frameRect()
                            orig_w = frame_rect.width() or 320
                            orig_h = frame_rect.height() or 320
                            scale_factor = min(max_gif_w / orig_w, max_gif_h / orig_h, 1.0)
                            target_w = max(64, int(orig_w * scale_factor))
                            target_h = max(64, int(orig_h * scale_factor))
                            movie.setScaledSize(QSize(target_w, target_h))
                            lbl.setFixedSize(target_w, target_h)
                            try:
                                layout.setAlignment(lbl, Qt.AlignmentFlag.AlignHCenter)
                            except Exception:
                                pass
                    except Exception:
                        pass
                except Exception:
                    pass

            center_card()
            self._loading_overlay.show()
            self._loading_overlay.raise_()
            QApplication.processEvents()
        except Exception:
            pass

    def hide_loading_overlay(self):
        """Hide the loading overlay if shown."""
        try:
            if hasattr(self, "_loading_overlay") and self._loading_overlay:
                try:
                    # Stop GIF movie if present
                    gif_label = self._loading_overlay.findChild(QLabel, "loading_gif_label")
                    if gif_label is not None and gif_label.movie() is not None:
                        gif_label.movie().stop()
                except Exception:
                    pass
                self._loading_overlay.hide()
                self._loading_overlay.deleteLater()
                self._loading_overlay = None
                QApplication.processEvents()
        except Exception:
            pass
    
    def show_history_page(self):
        """Show History page with analysis history"""
        # Hide top bar for history page (no need for Export, Download, Start Analysis buttons)
        if hasattr(self, 'top_bar_widget'):
            self.top_bar_widget.hide()
        
        # Set normal margins for history page
        if hasattr(self, 'content_layout'):
            self.content_layout.setContentsMargins(32, 24, 32, 24)
            self.content_layout.setSpacing(32)
        
        # Clear all existing widgets from content layout
        self.clear_content_layout()
        
        # Create and show History widget with real data
        if not hasattr(self, 'history_widget') or self.history_widget is None:
            self.history_widget = HistoryPage(parent=self, history_items=self.history_items)
        else:
            # Update existing widget with current data
            self.history_widget.update_history_data(self.history_items)
        
        self.content_layout.addWidget(self.history_widget)
        self.history_widget.show()
    
    def show_downloads_page(self):
        """Show downloads page"""
        # Clean up downloads history (remove duplicates and non-existent files)
        self.cleanup_downloads_history()
        
        # Hide top bar for downloads page (no need for Export, Download, Start Analysis buttons)
        if hasattr(self, 'top_bar_widget'):
            self.top_bar_widget.hide()
        
        # Set normal margins for downloads page
        if hasattr(self, 'content_layout'):
            self.content_layout.setContentsMargins(32, 24, 32, 24)
            self.content_layout.setSpacing(32)
        
        # Clear all existing widgets from content layout
        self.clear_content_layout()
        
        # Create and show downloads page
        if not hasattr(self, 'downloads_page') or self.downloads_page is None:
            # Load downloads data
            download_items = self.load_downloads_data()
            self.downloads_page = DownloadsPage(self, download_items)
            self.downloads_page.open_file_clicked.connect(self.open_downloaded_file)
            self.downloads_page.delete_file_clicked.connect(self.delete_downloaded_file)
        else:
            # Update existing downloads page with fresh data
            download_items = self.load_downloads_data()
            self.downloads_page.update_downloads_data(download_items)
        
        self.content_layout.addWidget(self.downloads_page)
        self.downloads_page.show()
    
    def show_info_page(self):
        """Show info/about page with program design"""
        # Hide top bar for info page
        if hasattr(self, 'top_bar_widget'):
            self.top_bar_widget.hide()
        
        # Set content widget background to match info page gradient
        if hasattr(self, 'content_widget'):
            self.content_widget.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 #FFFFFF,
                        stop:0.3 #F8F9FA,
                        stop:0.7 #F1F3F4,
                        stop:1 #E8EAED);
                    border: none;
                }
            """)
        
        # Remove margins for info page to fill entire content area
        if hasattr(self, 'content_layout'):
            self.content_layout.setContentsMargins(0, 0, 0, 0)
            self.content_layout.setSpacing(0)
        
        # Clear all existing widgets from content layout
        self.clear_content_layout()
        
        # Create and show info page
        if not hasattr(self, 'info_page') or self.info_page is None:
            self.create_info_widget()
        
        # Add with stretch so page expands to fill available height
        try:
            self.content_layout.addWidget(self.info_page, 1)
        except Exception:
            self.content_layout.addWidget(self.info_page)
        self.info_page.show()
    
    def create_info_widget(self):
        """Create clean and simple info page"""
        self.info_page = QWidget()
        # Ensure the info page expands to fill available space so vertical centering works
        try:
            self.info_page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        except Exception:
            pass
        self.info_page.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FFFFFF,
                    stop:0.3 #F8F9FA,
                    stop:0.7 #F1F3F4,
                    stop:1 #E8EAED);
                color: #1F2937;
            }
        """)
        
        # Main layout with centering
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self.info_page.setLayout(main_layout)
        
        # Top spacer will be inserted conditionally after screen size is known
        main_layout.addSpacing(0)
        
        # Content container with max width for better centering
        content_widget = QWidget()
        content_widget.setStyleSheet("""
            QWidget {
                background: transparent;
            }
        """)
        content_widget.setMaximumWidth(600)  # Limit width for better centering

        # Determine size variant based on current window width
        try:
            window_width = int(self.width()) if hasattr(self, 'width') else 1200
        except Exception:
            window_width = 1200
        size_variant = "small" if window_width < 1000 else "medium"
        is_laptop_or_smaller = window_width < 1600

        # Vertically center content for all sizes
        try:
            main_layout.insertStretch(0, 1)
        except Exception:
            main_layout.addSpacing(12)

        # Responsive content width based on window size
        try:
            max_width = 520 if size_variant == "small" else (680 if is_laptop_or_smaller else 820)
            content_widget.setMaximumWidth(max_width)
        except Exception:
            pass
        
        content_layout = QVBoxLayout()
        # More compact margins/spacing for laptop and smaller so features fit vertically
        if (size_variant == "small" or is_laptop_or_smaller):
            content_layout.setContentsMargins(24, 16, 24, 16)
            content_layout.setSpacing(20)
        else:
            content_layout.setContentsMargins(40, 40, 40, 40)
            content_layout.setSpacing(30)
        content_widget.setLayout(content_layout)
        
        # Header section
        header_layout = QVBoxLayout()
        header_layout.setSpacing(10 if (size_variant == "small" or is_laptop_or_smaller) else 16)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Logo container with right alignment
        logo_container = QWidget()
        logo_container_layout = QHBoxLayout()
        logo_container_layout.setContentsMargins(0, 0, 0, 0)
        logo_container_layout.setSpacing(0)
        
        # Add left spacer to push logo to the right
        logo_container_layout.addStretch()
        
        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        base_logo_size = 84 if (size_variant == "small" or is_laptop_or_smaller) else 100
        logo_label.setFixedSize(base_logo_size, base_logo_size)  # Smaller on laptop/small
        
        # Load login logo image
        logo_path = os.path.join(self.get_project_root(), "ui", "assets", "login_logo.png")
        if os.path.exists(logo_path):
            logo_pixmap = QPixmap(logo_path)
            if not logo_pixmap.isNull():
                # HiDPI-aware scaling for crisp login logo
                try:
                    screen = self.window().windowHandle().screen() if self.window() and self.window().windowHandle() else None
                    if screen is None:
                        from PyQt6.QtGui import QGuiApplication
                        screen = QGuiApplication.primaryScreen()
                    dpr = float(screen.devicePixelRatio()) if screen else 1.0
                    if dpr <= 0:
                        dpr = 1.0
                except Exception:
                    dpr = 1.0
                target_w, target_h = int(base_logo_size * dpr), int(base_logo_size * dpr)
                scaled_pixmap = logo_pixmap.scaled(
                    target_w, target_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                try:
                    scaled_pixmap.setDevicePixelRatio(dpr)
                except Exception:
                    pass
                logo_label.setPixmap(scaled_pixmap)
            else:
                # Fallback to emoji if logo loading fails
                logo_label.setText("⚡")
                logo_label.setFont(QFont("Arial", 40))
                logo_label.setStyleSheet("color: #3B82F6;")
        else:
            # Fallback to emoji if logo file doesn't exist
            logo_label.setText("⚡")
            logo_label.setFont(QFont("Arial", 40))
            logo_label.setStyleSheet("color: #3B82F6;")
        
        logo_container_layout.addWidget(logo_label)
        
        # Add right spacer for balance
        logo_container_layout.addStretch()
        
        logo_container.setLayout(logo_container_layout)
        header_layout.addWidget(logo_container)
        
        # Title
        title_label = QLabel("STUCK AI")
        title_px = 24 if (size_variant == "small") else (28 if is_laptop_or_smaller else 32)
        title_label.setFont(QFont("Poppins", title_px, QFont.Weight.DemiBold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937;
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        header_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("AI Video Scene Generator")
        subtitle_px = 12 if (size_variant == "small") else (14 if is_laptop_or_smaller else 16)
        subtitle_label.setFont(QFont("Inter", subtitle_px, QFont.Weight.Normal))
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #6B7280;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
            }
        """)
        header_layout.addWidget(subtitle_label)
        
        content_layout.addLayout(header_layout)
        
        # Version badge
        version_label = QLabel("v1.0.0 | Early Access")
        version_px = 10 if (size_variant == "small") else (11 if is_laptop_or_smaller else 12)
        version_label.setFont(QFont("Inter", version_px, QFont.Weight.Normal))
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("""
            QLabel {
                color: #9CA3AF;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #F8F9FA,
                    stop:0.5 #F1F3F4,
                    stop:1 #E8EAED);
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                padding: 4px 12px;
                font-family: 'Inter', 'Arial', sans-serif;
            }
        """)
        content_layout.addWidget(version_label)
        
        # Description
        desc_label = QLabel("Turn your scripts into professional, AI-powered video scenes in minutes with stock visuals ready.")
        desc_px = 12 if (size_variant == "small") else (14 if is_laptop_or_smaller else 16)
        desc_label.setFont(QFont("Inter", desc_px, QFont.Weight.Normal))
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setStyleSheet("""
            QLabel {
                color: #4B5563;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                line-height: 1.5;
            }
        """)
        content_layout.addWidget(desc_label)
        
        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("background: #E5E7EB; border: none; margin: {}px 0px;".format(12 if (size_variant == "small" or is_laptop_or_smaller) else 20))
        divider.setFixedHeight(1)
        content_layout.addWidget(divider)
        
        # Features section
        features_title = QLabel("Features")
        features_title.setFont(QFont("Poppins", 16 if (size_variant == "small" or is_laptop_or_smaller) else 18, QFont.Weight.DemiBold))
        features_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        features_title.setStyleSheet("""
            QLabel {
                color: #1F2937;
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        content_layout.addWidget(features_title)
        
        # Features grid
        features_grid = QGridLayout()
        # Increase spacing on laptops/smaller screens so cards are not cramped
        if size_variant == "small":
            # Phone/tablet/small windows: single column, moderate extra gaps
            try:
                features_grid.setVerticalSpacing(32)
                features_grid.setHorizontalSpacing(18)
            except Exception:
                features_grid.setSpacing(36)
        elif is_laptop_or_smaller:
            # Laptop widths: 2 columns with wider gaps between cards
            try:
                features_grid.setVerticalSpacing(56)
                features_grid.setHorizontalSpacing(32)
            except Exception:
                features_grid.setSpacing(56)
        else:
            # Large desktop: default spacing
            try:
                features_grid.setVerticalSpacing(16)
                features_grid.setHorizontalSpacing(16)
            except Exception:
                features_grid.setSpacing(16)
        features_grid.setContentsMargins(0, 0, 0, 0)
        
        features = [
            ("dart.png", "Smart Analysis", "AI-powered scene analysis"),
            ("media.png", "Stock Media", "Premium visual content"),
            ("fast.png", "Fast Processing", "Quick generation"),
            ("custom.png", "Customizable", "Flexible options")
        ]

        # Use a single column for small; laptop keeps 2 columns for balance
        num_cols = 1 if size_variant == "small" else 2

        for i, (icon, title, desc) in enumerate(features):
            feature_widget = self.create_simple_feature_card(icon, title, desc, size_variant)
            row = i // num_cols
            col = i % num_cols
            features_grid.addWidget(feature_widget, row, col)
        
        content_layout.addLayout(features_grid)
        
        # Footer (hide on laptop/small screens)
        if not (size_variant == "small" or is_laptop_or_smaller):
            footer_label = QLabel("Made with ❤️ by STUCK AI")
            footer_label.setFont(QFont("Inter", 12, QFont.Weight.Normal))
            footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            footer_label.setStyleSheet("""
                QLabel {
                    color: #9CA3AF;
                    background: transparent;
                    font-family: 'Inter', 'Arial', sans-serif;
                }
            """)
            content_layout.addWidget(footer_label)
        
        # Center container for horizontal centering
        center_container = QWidget()
        # Allow container to expand so internal stretches can center the content
        try:
            center_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        except Exception:
            pass
        center_layout = QHBoxLayout()
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(0)
        center_container.setLayout(center_layout)
        
        # Add left spacer
        center_layout.addStretch()
        
        # Add content widget
        center_layout.addWidget(content_widget)
        
        # Add right spacer
        center_layout.addStretch()
        
        # Add center container to main layout
        main_layout.addWidget(center_container)
        
        # Bottom spacer: always add to vertically center content
        main_layout.addStretch()
        
    def create_simple_feature_card(self, icon: str, title: str, description: str, size_variant: str = "medium") -> QWidget:
        """Create a simple feature card with responsive/icon-DPI aware sizing"""
        card = QFrame()
        # Responsive card height
        if size_variant == "small":
            card.setFixedHeight(104)
        else:
            card.setFixedHeight(116)
        card.setStyleSheet("""
            QFrame {
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
            QFrame:hover {
                background: #F3F4F6;
                border-color: #3B82F6;
            }
            QFrame QLabel {
                border: none;
                background: transparent;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        card.setLayout(layout)
        
        # Icon
        icon_label = QLabel()
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("border: none; background: transparent;")

        # Define responsive sizes
        icon_px = 28 if size_variant == "small" else 40
        title_px = 11 if size_variant == "small" else 12
        desc_px = 9 if size_variant == "small" else 10
        
        # Load PNG icon if it's a file path
        if icon.endswith('.png'):
            icon_path = os.path.join(self.get_project_root(), "ui", "assets", icon)
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                if not pixmap.isNull():
                    # HiDPI-aware scaling for crisp icons
                    try:
                        screen = self.window().windowHandle().screen() if self.window() and self.window().windowHandle() else None
                        if screen is None:
                            from PyQt6.QtGui import QGuiApplication
                            screen = QGuiApplication.primaryScreen()
                        dpr = float(screen.devicePixelRatio()) if screen else 1.0
                        if dpr <= 0:
                            dpr = 1.0
                    except Exception:
                        dpr = 1.0
                    target = int(icon_px * dpr)
                    scaled_pixmap = pixmap.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    try:
                        scaled_pixmap.setDevicePixelRatio(dpr)
                    except Exception:
                        pass
                    icon_label.setPixmap(scaled_pixmap)
                else:
                    # Fallback to text if image loading fails
                    icon_label.setText("📁")
                    icon_label.setFont(QFont("Arial", icon_px))
                    icon_label.setStyleSheet("color: #3B82F6; border: none; background: transparent;")
            else:
                # Fallback to text if file not found
                icon_label.setText("📁")
                icon_label.setFont(QFont("Arial", icon_px))
                icon_label.setStyleSheet("color: #3B82F6; border: none; background: transparent;")
        else:
            # Use emoji if it's not a PNG file
            icon_label.setText(icon)
            icon_label.setFont(QFont("Arial", icon_px))
            icon_label.setStyleSheet("color: #3B82F6; border: none; background: transparent;")
        
        layout.addWidget(icon_label)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Poppins", title_px, QFont.Weight.DemiBold))
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937;
                background: transparent;
                border: none;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setFont(QFont("Inter", desc_px, QFont.Weight.Normal))
        desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("""
            QLabel {
                color: #6B7280;
                background: transparent;
                border: none;
                font-family: 'Inter', 'Arial', sans-serif;
            }
        """)
        layout.addWidget(desc_label)
        
        return card
    def create_clean_header_section(self, parent_layout):
        """Create clean header section with white theme"""
        header_container = QWidget()
        header_container.setFixedHeight(160)
        header_container.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border-bottom: 1px solid #E5E7EB;
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }
        """)
        
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(40, 25, 40, 25)
        header_layout.setSpacing(30)
        header_container.setLayout(header_layout)
        
        # Left side - Clean branding
        branding_layout = QVBoxLayout()
        branding_layout.setSpacing(12)
        
        # Clean title - Use Poppins SemiBold
        title_label = QLabel("AI REVIEW")
        # Use Poppins SemiBold for main title
        if hasattr(self, 'loaded_fonts') and "Poppins SemiBold" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 32, QFont.Weight.Bold))
        elif hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins", 32, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 32, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2937; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        branding_layout.addWidget(title_label)
        
        # Clean subtitle with proper line height - Use Inter Regular
        subtitle_label = QLabel("Advanced Video Quality Analysis & AI Enhancement")
        # Use Inter Regular for subtitle
        if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
            subtitle_label.setFont(QFont("Inter 24pt", 13))
        else:
            subtitle_label.setFont(QFont("Arial", 13))
        subtitle_label.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                line-height: 125%;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        branding_layout.addWidget(subtitle_label)
        
        # Clean feature badges
        badges_layout = QHBoxLayout()
        badges_layout.setSpacing(10)
        
        badges = ["AI POWERED", "REAL-TIME", "PROFESSIONAL"]
        for badge_text in badges:
            badge = QLabel(badge_text)
            badge.setFont(QFont("Arial", 8, QFont.Weight.Bold))
            badge.setStyleSheet("""
                QLabel {
                    background: #3B82F6;
                    color: white;
                    border-radius: 10px;
                    padding: 4px 8px;
                }
            """)
            badges_layout.addWidget(badge)
        
        badges_layout.addStretch()
        branding_layout.addLayout(badges_layout)
        branding_layout.addStretch()
        
        header_layout.addLayout(branding_layout)
        header_layout.addStretch()
        
        # Right side - Premium animated stats
        stats_container = AnimatedStatsContainer()
        
        stats_layout = QVBoxLayout()
        stats_layout.setContentsMargins(15, 10, 15, 10)
        stats_layout.setSpacing(8)
        stats_container.setLayout(stats_layout)
        
        # Clean stats title - Transparent background - Use Poppins SemiBold
        stats_title = QLabel("✨ ANALYSIS POWER")
        # Use Poppins SemiBold for stats title
        if hasattr(self, 'loaded_fonts') and "Poppins SemiBold" in self.loaded_fonts:
            stats_title.setFont(QFont("Poppins SemiBold", 11, QFont.Weight.Bold))
        elif hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            stats_title.setFont(QFont("Poppins", 11, QFont.Weight.Bold))
        else:
            stats_title.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        stats_title.setStyleSheet("""
            QLabel {
                color: #374151; 
                background: transparent; 
                border: none;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        stats_layout.addWidget(stats_title)
        
        stats_items = [
            ("dart.png", "99.9%", "Accuracy"),
            ("fast.png", "< 30s", "Speed"),
        ]
        
        for icon, value, label in stats_items:
            stat_row = QHBoxLayout()
            stat_row.setSpacing(6)
            
            # Icon - Transparent background
            stat_icon = QLabel()
            stat_icon.setFixedWidth(20)
            stat_icon.setStyleSheet("background: transparent; border: none;")
            
            # Load PNG icon if it's a file path
            if icon.endswith('.png'):
                icon_path = os.path.join(self.get_project_root(), "ui", "assets", icon)
                if os.path.exists(icon_path):
                    pixmap = QPixmap(icon_path)
                    if not pixmap.isNull():
                        # Scale icon to appropriate size
                        scaled_pixmap = pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                        stat_icon.setPixmap(scaled_pixmap)
                    else:
                        # Fallback to text if image loading fails
                        stat_icon.setText("📁")
                        stat_icon.setFont(QFont("Arial", 16))
                else:
                    # Fallback to text if file not found
                    stat_icon.setText("📁")
                    stat_icon.setFont(QFont("Arial", 16))
            else:
                # Use emoji if it's not a PNG file
                stat_icon.setText(icon)
                stat_icon.setFont(QFont("Arial", 16))
            
            stat_row.addWidget(stat_icon)
            
            # Value - Transparent background
            stat_value = QLabel(value)
            stat_value.setFont(QFont("Arial", 12, QFont.Weight.Bold))
            stat_value.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
            stat_row.addWidget(stat_value)
            
            # Label - Transparent background - Use Inter Regular
            stat_label = QLabel(label)
            # Use Inter Regular for stat labels
            if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
                stat_label.setFont(QFont("Inter 24pt", 8))
            else:
                stat_label.setFont(QFont("Arial", 8))
            stat_label.setStyleSheet("""
                QLabel {
                    color: #6B7280; 
                    background: transparent; 
                    border: none;
                    font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                }
            """)
            stat_row.addWidget(stat_label)
            
            stat_row.addStretch()
            stats_layout.addLayout(stat_row)
        
        header_layout.addWidget(stats_container)
        parent_layout.addWidget(header_container)
        
    def create_clean_main_content(self, parent_layout):
        """Create clean main content area with centered upload"""
        main_container = QWidget()
        main_container.setStyleSheet("background: white;")
        
        # Center layout for upload container
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(40, 20, 40, 20)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_container.setLayout(main_layout)
        
        # Centered upload area with drag & drop functionality
        self.upload_container = DragDropUploadWidget()
        self.upload_container.file_dropped.connect(self.analyze_video_quality)
        self.upload_container.upload_btn.clicked.connect(self.select_video_file)
        
        main_layout.addWidget(self.upload_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Analysis results display area
        self.analysis_content = QLabel()
        self.analysis_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analysis_content.setStyleSheet("""
            QLabel {
                color: #6B7280;
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                font-size: 14px;
                padding: 20px;
                border: 2px dashed #E5E7EB;
                border-radius: 12px;
                margin: 20px;
            }
        """)
        self.analysis_content.setText("Video dosyasını yükleyin veya sürükleyip bırakın")
        self.analysis_content.show()
        
        main_layout.addWidget(self.analysis_content, alignment=Qt.AlignmentFlag.AlignCenter)
        
        parent_layout.addWidget(main_container)
        
    def set_clean_waiting_state(self):
        """Set clean waiting state for analysis content"""
        # Since analysis_content is now hidden, this function does nothing
        # but we keep it to avoid errors in existing code
        pass
        
    def create_clean_features_section(self, parent_layout):
        """Create clean features section"""
        self.features_container = QWidget()
        self.features_container.setStyleSheet("""
            QWidget {
                background: #FAFBFC;
                border-top: 1px solid #E5E7EB;
                border-bottom-left-radius: 20px;
                border-bottom-right-radius: 20px;
            }
        """)
        
        features_layout = QVBoxLayout()
        features_layout.setContentsMargins(40, 25, 40, 30)
        features_layout.setSpacing(20)
        self.features_container.setLayout(features_layout)
        
        # Clean features title - Use Poppins SemiBold
        features_title = QLabel("ADVANCED ANALYSIS CAPABILITIES")
        # Use Poppins SemiBold for features title
        if hasattr(self, 'loaded_fonts') and "Poppins SemiBold" in self.loaded_fonts:
            features_title.setFont(QFont("Poppins SemiBold", 18, QFont.Weight.Bold))
        elif hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            features_title.setFont(QFont("Poppins", 18, QFont.Weight.Bold))
        else:
            features_title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        features_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        features_title.setStyleSheet("""
            QLabel {
                color: #111827; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        features_layout.addWidget(features_title)
        
        features_subtitle = QLabel("Powered by cutting-edge AI technology for professional video analysis")
        # Use Inter Regular for features subtitle
        if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
            features_subtitle.setFont(QFont("Inter 24pt", 11))
        else:
            features_subtitle.setFont(QFont("Arial", 11))
        features_subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        features_subtitle.setStyleSheet("""
            QLabel {
                color: #6B7280; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        features_layout.addWidget(features_subtitle)
        
        # Clean features grid
        features_grid = QHBoxLayout()
        features_grid.setSpacing(15)
        
        # Clean feature cards
        features = [
            ("🎬", "VIDEO QUALITY", "Advanced resolution,\nbitrate analysis", "#3B82F6"),
            ("🔍", "ISSUE DETECTION", "Intelligent detection\nof video artifacts", "#8B5CF6"),
            ("⚡", "AI ENHANCEMENT", "Smart recommendations\nfor improvement", "#10B981"),
            ("📈", "AI SCORING", "Comprehensive quality\nrating system", "#F59E0B")
        ]
        
        for icon, title, desc, color in features:
            feature_card = QWidget()
            feature_card.setFixedSize(180, 160)
            feature_card.setStyleSheet(f"""
                QWidget {{
                    background: white;
                    border: none;
                    border-radius: 12px;
                    /* box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06); */
                }}
                QWidget:hover {{
                    background: #F8FAFC;
                    /* box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06); */
                }}
            """)
            
            card_layout = QVBoxLayout()
            card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.setContentsMargins(15, 15, 15, 15)
            card_layout.setSpacing(8)
            feature_card.setLayout(card_layout)
            
            # Clean feature icon - NO BORDER
            feature_icon_container = QWidget()
            feature_icon_container.setFixedSize(50, 50)
            feature_icon_container.setStyleSheet(f"""
                QWidget {{
                    background: {color}15;
                    border: none;
                    border-radius: 25px;
                }}
            """)
            
            icon_layout = QVBoxLayout()
            icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_layout.setContentsMargins(0, 0, 0, 0)
            feature_icon_container.setLayout(icon_layout)
            
            # Icon label - NO BORDER
            feature_icon = QLabel(icon)
            feature_icon.setFont(QFont("Arial", 20))
            feature_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            feature_icon.setStyleSheet("background: transparent; border: none;")
            icon_layout.addWidget(feature_icon)
            
            card_layout.addWidget(feature_icon_container, alignment=Qt.AlignmentFlag.AlignCenter)
            
            # Clean feature title - NO BORDER - Use Inter Regular
            feature_title = QLabel(title)
            # Use Inter Regular for feature titles
            if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
                feature_title.setFont(QFont("Inter 24pt", 10, QFont.Weight.Bold))
            else:
                feature_title.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            feature_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            feature_title.setStyleSheet(f"""
                QLabel {{
                    color: {color}; 
                    background: transparent; 
                    border: none;
                    font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                }}
            """)
            card_layout.addWidget(feature_title)
            
            # Clean feature description - NO BORDER - Use Inter Regular
            feature_desc = QLabel(desc)
            # Use Inter Regular for feature descriptions
            if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
                feature_desc.setFont(QFont("Inter 24pt", 8))
            else:
                feature_desc.setFont(QFont("Arial", 8))
            feature_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            feature_desc.setStyleSheet("""
                QLabel {
                    color: #6B7280; 
                    background: transparent; 
                    border: none;
                    font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                }
            """)
            feature_desc.setWordWrap(True)
            card_layout.addWidget(feature_desc)
            
            features_grid.addWidget(feature_card)
        
        features_layout.addLayout(features_grid)
        parent_layout.addWidget(self.features_container)
    
    def clear_content_layout(self):
        """Clear all widgets from content layout"""
        # Hide all widgets first
        if hasattr(self, 'welcome_widget') and self.welcome_widget:
            self.welcome_widget.hide()
        if hasattr(self, 'left_panel') and self.left_panel:
            self.left_panel.hide()
        if hasattr(self, 'right_panel') and self.right_panel:
            self.right_panel.hide()
        if hasattr(self, 'ai_review_widget') and self.ai_review_widget:
            self.ai_review_widget.hide()
        if hasattr(self, 'history_widget') and self.history_widget:
            self.history_widget.hide()
        if hasattr(self, 'downloads_page') and self.downloads_page:
            self.downloads_page.hide()
        if hasattr(self, 'info_page') and self.info_page:
            self.info_page.hide()
        
        # Remove all widgets from layout without deleting them
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
    
    def create_ai_review_widget(self):
        """Create AI Review page with video quality analysis"""
        self.ai_review_widget = QWidget()
        self.ai_review_widget.setStyleSheet("""
            QWidget {
                background-color: white;
                border-radius: 20px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(30)
        self.ai_review_widget.setLayout(layout)
        
        # Page Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(15)
        
        # Icon
        icon_label = QLabel("🧠")
        icon_label.setFont(QFont("Inter", 32))
        icon_label.setStyleSheet("color: #111827;")
        header_layout.addWidget(icon_label)
        
        # Title and description
        title_section = QVBoxLayout()
        title_section.setSpacing(8)
        
        title_label = QLabel("AI Review & Video Quality Analysis")
        title_label.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #111827;")
        title_section.addWidget(title_label)
        
        subtitle_label = QLabel("Analyze video quality, detect issues, and get AI-powered recommendations")
        subtitle_label.setFont(QFont("Inter", 16))
        subtitle_label.setStyleSheet("color: #6B7280;")
        title_section.addWidget(subtitle_label)
        
        header_layout.addLayout(title_section)
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Main content area
        content_layout = QHBoxLayout()
        content_layout.setSpacing(30)
        
        # Left panel - Upload area using DragDropUploadWidget
        self.ai_review_upload_container = DragDropUploadWidget()
        self.ai_review_upload_container.file_dropped.connect(self.analyze_video_quality)
        self.ai_review_upload_container.upload_btn.clicked.connect(self.select_video_file)
        
        content_layout.addWidget(self.ai_review_upload_container)
        
        # Right panel - Analysis results
        results_panel = QWidget()
        results_panel.setStyleSheet("""
            QWidget {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 16px;
                padding: 20px;
            }
        """)
        
        results_layout = QVBoxLayout()
        results_layout.setSpacing(20)
        results_panel.setLayout(results_layout)
        
        # Results header
        results_header = QLabel("Analysis Results")
        results_header.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        results_header.setStyleSheet("color: #111827;")
        
        # Add camera icon to results header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        header_layout.setContentsMargins(0, 0, 0, 0)
        
        # Camera icon
        camera_icon = QLabel()
        camera_icon.setStyleSheet("margin-top: 2px;")
        try:
            camera_path = os.path.abspath("ui/assets/camera.png")
            if os.path.exists(camera_path):
                pixmap = QPixmap(camera_path)
                if not pixmap.isNull():
                    try:
                        from PyQt6.QtGui import QGuiApplication
                        screen = QGuiApplication.primaryScreen()
                        dpr = float(screen.devicePixelRatio()) if screen else 1.0
                    except Exception:
                        dpr = 1.0
                    target_w = int(52 * dpr)
                    target_h = int(52 * dpr)
                    scaled_pixmap = pixmap.scaled(
                        target_w,
                        target_h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    try:
                        scaled_pixmap.setDevicePixelRatio(dpr)
                    except Exception:
                        pass
                    camera_icon.setPixmap(scaled_pixmap)
                    print(f"✅ Camera icon loaded successfully: {camera_path} (dpr={dpr})")
                else:
                    print(f"⚠️ Failed to load camera icon: {camera_path}")
            else:
                print(f"⚠️ Camera icon not found: {camera_path}")
        except Exception as e:
            print(f"⚠️ Error loading camera icon: {e}")
        
        header_layout.addWidget(camera_icon)
        header_layout.addWidget(results_header)
        header_layout.addStretch()
        
        results_layout.addLayout(header_layout)
        
        # Placeholder content
        self.analysis_content = QLabel("Select a video file to begin analysis...")
        self.analysis_content.setFont(QFont("Inter", 14))
        self.analysis_content.setStyleSheet("color: #9CA3AF;")
        self.analysis_content.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.analysis_content.setMinimumHeight(400)
        results_layout.addWidget(self.analysis_content)
        
        content_layout.addWidget(results_panel)
        layout.addLayout(content_layout)
        
        # Features section
        features_label = QLabel("🎯 AI Analysis Features")
        features_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        features_label.setStyleSheet("color: #111827; margin-top: 20px;")
        layout.addWidget(features_label)
        
        features_grid = QHBoxLayout()
        features_grid.setSpacing(20)
        
        # Feature cards
        features = [
            ("🎬", "Video Quality", "Resolution, bitrate, and\ncompression analysis"),
            ("🔍", "Issue Detection", "Automatic detection of\ncommon video problems"),
            ("⚡", "AI Enhancement", "Smart recommendations\nfor quality improvement"),
            ("📈", "AI Scoring", "Overall quality rating\nand detailed metrics")
        ]
        
        for icon, title, desc in features:
            feature_card = QWidget()
            feature_card.setStyleSheet("""
                QWidget {
                    background: #F8FAFC;
                    border: 1px solid #E5E7EB;
                    border-radius: 12px;
                    padding: 16px;
                }
            """)
            
            card_layout = QVBoxLayout()
            card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.setSpacing(8)
            feature_card.setLayout(card_layout)
            
            feature_icon = QLabel(icon)
            feature_icon.setFont(QFont("Inter", 24))
            feature_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card_layout.addWidget(feature_icon)
            
            feature_title = QLabel(title)
            feature_title.setFont(QFont("Inter", 14, QFont.Weight.Bold))
            feature_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            feature_title.setStyleSheet("color: #111827;")
            card_layout.addWidget(feature_title)
            
            feature_desc = QLabel(desc)
            feature_desc.setFont(QFont("Inter", 12))
            feature_desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
            feature_desc.setStyleSheet("color: #6B7280;")
            card_layout.addWidget(feature_desc)
            
            features_grid.addWidget(feature_card)
        
        layout.addLayout(features_grid)
    
    def create_premium_ai_review_widget(self):
        """Create premium AI Review page with clean white design"""
        self.ai_review_widget = QWidget()
        self.ai_review_widget.setStyleSheet("""
            QWidget {
                background: white;
                border-radius: 20px;
                color: #111827;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.ai_review_widget.setLayout(layout)
        
        # Create clean header section
        self.create_clean_header_section(layout)
        
        # Create clean main content
        self.create_clean_main_content(layout)
        
        # Create clean features section
        self.create_clean_features_section(layout)
        
        # Store reference to layout for dynamic updates
        self.ai_review_layout = layout
    
    def create_advanced_analysis_dashboard(self, result: dict):
        """Create beautiful analysis dashboard with NEW ANALYSIS button"""
        try:
            print("🎨 Creating beautiful analysis dashboard...")
            print(f"📊 Analysis result keys: {list(result.keys())}")
            
            # Hide the features container (Advanced Analysis Capabilities)
            if hasattr(self, 'features_container'):
                self.features_container.hide()
                
            # Remove existing analysis content
            if hasattr(self, 'analysis_content'):
                self.analysis_content.hide()
                
            # Get the ai_review_widget's main layout directly
            layout = self.ai_review_widget.layout()
            if not layout:
                return
            
            # Find the main content area (after header) and clear only that part
            # Keep the header section intact
            main_content_found = False
            for i in range(layout.count()):
                child = layout.itemAt(i)
                if child.widget():
                    widget = child.widget()
                    # Check if this is the main content area (upload container or analysis content)
                    if (hasattr(widget, 'objectName') and widget.objectName() == "main_content") or \
                       (hasattr(self, 'upload_container') and widget == self.upload_container) or \
                       (hasattr(self, 'analysis_content') and widget == self.analysis_content):
                        # Remove this widget and replace with dashboard
                        layout.removeItem(child)
                        if child.widget():
                            child.widget().deleteLater()
                        main_content_found = True
                        break
            
            # If we didn't find the specific content area, clear everything after header
            if not main_content_found:
                # Keep first item (header) and remove the rest
                while layout.count() > 1:
                    child = layout.takeAt(1)
                    if child.widget():
                        child.widget().deleteLater()
            
            # Extract data from analysis
            file_info = result.get("file_info", {})
            video_props = result.get("video_properties", {})
            quality_metrics = result.get("quality_metrics", {})
            performance_score = result.get("performance_score", {})
            ai_recommendations = result.get("ai_recommendations", [])
            
            # Create main dashboard widget
            dashboard_widget = QWidget()
            dashboard_widget.setMaximumWidth(1200)  # Limit width for better centering
            dashboard_widget.setStyleSheet("""
                QWidget {
                    background: white;
                    border: none;
                }
            """)
            
            dashboard_layout = QVBoxLayout()
            dashboard_layout.setContentsMargins(40, 20, 40, 20)  # Balanced margins
            dashboard_layout.setSpacing(20)
            dashboard_layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align content to top
            dashboard_widget.setLayout(dashboard_layout)
            
            # Dashboard Header - ANALYSIS COMPLETE section
            header_widget = QWidget()
            header_widget.setFixedHeight(60)
            header_widget.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #10B981, stop:1 #059669);
                    border-radius: 12px;
                }
            """)
            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(20, 15, 20, 15)
            header_widget.setLayout(header_layout)
            
            status_label = QLabel("✅ ANALYSIS COMPLETE")
            # Use Poppins for ANALYSIS COMPLETE
            if hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
                status_label.setFont(QFont("Poppins", 14, QFont.Weight.Bold))
            else:
                status_label.setFont(QFont("Arial", 14, QFont.Weight.Bold))
            status_label.setStyleSheet("color: white; background: transparent; font-family: 'Poppins', 'Arial', sans-serif;")
            header_layout.addWidget(status_label)
            
            filename_label = QLabel(f"📁 {file_info.get('filename', 'Unknown')}")
            filename_label.setFont(QFont("Arial", 12))
            filename_label.setStyleSheet("color: white; background: transparent;")
            header_layout.addWidget(filename_label)
            
            header_layout.addStretch()
            
            # New Analysis button
            new_analysis_btn = QPushButton("🔄 NEW ANALYSIS")
            new_analysis_btn.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            new_analysis_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            new_analysis_btn.setFixedSize(140, 35)
            new_analysis_btn.setStyleSheet("""
                QPushButton {
                    background: rgba(255, 255, 255, 0.2);
                    color: white;
                    border: 1px solid rgba(255, 255, 255, 0.3);
                    border-radius: 8px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.3);
                    border: 1px solid rgba(255, 255, 255, 0.5);
                }
                QPushButton:pressed {
                    background: rgba(255, 255, 255, 0.4);
                }
            """)
            new_analysis_btn.clicked.connect(self.start_new_analysis)
            header_layout.addWidget(new_analysis_btn)
            
            dashboard_layout.addWidget(header_widget)
            
            # Create horizontal layout for metrics and recommendations
            content_layout = QHBoxLayout()
            content_layout.setSpacing(20)
            content_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Center the cards
            
            # Left side - Quality Metrics Card
            quality_card = self.create_quality_metrics_card(quality_metrics, performance_score)
            content_layout.addWidget(quality_card)
            
            # Right side - AI Recommendations Card
            if ai_recommendations:
                recommendations_card = self.create_recommendations_card(ai_recommendations)
                content_layout.addWidget(recommendations_card)
            else:
                # Add spacer if no recommendations
                content_layout.addStretch()
            
            dashboard_layout.addLayout(content_layout)
            
            # Add dashboard to layout with center alignment
            layout.addWidget(dashboard_widget, alignment=Qt.AlignmentFlag.AlignCenter)
            dashboard_widget.show()
            
            # Store reference
            self.analysis_dashboard = dashboard_widget
            
            # Restore original margins for proper layout
            layout.setContentsMargins(40, 40, 40, 40)
            layout.setSpacing(30)
            
            print("✅ Beautiful dashboard created successfully!")
                
        except Exception as e:
            print(f"❌ Error creating dashboard: {e}")
            import traceback
            traceback.print_exc()
    
    def create_quality_metrics_card(self, quality_metrics: dict, performance_score: dict) -> QWidget:
        """Create quality metrics card with progress bars"""
        card = QWidget()
        card.setMinimumHeight(350)
        card.setMinimumWidth(380)
        card.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 22, 25, 22)
        layout.setSpacing(18)
        card.setLayout(layout)
        
        # Card header
        header_layout = QHBoxLayout()
        header_icon = QLabel("📊")
        header_icon.setFont(QFont("Arial", 16))
        header_icon.setStyleSheet("background: transparent;")
        header_layout.addWidget(header_icon)
        
        header_title = QLabel("QUALITY METRICS")
        # Use Poppins for QUALITY METRICS
        if hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            header_title.setFont(QFont("Poppins", 13, QFont.Weight.Bold))
        else:
            header_title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        header_title.setStyleSheet("color: #374151; background: transparent; font-family: 'Poppins', 'Arial', sans-serif;")
        header_layout.addWidget(header_title)
        
        header_layout.addStretch()
        
        # Overall score badge
        overall_score = performance_score.get('overall_score', 0)
        grade = performance_score.get('grade', 'N/A')
        score_badge = QLabel(f"{overall_score:.0f}% ({grade})")
        score_badge.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        score_badge.setStyleSheet("""
            QLabel {
                background: #3B82F6;
                color: white;
                border-radius: 12px;
                padding: 6px 12px;
            }
        """)
        header_layout.addWidget(score_badge)
        
        layout.addLayout(header_layout)
        
        # Quality breakdown with progress bars
        breakdown = performance_score.get('breakdown', {})
        metrics = [
            ("Resolution Quality", breakdown.get('resolution', 0), 25, "#10B981"),
            ("Visual Quality", breakdown.get('quality', 0), 25, "#3B82F6"),
            ("Technical Score", breakdown.get('technical', 0), 25, "#8B5CF6"),
            ("Compatibility", breakdown.get('compatibility', 0), 25, "#F59E0B"),
        ]
        
        for label, value, max_val, color in metrics:
            # Create a container widget for each metric without border
            metric_widget = QWidget()
            metric_widget.setStyleSheet("""
                QWidget {
                    background: transparent;
                    border: none;
                }
            """)
            
            metric_layout = QVBoxLayout()
            metric_layout.setSpacing(6)
            metric_layout.setContentsMargins(0, 0, 0, 0)  # Remove all margins
            metric_widget.setLayout(metric_layout)
            
            # Label with score
            label_layout = QHBoxLayout()
            label_layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
            metric_label = QLabel(label)
            # Use Inter Regular for metric labels
            if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
                metric_label.setFont(QFont("Inter 24pt", 12))
            else:
                metric_label.setFont(QFont("Arial", 12))
            metric_label.setStyleSheet("color: #374151; background: transparent; font-weight: 600; font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;")
            label_layout.addWidget(metric_label)
            
            label_layout.addStretch()
            
            score_label = QLabel(f"{value:.1f}/{max_val}")
            score_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
            score_label.setStyleSheet(f"color: {color}; background: transparent;")
            label_layout.addWidget(score_label)
            
            metric_layout.addLayout(label_layout)
            
            # Progress bar
            progress_bar = QProgressBar()
            progress_bar.setRange(0, int(max_val * 10))  # Scale by 10 for precision
            progress_bar.setValue(int(value * 10))
            progress_bar.setFixedHeight(8)
            progress_bar.setTextVisible(False)
            progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background: #E5E7EB;
                    border: none;
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 4px;
                }}
            """)
            metric_layout.addWidget(progress_bar)
            
            layout.addWidget(metric_widget)
        
        return card
    
    def create_recommendations_card(self, recommendations: list) -> QWidget:
        """Create AI recommendations card"""
        card = QWidget()
        card.setMinimumHeight(350)
        card.setMinimumWidth(380)
        card.setStyleSheet("""
            QWidget {
                background: #F8FAFC;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(25, 22, 25, 22)
        layout.setSpacing(18)
        card.setLayout(layout)
        
        # Card header
        header_layout = QHBoxLayout()
        header_icon = QLabel("💡")
        header_icon.setFont(QFont("Arial", 16))
        header_icon.setStyleSheet("background: transparent;")
        header_layout.addWidget(header_icon)
        
        header_title = QLabel("AI RECOMMENDATIONS")
        # Use Poppins for AI RECOMMENDATIONS
        if hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            header_title.setFont(QFont("Poppins", 13, QFont.Weight.Bold))
        else:
            header_title.setFont(QFont("Arial", 13, QFont.Weight.Bold))
        header_title.setStyleSheet("color: #374151; background: transparent; font-family: 'Poppins', 'Arial', sans-serif;")
        header_layout.addWidget(header_title)
        
        header_layout.addStretch()
        layout.addLayout(header_layout)
        
        # Recommendations list
        for i, recommendation in enumerate(recommendations[:5]):  # Show max 5
            rec_layout = QHBoxLayout()
            rec_layout.setSpacing(15)
            
            # Number badge
            number_badge = QLabel(str(i + 1))
            number_badge.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            number_badge.setFixedSize(24, 24)
            number_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
            number_badge.setStyleSheet("""
                QLabel {
                    background: #3B82F6;
                    color: white;
                    border-radius: 12px;
                }
            """)
            rec_layout.addWidget(number_badge)
            
            # Recommendation text
            rec_text = QLabel(recommendation)
            # Use Inter Regular for recommendation text
            if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
                rec_text.setFont(QFont("Inter 24pt", 12))
            else:
                rec_text.setFont(QFont("Arial", 12))
            rec_text.setStyleSheet("color: #374151; background: transparent; line-height: 1.5; font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;")
            rec_text.setWordWrap(True)
            rec_layout.addWidget(rec_text)
            
            layout.addLayout(rec_layout)
        
        return card
    
    def start_new_analysis(self):
        """Start a new analysis - go back to AI Review interface"""
        print("🔄 Starting new analysis...")
        
        # Simply call show_ai_review_page to reset everything properly
        self.show_ai_review_page()
        
        print("✅ Ready for new analysis!")
    
    def create_simple_header(self, result: dict) -> QWidget:
        """Create simple header with file info in English"""
        header_widget = QWidget()
        header_layout = QVBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)  # Reduced spacing
        header_widget.setLayout(header_layout)
        
        # Title (moved to top)
        title_label = QLabel("✅ Video Analysis Complete!")
        title_label.setFont(QFont("Inter", 28, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #10B981; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(title_label)
        
        # File details
        if 'file_info' in result:
            file_info = result['file_info']
            filename_label = QLabel(f"📁 {file_info.get('filename', 'Unknown')}")
            filename_label.setFont(QFont("Inter", 16))
            filename_label.setStyleSheet("color: #374151; background: transparent;")
            filename_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            header_layout.addWidget(filename_label)
        
        return header_widget
    
    def create_simple_ratings_section(self, result: dict) -> QWidget:
        """Create simple text-based ratings section"""
        section_widget = QWidget()
        section_layout = QVBoxLayout(section_widget)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(15)  # Reduced spacing
        
        # Section title
        title_label = QLabel("📊 Video Performance Ratings")
        title_label.setFont(QFont("Inter", 24, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #111827; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_layout.addWidget(title_label)
        
        # Create simple text ratings container
        ratings_container = QWidget()
        ratings_container.setStyleSheet("""
            QWidget {
                background: transparent;
                min-width: 600px;
                max-width: 800px;
            }
        """)
        ratings_container.setFixedHeight(150)  # Reduced height for horizontal layout
        
        # Use QHBoxLayout for horizontal arrangement of all 4 ratings
        horizontal_layout = QHBoxLayout(ratings_container)
        horizontal_layout.setSpacing(20)  # Gap between rating widgets
        horizontal_layout.setContentsMargins(20, 20, 20, 20)
        
        # Calculate ratings from result data
        ratings = []
        
        if 'performance_score' in result:
            perf = result['performance_score']
            breakdown = perf.get('breakdown', {})
            
            # Get quality metrics from different sources
            quality_metrics = result.get('quality_metrics', {})
            overall_quality = quality_metrics.get('overall_quality_score', 0)
            
            # Convert numpy values to float and handle different scales
            quality_score = float(breakdown.get('quality', 0))
            resolution_score = float(breakdown.get('resolution', 0))
            technical_score = float(breakdown.get('technical', 0))
            compatibility_score = float(breakdown.get('compatibility', 0))
            
            # Convert overall quality score (0-100) to 0-10 scale
            overall_quality_10 = round(float(overall_quality) / 10, 1) if overall_quality else 7.0
            
            # Convert breakdown scores (already in 0-25 scale) to 0-10 scale
            quality_10 = round(quality_score * 10 / 25, 1) if quality_score else overall_quality_10
            resolution_10 = round(resolution_score * 10 / 25, 1) if resolution_score else 8.0
            technical_10 = round(technical_score * 10 / 25, 1) if technical_score else 6.0
            compatibility_10 = round(compatibility_score * 10 / 25, 1) if compatibility_score else 9.0
            
            ratings = [
                ("Quality", quality_10),
                ("Resolution", resolution_10),
                ("Technical", technical_10),
                ("Compatibility", compatibility_10)
            ]
        else:
            # Default ratings if no data
            ratings = [
                ("Quality", 7.5),
                ("Resolution", 8.0),
                ("Technical", 6.5),
                ("Compatibility", 9.0)
            ]
 
        
        # Create simple text ratings in horizontal layout
        colors = ["#3B82F6", "#10B981", "#F59E0B", "#EF4444"]
        
        for i, (title, rating) in enumerate(ratings):
            text_widget = self.create_simple_text_rating(title, rating, colors[i])
            horizontal_layout.addWidget(text_widget)
            text_widget.show()  # Explicitly show the widget
        
        # Force layout update
        ratings_container.updateGeometry()
        
        # Add ratings container directly to section layout
        section_layout.addWidget(ratings_container, alignment=Qt.AlignmentFlag.AlignCenter)
        
        return section_widget
    
    def create_simple_text_rating(self, title: str, rating: float, color: str) -> QWidget:
        """Create simple text-based rating without cards"""
        text_widget = QWidget()
        text_widget.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
                min-height: 60px;
                min-width: 140px;
            }
        """)
        
        # Create a simple vertical layout
        text_layout = QVBoxLayout(text_widget)
        text_layout.setContentsMargins(5, 5, 5, 5)
        text_layout.setSpacing(5)
        
        # Title label
        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color}; background: transparent; border: none;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setMinimumHeight(25)
        text_layout.addWidget(title_label)
        
        # Rating label
        rating_text = f"{rating}/10"
        rating_label = QLabel(rating_text)
        rating_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))
        rating_label.setStyleSheet(f"color: {color}; background: transparent; border: none; font-weight: bold;")
        rating_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rating_label.setMinimumHeight(30)
        text_layout.addWidget(rating_label)
        
        return text_widget
    def create_simple_recommendations(self, result: dict) -> QWidget:
        """Create recommendations section with proper text wrapping and padding"""
        section_widget = QWidget()
        section_layout = QVBoxLayout(section_widget)
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(15)  # Reduced spacing
        
        # Section title
        title_label = QLabel("AI Recommendations")
        title_label.setFont(QFont("Inter", 20, QFont.Weight.Bold))  # Smaller font
        title_label.setStyleSheet("color: #111827; background: transparent;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        section_layout.addWidget(title_label)
        
        # Create recommendations container with proper constraints
        recommendations_container = QWidget()
        recommendations_container.setMinimumHeight(200)  # Ensure minimum height
        recommendations_container.setStyleSheet("""
            QWidget {
                background: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 12px;
                padding: 20px;
                max-width: 1000px;
                min-width: 600px;
                min-height: 200px;
            }
        """)
        
        # Create recommendations layout with proper spacing
        recommendations_layout = QVBoxLayout(recommendations_container)
        recommendations_layout.setContentsMargins(20, 20, 20, 20)  # Reduced padding
        recommendations_layout.setSpacing(12)  # Reduced spacing
        
        # Create recommendations list (already optimized to 3-10 words)
        if 'ai_recommendations' in result and result['ai_recommendations']:
            recommendations = result['ai_recommendations'][:5]  # Show max 5 recommendations
            print(f"🔍 Creating UI for recommendations: {recommendations}")
            
            # Display recommendations directly (they are already short)
            for i, rec in enumerate(recommendations, 1):
                rec_label = QLabel(f"{i}. {rec}")
                rec_label.setFont(QFont("Inter", 13))
                rec_label.setStyleSheet("""
                    QLabel {
                        color: #374151;
                        background: transparent;
                        border: none;
                        padding: 8px 0px;
                        line-height: 1.5;
                    }
                """)
                rec_label.setWordWrap(True)
                rec_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
                rec_label.setMinimumHeight(25)
                rec_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
                recommendations_layout.addWidget(rec_label)
                print(f"✅ Added recommendation {i}: {rec}")
        else:
            print(f"⚠️ No AI recommendations found in result! Keys available: {list(result.keys()) if result else 'No result'}")
            if result and 'ai_recommendations' in result:
                print(f"📊 AI recommendations value: {result['ai_recommendations']}")
            
            # Default short recommendations
            default_recs = [
                "Optimize video quality settings",
                "Check resolution compatibility", 
                "Verify technical parameters",
                "Test cross-platform compatibility"
            ]
            
            for i, rec in enumerate(default_recs, 1):
                rec_label = QLabel(f"{i}. {rec}")
                rec_label.setFont(QFont("Inter", 13))
                rec_label.setStyleSheet("""
                    QLabel {
                        color: #374151;
                        background: transparent;
                        border: none;
                        padding: 8px 0px;
                        line-height: 1.5;
                    }
                """)
                rec_label.setWordWrap(True)
                rec_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
                rec_label.setMinimumHeight(25)
                rec_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.MinimumExpanding)
                recommendations_layout.addWidget(rec_label)
                print(f"✅ Added default recommendation {i}: {rec}")
        
        # Center the recommendations container
        center_layout = QHBoxLayout()
        center_layout.addStretch()
        center_layout.addWidget(recommendations_container)
        center_layout.addStretch()
        
        section_layout.addLayout(center_layout)
        
        return section_widget
    
    def generate_category_recommendations(self, result: dict) -> dict:
        """Generate category-specific recommendations based on analysis results"""
        recommendations = {}
        
        # Get performance scores
        if 'performance_score' in result:
            perf = result['performance_score']
            breakdown = perf.get('breakdown', {})
            
            # Quality recommendations
            quality_score = float(breakdown.get('quality', 0))
            if quality_score >= 20:
                recommendations['Quality'] = [
                    "Excellent video quality detected",
                    "No quality improvements needed",
                    "Suitable for professional use"
                ]
            elif quality_score >= 15:
                recommendations['Quality'] = [
                    "Good video quality with minor issues",
                    "Consider slight brightness adjustments",
                    "Monitor for compression artifacts"
                ]
            else:
                recommendations['Quality'] = [
                    "Quality needs improvement",
                    "Check for blur or noise issues",
                    "Consider re-encoding with better settings"
                ]
            
            # Resolution recommendations
            resolution_score = float(breakdown.get('resolution', 0))
            if resolution_score >= 20:
                recommendations['Resolution'] = [
                    "Optimal resolution for current standards",
                    "Excellent for high-quality displays",
                    "Future-proof for upcoming technologies"
                ]
            elif resolution_score >= 15:
                recommendations['Resolution'] = [
                    "Good resolution, suitable for most uses",
                    "Consider upgrading for 4K displays",
                    "Adequate for streaming platforms"
                ]
            else:
                recommendations['Resolution'] = [
                    "Resolution could be improved",
                    "Consider higher resolution for better clarity",
                    "May appear pixelated on large screens"
                ]
            
            # Technical recommendations
            technical_score = float(breakdown.get('technical', 0))
            if technical_score >= 15:
                recommendations['Technical'] = [
                    "Technical parameters are well optimized",
                    "Smooth playback expected",
                    "Compatible with most devices"
                ]
            elif technical_score >= 10:
                recommendations['Technical'] = [
                    "Technical settings are adequate",
                    "Consider bitrate optimization",
                    "Monitor for playback issues"
                ]
            else:
                recommendations['Technical'] = [
                    "Technical improvements recommended",
                    "Check codec compatibility",
                    "Optimize bitrate and frame rate"
                ]
            
            # Compatibility recommendations
            compatibility_score = float(breakdown.get('compatibility', 0))
            if compatibility_score >= 20:
                recommendations['Compatibility'] = [
                    "Excellent device compatibility",
                    "Works across all major platforms",
                    "No format conversion needed"
                ]
            elif compatibility_score >= 15:
                recommendations['Compatibility'] = [
                    "Good compatibility with most devices",
                    "Minor format considerations",
                    "Suitable for cross-platform use"
                ]
            else:
                recommendations['Compatibility'] = [
                    "Compatibility issues may arise",
                    "Consider format conversion",
                    "Test on target devices"
                ]
        
        return recommendations
    
    def get_category_color(self, category: str) -> str:
        """Get color for each category"""
        colors = {
            'Quality': '#3B82F6',      # Blue
            'Resolution': '#10B981',   # Green
            'Technical': '#F59E0B',    # Orange
            'Compatibility': '#EF4444' # Red
        }
        return colors.get(category, '#6B7280')
    
    def create_stats_cards(self, result: dict) -> QWidget:
        """Create statistics cards row"""
        stats_widget = QWidget()
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(15)
        stats_widget.setLayout(stats_layout)
        
        # Video properties card
        if 'video_properties' in result:
            video_props = result['video_properties']
            video_card = self.create_stat_card(
                "🎬 Video Properties",
                f"{video_props.get('width', 0)}x{video_props.get('height', 0)}",
                f"{video_props.get('fps', 0)} FPS • {video_props.get('duration_seconds', 0):.1f}s",
                "#3B82F6"
            )
            stats_layout.addWidget(video_card)
        
        # Quality metrics card
        if 'quality_metrics' in result:
            quality = result['quality_metrics']
            quality_card = self.create_stat_card(
                "🔍 Quality Metrics",
                f"{quality.get('overall_quality_score', 0):.1f}/10",
                f"Blur: {quality.get('average_blur_score', 0):.1f} • Bright: {quality.get('average_brightness', 0):.1f}",
                "#8B5CF6"
            )
            stats_layout.addWidget(quality_card)
        
        # Codec info card
        if 'video_properties' in result:
            video_props = result['video_properties']
            codec_card = self.create_stat_card(
                "🎞️ Codec Info",
                video_props.get('codec', 'Unknown'),
                f"{video_props.get('bitrate_kbps', 0)} kbps • {video_props.get('quality_category', 'Unknown')}",
                "#F59E0B"
            )
            stats_layout.addWidget(codec_card)
        
        return stats_widget
    
    def create_simple_stats_section(self, result: dict) -> QWidget:
        """Create simple stats section with key metrics"""
        stats_widget = QWidget()
        stats_layout = QHBoxLayout()
        stats_layout.setContentsMargins(0, 0, 0, 0)
        stats_layout.setSpacing(15)
        stats_widget.setLayout(stats_layout)
        
        # Video Properties
        if 'video_properties' in result:
            props = result['video_properties']
            props_card = self.create_simple_card(
                "🎬 Video Properties",
                f"Resolution: {props.get('width', 0)}x{props.get('height', 0)}\n"
                f"Duration: {props.get('duration_seconds', 0):.1f}s\n"
                f"FPS: {props.get('fps', 0):.1f}",
                "#3B82F6"
            )
            stats_layout.addWidget(props_card)
        
        # Quality Score
        if 'quality_metrics' in result:
            quality = result['quality_metrics']
            quality_card = self.create_simple_card(
                "📊 Quality Score",
                f"Overall: {quality.get('overall_quality_score', 0):.1f}/100\n"
                f"Blur: {quality.get('blur_assessment', 'Unknown')}\n"
                f"Brightness: {quality.get('brightness_assessment', 'Unknown')}",
                "#10B981"
            )
            stats_layout.addWidget(quality_card)
        
        # Performance Score
        if 'performance_score' in result:
            perf = result['performance_score']
            perf_card = self.create_simple_card(
                "🏆 Performance",
                f"Score: {perf.get('overall_score', 0):.1f}/100\n"
                f"Grade: {perf.get('grade', 'N/A')}\n"
                f"Category: {perf.get('category', 'Unknown')}",
                "#F59E0B"
            )
            stats_layout.addWidget(perf_card)
        
        stats_layout.addStretch()
        return stats_widget
    
    def create_simple_card(self, title: str, content: str, color: str) -> QWidget:
        """Create a simple info card"""
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: white;
                border: 2px solid {color};
                border-radius: 12px;
                padding: 15px;
                min-height: 120px;
            }}
        """)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(8)
        card.setLayout(layout)
        
        # Title
        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title_label.setStyleSheet(f"color: {color}; background: transparent;")
        layout.addWidget(title_label)
        
        # Content
        content_label = QLabel(content)
        content_label.setFont(QFont("Inter", 11))
        content_label.setStyleSheet("color: #374151; background: transparent; line-height: 1.4;")
        content_label.setWordWrap(True)
        layout.addWidget(content_label)
        
        return card
    
    def create_quality_performance_section(self, result: dict) -> QWidget:
        """Create quality and performance section"""
        section_widget = QWidget()
        section_layout = QHBoxLayout()
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(20)
        section_widget.setLayout(section_layout)
        
        # Quality metrics
        if 'quality_metrics' in result:
            quality = result['quality_metrics']
            quality_widget = QWidget()
            quality_widget.setStyleSheet("""
                QWidget {
                    background: white;
                    border: 2px solid #10B981;
                    border-radius: 12px;
                    padding: 20px;
                }
            """)
            
            quality_layout = QVBoxLayout()
            quality_layout.setContentsMargins(20, 20, 20, 20)
            quality_layout.setSpacing(10)
            quality_widget.setLayout(quality_layout)
            
            title = QLabel("📊 Quality Analysis")
            title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
            title.setStyleSheet("color: #10B981; background: transparent;")
            quality_layout.addWidget(title)
            
            # Quality details
            details = []
            if 'overall_quality_score' in quality:
                details.append(f"Overall Score: {quality['overall_quality_score']:.1f}/100")
            if 'blur_assessment' in quality:
                details.append(f"Blur Assessment: {quality['blur_assessment']}")
            if 'brightness_assessment' in quality:
                details.append(f"Brightness: {quality['brightness_assessment']}")
            if 'frames_analyzed' in quality:
                details.append(f"Frames Analyzed: {quality['frames_analyzed']}")
            
            for detail in details:
                detail_label = QLabel(detail)
                detail_label.setFont(QFont("Inter", 12))
                detail_label.setStyleSheet("color: #374151; background: transparent;")
                quality_layout.addWidget(detail_label)
            
            section_layout.addWidget(quality_widget)
        
        # Performance metrics
        if 'performance_score' in result:
            perf = result['performance_score']
            perf_widget = QWidget()
            perf_widget.setStyleSheet("""
                QWidget {
                    background: white;
                    border: 2px solid #F59E0B;
                    border-radius: 12px;
                    padding: 20px;
                }
            """)
            
            perf_layout = QVBoxLayout()
            perf_layout.setContentsMargins(20, 20, 20, 20)
            perf_layout.setSpacing(10)
            perf_widget.setLayout(perf_layout)
            
            title = QLabel("🏆 Performance Score")
            title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
            title.setStyleSheet("color: #F59E0B; background: transparent;")
            perf_layout.addWidget(title)
            
            # Performance details
            details = []
            if 'overall_score' in perf:
                details.append(f"Overall Score: {perf['overall_score']:.1f}/100")
            if 'grade' in perf:
                details.append(f"Grade: {perf['grade']}")
            if 'category' in perf:
                details.append(f"Category: {perf['category']}")
            
            if 'breakdown' in perf:
                breakdown = perf['breakdown']
                for key, value in breakdown.items():
                    details.append(f"{key.title()}: {value:.1f}")
            
            for detail in details:
                detail_label = QLabel(detail)
                detail_label.setFont(QFont("Inter", 12))
                detail_label.setStyleSheet("color: #374151; background: transparent;")
                perf_layout.addWidget(detail_label)
            
            section_layout.addWidget(perf_widget)
        
        section_layout.addStretch()
        return section_widget
    
    def create_recommendations_section(self, result: dict) -> QWidget:
        """Create recommendations and issues section"""
        section_widget = QWidget()
        section_layout = QHBoxLayout()
        section_layout.setContentsMargins(0, 0, 0, 0)
        section_layout.setSpacing(20)
        section_widget.setLayout(section_layout)
        
        # AI Recommendations
        if 'ai_recommendations' in result and result['ai_recommendations']:
            rec_widget = QWidget()
            rec_widget.setStyleSheet("""
                QWidget {
                    background: white;
                    border: 2px solid #10B981;
                    border-radius: 12px;
                    padding: 20px;
                }
            """)
            
            rec_layout = QVBoxLayout()
            rec_layout.setContentsMargins(20, 20, 20, 20)
            rec_layout.setSpacing(10)
            rec_widget.setLayout(rec_layout)
            
            title = QLabel("💡 AI Recommendations")
            title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
            title.setStyleSheet("color: #10B981; background: transparent;")
            rec_layout.addWidget(title)
            
            for i, rec in enumerate(result['ai_recommendations'][:3], 1):
                rec_label = QLabel(f"{i}. {rec}")
                rec_label.setFont(QFont("Inter", 11))
                rec_label.setStyleSheet("color: #374151; background: transparent;")
                rec_label.setWordWrap(True)
                rec_layout.addWidget(rec_label)
            
            section_layout.addWidget(rec_widget)
        
        # Issues section
        if 'frame_analysis' in result:
            frame_analysis = result['frame_analysis']
            if 'visual_issues' in frame_analysis and frame_analysis['visual_issues']:
                issues_widget = QWidget()
                issues_widget.setStyleSheet("""
                    QWidget {
                        background: white;
                        border: 2px solid #EF4444;
                        border-radius: 12px;
                        padding: 20px;
                    }
                """)
                
                issues_layout = QVBoxLayout()
                issues_layout.setContentsMargins(20, 20, 20, 20)
                issues_layout.setSpacing(10)
                issues_widget.setLayout(issues_layout)
                
                title = QLabel("⚠️ Detected Issues")
                title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
                title.setStyleSheet("color: #EF4444; background: transparent;")
                issues_layout.addWidget(title)
                
                for issue in frame_analysis['visual_issues'][:3]:
                    issue_label = QLabel(f"• {issue}")
                    issue_label.setFont(QFont("Inter", 11))
                    issue_label.setStyleSheet("color: #374151; background: transparent;")
                    issue_label.setWordWrap(True)
                    issues_layout.addWidget(issue_label)
                
                section_layout.addWidget(issues_widget)
        
        section_layout.addStretch()
        return section_widget
    
    def create_stat_card(self, title: str, main_value: str, subtitle: str, color: str) -> QWidget:
        """Create a single statistics card"""
        card = QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background: white;
                border: 2px solid {color};
                border-radius: 12px;
                padding: 15px;
            }}
        """)
        card.setFixedHeight(100)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(5)
        card.setLayout(layout)
        
        title_label = QLabel(title)
        title_label.setFont(QFont("Inter", 12, QFont.Weight.Medium))
        title_label.setStyleSheet(f"color: {color}; background: transparent;")
        layout.addWidget(title_label)
        
        main_label = QLabel(main_value)
        main_label.setFont(QFont("Inter", 16, QFont.Weight.Bold))
        main_label.setStyleSheet("color: #111827; background: transparent;")
        layout.addWidget(main_label)
        
        subtitle_label = QLabel(subtitle)
        subtitle_label.setFont(QFont("Inter", 10))
        subtitle_label.setStyleSheet("color: #6B7280; background: transparent;")
        layout.addWidget(subtitle_label)
        
        return card
    
    def create_charts_section(self, result: dict) -> QWidget:
        """Create charts and graphs section"""
        charts_widget = QWidget()
        charts_layout = QHBoxLayout()
        charts_layout.setContentsMargins(0, 0, 0, 0)
        charts_layout.setSpacing(20)
        charts_widget.setLayout(charts_layout)
        
        # Performance breakdown chart
        if 'performance_score' in result:
            perf = result['performance_score']
            breakdown_widget = self.create_performance_chart(perf)
            charts_layout.addWidget(breakdown_widget)
        
        # Quality metrics chart
        if 'quality_metrics' in result:
            quality = result['quality_metrics']
            quality_widget = self.create_quality_chart(quality)
            charts_layout.addWidget(quality_widget)
        
        return charts_widget
    
    def create_performance_chart(self, perf: dict) -> QWidget:
        """Create performance breakdown chart with matplotlib"""
        chart_widget = QWidget()
        chart_widget.setStyleSheet("""
            QWidget {
                background: white;
                border: 2px solid #E5E7EB;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        chart_widget.setFixedHeight(250)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        chart_widget.setLayout(layout)
        
        # Title
        title_label = QLabel("🏆 Performance Breakdown")
        title_label.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #111827; background: transparent;")
        layout.addWidget(title_label)
        
        if MATPLOTLIB_AVAILABLE:
            try:
                # Create matplotlib figure
                fig = Figure(figsize=(6, 3), dpi=100)
                canvas = FigureCanvas(fig)
                ax = fig.add_subplot(111)
                
                # Get breakdown data
                breakdown = perf.get('breakdown', {})
                categories = ['Resolution', 'Quality', 'Technical', 'Compatibility']
                colors = ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B']
                
                # Extract values
                values = [breakdown.get(cat.lower(), 0) for cat in categories]
                
                # Create horizontal bar chart
                bars = ax.barh(categories, values, color=colors, alpha=0.8, height=0.6)
                
                # Customize chart
                ax.set_xlim(0, 25)
                ax.set_xlabel('Score', fontsize=10, color='#374151')
                ax.grid(True, alpha=0.3, axis='x')
                ax.set_facecolor('#F9FAFB')
                
                # Add value labels on bars
                for i, (bar, value) in enumerate(zip(bars, values)):
                    width = bar.get_width()
                    ax.text(width + 0.5, bar.get_y() + bar.get_height()/2, 
                           f'{value:.0f}', ha='left', va='center', 
                           fontsize=10, fontweight='bold', color='#374151')
                
                # Remove spines
                for spine in ax.spines.values():
                    spine.set_visible(False)
                
                # Remove y-axis labels
                ax.set_yticklabels([])
                ax.tick_params(axis='y', length=0)
                
                fig.tight_layout()
                layout.addWidget(canvas)
                
            except Exception as e:
                print(f"Error creating matplotlib chart: {e}")
                # Fallback to simple progress bars
                self.create_simple_performance_chart(perf, layout)
        else:
            # Fallback to simple progress bars
            self.create_simple_performance_chart(perf, layout)
        
        return chart_widget
    
    def create_simple_performance_chart(self, perf: dict, layout: QVBoxLayout):
        """Create simple performance chart using QProgressBar as fallback"""
        breakdown = perf.get('breakdown', {})
        categories = ['Resolution', 'Quality', 'Technical', 'Compatibility']
        colors = ['#3B82F6', '#8B5CF6', '#10B981', '#F59E0B']
        
        for i, (category, color) in enumerate(zip(categories, colors)):
            container = QWidget()
            container_layout = QHBoxLayout()
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(10)
            container.setLayout(container_layout)
            
            label = QLabel(category)
            label.setFont(QFont("Inter", 10))
            label.setStyleSheet("color: #374151; background: transparent;")
            label.setFixedWidth(80)
            container_layout.addWidget(label)
            
            progress = QProgressBar()
            progress.setMaximum(25)
            progress.setValue(int(breakdown.get(category.lower(), 0)))
            progress.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #E5E7EB;
                    border-radius: 6px;
                    text-align: center;
                    background: #F3F4F6;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 6px;
                }}
            """)
            container_layout.addWidget(progress)
            
            value_label = QLabel(f"{breakdown.get(category.lower(), 0):.0f}")
            value_label.setFont(QFont("Inter", 10, QFont.Weight.Medium))
            value_label.setStyleSheet("color: #374151; background: transparent;")
            value_label.setFixedWidth(30)
            container_layout.addWidget(value_label)
            
            layout.addWidget(container)
    def create_quality_chart(self, quality: dict) -> QWidget:
        """Create quality metrics chart with matplotlib"""
        chart_widget = QWidget()
        chart_widget.setStyleSheet("""
            QWidget {
                background: white;
                border: 2px solid #E5E7EB;
                border-radius: 12px;
                padding: 20px;
            }
        """)
        chart_widget.setFixedHeight(250)
        
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        chart_widget.setLayout(layout)
        
        # Title
        title_label = QLabel("🔍 Quality Metrics")
        title_label.setFont(QFont("Inter", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #111827; background: transparent;")
        layout.addWidget(title_label)
        
        if MATPLOTLIB_AVAILABLE:
            try:
                # Create matplotlib figure
                fig = Figure(figsize=(6, 3), dpi=100)
                canvas = FigureCanvas(fig)
                ax = fig.add_subplot(111)
                
                # Quality metrics data
                metrics = [
                    ("Overall Quality", quality.get('overall_quality_score', 0), 10, "#10B981"),
                    ("Blur Score", quality.get('average_blur_score', 0), 1000, "#8B5CF6"),
                    ("Brightness", quality.get('average_brightness', 0), 255, "#F59E0B")
                ]
                
                names = [metric[0] for metric in metrics]
                values = [metric[1] for metric in metrics]
                max_vals = [metric[2] for metric in metrics]
                colors = [metric[3] for metric in metrics]
                
                # Normalize values to percentage
                normalized_values = [val / max_val * 100 for val, max_val in zip(values, max_vals)]
                
                # Create horizontal bar chart
                bars = ax.barh(names, normalized_values, color=colors, alpha=0.8, height=0.6)
                
                # Customize chart
                ax.set_xlim(0, 100)
                ax.set_xlabel('Percentage (%)', fontsize=10, color='#374151')
                ax.grid(True, alpha=0.3, axis='x')
                ax.set_facecolor('#F9FAFB')
                
                # Add value labels on bars
                for i, (bar, value, norm_val) in enumerate(zip(bars, values, normalized_values)):
                    width = bar.get_width()
                    ax.text(width + 2, bar.get_y() + bar.get_height()/2, 
                           f'{value:.1f}', ha='left', va='center', 
                           fontsize=10, fontweight='bold', color='#374151')
                
                # Remove spines
                for spine in ax.spines.values():
                    spine.set_visible(False)
                
                # Remove y-axis labels
                ax.set_yticklabels([])
                ax.tick_params(axis='y', length=0)
                
                fig.tight_layout()
                layout.addWidget(canvas)
                
            except Exception as e:
                print(f"Error creating matplotlib quality chart: {e}")
                # Fallback to simple progress bars
                self.create_simple_quality_chart(quality, layout)
        else:
            # Fallback to simple progress bars
            self.create_simple_quality_chart(quality, layout)
        
        return chart_widget
    
    def create_simple_quality_chart(self, quality: dict, layout: QVBoxLayout):
        """Create simple quality chart using QProgressBar as fallback"""
        # Quality indicators
        metrics = [
            ("Overall Quality", quality.get('overall_quality_score', 0), 10, "#10B981"),
            ("Blur Score", quality.get('average_blur_score', 0), 1000, "#8B5CF6"),
            ("Brightness", quality.get('average_brightness', 0), 255, "#F59E0B")
        ]
        
        for metric_name, value, max_val, color in metrics:
            container = QWidget()
            container_layout = QHBoxLayout()
            container_layout.setContentsMargins(0, 0, 0, 0)
            container_layout.setSpacing(10)
            container.setLayout(container_layout)
            
            label = QLabel(metric_name)
            label.setFont(QFont("Inter", 10))
            label.setStyleSheet("color: #374151; background: transparent;")
            label.setFixedWidth(100)
            container_layout.addWidget(label)
            
            progress = QProgressBar()
            progress.setMaximum(max_val)
            progress.setValue(int(value))
            progress.setStyleSheet(f"""
                QProgressBar {{
                    border: 1px solid #E5E7EB;
                    border-radius: 6px;
                    text-align: center;
                    background: #F3F4F6;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 6px;
                }}
            """)
            container_layout.addWidget(progress)
            
            value_label = QLabel(f"{value:.1f}")
            value_label.setFont(QFont("Inter", 10, QFont.Weight.Medium))
            value_label.setStyleSheet("color: #374151; background: transparent;")
            value_label.setFixedWidth(40)
            container_layout.addWidget(value_label)
            
            layout.addWidget(container)
    
    def create_radar_chart(self, result: dict) -> QWidget:
        """Create a radar chart showing performance breakdown"""
        if not MATPLOTLIB_AVAILABLE:
            # Fallback to simple text display
            radar_widget = QWidget()
            radar_layout = QVBoxLayout(radar_widget)
            radar_layout.setSpacing(10)
            
            title = QLabel("Performance Breakdown")
            title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
            title.setStyleSheet("color: #374151; background: transparent;")
            radar_layout.addWidget(title)
            
            if 'performance_score' in result and 'breakdown' in result['performance_score']:
                breakdown = result['performance_score']['breakdown']
                for key, value in breakdown.items():
                    label = QLabel(f"{key.title()}: {value:.1f}")
                    label.setFont(QFont("Inter", 12))
                    label.setStyleSheet("color: #6B7280; background: transparent;")
                    radar_layout.addWidget(label)
            
            return radar_widget
        
        try:
            # Create matplotlib radar chart
            fig = Figure(figsize=(8, 6))
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111, projection='polar')
            
            if 'performance_score' in result and 'breakdown' in result['performance_score']:
                breakdown = result['performance_score']['breakdown']
                
                # Categories and values
                categories = list(breakdown.keys())
                values = list(breakdown.values())
                
                # Convert to radians
                angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
                values += values[:1]  # Close the plot
                angles += angles[:1]
                
                # Plot
                ax.plot(angles, values, 'o-', linewidth=2, color='#10B981')
                ax.fill(angles, values, alpha=0.25, color='#10B981')
                
                # Set labels
                ax.set_xticks(angles[:-1])
                ax.set_xticklabels([cat.title() for cat in categories])
                ax.set_ylim(0, 25)
                ax.set_title('Performance Breakdown', pad=20, fontsize=14, fontweight='bold')
                
                # Grid
                ax.grid(True, alpha=0.3)
            
            fig.tight_layout()
            return canvas
            
        except Exception as e:
            print(f"❌ Error creating radar chart: {e}")
            # Fallback to simple text display
            radar_widget = QWidget()
            radar_layout = QVBoxLayout(radar_widget)
            radar_layout.setSpacing(10)
            
            title = QLabel("Performance Breakdown")
            title.setFont(QFont("Inter", 16, QFont.Weight.Bold))
            title.setStyleSheet("color: #374151; background: transparent;")
            radar_layout.addWidget(title)
            
            if 'performance_score' in result and 'breakdown' in result['performance_score']:
                breakdown = result['performance_score']['breakdown']
                for key, value in breakdown.items():
                    label = QLabel(f"{key.title()}: {value:.1f}")
                    label.setFont(QFont("Inter", 12))
                    label.setStyleSheet("color: #6B7280; background: transparent;")
                    radar_layout.addWidget(label)
            
            return radar_widget
    
    def create_details_section(self, result: dict) -> QWidget:
        """Create details and recommendations section"""
        details_widget = QWidget()
        details_layout = QHBoxLayout()
        details_layout.setContentsMargins(0, 0, 0, 0)
        details_layout.setSpacing(20)
        details_widget.setLayout(details_layout)
        
        # AI Recommendations
        if 'ai_recommendations' in result and result['ai_recommendations']:
            rec_widget = QWidget()
            rec_widget.setStyleSheet("""
                QWidget {
                    background: white;
                    border: 2px solid #10B981;
                    border-radius: 12px;
                    padding: 20px;
                }
            """)
            rec_widget.setFixedHeight(150)
            
            rec_layout = QVBoxLayout()
            rec_layout.setContentsMargins(20, 20, 20, 20)
            rec_layout.setSpacing(10)
            rec_widget.setLayout(rec_layout)
            
            title_label = QLabel("💡 AI Recommendations")
            title_label.setFont(QFont("Inter", 14, QFont.Weight.Bold))
            title_label.setStyleSheet("color: #10B981; background: transparent;")
            rec_layout.addWidget(title_label)
            
            for i, rec in enumerate(result['ai_recommendations'][:2], 1):
                rec_label = QLabel(f"{i}. {rec}")
                rec_label.setFont(QFont("Inter", 11))
                rec_label.setStyleSheet("color: #374151; background: transparent;")
                rec_label.setWordWrap(True)
                rec_layout.addWidget(rec_label)
            
            details_layout.addWidget(rec_widget)
        
        # Issues section
        if 'frame_analysis' in result:
            frame_analysis = result['frame_analysis']
            if 'visual_issues' in frame_analysis and frame_analysis['visual_issues']:
                issues_widget = QWidget()
                issues_widget.setStyleSheet("""
                    QWidget {
                        background: white;
                        border: 2px solid #EF4444;
                        border-radius: 12px;
                        padding: 20px;
                    }
                """)
                issues_widget.setFixedHeight(150)
                
                issues_layout = QVBoxLayout()
                issues_layout.setContentsMargins(20, 20, 20, 20)
                issues_layout.setSpacing(10)
                issues_widget.setLayout(issues_layout)
                
                title_label = QLabel("⚠️ Detected Issues")
                title_label.setFont(QFont("Inter", 14, QFont.Weight.Bold))
                title_label.setStyleSheet("color: #EF4444; background: transparent;")
                issues_layout.addWidget(title_label)
                
                for issue in frame_analysis['visual_issues'][:2]:
                    issue_label = QLabel(f"• {issue}")
                    issue_label.setFont(QFont("Inter", 11))
                    issue_label.setStyleSheet("color: #374151; background: transparent;")
                    issue_label.setWordWrap(True)
                    issues_layout.addWidget(issue_label)
                
                details_layout.addWidget(issues_widget)
        
        details_layout.addStretch()
        return details_widget
            
    def create_welcome_widget(self):
        """Create welcome page widget"""
        # Create a frame wrapper with size constraints
        self.welcome_widget = QFrame()
        self.welcome_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Set maximum size to prevent gradient overflow
        self.welcome_widget.setMaximumSize(2000, 1500)  # Reasonable maximum size
        self.welcome_widget.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #FFFFFF,
                    stop:0.2 #F0F9FF,
                    stop:0.4 #E0F2FE,
                    stop:0.6 #BAE6FD,
                    stop:0.8 #7DD3FC,
                    stop:1 #38BDF8);
                border-radius: 20px;
                border: none;
            }
        """)
        
        # Set widget attributes to prevent gradient from extending beyond borders
        self.welcome_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.welcome_widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, False)
        
        # Create the actual content widget inside
        self.welcome_content = QWidget()
        self.welcome_content.setStyleSheet("QWidget { background: transparent; }")
        
        # Initialize animation variables
        self.animation_timer = QTimer()
        self.animation_phase = 0.0
        self.animation_timer.timeout.connect(self.update_gradient_animation)
        self.animation_timer.start(50)  # Update every 50ms for smooth animation
        
        # Set initial animated gradient
        self.update_welcome_gradient()
        
        # Set up the frame layout
        frame_layout = QVBoxLayout()
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(0)
        self.welcome_widget.setLayout(frame_layout)
        frame_layout.addWidget(self.welcome_content)
        
        # Set up the content layout
        welcome_layout = QVBoxLayout()
        welcome_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.setSpacing(40)
        welcome_layout.setContentsMargins(60, 80, 60, 80)
        self.welcome_content.setLayout(welcome_layout)
        
        # Main title - using Poppins SemiBold
        title_label = QLabel("AI POWERED STOCK FINDER")
        # Use Poppins SemiBold for the main title
        if hasattr(self, 'loaded_fonts') and "Poppins SemiBold" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 48, QFont.Weight.Bold))
        elif hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins", 48, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 48, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #1F2341;
                text-align: center;
                    background: transparent; 
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(title_label)
        
        # Subtitle - using Inter Regular
        subtitle_label = QLabel("Discover the perfect visuals for your content with AI")
        # Use Inter Regular for subtitle
        if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
            subtitle_label.setFont(QFont("Inter 24pt", 16))
        else:
            subtitle_label.setFont(QFont("Arial", 16))
        subtitle_label.setStyleSheet("""
                QLabel {
                color: #64748B;
                text-align: center;
                    background: transparent; 
                    font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                }
            """)
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_layout.addWidget(subtitle_label)
        
        # Get Started Button - using Poppins Medium
        get_started_btn = QPushButton("✦ Get Started")
        # Use Poppins for button (medium weight)
        if hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            get_started_btn.setFont(QFont("Poppins", 14, QFont.Weight.Medium))
        else:
            get_started_btn.setFont(QFont("Arial", 14, QFont.Weight.Medium))
        get_started_btn.setFixedSize(200, 50)
        get_started_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6366F1, stop:1 #8B5CF6);
                color: white;
                border: none;
                border-radius: 25px;
                font-weight: 500;
                font-family: 'Poppins', 'Arial', sans-serif;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5B5BF7, stop:1 #7C3AED);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4F46E5, stop:1 #7C2D12);
            }
        """)
        get_started_btn.clicked.connect(lambda: self.change_tab(1))  # Go to Create tab
        
        # Center the button
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(get_started_btn)
        button_layout.addStretch()
        welcome_layout.addLayout(button_layout)
    
    def update_gradient_animation(self):
        """Update the animated gradient"""
        self.animation_phase += 0.03  # Smooth animation speed
        if self.animation_phase > 6.28:  # 2π
            self.animation_phase = 0.0
        self.update_welcome_gradient()
    
    def update_welcome_gradient(self):
        """Update welcome widget gradient with animation"""
        import math
        
        # Calculate animated gradient direction with limited range
        wave_offset = math.sin(self.animation_phase) * 0.2  # Reduced from 0.3 to 0.2
        x1 = 0.5 + wave_offset
        y1 = 0.0
        x2 = 0.5 - wave_offset  
        y2 = 1.0
        
        # Ensure gradient coordinates stay within reasonable bounds
        x1 = max(0.0, min(1.0, x1))
        x2 = max(0.0, min(1.0, x2))
        
                        # Apply animated gradient to frame with proper border-radius
        if hasattr(self, 'welcome_widget'):
            self.welcome_widget.setStyleSheet(f"""
                QFrame {{
                    background: qlineargradient(x1:{x1}, y1:{y1}, x2:{x2}, y2:{y2},
                        stop:0 #FFFFFF,
                        stop:0.2 #F0F9FF,
                        stop:0.4 #E0F2FE,
                        stop:0.6 #BAE6FD,
                        stop:0.8 #7DD3FC,
                        stop:1 #38BDF8);
                    border-radius: 20px;
                    border: none;
                }}
            """)
    
    def change_tab(self, index):
        """Change to the specified tab"""
        if index == 1:  # Create tab
            self.on_sidebar_navigation("create")
        elif index == 2:  # AI Review tab  
            self.on_sidebar_navigation("ai_review")
        # Add other tabs as needed
    
    def on_sidebar_navigation(self, page_id: str):
        """Handle sidebar navigation"""
        # Update page title based on navigation
        page_titles = {
            "home": "Home",
            "ai_review": "AI Review",
            "downloads": "Downloads", 
            "history": "History",
            "settings": "Settings",
            "info": "About",
            "create": "Create New Analysis"
        }
        
        # Store current page ID for later use (e.g., when restoring title after settings)
        if page_id != "settings":  # Don't store settings as current page
            self.current_page_id = page_id
        
        # Update page title only for non-settings pages (settings shows a dialog)
        if hasattr(self, 'page_title_label') and page_id in page_titles:
            if page_id != "settings":  # Don't change title for settings - dialog will handle it
                self.page_title_label.setText(page_titles[page_id])
        
        # Only update credits for specific pages that need it
        if page_id in ["ai_review", "create"]:
            self.load_user_analysis_credits()
        
        # Note: AI Review plan restrictions are now checked when user interacts with upload
        
        # Handle specific navigation actions
        if page_id == "settings":
            self.open_settings()
        elif page_id == "info":
            self.show_info_page()
        elif page_id == "create":
            # The Create button triggers analysis interface
            self.show_main_interface()
            # Only the welcome tour may trigger coachmarks
            if getattr(self, '_tour_active', False):
                # Close first coachmark and show textbox-focused coachmark
                try:
                    self.hide_coachmark()
                except Exception:
                    pass
                # Delay slightly to ensure UI is ready
                QTimer.singleShot(300, self.show_textbox_coachmark)
        elif page_id == "downloads":
            self.show_downloads_page()
        elif page_id == "history":
            self.show_history_page()
        elif page_id == "ai_review":
            self.show_ai_review_page()
        else:
            # Show appropriate content for other pages
            self.show_page_content(page_id)
    

    
    def on_login_successful(self, user: User):
        """Handle successful login"""
        # Login successful
        
        # Set current user - THIS WAS MISSING!
        self.current_user = user
        print(f"💰 Current user set: {user.email} (ID: {user.id})")
        
        self.sidebar.update_user_display(user)
        
        # Initialize cost tracking service after user login
        if self.auth_service and user:
            try:
                self.cost_tracking_service = CostTrackingService(self.auth_service)
                self.scene_cost_tracking_service = SceneCostTrackingService(self.auth_service)
                print("💰 Cost tracking service initialized after login")
                print("💰 Scene cost tracking service initialized after login")
            except Exception as e:
                print(f"⚠️ Could not initialize cost tracking service: {e}")
        
        # Load user's analysis credits and plan info
        self.load_user_analysis_credits()
        
        # Directly update plan display
        # Update sidebar plan display (delayed for performance)
        QTimer.singleShot(500, self.sidebar.update_plan_display)

        # Show Welcome Tour prompt after login (if enabled) – schedule once safely
        try:
            QTimer.singleShot(600, self.maybe_show_welcome_tour)
        except Exception:
            pass
        
        # Login popup removed - user will see the main interface directly
    
    def logout_user(self):
        """Logout current user"""
        if self.auth_service:
            result = self.auth_service.sign_out()
            if result["success"]:
                self.current_user = None
                self.current_profile = None
                self.cost_tracking_service = None
                self.scene_cost_tracking_service = None
                self.sidebar.update_user_display()
                
                # Clear analysis credits display
                self.update_analysis_credits_display(0)
                
                # Show success message
                success_dialog = PremiumSuccessDialog(
                    self,
                    "Sign Out Successful",
                    "Successfully signed out.",
                    "👋"
                )
                success_dialog.exec()
            else:
                QMessageBox.warning(self, "Sign Out Error", result["message"])
    
    def update_analysis_credits_display(self, credits: int):
        """Update the analysis credits display"""
        if hasattr(self, 'analysis_credits_badge'):
            self.analysis_credits_badge.setText(f"Analysis Credits: {credits}")
            
            # Change color based on credits
            if credits <= 0:
                self.analysis_credits_badge.setStyleSheet("""
                    QLabel {
                        color: #EF4444;
                        font-size: 12px;
                        font-weight: bold;
                        background: transparent;
                        border: none;
                    }
                """)
            elif credits <= 2:
                self.analysis_credits_badge.setStyleSheet("""
                    QLabel {
                        color: #F59E0B;
                        font-size: 12px;
                        font-weight: bold;
                        background: transparent;
                        border: none;
                    }
                """)
            else:
                self.analysis_credits_badge.setStyleSheet("""
                    QLabel {
                        color: #10B981;
                        font-size: 12px;
                        font-weight: bold;
                        background: transparent;
                        border: none;
                    }
                """)
    
    def load_user_analysis_credits(self, force_refresh=False):
        """Load and display user's analysis credits with caching"""
        if not self.auth_service or not self.current_user:
            return
            
        # Check cache first (cache for 30 seconds)
        current_time = time.time()
        if (not force_refresh and 
            hasattr(self, '_credits_cache') and 
            hasattr(self, '_credits_cache_time') and
            current_time - self._credits_cache_time < 30):
            # Use cached credits
            self.update_analysis_credits_display(self._credits_cache)
            return
            
        # Fetch fresh credits from Supabase
        credits = self.auth_service.get_user_analysis_count(self.current_user.id)
        
        # Cache the result
        self._credits_cache = credits
        self._credits_cache_time = current_time
        
        self.update_analysis_credits_display(credits)
        
        # Also update AI Image Credits display
        self.update_ai_image_credits_display()
        
        # Also update plan display (but don't cache this as it's less critical)
        if hasattr(self, 'sidebar'):
            self.sidebar.update_plan_display()
    
    def update_ai_image_credits_display(self):
        """Update AI Image Credits display"""
        if hasattr(self, 'ai_image_credits_badge') and self.auth_service and self.current_user:
            # Get AI Image Count
            ai_image_count = self.auth_service.get_user_ai_image_count(self.current_user.id)
            
            self.ai_image_credits_badge.setText(f"AI Image Credits: {ai_image_count}")
            
            # Change color based on AI image credits
            if ai_image_count <= 0:
                self.ai_image_credits_badge.setStyleSheet("""
                    QLabel {
                        color: #EF4444;
                        font-size: 12px;
                        font-weight: bold;
                        background: transparent;
                        border: none;
                    }
                """)
            elif ai_image_count <= 2:
                self.ai_image_credits_badge.setStyleSheet("""
                    QLabel {
                        color: #F59E0B;
                        font-size: 12px;
                        font-weight: bold;
                        background: transparent;
                        border: none;
                    }
                """)
            else:
                self.ai_image_credits_badge.setStyleSheet("""
                    QLabel {
                        color: #8B5CF6;
                        font-size: 12px;
                        font-weight: bold;
                        background: transparent;
                        border: none;
                    }
                """)
    
    def decrement_ai_image_count(self):
        """Decrement AI Image Count and update display"""
        if self.auth_service and self.current_user:
            # Prevent UI from starting generation when credits are already 0
            try:
                current = self.auth_service.get_user_ai_image_count(self.current_user.id)
            except Exception:
                current = None
            if isinstance(current, int) and current <= 0:
                return {"success": False, "message": "no_ai_image_credits"}
            result = self.auth_service.decrement_ai_image_count(self.current_user.id)
            if result["success"]:
                self.update_ai_image_credits_display()
            return result
        return {"success": False, "message": "No authentication service"}
    
    def update_ai_image_in_scene_data(self, updated_suggestion: Dict[str, Any]):
        """Update AI image in scene data to persist generated images"""
        try:
            if not self.scenes_data or self.current_scene_index >= len(self.scenes_data):
                print("❌ No scene data available for AI image update")
                return
            
            scene = self.scenes_data[self.current_scene_index]
            ai_images = scene.get('ai_images', [])
            
            # Find and update the matching AI image suggestion
            for i, suggestion in enumerate(ai_images):
                if (
                    suggestion.get('id') == updated_suggestion.get('id') or 
                    suggestion.get('title') == updated_suggestion.get('title') or
                    (suggestion.get('prompt') and suggestion.get('prompt') == updated_suggestion.get('prompt'))
                ):
                    print(f"🔄 Updating AI image in scene data: {updated_suggestion.get('title', 'Unknown')}")
                    ai_images[i] = updated_suggestion.copy()
                    
                    # Also update the scene media cache
                    if self.current_scene_index in self.scene_media_cache:
                        cache = self.scene_media_cache[self.current_scene_index]
                        cache_ai_images = cache.get('ai_images', [])
                        for j, cache_suggestion in enumerate(cache_ai_images):
                            if (
                                cache_suggestion.get('id') == updated_suggestion.get('id') or 
                                cache_suggestion.get('title') == updated_suggestion.get('title') or
                                (cache_suggestion.get('prompt') and cache_suggestion.get('prompt') == updated_suggestion.get('prompt'))
                            ):
                                cache_ai_images[j] = updated_suggestion.copy()
                                break
                        cache['ai_images'] = cache_ai_images
                        self.scene_media_cache[self.current_scene_index] = cache
                    
                    print(f"✅ AI image updated in scene data and cache")
                    return
            
            print(f"⚠️ AI image not found in scene data for update")
            
        except Exception as e:
            print(f"❌ Error updating AI image in scene data: {e}")
            import traceback
            traceback.print_exc()

    def mark_ai_image_generating_by_prompt(self, prompt: str) -> None:
        """Mark the AI image with matching prompt as generating in scene data and cache"""
        try:
            if not self.scenes_data or self.current_scene_index >= len(self.scenes_data):
                return
            scene = self.scenes_data[self.current_scene_index]
            ai_images = scene.get('ai_images', [])
            updated = False
            for i, suggestion in enumerate(ai_images):
                if suggestion.get('prompt') == prompt:
                    ai_images[i] = {**suggestion, 'ai_generating': True}
                    updated = True
                    break
            if updated and self.current_scene_index in self.scene_media_cache:
                cache = self.scene_media_cache[self.current_scene_index]
                cache_ai = cache.get('ai_images', [])
                for j, suggestion in enumerate(cache_ai):
                    if suggestion.get('prompt') == prompt:
                        cache_ai[j] = {**suggestion, 'ai_generating': True}
                        break
                cache['ai_images'] = cache_ai
                self.scene_media_cache[self.current_scene_index] = cache
        except Exception as e:
            print(f"⚠️ Could not mark AI image generating by prompt: {e}")
    
    def clear_thumbnail_caches(self):
        """Clear thumbnail caches from all MediaCard instances"""
        try:
            # Clear thumbnail caches from current tab widgets
            for tab_widget in [self.stock_images_tab, self.stock_videos_tab, self.ai_images_tab]:
                if hasattr(tab_widget, 'findChild'):
                    scroll_area = tab_widget.findChild(QScrollArea)
                    if scroll_area:
                        grid_widget = scroll_area.widget()
                        if grid_widget:
                            layout = grid_widget.layout()
                            if layout:
                                # Clear thumbnail_loaded flags from all MediaCard instances
                                for i in range(layout.count()):
                                    child = layout.itemAt(i)
                                    if child:
                                        widget = child.widget()
                                        if widget and hasattr(widget, 'thumbnail_loaded'):
                                            widget.thumbnail_loaded = False
                                            print(f"🧹 Cleared thumbnail cache for MediaCard")
            
            print("✅ All thumbnail caches cleared")
            
        except Exception as e:
            print(f"❌ Error clearing thumbnail caches: {e}")
            import traceback
            traceback.print_exc()
    
    def can_access_ai_image(self) -> bool:
        """Check if current user can access AI Image feature"""
        if not self.auth_service or not self.current_user:
            return False
        return self.auth_service.can_use_ai_image(self.current_user.id)
    
    def can_access_ai_review(self) -> bool:
        """Check if current user can access AI Review feature (blocks only Free plan users)"""
        if not self.auth_service or not self.current_user:
            return False
        return self.auth_service.can_use_ai_review(self.current_user.id)
    
    def is_free_plan_user(self) -> bool:
        """Check if current user is on Free plan specifically"""
        if not self.auth_service or not self.current_user:
            return False  # Do not assume Free when auth is unavailable
        
        try:
            plan_info = self.get_user_plan_info()
            return plan_info.get("plan_type") == "Free"
        except:
            return False  # Do not assume Free on error
    
    def get_highlight_color_rgb(self, color_name: str) -> Tuple[int, int, int]:
        """Convert highlight color name to RGB values"""
        color_mapping = {
            "Blue": (59, 130, 246),     # #3B82F6
            "Green": (16, 185, 129),    # #10B981
            "Purple": (139, 92, 246),   # #8B5CF6
            "Red": (239, 68, 68),       # #EF4444
            "Orange": (245, 158, 11),   # #F59E0B
            "Pink": (236, 72, 153)      # #EC4899
        }
        return color_mapping.get(color_name, (59, 130, 246))  # Default to Blue
    
    def apply_highlight_color_from_settings(self):
        """Apply the current highlight color from settings to text input"""
        if hasattr(self, 'text_input') and hasattr(self.text_input, 'set_highlight_color'):
            # Get current highlight color from settings
            current_color = self.settings.get('highlight_color', 'Blue')
            r, g, b = self.get_highlight_color_rgb(current_color)
            
            # Apply the color with transparency
            self.text_input.set_highlight_color(QColor(r, g, b), 80)
            print(f"🎨 Applied highlight color: {current_color} -> RGB({r}, {g}, {b})")
    
    def get_user_plan_info(self) -> Dict[str, Any]:
        """Get current user's plan information"""
        if not self.auth_service or not self.current_user:
            # Do not assume a plan when Supabase/user is unavailable
            return {
                "plan_type": "Unknown",
                "analysis_count": 0,
                "ai_image_enabled": False,
                "ai_review_enabled": False
            }
        
        result = self.auth_service.get_plan_restrictions(self.current_user.id)
        
        if result["success"]:
            return result["restrictions"]
        else:
            # Do not fabricate a plan when Supabase lookup fails
            return {
                "plan_type": "Unknown",
                "analysis_count": 0,
                "ai_image_enabled": False,
                "ai_review_enabled": False
            }
    
    def show_plan_restriction_dialog(self, feature_name: str, required_plan: str):
        """Show a modern, kind plan restriction dialog"""
        title = f"{feature_name}"
        current = self.get_user_plan_info().get('plan_type', 'Free')
        # Build kind message
        msg = (
            f"This feature is available on {required_plan} and above.\n"
            f"Current plan: {current}.\n\n"
            "Upgrade to continue with all features."
        )
        # Reuse modern PremiumConfirmDialog styling
        try:
            def _open_pricing():
                try:
                    import webbrowser as _wb
                    _wb.open("https://dashboard.stuckai.net/pricing")
                except Exception:
                    pass
            dialog = PremiumConfirmDialog(
                self,
                title="Premium Feature",
                message=msg,
                icon="✨",
                confirm_text="Upgrade to Plus",
                confirm_variant="primary",
                on_confirm=_open_pricing
            )
            dialog.exec()
        except Exception:
            # Fallback
            QMessageBox.information(self, "Premium Feature", msg)
    
    def show_device_restriction_dialog(self, message: str):
        """Show modern dialog when device restriction is triggered"""
        dialog = ModernDeviceRestrictionDialog(self, message)
        dialog.exec()
    
    def apply_restricted_tab_styling(self):
        """Apply restricted styling to AI Images tab"""
        if hasattr(self, 'tab_widget'):
            # Get the AI Images tab index (should be index 2)
            ai_images_tab_index = 2
            
            # Get user plan info directly
            plan_info = self.get_user_plan_info()
            user_plan = plan_info.get("plan_type", "Free")
            
            if user_plan == "Free":
                # Apply restricted styling to the tab
                pass
            else:
                # For Plus/Elite users, show normal styling
                pass
    
    def create_restricted_tab_icon(self):
        """Create a restricted tab icon with lock symbol"""
        from PyQt6.QtSvg import QSvgRenderer
        from PyQt6.QtCore import QByteArray
        
        # Create a simple lock icon SVG
        lock_svg = """
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 7H11V5C11 2.24 8.76 0 6 0C3.24 0 1 2.24 1 5V7H0V16H12V7ZM3 5C3 3.34 4.34 2 6 2C7.66 2 9 3.34 9 5V7H3V5Z" fill="#9CA3AF"/>
        </svg>
        """
        
        try:
            # Create icon from SVG
            renderer = QSvgRenderer(QByteArray(lock_svg.encode('utf-8')))
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
        except Exception as e:
            print(f"Error creating restricted tab icon: {e}")
            return QIcon()
    def display_restricted_ai_images_content(self, tab_widget):
        """Display restricted AI Images content with upgrade message and background AI images"""
        # Clear existing content
        scroll_area = tab_widget.findChild(QScrollArea)
        if scroll_area:
            grid_widget = scroll_area.widget()
            if grid_widget:
                layout = grid_widget.layout()
                if layout:
                    # Clear existing content
                    for i in reversed(range(layout.count())):
                        child = layout.itemAt(i)
                        if child:
                            widget = child.widget()
                            if widget:
                                widget.deleteLater()
        
        # Create main container with background AI images
        main_container = QWidget()
        
        # Create main layout - no margins to fill entire space
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_container.setLayout(main_layout)
        
        # Create background widget with ai_lock.png
        background_widget = QWidget()
        
        # Load ai_lock.png as background using QLabel with proper overlay support
        try:
            lock_pixmap = QPixmap("ui/assets/ai_lock.png")
            if not lock_pixmap.isNull():
                # Create a QLabel to hold the background image
                background_label = QLabel(background_widget)
                background_label.setScaledContents(False)  # Manuel kontrol için False
                background_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                background_label.setStyleSheet("""
                    QLabel {
                        background: transparent;
                        border-radius: 0px;
                    }
                """)
                
                # Make background fully responsive (no large minimums)
                try:
                    background_widget.setMinimumSize(0, 0)
                    background_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                except Exception:
                    pass
                
                # İlk yükleme için PNG'yi oranlı ve ortalanmış şekilde ayarla (iç boşluk bırak)
                avail_w = max(1, background_widget.width() - 40)
                avail_h = max(1, background_widget.height() - 80)
                scaled = lock_pixmap.scaled(
                    avail_w,
                    avail_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                background_label.setPixmap(scaled)

                # PNG'nin boyutlarını al
                w = scaled.width()
                h = scaled.height()

                # Ortalamak için pozisyon hesapla
                x = (background_widget.width() - w) // 2
                y = (background_widget.height() - h) // 2

                # PNG'yi ortala
                background_label.setGeometry(x, y, w, h)
                
                # Set transparent background for the widget
                background_widget.setStyleSheet("""
                    QWidget {
                        background: transparent;
                        border-radius: 0px;
                    }
                """)
                
                # Store background_label reference for resize handling
                background_widget.background_label = background_label
                
                # Store background_label reference for resize handling
                background_widget.background_label = background_label
                
                # Enable overlay support by setting widget as parent for overlay elements
                background_widget.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
            else:
                # Fallback to gradient background if image loading fails
                background_widget.setStyleSheet("""
                    QWidget {
                        background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                            stop:0 rgba(59, 130, 246, 0.05),
                            stop:0.5 rgba(147, 51, 234, 0.05),
                        stop:1 rgba(236, 72, 153, 0.05));
                        border-radius: 16px;
                    }
                """)
        except Exception as e:
            # Fallback to gradient background if image loading fails
            background_widget.setStyleSheet("""
                QWidget {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                        stop:0 rgba(59, 130, 246, 0.05),
                        stop:0.5 rgba(147, 51, 234, 0.05),
                        stop:1 rgba(236, 72, 153, 0.05));
                    border-radius: 16px;
                }
            """)
        
        # Create background layout - no margins to fill entire space
        bg_layout = QVBoxLayout()
        bg_layout.setContentsMargins(0, 0, 0, 0)
        bg_layout.setSpacing(0)
        background_widget.setLayout(bg_layout)
        
        # Handle resize events to update both background image and button
        def resize_everything(event):
            if hasattr(background_widget, 'background_label'):
                # PNG'yi ekran boyutuna oranlı, taşma olmadan büyüt (iç boşlukla)
                avail_w = max(1, background_widget.width() - 40)
                avail_h = max(1, background_widget.height() - 80)
                scaled = lock_pixmap.scaled(
                    avail_w,
                    avail_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                background_widget.background_label.setPixmap(scaled)

                # PNG'nin yeni boyutlarını al
                w = scaled.width()
                h = scaled.height()

                # Ortalamak için pozisyon hesapla
                x = (background_widget.width() - w) // 2
                y = (background_widget.height() - h) // 2

                # PNG'yi ortala
                background_widget.background_label.setGeometry(x, y, w, h)

                # Upgrade butonu: boyut ve fontu ekrana göre ayarla, PNG'nin altına ortala
                if hasattr(background_widget, 'upgrade_button') and hasattr(background_widget, 'background_label'):
                    rect = background_widget.background_label.geometry()
                    avail_btn_w = max(140, min(320, rect.width()))
                    background_widget.upgrade_button.setMaximumWidth(avail_btn_w)
                    background_widget.upgrade_button.setMinimumWidth(min(200, avail_btn_w))
                    new_h = max(40, min(52, int(background_widget.height() * 0.06)))
                    background_widget.upgrade_button.setFixedHeight(new_h)
                    # Scale font and pill radius
                    try:
                        fs = 13 if avail_btn_w < 200 else (14 if avail_btn_w < 260 else 15)
                        f = background_widget.upgrade_button.font(); f.setPointSize(fs); background_widget.upgrade_button.setFont(f)
                        radius = max(14, new_h // 2)
                        background_widget.upgrade_button.setStyleSheet(f"""
                            QPushButton {{
                                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3B82F6, stop:1 #2563EB);
                                border: none; color: white; font-family: 'Inter', 'Arial', sans-serif;
                                font-size: {fs}px; font-weight: 600; border-radius: {radius}px; padding: 0 16px;
                            }}
                            QPushButton:hover {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #2563EB, stop:1 #1D4ED8); }}
                            QPushButton:pressed {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1D4ED8, stop:1 #1E40AF); }}
                        """)
                    except Exception:
                        pass
                    btn_w = background_widget.upgrade_button.width()
                    btn_h = background_widget.upgrade_button.height()
                    btn_x = (background_widget.width() - btn_w) // 2
                    btn_y = min(y + h + 20, background_widget.height() - btn_h - 40)
                    background_widget.upgrade_button.move(btn_x, btn_y)

            try:
                if hasattr(background_widget, '_extra_repos') and callable(background_widget._extra_repos):
                    background_widget._extra_repos()
            except Exception:
                pass
            event.accept()
        
        background_widget.resizeEvent = resize_everything
        
        # No need to load individual AI images - ai_lock.png is the background
        
        # Add background widget to main container
        main_layout.addWidget(background_widget, 1)  # Stretch factor 1 to fill available space
        
        # No need for content container anymore - button is directly on background widget
        
        # Upgrade button - add directly to background widget for proper overlay
        upgrade_button = QPushButton("Upgrade to Plus Plan", background_widget)
        try:
            upgrade_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        except Exception:
            pass
        upgrade_button.setMinimumWidth(140)
        upgrade_button.setMaximumWidth(320)
        upgrade_button.setMinimumHeight(44)
        upgrade_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #2563EB);
                border: none;
                color: white;
                font-family: 'Inter', 'Arial', sans-serif;
                font-size: 15px;
                font-weight: 600;
                border-radius: 22px;
                padding: 0 16px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2563EB, stop:1 #1D4ED8);
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1D4ED8, stop:1 #1E40AF);
            }
        """)
        upgrade_button.clicked.connect(lambda: webbrowser.open("https://dashboard.stuckai.net/pricing"))
        
        # Position button responsively in the center of the background widget, but lower
        self.position_upgrade_button(background_widget, upgrade_button)
        # Also update on every resize to follow the PNG
        try:
            def _reposition_btn():
                if hasattr(background_widget, 'background_label'):
                    rect = background_widget.background_label.geometry()
                    btn_w = upgrade_button.width()
                    btn_h = upgrade_button.height()
                    btn_x = rect.x() + (rect.width() - btn_w) // 2
                    btn_y = min(rect.y() + rect.height() + 20, background_widget.height() - btn_h - 40)
                    upgrade_button.move(btn_x, btn_y)
            background_widget._extra_repos = _reposition_btn
        except Exception:
            pass
        
        # Ensure button is on top of everything
        upgrade_button.raise_()
        upgrade_button.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        upgrade_button.show()  # Make sure button is visible
        
        # Button positioning is now handled in resize_everything function
        
        # Store references for responsive positioning
        background_widget.upgrade_button = upgrade_button
        
        # Button is now directly on background widget, no need for content container
        
        # Add the main container to the tab and disable scrolling
        if scroll_area:
            # Disable scrolling
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll_area.setWidgetResizable(True)
            
            grid_widget = scroll_area.widget()
            if grid_widget:
                layout = grid_widget.layout()
                if layout:
                    layout.addWidget(main_container, 0, 0, 1, 3)  # Span all columns
        
    def create_top_bar(self, parent_layout):
        """Create top bar for content area with action buttons"""
        self.top_bar_widget = QWidget()
        self.top_bar_widget.setFixedHeight(70)
        self.top_bar_widget.setStyleSheet("""
            QWidget {
                background: white;
                border-bottom: 1px solid #E5E7EB;
                border-top-left-radius: 20px;
                border-top-right-radius: 20px;
            }
        """)
        
        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(32, 16, 32, 16)
        top_bar_layout.setSpacing(16)
        self.top_bar_widget.setLayout(top_bar_layout)
        
        # Left side - Page title (dynamic based on sidebar selection)
        self.page_title_label = QLabel("Home")
        # Use Poppins SemiBold for page title
        if hasattr(self, 'loaded_fonts') and "Poppins SemiBold" in self.loaded_fonts:
            self.page_title_label.setFont(QFont("Poppins SemiBold", 20, QFont.Weight.Bold))
        elif hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            self.page_title_label.setFont(QFont("Poppins", 20, QFont.Weight.Bold))
        else:
            self.page_title_label.setFont(QFont("Arial", 20, QFont.Weight.Bold))
        self.page_title_label.setStyleSheet("""
            QLabel {
                color: #111827; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        top_bar_layout.addWidget(self.page_title_label)
        
        top_bar_layout.addStretch()
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(12)
        
        # Combined credits container (tek container)
        credits_container = QWidget()
        credits_container.setStyleSheet("""
            QWidget {
                background: transparent;
                border: none;
                padding: 0px;
                margin: 0px;
            }
        """)
        credits_layout = QHBoxLayout()
        credits_layout.setContentsMargins(0, 0, 0, 0)
        credits_layout.setSpacing(16)
        credits_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        credits_container.setLayout(credits_layout)
        
        # Analysis credits section
        analysis_credits_layout = QHBoxLayout()
        analysis_credits_layout.setContentsMargins(0, 0, 0, 0)
        analysis_credits_layout.setSpacing(0)
        analysis_credits_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # Analysis credits icon
        self.analysis_credits_icon = QLabel()
        try:
            credit_path = os.path.abspath("ui/assets/credit.png")
            if os.path.exists(credit_path):
                credit_pixmap = QPixmap(credit_path)
                if not credit_pixmap.isNull():
                    scaled_pixmap = credit_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.analysis_credits_icon.setPixmap(scaled_pixmap)
                    print(f"✅ Credit icon loaded successfully: {credit_path}")
                else:
                    print(f"⚠️ Failed to load credit icon: {credit_path}")
                    self.analysis_credits_icon.setText("🎯")
            else:
                print(f"⚠️ Credit icon not found: {credit_path}")
                self.analysis_credits_icon.setText("🎯")
        except Exception as e:
            print(f"⚠️ Error loading credit icon: {e}")
            self.analysis_credits_icon.setText("🎯")
        
        self.analysis_credits_icon.setStyleSheet("background: transparent; margin: 0px;")
        self.analysis_credits_icon.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        analysis_credits_layout.addWidget(self.analysis_credits_icon)
        
        # Analysis credits text
        self.analysis_credits_badge = QLabel("Analysis Credits: 0")
        self.analysis_credits_badge.setStyleSheet("""
            QLabel {
                color: #3B82F6;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
        """)
        self.analysis_credits_badge.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        analysis_credits_layout.addWidget(self.analysis_credits_badge)
        
        # AI Image credits section
        ai_credits_layout = QHBoxLayout()
        ai_credits_layout.setContentsMargins(0, 0, 0, 0)
        ai_credits_layout.setSpacing(0)
        ai_credits_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        
        # AI Image credits icon
        self.ai_image_credits_icon = QLabel()
        try:
            ai_credit_path = os.path.abspath("ui/assets/ai_credit.png")
            if os.path.exists(ai_credit_path):
                ai_credit_pixmap = QPixmap(ai_credit_path)
                if not ai_credit_pixmap.isNull():
                    scaled_pixmap = ai_credit_pixmap.scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.ai_image_credits_icon.setPixmap(scaled_pixmap)
                    print(f"✅ AI Credit icon loaded successfully: {ai_credit_path}")
                else:
                    print(f"⚠️ Failed to load AI credit icon: {ai_credit_path}")
                    self.ai_image_credits_icon.setText("🎨")
            else:
                print(f"⚠️ AI Credit icon not found: {ai_credit_path}")
                self.ai_image_credits_icon.setText("🎨")
        except Exception as e:
            print(f"⚠️ Error loading AI credit icon: {e}")
            self.ai_image_credits_icon.setText("🎨")
        
        self.ai_image_credits_icon.setStyleSheet("background: transparent; margin: 0px;")
        self.ai_image_credits_icon.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        ai_credits_layout.addWidget(self.ai_image_credits_icon)
        
        # AI Image credits text
        self.ai_image_credits_badge = QLabel("AI Image Credits: 0")
        self.ai_image_credits_badge.setStyleSheet("""
            QLabel {
                color: #8B5CF6;
                font-size: 12px;
                font-weight: 600;
                background: transparent;
                border: none;
            }
        """)
        self.ai_image_credits_badge.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        ai_credits_layout.addWidget(self.ai_image_credits_badge)
        
        # Add both credit sections to the combined container
        credits_layout.addLayout(analysis_credits_layout)
        credits_layout.addLayout(ai_credits_layout)
        
        # Add the combined credits container to button layout
        button_layout.addWidget(credits_container)
        
        # Download button
        self.download_btn = ModernButton("📥 Download")
        self.download_btn.clicked.connect(self.download_selected_media)
        self.download_btn.setEnabled(False)
        button_layout.addWidget(self.download_btn)
        
        # Start Analysis button
        self.analyze_btn = ModernButton("Start Analysis", "primary")
        self.analyze_btn.clicked.connect(self.start_analysis)
        button_layout.addWidget(self.analyze_btn)
        
        top_bar_layout.addLayout(button_layout)
        
        parent_layout.addWidget(self.top_bar_widget)
        
    def create_content_area(self, parent_layout):
        """Create main content area"""
        content_widget = QWidget()
        content_layout = QHBoxLayout()
        # Default margins for main interface, will be adjusted for welcome page
        content_layout.setContentsMargins(32, 24, 32, 24)
        content_layout.setSpacing(32)
        content_widget.setLayout(content_layout)
        
        # Store reference for later use
        self.content_widget = content_widget
        self.content_layout = content_layout  # Store layout reference too
        
        # Left panel - Text Input
        self.left_panel = QWidget()
        self.create_left_panel_content(self.left_panel, content_layout)
        
        # Right panel - Results
        self.right_panel = QWidget()
        self.create_right_panel_content(self.right_panel, content_layout)
        
        parent_layout.addWidget(content_widget)
        
    def create_left_panel_content(self, left_widget, parent_layout):
        """Create left panel with text input"""
        left_widget.setFixedWidth(400)
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(16)
        left_widget.setLayout(left_layout)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)
        
        # Text logo icon
        text_logo_icon = QLabel()
        text_logo_icon.setStyleSheet("margin-top: 2px;")
        try:
            text_logo_path = os.path.abspath("ui/assets/text_logo.png")
            if os.path.exists(text_logo_path):
                pixmap = QPixmap(text_logo_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    text_logo_icon.setPixmap(scaled_pixmap)
                    print(f"✅ Text logo loaded successfully: {text_logo_path}")
                else:
                    print(f"⚠️ Failed to load text logo: {text_logo_path}")
            else:
                print(f"⚠️ Text logo not found: {text_logo_path}")
        except Exception as e:
            print(f"⚠️ Error loading text logo: {e}")
        
        header_layout.addWidget(text_logo_icon)
        
        # Title
        title_label = QLabel("Your Script / Content")
        # Use Poppins SemiBold for title
        if hasattr(self, 'loaded_fonts') and "Poppins SemiBold" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 18, QFont.Weight.Bold))
        elif hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins", 18, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #111827;
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        left_layout.addLayout(header_layout)
        
        # Subtitle removed - placeholder text will be in the text input instead
        
        # Text input
        self.text_input = HighlightableTextWidget()
        self.text_input.setFont(QFont("Inter", 14))
        # Set placeholder text
        self.text_input.setPlaceholderText("Enter your content to analyze...")
        self.text_input.setStyleSheet("""
            QTextEdit {
                background: white;
                border: 1px solid #D1D5DB;
                border-radius: 12px;
                padding: 16px;
                color: #111827;
                selection-background-color: #DBEAFE;
            }
            QTextEdit:focus {
                border-color: #3B82F6;
                outline: none;
            }
            QTextEdit::placeholder {
                color: rgba(107, 114, 128, 0.6);
                font-style: italic;
            }
            QScrollBar:vertical {
                background: #F5F5F5;
                width: 12px;
                border-radius: 6px;
                margin: 0px;
                border: 1px solid #E5E5E5;
            }
            QScrollBar::handle:vertical {
                background: #D4D4D4;
                border-radius: 6px;
                min-height: 40px;
                margin: 1px;
                border: 1px solid #B5B5B5;
            }
            QScrollBar::handle:vertical:hover {
                background: #A3A3A3;
                border: 1px solid #8B8B8B;
            }
            QScrollBar::handle:vertical:pressed {
                background: #737373;
                border: 1px solid #525252;
            }
            QScrollBar::add-line:vertical {
                height: 24px;
                background: #F5F5F5;
                border-radius: 6px;
                subcontrol-position: bottom;
                subcontrol-origin: margin;
                border: 1px solid #E5E5E5;
            }
            QScrollBar::sub-line:vertical {
                height: 24px;
                background: #F5F5F5;
                border-radius: 6px;
                subcontrol-position: top;
                subcontrol-origin: margin;
                border: 1px solid #E5E5E5;
            }
            QScrollBar::add-line:vertical::down-arrow {
                image: none;
                border: none;
                background: none;
                color: #737373;
                font-size: 14px;
                font-weight: bold;
                content: "▼";
            }
            QScrollBar::sub-line:vertical::up-arrow {
                image: none;
                border: none;
                background: none;
                color: #737373;
                font-size: 14px;
                font-weight: bold;
                content: "▲";
            }
            QScrollBar::add-line:vertical:hover {
                background: #E5E5E5;
                border: 1px solid #D4D4D4;
            }
            QScrollBar::sub-line:vertical:hover {
                background: #E5E5E5;
                border: 1px solid #D4D4D4;
            }
            QScrollBar::add-line:vertical:pressed {
                background: #D4D4D4;
                border: 1px solid #A3A3A3;
            }
            QScrollBar::sub-line:vertical:pressed {
                background: #D4D4D4;
                border: 1px solid #A3A3A3;
            }
        """)
        
        # Set highlight color based on settings
        self.apply_highlight_color_from_settings()
        
        # Connect text changed signal for character counting
        self.text_input.textChanged.connect(self.on_text_changed)
        
        left_layout.addWidget(self.text_input)
        
        # Character counter
        self.char_counter_label = QLabel("0 / 10,000 characters")
        self.char_counter_label.setFont(QFont("Inter", 12))
        self.char_counter_label.setStyleSheet("""
            QLabel {
                color: #6B7280;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                padding: 4px 0px;
            }
        """)
        self.char_counter_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        left_layout.addWidget(self.char_counter_label)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 2px;
                background: #F3F4F6;
            }
            QProgressBar::chunk {
                background: #3B82F6;
                border-radius: 2px;
            }
        """)
        left_layout.addWidget(self.progress_bar)
        
        # Status label

        
        parent_layout.addWidget(left_widget)
        
    def create_right_panel_content(self, right_widget, parent_layout):
        """Create right panel with results"""
        right_layout = QVBoxLayout()
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(4)
        right_widget.setLayout(right_layout)
        
        # Header
        header_widget = QWidget()
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)
        header_widget.setLayout(header_layout)
        
        # Left side - Title
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        
        # Camera icon
        camera_icon = QLabel()
        camera_icon.setStyleSheet("margin-top: 2px;")
        try:
            camera_path = os.path.abspath("ui/assets/camera.png")
            if os.path.exists(camera_path):
                pixmap = QPixmap(camera_path)
                if not pixmap.isNull():
                    try:
                        from PyQt6.QtGui import QGuiApplication
                        screen = QGuiApplication.primaryScreen()
                        dpr = float(screen.devicePixelRatio()) if screen else 1.0
                    except Exception:
                        dpr = 1.0
                    target_w = int(48 * dpr)
                    target_h = int(48 * dpr)
                    scaled_pixmap = pixmap.scaled(
                        target_w,
                        target_h,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    try:
                        scaled_pixmap.setDevicePixelRatio(dpr)
                    except Exception:
                        pass
                    camera_icon.setPixmap(scaled_pixmap)
                    print(f"✅ Camera icon loaded successfully: {camera_path} (dpr={dpr})")
                else:
                    print(f"⚠️ Failed to load camera icon: {camera_path}")
            else:
                print(f"⚠️ Camera icon not found: {camera_path}")
        except Exception as e:
            print(f"⚠️ Error loading camera icon: {e}")
        
        title_layout.addWidget(camera_icon)
        
        # Title
        title_label = QLabel("Analysis Results")
        # Use Poppins SemiBold for Analysis Results title
        if hasattr(self, 'loaded_fonts') and "Poppins SemiBold" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins SemiBold", 18, QFont.Weight.Bold))
        elif hasattr(self, 'loaded_fonts') and "Poppins" in self.loaded_fonts:
            title_label.setFont(QFont("Poppins", 18, QFont.Weight.Bold))
        else:
            title_label.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title_label.setStyleSheet("""
            QLabel {
                color: #111827; 
                background: transparent;
                font-family: 'Poppins SemiBold', 'Poppins', 'Arial', sans-serif;
            }
        """)
        title_layout.addWidget(title_label)
        # Store reference for coachmarks anchoring
        try:
            self.analysis_results_title_label = title_label
        except Exception:
            pass
        
        header_layout.addLayout(title_layout)
        header_layout.addStretch()
        
        # Right side - Navigation (initially hidden)
        self.nav_container = QWidget()
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(12)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        self.nav_container.setLayout(nav_layout)
        
        # Scene info
        self.scene_nav_label = QLabel("Chapter 1/1 → Scene 1/8")
        self.scene_nav_label.setFont(QFont("Inter", 14, QFont.Weight.Medium))
        self.scene_nav_label.setStyleSheet("color: #6B7280;")
        nav_layout.addWidget(self.scene_nav_label)
        
        # Navigation buttons
        nav_button_style = """
            QPushButton {
                background: white;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 8px;
                color: #6B7280;
                font-size: 14px;
                min-width: 32px;
                max-width: 32px;
                min-height: 32px;
                max-height: 32px;
            }
            QPushButton:hover {
                border-color: #3B82F6;
                background: #F8FAFC;
            }
            QPushButton:disabled {
                color: #D1D5DB;
                background: #F9FAFB;
            }
        """
        
        # Create SVG icons for navigation buttons
        def create_svg_icon(svg_path: str, size: QSize = QSize(24, 24), color: str = "#6B7280") -> QIcon:
            """Create icon from SVG file"""
            try:
                if os.path.exists(svg_path):
                    with open(svg_path, 'r', encoding='utf-8') as f:
                        svg_content = f.read()
                    
                    # Replace currentColor with actual color
                    svg_content = svg_content.replace('stroke="currentColor"', f'stroke="{color}"')
                    
                    # Create QIcon from SVG content
                    icon = QIcon()
                    pixmap = QPixmap(size)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    
                    renderer = QSvgRenderer()
                    success = renderer.load(QByteArray(svg_content.encode('utf-8')))
                    
                    if success:
                        painter = QPainter(pixmap)
                        renderer.render(painter)
                        painter.end()
                        
                        icon.addPixmap(pixmap)
                        return icon
            except Exception as e:
                print(f"Error loading SVG icon {svg_path}: {e}")
            
            # Fallback to text if SVG fails
            return QIcon()
        
        # Create navigation buttons with SVG icons
        self.prev_btn = QPushButton()
        prev_icon = create_svg_icon("ui/assets/step-back.svg", QSize(20, 20), "#6B7280")
        self.prev_btn.setIcon(prev_icon)
        self.prev_btn.setIconSize(QSize(20, 20))
        self.prev_btn.setStyleSheet(nav_button_style)
        self.prev_btn.clicked.connect(self.prev_scene)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton()
        next_icon = create_svg_icon("ui/assets/step-forward.svg", QSize(20, 20), "#6B7280")
        self.next_btn.setIcon(next_icon)
        self.next_btn.setIconSize(QSize(20, 20))
        self.next_btn.setStyleSheet(nav_button_style)
        self.next_btn.clicked.connect(self.next_scene)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)
        
        # Initially hide navigation
        self.nav_container.hide()
        
        header_layout.addWidget(self.nav_container)
        right_layout.addWidget(header_widget)
        
        # Scene info (moved to top, right after header)
        self.scene_name_label = QLabel("Select analysis to view scene details")
        # Use Inter Regular for scene info
        if hasattr(self, 'loaded_fonts') and "Inter 24pt" in self.loaded_fonts:
            self.scene_name_label.setFont(QFont("Inter 24pt", 16, QFont.Weight.Bold))
        else:
            self.scene_name_label.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        self.scene_name_label.setStyleSheet("""
            QLabel {
                color: #111827; 
                background: transparent;
                font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
            }
        """)
        right_layout.addWidget(self.scene_name_label)
        
        # University name
        self.university_label = QLabel("")
        self.university_label.setFont(QFont("Inter", 14))
        self.university_label.setStyleSheet("color: #6B7280;")
        right_layout.addWidget(self.university_label)
        
        # Visual prompt
        self.visual_prompt_label = QLabel("")
        self.visual_prompt_label.setFont(QFont("Inter", 12))
        self.visual_prompt_label.setStyleSheet("color: #9CA3AF;")
        self.visual_prompt_label.setWordWrap(True)
        right_layout.addWidget(self.visual_prompt_label)
        
        # Add small spacer to reduce gap before tabs
        tab_spacer = QSpacerItem(20, 4, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        right_layout.addItem(tab_spacer)
        
        # Create custom tab bar with download button
        tab_bar_container = QWidget()
        tab_bar_layout = QHBoxLayout()
        tab_bar_layout.setContentsMargins(0, 0, 0, 0)
        tab_bar_layout.setSpacing(16)
        tab_bar_container.setLayout(tab_bar_layout)
        
        # Create custom tab buttons
        self.create_custom_tab_bar(tab_bar_layout)
        
        # Add download button to the same row
        tab_bar_layout.addWidget(self.download_btn)
        
        right_layout.addWidget(tab_bar_container)
        
        # Create tab content area
        self.create_tab_content(right_layout)
        
        parent_layout.addWidget(right_widget)
        
    def create_custom_tab_bar(self, parent_layout):
        """Create custom tab bar with buttons"""
        # Create tab buttons
        self.stock_images_tab_btn = QPushButton("Stock Images")
        self.stock_videos_tab_btn = QPushButton("Stock Videos")
        self.ai_images_tab_btn = QPushButton("AI Images")
        
        # Style the tab buttons
        default_tab_style = """
            QPushButton {
                background: transparent;
                border: none;
                padding: 8px 16px;
                color: #6B7280;
                font-size: 16px;
                font-weight: 500;
                border-bottom: 2px solid transparent;
            }
            QPushButton:hover {
                color: #374151;
            }
        """
        
        # Apply default style to all buttons
        self.stock_images_tab_btn.setStyleSheet(default_tab_style)
        self.stock_videos_tab_btn.setStyleSheet(default_tab_style)
        self.ai_images_tab_btn.setStyleSheet(default_tab_style)
        
        # Make buttons checkable
        self.stock_images_tab_btn.setCheckable(True)
        self.stock_videos_tab_btn.setCheckable(True)
        self.ai_images_tab_btn.setCheckable(True)
        
        # Set default selection
        self.stock_videos_tab_btn.setChecked(True)
        
        # Connect signals
        self.stock_images_tab_btn.clicked.connect(lambda: self.switch_tab(0))
        self.stock_videos_tab_btn.clicked.connect(lambda: self.switch_tab(1))
        self.ai_images_tab_btn.clicked.connect(lambda: self.switch_tab(2))
        
        # Add to layout
        parent_layout.addWidget(self.stock_images_tab_btn)
        parent_layout.addWidget(self.stock_videos_tab_btn)
        parent_layout.addWidget(self.ai_images_tab_btn)
        
        # Add stretch to push download button to the right
        parent_layout.addStretch()
        
    def create_tab_content(self, parent_layout):
        """Create tab content area"""
        # Use QStackedWidget instead of QTabWidget to avoid tab bar
        self.tab_widget = QStackedWidget()
        
        # Create tabs
        self.stock_images_tab = self.create_media_tab("stock_images")
        self.stock_videos_tab = self.create_media_tab("stock_videos")
        self.ai_images_tab = self.create_media_tab("ai_images")
        
        self.tab_widget.addWidget(self.stock_images_tab)
        self.tab_widget.addWidget(self.stock_videos_tab)
        self.tab_widget.addWidget(self.ai_images_tab)
        
        # Check user plan and apply appropriate styling
        # Get user plan info directly
        plan_info = self.get_user_plan_info()
        user_plan = plan_info.get("plan_type", "Free")
        
        print(f"DEBUG: User plan detected: {user_plan}")
        
        if user_plan == "Free":
            # Free plan user - apply restricted styling
            print("DEBUG: Applying restricted styling for Free plan")
            self.ai_images_tab_restricted = True
            self.apply_restricted_tab_styling()
        else:
            # Plus/Elite user - no restrictions
            print(f"DEBUG: Applying normal styling for {user_plan} plan")
            self.ai_images_tab_restricted = False
        
        # Set default tab
        self.tab_widget.setCurrentIndex(0)  # Stock Images
        
        # Connect tab change
        self.tab_widget.currentChanged.connect(self.on_tab_changed)
        
        # Set initial tab button state
        self.switch_tab(0)  # Stock Images
        
        parent_layout.addWidget(self.tab_widget)
        
    def switch_tab(self, tab_index):
        """Switch between tabs"""
        # Uncheck all buttons and reset styles
        self.stock_images_tab_btn.setChecked(False)
        self.stock_videos_tab_btn.setChecked(False)
        self.ai_images_tab_btn.setChecked(False)
        
        # Reset all button styles to default
        default_style = """
            QPushButton {
                background: transparent;
                border: none;
                padding: 8px 16px;
                color: #6B7280;
                font-size: 16px;
                font-weight: 500;
                border-bottom: 2px solid transparent;
                border-radius: 0px;
            }
            QPushButton:hover {
                color: #374151;
            }
        """
        selected_style = default_style + """
            QPushButton:checked {
                color: #3B82F6;
                border-bottom: 2px solid #3B82F6;
                border-radius: 0px;
            }
        """
        
        self.stock_images_tab_btn.setStyleSheet(default_style)
        self.stock_videos_tab_btn.setStyleSheet(default_style)
        self.ai_images_tab_btn.setStyleSheet(default_style)
        
        # Check the selected button and apply specific styling
        if tab_index == 0:
            self.stock_images_tab_btn.setChecked(True)
            self.stock_images_tab_btn.setStyleSheet(selected_style)
        elif tab_index == 1:
            self.stock_videos_tab_btn.setChecked(True)
            self.stock_videos_tab_btn.setStyleSheet(selected_style)
        elif tab_index == 2:
            self.ai_images_tab_btn.setChecked(True)
            # Gradient text + gradient underline (straight) like on monitor
            self.ai_images_tab_btn.setStyleSheet(default_style + """
                QPushButton:checked {
                    color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5170FF,
                        stop:0.5 #7A5CFF,
                        stop:1 #FF66C4);
                    border-bottom: 2px solid qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #5170FF,
                        stop:0.5 #7A5CFF,
                        stop:1 #FF66C4);
                    border-radius: 0px;
                }
            """)
        
        # Switch tab content
        self.tab_widget.setCurrentIndex(tab_index)
        
    def create_media_tab(self, tab_type="ai_images"):
        """Create media tab with scroll area"""
        tab_widget = QWidget()
        tab_widget.setStyleSheet("background: white;")
        tab_layout = QVBoxLayout()
        tab_layout.setContentsMargins(24, 16, 24, 24)
        tab_widget.setLayout(tab_layout)
        
        # Scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: white;
            }
            QScrollBar:vertical {
                background: #F9FAFB;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB;
                border-radius: 4px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9CA3AF;
            }
        """)
        
        # Grid widget
        grid_widget = QWidget()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(20)
        grid_widget.setLayout(grid_layout)
        
        # Initial message
        if tab_type == "stock_images":
            self.stock_images_suggestions_label = QLabel("▶ Run analysis to see media suggestions")
            self.stock_images_suggestions_label.setFont(QFont("Inter", 16))
            self.stock_images_suggestions_label.setStyleSheet("color: #9CA3AF;")
            self.stock_images_suggestions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid_layout.addWidget(self.stock_images_suggestions_label, 0, 0, 1, 3)
        elif tab_type == "stock_videos":
            self.stock_videos_suggestions_label = QLabel("▶ Run analysis to see media suggestions")
            self.stock_videos_suggestions_label.setFont(QFont("Inter", 16))
            self.stock_videos_suggestions_label.setStyleSheet("color: #9CA3AF;")
            self.stock_videos_suggestions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid_layout.addWidget(self.stock_videos_suggestions_label, 0, 0, 1, 3)
        else:  # ai_images
            self.ai_media_suggestions_label = QLabel("▶ Run analysis to see media suggestions")
            self.ai_media_suggestions_label.setFont(QFont("Inter", 16))
            self.ai_media_suggestions_label.setStyleSheet("color: #9CA3AF;")
            self.ai_media_suggestions_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid_layout.addWidget(self.ai_media_suggestions_label, 0, 0, 1, 3)
        
        scroll_area.setWidget(grid_widget)
        tab_layout.addWidget(scroll_area)
        
        return tab_widget
        
    def create_status_bar(self):
        """Create status bar"""
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: white;
                border-top: 1px solid #E5E7EB;
                padding: 8px 16px;
            }
        """)
        self.setStatusBar(self.status_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Inter", 12))
        self.status_label.setStyleSheet("color: #6B7280;")
        self.status_bar.addWidget(self.status_label)
        
    def setup_style(self):
        """Setup application styling"""
        self.setStyleSheet("""
            QMainWindow {
                background: #F9FAFB;
            }
            QWidget {
                background: #F9FAFB;
                font-family: 'Inter', 'Segoe UI', 'Roboto', sans-serif;
            }
        """)
        
    def load_default_text(self):
        """Load default text"""
        default_text = read_input_file()
        if default_text:
            # Clear any existing highlights first
            if hasattr(self.text_input, 'clear_highlight'):
                self.text_input.clear_highlight()
            self.text_input.setPlainText(default_text)
            # Update character counter after loading default text
            self.update_character_counter()
    
    def on_text_changed(self):
        """Handle text changes and update character counter"""
        self.update_character_counter()
        try:
            text_now = self.text_input.toPlainText().strip() if hasattr(self, 'text_input') else ""
            if text_now:
                # Hide textbox coachmark overlay and ensure full cleanup before proceeding
                was_text_overlay_active = False
                try:
                    was_text_overlay_active = (
                        getattr(self, '_coach_overlay', None)
                        and getattr(self._coach_overlay, 'objectName', lambda: '')() == 'coach_overlay_text'
                    )
                    if was_text_overlay_active:
                        # Only close if this is the textbox overlay
                        self.hide_coachmark()
                        # Extra cleanup in case top-level labels remain
                        try:
                            if getattr(self, '_coach_pointer_label', None):
                                self._coach_pointer_label.close()
                                self._coach_pointer_label.deleteLater()
                                self._coach_pointer_label = None
                        except Exception:
                            pass
                        try:
                            if getattr(self, '_coach_caption', None):
                                self._coach_caption.close()
                                self._coach_caption.deleteLater()
                                self._coach_caption = None
                        except Exception:
                            pass
                        try:
                            self._coach_pointer_movie = None
                        except Exception:
                            pass
                except Exception:
                    pass
                # Only schedule Start Analysis coachmark when the textbox overlay was active
                if was_text_overlay_active:
                    if (not getattr(self, '_start_coachmark_shown', False)
                            and not getattr(self, '_start_coachmark_triggered', False)):
                        try:
                            self._start_coachmark_triggered = True
                        except Exception:
                            pass
                        QTimer.singleShot(0, self._try_show_start_button_coachmark_once)
        except Exception:
            pass
    
    def update_character_counter(self):
        """Update the character counter display"""
        text = self.text_input.toPlainText()
        char_count = len(text)
        max_chars = 10000
        
        # Update counter label
        self.char_counter_label.setText(f"{char_count:,} / {max_chars:,} characters")
        
        # Change color based on character count
        if char_count > max_chars:
            self.char_counter_label.setStyleSheet("""
                QLabel {
                    color: #EF4444;
                    background: transparent;
                    font-family: 'Inter', 'Arial', sans-serif;
                    padding: 4px 0px;
                    font-weight: 500;
                }
            """)
        elif char_count > max_chars * 0.9:  # Warning at 90%
            self.char_counter_label.setStyleSheet("""
                QLabel {
                    color: #F59E0B;
                    background: transparent;
                    font-family: 'Inter', 'Arial', sans-serif;
                    padding: 4px 0px;
                    font-weight: 500;
                }
            """)
        else:
            self.char_counter_label.setStyleSheet("""
                QLabel {
                    color: #6B7280;
                    background: transparent;
                    font-family: 'Inter', 'Arial', sans-serif;
                    padding: 4px 0px;
                }
            """)
            
    def start_analysis(self):
        """Start analysis"""
        # Clear all caches before starting new analysis
        if hasattr(self, 'scene_media_cache'):
            self.scene_media_cache.clear()
            print("Scene media cache cleared for new analysis")
        
        if hasattr(self, 'scene_loading_states'):
            self.scene_loading_states.clear()
            print("Scene loading states cleared for new analysis")
        
        if hasattr(self, 'background_analysis_threads'):
            self.background_analysis_threads.clear()
            print("Background analysis threads cleared for new analysis")
        
        # Clear credits cache
        if hasattr(self, '_credits_cache'):
            delattr(self, '_credits_cache')
        if hasattr(self, '_credits_cache_time'):
            delattr(self, '_credits_cache_time')
        
        # Clear thumbnail caches from MediaCard instances
        self.clear_thumbnail_caches()

        # Clear AI generation status/results cache
        if hasattr(self, 'ai_generation_status'):
            self.ai_generation_status.clear()
        if hasattr(self, 'ai_generation_results'):
            self.ai_generation_results.clear()
        if hasattr(self, 'ai_generation_media_cards'):
            self.ai_generation_media_cards.clear()
        if hasattr(self, 'ai_generation_threads'):
            # Stop any running generation threads safely
            try:
                for prompt, thread in list(self.ai_generation_threads.items()):
                    try:
                        if thread.isRunning():
                            thread.requestInterruption()
                            thread.wait(100)
                    except Exception:
                        pass
                self.ai_generation_threads.clear()
            except Exception:
                self.ai_generation_threads = {}
        print("AI generation caches cleared for new analysis")

        # Clear on-disk AI image cache (downloads/ai_*.jpg)
        try:
            downloads_dir = os.path.join(self.get_project_root(), "downloads")
            if os.path.exists(downloads_dir):
                for name in os.listdir(downloads_dir):
                    if name.startswith("ai_") and name.endswith(".jpg"):
                        try:
                            os.remove(os.path.join(downloads_dir, name))
                        except Exception:
                            pass
                print("AI image disk cache cleared")
        except Exception as e:
            print(f"Warning: could not clear AI image disk cache: {e}")
        
        # Immediately update UI to show analyzing state
        self.analyze_btn.setEnabled(False)
        self.analyze_btn.setText("Analyzing...")
        self.progress_bar.setValue(0)
        
        # Hide navigation during analysis
        if hasattr(self, 'nav_container'):
            self.nav_container.hide()
        
        # Update media suggestions labels for all tabs
        if hasattr(self, 'stock_images_suggestions_label') and self.stock_images_suggestions_label is not None:
            try:
                self.stock_images_suggestions_label.setText("▶ Analysis results will show media suggestions when complete")
                self.stock_images_suggestions_label.setStyleSheet("color: #3B82F6;")  # Blue color to indicate active state
            except RuntimeError:
                # Widget has been deleted, remove the reference
                self.stock_images_suggestions_label = None
                print("Warning: stock_images_suggestions_label was deleted")
        
        if hasattr(self, 'stock_videos_suggestions_label') and self.stock_videos_suggestions_label is not None:
            try:
                self.stock_videos_suggestions_label.setText("▶ Analysis results will show media suggestions when complete")
                self.stock_videos_suggestions_label.setStyleSheet("color: #3B82F6;")  # Blue color to indicate active state
            except RuntimeError:
                # Widget has been deleted, remove the reference
                self.stock_videos_suggestions_label = None
                print("Warning: stock_videos_suggestions_label was deleted")
        
        if hasattr(self, 'ai_media_suggestions_label') and self.ai_media_suggestions_label is not None:
            try:
                self.ai_media_suggestions_label.setText("▶ Analysis results will show media suggestions when complete")
                self.ai_media_suggestions_label.setStyleSheet("color: #3B82F6;")  # Blue color to indicate active state
            except RuntimeError:
                # Widget has been deleted, remove the reference
                self.ai_media_suggestions_label = None
                print("Warning: ai_media_suggestions_label was deleted")
        
        # Force UI update immediately
        QApplication.processEvents()
        
        # Get text input
        text = self.text_input.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Analyze", "Please enter text to analyze.")
            # Reset UI on error
            self.analyze_btn.setEnabled(True)
            self.analyze_btn.setText("Start Analysis")
            return
        
        # Check character limit
        if len(text) > 10000:
            char_limit_dialog = ModernCharLimitDialog(self, len(text))
            char_limit_dialog.exec()
            # Reset UI on error
            self.analyze_btn.setEnabled(True)
            self.analyze_btn.setText("Start Analysis")
            return
        
        # Check if user is authenticated (fast check)
        if not self.current_user:
            QMessageBox.warning(self, "Sign In Required", "Please sign in to start the analysis.")
            # Reset UI on error
            self.analyze_btn.setEnabled(True)
            self.analyze_btn.setText("Start Analysis")
            return
        
        # Check auth service (fast check)
        if not self.auth_service:
            QMessageBox.warning(
                self,
                "Sign In",
                "We couldn't reach the sign-in service. Please restart the app and try again."
            )
            # Reset UI on error
            self.analyze_btn.setEnabled(True)
            self.analyze_btn.setText("Start Analysis")
            return
        
        # Start validation in background thread to avoid UI blocking
        self.validation_thread = ValidationThread(self.auth_service, self.current_user.id, text, self.settings.copy())
        self.validation_thread.validation_complete.connect(self.on_validation_complete)
        self.validation_thread.validation_error.connect(self.on_validation_error)
        self.validation_thread.start()
    def on_validation_complete(self, result):
        """Handle validation completion"""
        try:
            # Reset duplicate tracking and small caches at the start of an analysis session
            try:
                from logic.stock_api_service import stock_service
                stock_service.reset_duplicate_tracking()
            except Exception:
                pass
            # Check AI Image restrictions and modify settings accordingly
            if not self.can_access_ai_image():
                # Disable AI Images for non-Elite users
                result['settings']['ai_images_count'] = 0
                print("AI Images disabled for current plan")
            
            # Show remaining credits
            remaining = result.get("remaining_count", result.get("analysis_count", 0) - 1)
            self.update_analysis_credits_display(remaining)
            
            # Start smart analysis thread
            self.analysis_thread = SmartAnalysisThread(
                result['text'], 
                result['settings'],
                user_id=self.current_user.id if self.current_user else None,
                cost_tracking_service=self.cost_tracking_service,
                scene_cost_tracking_service=self.scene_cost_tracking_service
            )
            self.analysis_thread.progress_updated.connect(self.update_progress)
            self.analysis_thread.analysis_complete.connect(self.analysis_complete)
            self.analysis_thread.analysis_error.connect(self.analysis_error)
            self.analysis_thread.start()
            
        except Exception as e:
            print(f"Error in validation completion: {e}")
            self.analysis_error("Validation failed")
    
    def on_validation_error(self, error_type, message):
        """Handle validation errors"""
        # Reset UI on error
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Start Analysis")
        
        if error_type == "credits":
            credits_dialog = ModernCreditsDialog(self)
            credits_dialog.exec()
        elif error_type == "device_restriction":
            self.show_device_restriction_dialog(message)
        elif error_type == "auth":
            QMessageBox.warning(self, "Sign In", "Your session needs attention. Please sign in again.")
        else:
            # Heuristic: some RPC errors wrap our JSON in a generic message
            msg_lower = (message or "").lower()
            if ("device_or_ip_already_used" in msg_lower or
                "device_ip_already_used" in msg_lower or
                ("json could not be generated" in msg_lower and "restricted" in msg_lower)):
                self.show_device_restriction_dialog(message)
            else:
                QMessageBox.warning(self, "Notice", "Something went wrong. Please try again.")
        
    def update_progress(self, progress: float, status: str):
        """Update progress with smooth animation"""
        target_progress = int(progress * 100)
        current_progress = self.progress_bar.value()
        
        # Only animate if there's a significant change
        if abs(target_progress - current_progress) > 2:
            # Create smooth animation
            from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
            
            # Create animation for progress bar
            self.progress_animation = QPropertyAnimation(self.progress_bar, b"value")
            self.progress_animation.setDuration(500)  # 500ms animation for smoother feel
            self.progress_animation.setStartValue(current_progress)
            self.progress_animation.setEndValue(target_progress)
            self.progress_animation.setEasingCurve(QEasingCurve.Type.OutQuart)
            
            # Start animation
            self.progress_animation.start()
        else:
            # For small changes, update directly
            self.progress_bar.setValue(target_progress)
        
        # Update status labels (removed - status bar no longer exists)

        
        # Force application to process events
        QApplication.processEvents()
        
    def analysis_complete(self, scenes_data: List[Dict[str, Any]]):
        """Handle analysis completion"""
        self.scenes_data = scenes_data
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Start Analysis")
        
        scenes_count = len(scenes_data)
        # Status label removed - status bar no longer exists
        
        # Animate to 100% completion with longer duration
        from PyQt6.QtCore import QPropertyAnimation, QEasingCurve
        self.final_progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self.final_progress_animation.setDuration(800)  # 800ms for final animation
        self.final_progress_animation.setStartValue(self.progress_bar.value())
        self.final_progress_animation.setEndValue(100)
        self.final_progress_animation.setEasingCurve(QEasingCurve.Type.OutQuart)
        self.final_progress_animation.start()
        
        # Add to history
        self.add_to_history(scenes_data)
        
        # Clear credits cache to refresh after analysis
        if hasattr(self, '_credits_cache'):
            delattr(self, '_credits_cache')
        if hasattr(self, '_credits_cache_time'):
            delattr(self, '_credits_cache_time')
        
        # Initialize lazy loading states
        self.scene_loading_states.clear()
        self.scene_media_cache.clear()
        self.background_analysis_threads = {}  # Store background analysis threads
        for i in range(len(scenes_data)):
            self.scene_loading_states[i] = 'pending'  # pending, loading, ready, error
        
        # Show first scene and start smart loading
        if scenes_data:
            self.current_scene_index = 0
            self.display_scene(0)
            # Start loading first scene immediately if it's analyzed
            if scenes_data[0].get('analyzed', False):
                self.start_lazy_loading_for_scene(0)
            # Start loading next few analyzed scenes in background
            self.start_background_lazy_loading()
            
            # Show navigation after analysis is complete
            if hasattr(self, 'nav_container'):
                self.nav_container.show()
            
            # Hide media suggestions labels after analysis is complete
            if hasattr(self, 'stock_images_suggestions_label') and self.stock_images_suggestions_label is not None:
                try:
                    self.stock_images_suggestions_label.hide()
                except RuntimeError:
                    # Widget has been deleted, remove the reference
                    self.stock_images_suggestions_label = None
                    print("Warning: stock_images_suggestions_label was deleted")
            
            if hasattr(self, 'stock_videos_suggestions_label') and self.stock_videos_suggestions_label is not None:
                try:
                    self.stock_videos_suggestions_label.hide()
                except RuntimeError:
                    # Widget has been deleted, remove the reference
                    self.stock_videos_suggestions_label = None
                    print("Warning: stock_videos_suggestions_label was deleted")
            
            if hasattr(self, 'ai_media_suggestions_label') and self.ai_media_suggestions_label is not None:
                try:
                    self.ai_media_suggestions_label.hide()
                except RuntimeError:
                    # Widget has been deleted, remove the reference
                    self.ai_media_suggestions_label = None
                    print("Warning: ai_media_suggestions_label was deleted")
            
            # Fire-and-forget activity POST for analysis completed
            try:
                details_parts = [f"Scenes: {len(scenes_data)}"]
                if scenes_data and isinstance(scenes_data[0], dict):
                    possible_title = scenes_data[0].get("title") or scenes_data[0].get("original_text")
                    if isinstance(possible_title, str) and possible_title.strip():
                        details_parts.append(f"Title: {possible_title[:60]}")
                self._post_activity_async(
                    activity_type="analysis_completed",
                    message="Analysis completed",
                    metadata={
                        "details": ", ".join(details_parts)
                    }
                )
            except Exception as _e:
                print(f"Activity post failed (analysis): {_e}")

    def add_to_history(self, scenes_data: List[Dict[str, Any]]):
        """Add analysis result to history"""
        from datetime import datetime
        
        print(f"🔍 DEBUG: add_to_history called with {len(scenes_data)} scenes")
        print(f"🔍 DEBUG: Current history items count: {len(self.history_items)}")
        print(f"🔍 DEBUG: History counter: {self.history_counter}")
        
        # Get analysis title from first scene
        title = "Unknown Analysis"
        if scenes_data and len(scenes_data) > 0:
            first_scene = scenes_data[0]
            original_text = first_scene.get('original_text', '')
            if original_text:
                # Get first line as title
                lines = original_text.strip().split('\n')
                title = lines[0][:50] + "..." if len(lines[0]) > 50 else lines[0]
            else:
                title = f"Analysis {self.history_counter}"
        
        # Calculate total outputs
        total_outputs = 0
        content_type = "Mixed"
        
        for scene in scenes_data:
            stock_images = len(scene.get('stock_images', []))
            stock_videos = len(scene.get('stock_videos', []))
            ai_images = len(scene.get('ai_images', []))
            total_outputs += stock_images + stock_videos + ai_images
            
            # Determine content type
            if stock_images > 0 and stock_videos == 0 and ai_images == 0:
                content_type = "Stock Images"
            elif stock_videos > 0 and stock_images == 0 and ai_images == 0:
                content_type = "Stock Videos"
            elif ai_images > 0 and stock_images == 0 and stock_videos == 0:
                content_type = "AI Images"
            else:
                content_type = "Mixed Content"
        
        # Get original text from text input
        original_text = self.text_input.toPlainText().strip()
        
        print(f"🔍 DEBUG: Creating history item - Title: {title}, Type: {content_type}, Outputs: {total_outputs}")
        
        # Create history item
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
        history_item = HistoryItem(
            id=str(self.history_counter),
            title=title,
            content_type=content_type,
            output_count=total_outputs,
            date=current_time,
            status="completed",
            original_text=original_text
        )
        
        # Add to history list
        self.history_items.insert(0, history_item)  # Add to beginning
        self.history_counter += 1
        
        print(f"🔍 DEBUG: Added to history list. New count: {len(self.history_items)}")
        
        # Update history page if it exists
        if hasattr(self, 'history_widget') and self.history_widget:
            self.history_widget.update_history_data(self.history_items)
            print("🔍 DEBUG: Updated history widget")
        
        # Save history to file and snapshot content
        print("🔍 DEBUG: Calling save_history_to_file...")
        self.save_history_to_file()
        try:
            print("🔍 DEBUG: Calling _save_history_snapshot...")
            self._save_history_snapshot(history_item, scenes_data)
        except Exception as e:
            print(f"❌ Error saving history snapshot: {e}")
    
    def load_history_from_file(self):
        """Load history data from JSON file"""
        try:
            # Ensure data directory exists
            data_dir = os.path.dirname(self.history_file)
            os.makedirs(data_dir, exist_ok=True)
            
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Load history items
                    self.history_items = []
                    for item_data in data.get('history_items', []):
                        history_item = HistoryItem(
                            id=item_data['id'],
                            title=item_data['title'],
                            content_type=item_data['content_type'],
                            output_count=item_data['output_count'],
                            date=item_data['date'],
                            status=item_data['status'],
                            file_path=item_data.get('file_path', ''),
                            original_text=item_data.get('original_text', '')
                        )
                        self.history_items.append(history_item)
                    
                    # Load counter
                    self.history_counter = data.get('history_counter', 1)
                    
            else:
                # Start with empty history
                self.history_items = []
                self.history_counter = 1
                
        except Exception as e:
            # Start with empty history if there's an error
            self.history_items = []
            self.history_counter = 1
    
    def show_history_snapshot(self, item_id: str):
        """Open a saved history snapshot and display it without running analysis."""
        try:
            # Ensure history directory exists
            history_root = os.path.join(self.get_project_root(), 'history')
            os.makedirs(history_root, exist_ok=True)
            
            base_dir = os.path.join(history_root, item_id)
            scenes_path = os.path.join(base_dir, 'scenes.json')
            original_path = os.path.join(base_dir, 'original.txt')
            if not os.path.exists(scenes_path):
                QMessageBox.warning(self, "History", "We couldn't find the saved analysis.")
                return
            # Load scenes
            with open(scenes_path, 'r', encoding='utf-8') as f:
                loaded_scenes = json.load(f)
            # Load text
            loaded_text = ''
            if os.path.exists(original_path):
                with open(original_path, 'r', encoding='utf-8') as f:
                    loaded_text = f.read()
            # Switch to main UI and render
            self.show_main_interface()
            # Inject state
            self.scenes_data = loaded_scenes or []
            self.current_scene_index = 0
            self._is_viewing_history_snapshot = True
            # Track which history item is currently being viewed for persistence of late analyses
            self._current_history_item_id = item_id
            # Put text without triggering fresh analysis
            if hasattr(self, 'text_input'):
                # Clear any existing highlights first
                if hasattr(self.text_input, 'clear_highlight'):
                    self.text_input.clear_highlight()
                self.text_input.setPlainText(loaded_text)
                # Clear text selection to prevent highlighting
                cursor = self.text_input.textCursor()
                cursor.clearSelection()
                self.text_input.setTextCursor(cursor)
            # Reset loading states to ready for analyzed scenes
            self.scene_loading_states.clear()
            self.scene_media_cache.clear()
            self.background_analysis_threads = {}
            self.lazy_loading_threads = {}
            for i in range(len(self.scenes_data)):
                scene_i = self.scenes_data[i]
                if scene_i.get('analyzed', True):
                    self.scene_loading_states[i] = 'ready'
                    # Pre-seed cache with scene's own media to avoid None during navigation
                    self.scene_media_cache[i] = {
                        'stock_images': scene_i.get('stock_images', []),
                        'stock_videos': scene_i.get('stock_videos', []),
                        'ai_images': scene_i.get('ai_images', [])
                    }
                else:
                    # Not analyzed: let normal background analysis handle it
                    self.scene_loading_states[i] = 'pending'
            if self.scenes_data:
                self.display_scene(0)
            # Reveal navigation
            if hasattr(self, 'nav_container'):
                self.nav_container.show()
            print(f"📖 Loaded history snapshot {item_id}")
        except Exception as e:
            print(f"Error showing history snapshot: {e}")
            QMessageBox.critical(
                self,
                "History",
                "We couldn't open the saved analysis. Please try again."
            )
    
    def save_history_to_file(self):
        """Save history data to JSON file"""
        try:
            # Ensure data directory exists
            data_dir = os.path.dirname(self.history_file)
            os.makedirs(data_dir, exist_ok=True)
            
            print(f"🔍 DEBUG: Saving history to: {self.history_file}")
            print(f"🔍 DEBUG: Data directory: {data_dir}")
            print(f"🔍 DEBUG: Directory exists: {os.path.exists(data_dir)}")
            print(f"🔍 DEBUG: Can write to directory: {os.access(data_dir, os.W_OK)}")
            
            # Prepare data for saving
            data = {
                'history_items': [],
                'history_counter': self.history_counter
            }
            
            # Convert history items to dictionaries
            for item in self.history_items:
                item_data = {
                    'id': item.id,
                    'title': item.title,
                    'content_type': item.content_type,
                    'output_count': item.output_count,
                    'date': item.date,
                    'status': item.status,
                    'file_path': item.file_path,
                    'original_text': item.original_text
                }
                data['history_items'].append(item_data)
            
            # Save to file
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            print(f"✅ Successfully saved {len(self.history_items)} history items to file")
            print(f"✅ File exists after save: {os.path.exists(self.history_file)}")
            
        except Exception as e:
            print(f"❌ Error saving history to file: {e}")
            print(f"❌ Error type: {type(e).__name__}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
    
    def _save_history_snapshot(self, history_item: 'HistoryItem', scenes_data: List[Dict[str, Any]]):
        """Persist full analysis snapshot (text + media metadata) for later viewing without re-analysis.
        Saved under history/<id> with files: meta.json, original.txt, scenes.json, media/ (thumbs or references only).
        """
        try:
            base_dir = os.path.join(self.get_project_root(), 'history', history_item.id)
            print(f"🔍 DEBUG: Saving snapshot to: {base_dir}")
            print(f"🔍 DEBUG: Project root: {self.get_project_root()}")
            print(f"🔍 DEBUG: History item ID: {history_item.id}")
            
            os.makedirs(base_dir, exist_ok=True)
            print(f"🔍 DEBUG: Created directory: {os.path.exists(base_dir)}")
            
            # Save original text
            if history_item.original_text:
                original_path = os.path.join(base_dir, 'original.txt')
                with open(original_path, 'w', encoding='utf-8') as f:
                    f.write(history_item.original_text)
                print(f"🔍 DEBUG: Saved original text to: {original_path}")
            
            # Save scenes data (full)
            scenes_path = os.path.join(base_dir, 'scenes.json')
            with open(scenes_path, 'w', encoding='utf-8') as f:
                json.dump(scenes_data, f, indent=2, ensure_ascii=False)
            print(f"🔍 DEBUG: Saved scenes data to: {scenes_path}")
            
            # Save meta info
            meta = {
                'id': history_item.id,
                'title': history_item.title,
                'content_type': history_item.content_type,
                'output_count': history_item.output_count,
                'date': history_item.date,
                'status': history_item.status
            }
            meta_path = os.path.join(base_dir, 'meta.json')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(meta, f, indent=2, ensure_ascii=False)
            print(f"🔍 DEBUG: Saved meta data to: {meta_path}")
            
            # Optional: prepare media dir for future local copies
            media_dir = os.path.join(base_dir, 'media')
            os.makedirs(media_dir, exist_ok=True)
            print(f"🔍 DEBUG: Created media directory: {os.path.exists(media_dir)}")
            
            print(f"✅ Successfully saved history snapshot to {base_dir}")
        except Exception as e:
            print(f"❌ Error in _save_history_snapshot: {e}")
            import traceback
            print(f"❌ Traceback: {traceback.format_exc()}")
    
    def load_downloads_history_from_file(self):
        """Load downloads history data from JSON file"""
        try:
            # Ensure data directory exists
            data_dir = os.path.dirname(self.downloads_history_file)
            os.makedirs(data_dir, exist_ok=True)
            
            if os.path.exists(self.downloads_history_file):
                with open(self.downloads_history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # Load downloads history items
                    self.downloads_history = []
                    for item_data in data.get('downloads_history', []):
                        download_item = DownloadItem(
                            id=item_data['id'],
                            filename=item_data['filename'],
                            file_path=item_data['file_path'],
                            file_type=item_data['file_type'],
                            download_date=item_data['download_date'],
                            file_size=item_data.get('file_size', ''),
                            thumbnail_path=item_data.get('thumbnail_path', ''),
                            original_url=item_data.get('original_url', ''),
                            chapter=item_data.get('chapter', ''),
                            scene=item_data.get('scene', '')
                        )
                        self.downloads_history.append(download_item)
                    
                    # Clean up non-existent files and duplicates after loading
                    self.cleanup_downloads_history()
                    
            else:
                # Start with empty history
                self.downloads_history = []
                
        except Exception as e:
            # Start with empty history if there's an error
            self.downloads_history = []
    
    def save_downloads_history_to_file(self):
        """Save downloads history data to JSON file"""
        try:
            # Ensure data directory exists
            data_dir = os.path.dirname(self.downloads_history_file)
            os.makedirs(data_dir, exist_ok=True)
            
            # Prepare data for saving
            data = {
                'downloads_history': []
            }
            
            # Convert downloads history items to dictionaries
            for item in self.downloads_history:
                item_data = {
                    'id': item.id,
                    'filename': item.filename,
                    'file_path': item.file_path,
                    'file_type': item.file_type,
                    'download_date': item.download_date,
                    'file_size': item.file_size,
                    'thumbnail_path': item.thumbnail_path,
                    'original_url': item.original_url,
                    'chapter': item.chapter,
                    'scene': item.scene
                }
                data['downloads_history'].append(item_data)
            
            # Save to file
            with open(self.downloads_history_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            print(f"Saved {len(self.downloads_history)} downloads history items to file")
            
        except Exception as e:
            print(f"Error saving downloads history to file: {e}")

    def backfill_downloads_from_folder(self, folder_path: str):
        """Backfill downloads history by scanning a folder for media files"""
        try:
            if not folder_path or not os.path.isdir(folder_path):
                return
            # Supported media extensions
            exts = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.mp4', '.mov', '.avi', '.mkv', '.wmv', '.flv'}
            existing_paths = {os.path.normpath(item.file_path) for item in self.downloads_history}
            for name in os.listdir(folder_path):
                file_path = os.path.join(folder_path, name)
                if not os.path.isfile(file_path):
                    continue
                if os.path.splitext(name)[1].lower() not in exts:
                    continue
                if os.path.normpath(file_path) in existing_paths:
                    continue
                # Add to history (original_url unknown)
                self.add_to_downloads_history(file_path)
        except Exception as e:
            print(f"⚠️ Error backfilling from folder '{folder_path}': {e}")
    
    def add_to_downloads_history(self, file_path: str, original_url: str = "", chapter: str = "", scene: str = ""):
        """Add a downloaded file to downloads history"""
        try:
            if os.path.exists(file_path):
                # Check if file already exists in history to prevent duplicates
                normalized_path = os.path.normpath(file_path)
                for existing_item in self.downloads_history:
                    if os.path.normpath(existing_item.file_path) == normalized_path:
                        print(f"⚠️ File already in downloads history: {os.path.basename(file_path)}")
                        return
                
                # Get file info
                file_stat = os.stat(file_path)
                file_size = self.format_file_size(file_stat.st_size)
                download_date = datetime.fromtimestamp(file_stat.st_mtime).strftime("%Y-%m-%d %H:%M")
                filename = os.path.basename(file_path)
                
                # Determine file type
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
                    file_type = "image"
                    thumbnail_path = file_path
                elif file_ext in ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv']:
                    file_type = "video"
                    # Create thumbnail for video with unique name
                    thumbnail_path = self.create_video_thumbnail(file_path)
                else:
                    file_type = "other"
                    thumbnail_path = ""
                
                # Prefer AI badge by marking filename for AI images from Leonardo if original_url indicates so
                try:
                    if file_type == "image" and original_url and ("leonardo.ai" in original_url.lower() or "cdn.leonardo.ai" in original_url.lower()):
                        # Embed a hint in filename to aid badge detection without changing actual file
                        if "AI_Generated" not in filename:
                            filename = filename  # keep original on disk; we only store display name in history
                except Exception:
                    pass

                # Create download item
                download_item = DownloadItem(
                    id=str(uuid.uuid4()),
                    filename=filename,
                    file_path=file_path,
                    file_type=file_type,
                    download_date=download_date,
                    file_size=file_size,
                    thumbnail_path=thumbnail_path,
                    original_url=original_url,
                    chapter=chapter,
                    scene=scene
                )
                
                # Add to history (at the beginning)
                self.downloads_history.insert(0, download_item)
                
                # Save to file
                self.save_downloads_history_to_file()
                
                print(f"✅ Added to downloads history: {filename}")
                
        except Exception as e:
            print(f"❌ Error adding to downloads history: {e}")
    
    def cleanup_downloads_history(self):
        """Remove duplicates from downloads history (keep all files, even if missing)"""
        try:
            original_count = len(self.downloads_history)
            
            # Keep all files in history, even if they don't exist anymore
            # Only remove duplicates based on file path
            seen_paths = set()
            unique_items = []
            for item in self.downloads_history:
                normalized_path = os.path.normpath(item.file_path)
                if normalized_path not in seen_paths:
                    seen_paths.add(normalized_path)
                    unique_items.append(item)
            
            self.downloads_history = unique_items
            
            removed_count = original_count - len(self.downloads_history)
            
            if removed_count > 0:
                print(f"🧹 Cleaned up {removed_count} duplicate items from downloads history")
                self.save_downloads_history_to_file()
            
        except Exception as e:
            print(f"❌ Error cleaning up downloads history: {e}")
    
    def reset_downloads_history(self):
        """Reset downloads history completely"""
        try:
            print("🔄 Resetting downloads history...")
            self.downloads_history = []
            self.save_downloads_history_to_file()
            print("✅ Downloads history reset successfully")
        except Exception as e:
            print(f"❌ Error resetting downloads history: {e}")
    
    def add_failed_to_history(self):
        """Add failed analysis to history"""
        from datetime import datetime
        
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M")
        history_item = HistoryItem(
            id=str(self.history_counter),
            title=f"Failed Analysis {self.history_counter}",
            content_type="Failed",
            output_count=0,
            date=current_time,
            status="failed"
        )
        
        # Add to history list
        self.history_items.insert(0, history_item)  # Add to beginning
        self.history_counter += 1
        
        # Update history page if it exists
        if hasattr(self, 'history_widget') and self.history_widget:
            self.history_widget.update_history_data(self.history_items)
        
        # Save history to file
        self.save_history_to_file()
    
    def re_analyze_from_history(self, item_id: str):
        """Re-analyze a previous analysis from history"""
        print(f"Re-analyze called for item_id: {item_id}")
        # Exit snapshot viewing mode (if any)
        self._is_viewing_history_snapshot = False
        # Clear current history item tracking to avoid accidental persistence
        try:
            self._current_history_item_id = None
        except Exception:
            pass
        
        # Find the history item
        history_item = None
        for item in self.history_items:
            if item.id == item_id:
                history_item = item
                break
        
        if not history_item:
            print(f"History item with id {item_id} not found")
            return
        
        print(f"Found history item: {history_item.title}")
        print(f"Original text length: {len(history_item.original_text)}")
        
        # Try to get original text from history folder first, then fallback to JSON
        original_text = None
        
        # First try: Get from history folder
        try:
            history_root = os.path.join(self.get_project_root(), 'history')
            base_dir = os.path.join(history_root, item_id)
            original_path = os.path.join(base_dir, 'original.txt')
            if os.path.exists(original_path):
                with open(original_path, 'r', encoding='utf-8') as f:
                    original_text = f.read()
                print(f"Loaded original text from history folder: {len(original_text)} characters")
        except Exception as e:
            print(f"Could not load from history folder: {e}")
        
        # Fallback: Get from JSON
        if not original_text and history_item.original_text:
            original_text = history_item.original_text
            print(f"Loaded original text from JSON: {len(original_text)} characters")
        
        if not original_text:
            QMessageBox.warning(self, "Re-Analyze", 
                "The original text for this analysis isn't available.\n\n"
                "Please start a new analysis manually.")
            return
        
        # Clear all caches before starting re-analysis (same as start_analysis)
        if hasattr(self, 'scene_media_cache'):
            self.scene_media_cache.clear()
            print("Scene media cache cleared for re-analysis")
        
        if hasattr(self, 'scene_loading_states'):
            self.scene_loading_states.clear()
            print("Scene loading states cleared for re-analysis")
        
        if hasattr(self, 'background_analysis_threads'):
            self.background_analysis_threads.clear()
            print("Background analysis threads cleared for re-analysis")
        
        # Clear credits cache
        if hasattr(self, '_credits_cache'):
            delattr(self, '_credits_cache')
        if hasattr(self, '_credits_cache_time'):
            delattr(self, '_credits_cache_time')
        
        # Clear thumbnail caches from MediaCard instances
        self.clear_thumbnail_caches()

        # Clear AI generation status/results cache
        if hasattr(self, 'ai_generation_status'):
            self.ai_generation_status.clear()
        if hasattr(self, 'ai_generation_results'):
            self.ai_generation_results.clear()
        if hasattr(self, 'ai_generation_media_cards'):
            self.ai_generation_media_cards.clear()
        if hasattr(self, 'ai_generation_threads'):
            # Stop any running generation threads safely
            try:
                for prompt, thread in list(self.ai_generation_threads.items()):
                    try:
                        if thread.isRunning():
                            thread.requestInterruption()
                            thread.wait(100)
                    except Exception:
                        pass
                self.ai_generation_threads.clear()
            except Exception:
                pass
        
        # Clear scenes data to start fresh
        self.scenes_data = []
        self.current_scene_index = 0
        self.selected_media = {'images': [], 'videos': []}
        
        # Switch to main interface
        print("Switching to main interface...")
        self.show_main_interface()
        
        # Wait a moment for UI to update, then load text
        QTimer.singleShot(100, lambda: self._load_text_after_ui_update(original_text))
    
    def _load_text_after_ui_update(self, text: str):
        """Load text into text input after UI update"""
        print("Loading text after UI update...")
        if hasattr(self, 'text_input'):
            print("Setting text input...")
            # Clear any existing highlights first
            if hasattr(self.text_input, 'clear_highlight'):
                self.text_input.clear_highlight()
            self.text_input.setPlainText(text)
            print(f"Text input set with {len(text)} characters")
            
            # Focus on the text input for immediate editing
            self.text_input.setFocus()
            print("Focus set on text input")
        else:
            print("text_input still not found!")
            # Try again after a longer delay
            QTimer.singleShot(200, lambda: self._load_text_after_ui_update(text))
    
    def analysis_error(self, error_msg: str):
        """Handle analysis error with detailed information"""
        self.analyze_btn.setEnabled(True)
        self.analyze_btn.setText("Start Analysis")

        # Status label removed - status bar no longer exists
        self.progress_bar.setValue(0)
        
        # Reset media suggestions labels to original state
        if hasattr(self, 'stock_images_suggestions_label') and self.stock_images_suggestions_label is not None:
            try:
                self.stock_images_suggestions_label.setText("▶ Run analysis to see media suggestions")
                self.stock_images_suggestions_label.setStyleSheet("color: #9CA3AF;")
                self.stock_images_suggestions_label.show()
            except RuntimeError:
                # Widget has been deleted, remove the reference
                self.stock_images_suggestions_label = None
                print("Warning: stock_images_suggestions_label was deleted")
        
        if hasattr(self, 'stock_videos_suggestions_label') and self.stock_videos_suggestions_label is not None:
            try:
                self.stock_videos_suggestions_label.setText("▶ Run analysis to see media suggestions")
                self.stock_videos_suggestions_label.setStyleSheet("color: #9CA3AF;")
                self.stock_videos_suggestions_label.show()
            except RuntimeError:
                # Widget has been deleted, remove the reference
                self.stock_videos_suggestions_label = None
                print("Warning: stock_videos_suggestions_label was deleted")
        
        if hasattr(self, 'ai_media_suggestions_label') and self.ai_media_suggestions_label is not None:
            try:
                self.ai_media_suggestions_label.setText("▶ Run analysis to see media suggestions")
                self.ai_media_suggestions_label.setStyleSheet("color: #9CA3AF;")
                self.ai_media_suggestions_label.show()
            except RuntimeError:
                # Widget has been deleted, remove the reference
                self.ai_media_suggestions_label = None
                print("Warning: ai_media_suggestions_label was deleted")
        
        # Add failed analysis to history
        self.add_failed_to_history()
        
        # Create detailed error message
        detailed_msg = self.create_detailed_error_message(error_msg)
        
        # Show error dialog
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Analysis Error")
        msg_box.setText("Analysis failed!")
        msg_box.setDetailedText(detailed_msg)
        msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg_box.exec()
        
    def create_detailed_error_message(self, error_msg: str) -> str:
        """Create detailed error message with troubleshooting tips"""
        detailed_msg = f"Error: {error_msg}\n\n"
        
        # Check for common API issues
        if "API key" in error_msg.lower() or "401" in error_msg or "403" in error_msg:
            detailed_msg += "🔑 API Key Issues:\n"
            detailed_msg += "• Check your .env file contains valid API keys\n"
            detailed_msg += "• Verify your OpenAI API key is correct\n"
            detailed_msg += "• For stock APIs, ensure keys are properly configured\n"
            detailed_msg += "• Some features may work without stock API keys\n\n"
            
        if "rate limit" in error_msg.lower() or "429" in error_msg:
            detailed_msg += "⏰ Rate Limit Issues:\n"
            detailed_msg += "• Wait a few minutes before trying again\n"
            detailed_msg += "• Consider upgrading your API plan\n"
            detailed_msg += "• Reduce the number of scenes to analyze\n\n"
            
        if "connection" in error_msg.lower() or "network" in error_msg.lower():
            detailed_msg += "🌐 Connection Issues:\n"
            detailed_msg += "• Check your internet connection\n"
            detailed_msg += "• Try again in a few moments\n"
            detailed_msg += "• Verify you're not behind a restrictive firewall\n\n"
            
        detailed_msg += "💡 Troubleshooting Tips:\n"
        detailed_msg += "• Ensure your .env file is in the project root\n"
        detailed_msg += "• Try running with a smaller text input\n"
        detailed_msg += "• Check the console for additional error details\n"
        detailed_msg += "• Some stock media suggestions may still work without all APIs\n"
        
        return detailed_msg
        
    def display_scene(self, index: int):
        """Display scene information"""
        if not self.scenes_data or index < 0 or index >= len(self.scenes_data):
            return
            
        scene = self.scenes_data[index]
        
        # Update navigation info
        current_main_scene = scene.get('main_scene_id', 1)
        micro_scene_number = scene.get('micro_scene_id', 1)  # Doğru mikro-sahne ID'si
        total_main_scenes = max([s.get('main_scene_id', 1) for s in self.scenes_data]) if self.scenes_data else 0
        total_micro_scenes = len([s for s in self.scenes_data if s.get('main_scene_id', 1) == current_main_scene])
        
        nav_text = f"Chapter {current_main_scene}/{total_main_scenes} → Scene {micro_scene_number}/{total_micro_scenes}"
        self.scene_nav_label.setText(nav_text)
        
        # Update scene info
        scene_title = scene.get('scene_title', 'Scene Details')
        self.scene_name_label.setText(scene_title)
        
        # University name
        original_text = scene.get('original_text', '')
        if original_text:
            first_line = original_text.split('\n')[0]
            self.university_label.setText(first_line)
        
        # Visual prompt
        visual_prompt = scene.get('visual_prompt', '')
        self.visual_prompt_label.setText(visual_prompt)
        
        # Update navigation buttons (block forward if analyzing)
        self._update_navigation_buttons()
        
        # Update tab content safely (defer and guard against rapid navigation reentrancy)
        try:
            # Use immediate update for AI images to prevent empty pages
            self._safe_update_current_tab()
        except Exception:
            # Fallback to direct call
            try:
                self.update_current_tab()
            except Exception as _e:
                print(f"Warning: update_current_tab failed: {_e}")
        
        # Start smart scene loading (index is 0-based array index)
        self.start_smart_scene_loading(index)
        
        # Check if we should analyze additional scenes in background
        self.check_background_analysis_needed(index)
        
        # Proactively start background lazy loading for next analyzed scenes
        try:
            self.start_background_lazy_loading()
        except Exception:
            pass
        
        # Highlight the corresponding text in the input area
        self.highlight_scene_text(scene)
    
    def _safe_update_current_tab(self):
        try:
            self.update_current_tab()
        except Exception as e:
            print(f"Warning: _safe_update_current_tab failed: {e}")
    
    def highlight_scene_text(self, scene: Dict[str, Any]):
        """Highlight the text corresponding to the current scene without blocking the UI."""
        if not hasattr(self, 'text_input') or not self.text_input:
            return
        # Token to prevent stale delayed callbacks from applying after rapid navigation
        try:
            token = getattr(self, '_highlight_token', 0) + 1
            self._highlight_token = token
        except Exception:
            token = 0

        def _apply_clear():
            try:
                # Ignore if a newer navigation occurred
                if token != getattr(self, '_highlight_token', token):
                    return
                self.text_input.clear_highlight()
            except Exception:
                pass

        def _apply_highlight():
            try:
                # Ignore if a newer navigation occurred
                if token != getattr(self, '_highlight_token', token):
                    return
                start_index = scene.get('startIndex')
                end_index = scene.get('endIndex')
                if start_index is not None and end_index is not None:
                    self.text_input.highlight_range(start_index, end_index)
                else:
                    self.text_input.clear_highlight()
            except Exception:
                pass

        try:
            from PyQt6.QtCore import QTimer as _QT
            # Clear first in next event loop turn, then apply highlight shortly after
            _QT.singleShot(0, _apply_clear)
            _QT.singleShot(15, _apply_highlight)
        except Exception:
            # Fallback to immediate operations if timers are unavailable
            _apply_clear()
            _apply_highlight()
    
    def start_smart_scene_loading(self, scene_index: int):
        """Start smart scene loading for a specific micro-scene"""
        if scene_index >= len(self.scenes_data):
            return
            
        scene = self.scenes_data[scene_index]
        
        # In snapshot mode: skip for scenes already analyzed, allow for non-analyzed
        if getattr(self, '_is_viewing_history_snapshot', False) and scene.get('analyzed', False):
            return

        # If scene is already analyzed, just start lazy loading for media
        if scene.get('analyzed', False):
            if self.scene_loading_states.get(scene_index, 'pending') == 'pending':
                self.start_lazy_loading_for_scene(scene_index)
            return
        
        # If scene is not analyzed, start background analysis
        if not smart_media_cache.is_scene_cached(scene_index):
            print(f"🔄 Starting background analysis for micro-scene {scene_index}...")
            
            # Mark as loading
            self.scene_loading_states[scene_index] = 'loading'
            
            # Create and start background analysis thread (pass 1-based index)
            thread = BackgroundSceneAnalysisThread(scene_index + 1, scene, self.settings, self.current_user.id if self.current_user else None, self.cost_tracking_service, self.scene_cost_tracking_service)
            try:
                thread.setParent(self)
            except Exception:
                pass
            # Store 0-based array index on thread for cleanup
            try:
                thread._array_index = scene_index
            except Exception:
                pass
            thread.scene_analysis_complete.connect(self.on_scene_analysis_complete)
            thread.scene_analysis_error.connect(self.on_scene_analysis_error)
            try:
                thread.finished.connect(lambda: self._on_background_analysis_finished())
            except Exception:
                pass
            
            # Store thread reference
            self.background_analysis_threads[scene_index] = thread
            thread.start()
        # Re-evaluate navigation state after initiating loading
        if scene_index == self.current_scene_index:
            self._update_navigation_buttons()
    
    def _on_background_analysis_finished(self):
        """Handle when background analysis thread finishes"""
        try:
            # Remove any threads that report finished but still exist in dict
            for key, th in list(getattr(self, 'background_analysis_threads', {}).items()):
                try:
                    if hasattr(th, 'isRunning') and not th.isRunning():
                        del self.background_analysis_threads[key]
                except Exception:
                    pass
        except Exception:
            pass

    def check_background_analysis_needed(self, current_scene_index: int):
        """Check if we should analyze additional micro-scenes in background"""
        # Get micro-scenes that should be analyzed in background
        scenes_to_analyze = get_scenes_to_analyze_in_background(current_scene_index, self.scenes_data)
        
        for scene_index in scenes_to_analyze:
            if scene_index not in self.background_analysis_threads:
                scene = self.scenes_data[scene_index]
                scene_number = scene_index + 1  # Convert to 1-based scene number
                
                # In snapshot mode: only start background analysis for non-analyzed scenes
                if getattr(self, '_is_viewing_history_snapshot', False) and scene.get('analyzed', False):
                    continue

                print(f"🔄 Starting background analysis for micro-scene {scene_number} (triggered by navigation to scene {current_scene_index + 1})...")
                
                # Create and start background analysis thread (scene_number is already 1-based)
                thread = BackgroundSceneAnalysisThread(scene_number, scene, self.settings, self.current_user.id if self.current_user else None, self.cost_tracking_service, self.scene_cost_tracking_service)
                try:
                    thread.setParent(self)
                except Exception:
                    pass
                # Store 0-based array index on thread for cleanup
                try:
                    thread._array_index = scene_index
                except Exception:
                    pass
                thread.scene_analysis_complete.connect(self.on_scene_analysis_complete)
                thread.scene_analysis_error.connect(self.on_scene_analysis_error)
                try:
                    thread.finished.connect(lambda: self._on_background_analysis_finished())
                except Exception:
                    pass
                
                # Store thread reference
                self.background_analysis_threads[scene_index] = thread
                thread.start()
    
    def on_scene_analysis_complete(self, scene_index: int, scene_data: dict):
        """Handle scene analysis completion"""
        # scene_index is 1-based, convert to 0-based array index
        array_index = scene_index - 1
        # Guard against invalid indices
        if array_index < 0 or array_index >= len(self.scenes_data):
            try:
                print(f"⚠️ Ignoring scene_analysis_complete for out-of-range index {scene_index}")
            except Exception:
                pass
            return

        # Update the scene data
        self.scenes_data[array_index] = scene_data
        
        # Mark as ready (analysis includes media generation)
        self.scene_loading_states[array_index] = 'ready'
        
        # Cache the media data for this scene
        if scene_data:
            self.scene_media_cache[array_index] = {
                'stock_images': scene_data.get('stock_images', []),
                'stock_videos': scene_data.get('stock_videos', []),
                'ai_images': scene_data.get('ai_images', [])
            }
            # If media suggestions are not included, trigger lazy loading for this analyzed scene
            try:
                no_images = not self.scene_media_cache[array_index].get('stock_images')
                no_videos = not self.scene_media_cache[array_index].get('stock_videos')
                no_ai = not self.scene_media_cache[array_index].get('ai_images')
                if no_images and no_videos and no_ai:
                    # Mark as pending media and start lazy loading to fetch suggestions
                    self.scene_loading_states[array_index] = 'pending'
                    self.start_lazy_loading_for_scene(array_index)
            except Exception:
                pass
        
        # Clean up dictionary reference only; thread will self-delete on finished
        if array_index in self.background_analysis_threads:
            try:
                del self.background_analysis_threads[array_index]
            except Exception:
                pass
        
        # Update UI if this is the current scene
        if array_index == self.current_scene_index:
            self.update_current_tab()
            self._update_navigation_buttons()
        
        print(f"✅ Scene {scene_index} analysis complete with media")

        # If we are viewing a snapshot, persist the updated scenes back to the snapshot folder
        try:
            if getattr(self, '_is_viewing_history_snapshot', False) and getattr(self, '_current_history_item_id', None):
                base_dir = os.path.join(self.get_project_root(), 'history', self._current_history_item_id)
                os.makedirs(base_dir, exist_ok=True)
                # Write updated scenes.json
                with open(os.path.join(base_dir, 'scenes.json'), 'w', encoding='utf-8') as f:
                    json.dump(self.scenes_data, f, indent=2, ensure_ascii=False)

                # If all scenes analyzed, update history item status and meta
                all_analyzed = all(s.get('analyzed', False) for s in self.scenes_data)
                # Update corresponding HistoryItem in memory
                target_item = None
                for _item in getattr(self, 'history_items', []):
                    if getattr(_item, 'id', None) == self._current_history_item_id:
                        target_item = _item
                        break
                if target_item is not None:
                    try:
                        target_item.output_count = len(self.scenes_data)
                        if all_analyzed:
                            target_item.status = "completed"
                    except Exception:
                        pass

                    # Update meta.json to reflect latest status/output count
                    meta = {
                        'id': target_item.id,
                        'title': target_item.title,
                        'content_type': target_item.content_type,
                        'output_count': target_item.output_count,
                        'date': target_item.date,
                        'status': target_item.status
                    }
                    with open(os.path.join(base_dir, 'meta.json'), 'w', encoding='utf-8') as mf:
                        json.dump(meta, mf, indent=2, ensure_ascii=False)

                    # Persist history list to file
                    self.save_history_to_file()
                else:
                    # Still at least persist scenes.json
                    pass
        except Exception as _e:
            try:
                print(f"⚠️ Failed to persist updated snapshot: {_e}")
            except Exception:
                pass
    
    def on_scene_analysis_error(self, scene_index: int, error_message: str):
        """Handle scene analysis error"""
        # scene_index is 1-based, convert to 0-based array index
        array_index = scene_index - 1
        # Guard against invalid indices
        if array_index < 0 or array_index >= len(self.scenes_data):
            try:
                print(f"⚠️ Ignoring scene_analysis_error for out-of-range index {scene_index}: {error_message}")
            except Exception:
                pass
            return

        self.scene_loading_states[array_index] = 'error'
        
        # Clean up thread
        if array_index in self.background_analysis_threads:
            self.background_analysis_threads[array_index].deleteLater()
            del self.background_analysis_threads[array_index]
        
        # Update UI if this is the current scene
        if array_index == self.current_scene_index:
            self.update_current_tab()
            self._update_navigation_buttons()
        
        print(f"❌ Scene {scene_index} analysis error: {error_message}")
    
    def retry_media_loading(self, media_type: str):
        """Retry loading media for current scene"""
        if not self.scenes_data or self.current_scene_index >= len(self.scenes_data):
            return
            
        scene = self.scenes_data[self.current_scene_index]
        
        # Only retry if scene is analyzed
        if not scene.get('analyzed', False):
            print(f"⚠️ Cannot retry: Scene {self.current_scene_index} is not analyzed yet")
            return
            
        print(f"🔄 Retrying {media_type} loading for scene {self.current_scene_index}...")
        
        # Reset scene loading state to trigger reload
        self.scene_loading_states[self.current_scene_index] = 'pending'
        
        # Clear cached media for this scene
        if self.current_scene_index in self.scene_media_cache:
            del self.scene_media_cache[self.current_scene_index]
        
        # Start lazy loading again
        self.start_lazy_loading_for_scene(self.current_scene_index)
        
    def update_current_tab(self):
        """Update current tab content"""
        if not self.scenes_data or self.current_scene_index >= len(self.scenes_data):
            return
            
        try:
            scene = self.scenes_data[self.current_scene_index]
        except Exception as e:
            print(f"Warning: invalid scene index {self.current_scene_index}: {e}")
            return
        try:
            current_tab = self.tab_widget.currentIndex()
        except Exception as e:
            print(f"Warning: tab widget not ready: {e}")
            return
        
        # Check if scene is analyzed and media is ready
        scene_state = self.scene_loading_states.get(self.current_scene_index, 'pending')
        
        if scene.get('analyzed', False) and scene_state == 'ready':
            # Scene is analyzed and media is ready - use cached data if available
            if self.current_scene_index in self.scene_media_cache:
                # Use cached media data
                cache = self.scene_media_cache[self.current_scene_index]
                if current_tab == 0:  # Stock Images
                    suggestions = cache.get('stock_images', [])
                    media_type = 'stock_images'
                elif current_tab == 1:  # Stock Videos
                    suggestions = cache.get('stock_videos', [])
                    media_type = 'stock_videos'
                else:  # AI Images
                    suggestions = cache.get('ai_images', [])
                    media_type = 'ai_images'
                # Items loaded from cache
            else:
                # Fallback to scene data directly
                if current_tab == 0:  # Stock Images
                    suggestions = scene.get('stock_images', [])
                    media_type = 'stock_images'
                elif current_tab == 1:  # Stock Videos
                    suggestions = scene.get('stock_videos', [])
                    media_type = 'stock_videos'
                else:  # AI Images
                    suggestions = scene.get('ai_images', [])
                    media_type = 'ai_images'
                # Items loaded from scene data
            
            try:
                self.display_media_grid(current_tab, suggestions, media_type)
                # Force UI update after displaying media grid
                if media_type == "ai_images":
                    QApplication.processEvents()
            except Exception as e:
                print(f"Warning: display_media_grid failed: {e}")
                return
            
        elif scene.get('analyzed', False) and scene_state == 'loading':
            # Scene is analyzed but media is loading
            self.display_loading_state(current_tab)
            return
        elif scene.get('analyzed', False) and scene_state == 'error':
            # Scene is analyzed but media loading failed
            self.display_error_state(current_tab)
            return
        elif not scene.get('analyzed', False):
            # Scene is not analyzed yet
            self.display_loading_state(current_tab)
            return
        else:  # pending
            # Scene is analyzed but media not loaded yet
            self.display_loading_state(current_tab)
            self.start_lazy_loading_for_scene(self.current_scene_index)
            return
        
    def display_media_grid(self, tab_index: int, suggestions: List[Dict[str, Any]], media_type: str):
        """Display media in grid"""
        # Get the current tab's scroll area
        try:
            if tab_index == 0:
                tab_widget = self.stock_images_tab
            elif tab_index == 1:
                tab_widget = self.stock_videos_tab
            else:
                # Check if user can access AI Images
                if self.can_access_ai_image():
                    # User can access AI Images - show normal content
                    tab_widget = self.ai_images_tab
                else:
                    # User cannot access AI Images - show restricted content
                    if not hasattr(self, 'ai_images_tab_restricted'):
                        self.ai_images_tab_restricted = True
                        self.apply_restricted_tab_styling()
                    self.display_restricted_ai_images_content(tab_widget)
                    return
        except Exception as e:
            print(f"Warning: tab widget not ready: {e}")
            return
        
        # For AI Images, use faster loading strategy
        if media_type == "ai_images":
            # Use immediate display instead of delayed display to prevent empty pages
            self._display_ai_images_grid(tab_widget, suggestions)
            return
        
        # For other media types, use normal loading
        scroll_area = tab_widget.findChild(QScrollArea) if tab_widget else None
        if not scroll_area:
            return
            
        grid_widget = scroll_area.widget() if scroll_area else None
        if not grid_widget:
            return
            
        layout = grid_widget.layout() if grid_widget else None
        if not layout:
            return
        
        # Clear existing content
        for i in reversed(range(layout.count())):
            child = layout.itemAt(i)
            if child:
                widget = child.widget()
                if widget:
                    widget.deleteLater()
                
        if not suggestions:
            # Create a more informative empty state
            empty_widget = QWidget()
            empty_layout = QVBoxLayout()
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.setSpacing(16)
            
            # Icon
            icon_label = QLabel("🎬" if media_type == "stock_videos" else "📸" if media_type == "stock_images" else "🎨")
            icon_label.setFont(QFont("Arial", 48))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
            empty_layout.addWidget(icon_label)
            
            # Title
            title_label = QLabel(f"No {media_type.replace('_', ' ')} available")
            title_label.setFont(QFont("Inter", 16, QFont.Weight.Medium))
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("color: #6B7280; background: transparent; border: none;")
            empty_layout.addWidget(title_label)
            
            # Subtitle with helpful information
            if media_type == "stock_videos":
                subtitle_text = "API rate limit reached or no videos found for this scene"
            elif media_type == "stock_images":
                subtitle_text = "API rate limit reached or no images found for this scene"
            else:
                subtitle_text = "AI images not available for this scene"
                
            subtitle_label = QLabel(subtitle_text)
            subtitle_label.setFont(QFont("Inter", 12))
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle_label.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
            subtitle_label.setWordWrap(True)
            empty_layout.addWidget(subtitle_label)
            
            # Retry button for videos
            if media_type == "stock_videos":
                retry_button = QPushButton("🔄 Retry Loading")
                retry_button.setFont(QFont("Inter", 12, QFont.Weight.Medium))
                retry_button.setStyleSheet("""
                    QPushButton {
                        background: #3B82F6;
                        color: white;
                        border: none;
                        border-radius: 8px;
                        padding: 12px 24px;
                        font-weight: 500;
                    }
                    QPushButton:hover {
                        background: #2563EB;
                    }
                    QPushButton:pressed {
                        background: #1D4ED8;
                    }
                """)
                retry_button.clicked.connect(lambda: self.retry_media_loading(media_type))
                empty_layout.addWidget(retry_button)
            
            empty_widget.setLayout(empty_layout)
            layout.addWidget(empty_widget, 0, 0, 1, 3)  # Span all columns
            return
            
        # Create cards in 3-column grid
        for i, suggestion in enumerate(suggestions):
            row = i // 3
            col = i % 3
            
            card = MediaCard(suggestion, media_type, i)  # Pass index for numbering
            card.selection_changed.connect(self.on_media_selection_changed)
            
            # Check if this media is already selected and update the card accordingly
            item_id = suggestion.get('id', '')
            if media_type == 'stock_images' or media_type == 'ai_images':
                is_selected = any(x.get('id', '') == item_id for x in self.selected_media['images'])
            else:
                is_selected = any(x.get('id', '') == item_id for x in self.selected_media['videos'])
            
            if is_selected:
                card.checkbox.setChecked(True)
                card.is_selected = True
                card.setStyleSheet("""
                    QFrame {
                        background: #F8F9FA;
                        border: 2px solid #3B82F6;
                        border-radius: 25px;
                    }
                """)
            
            # Add card to grid layout with proper positioning
            layout.addWidget(card, row, col)

    def _display_ai_images_grid(self, tab_widget: QWidget, suggestions: List[Dict[str, Any]]):
        """Render AI Images cards in their grid (called async via QTimer)."""
        try:
            if not tab_widget:
                return
            scroll_area = tab_widget.findChild(QScrollArea)
            if not scroll_area:
                return
            grid_widget = scroll_area.widget()
            if not grid_widget:
                return
            layout = grid_widget.layout()
            if not layout:
                return

            # Clear existing content
            for i in reversed(range(layout.count())):
                child = layout.itemAt(i)
                if child:
                    widget = child.widget()
                    if widget:
                        widget.deleteLater()

            if not suggestions:
                # Empty state for AI Images
                empty_widget = QWidget()
                empty_layout = QVBoxLayout()
                empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                empty_layout.setSpacing(16)

                icon_label = QLabel("🎨")
                icon_label.setFont(QFont("Arial", 48))
                icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                icon_label.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
                empty_layout.addWidget(icon_label)

                title_label = QLabel("No AI images available")
                title_label.setFont(QFont("Inter", 16, QFont.Weight.Medium))
                title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                title_label.setStyleSheet("color: #6B7280; background: transparent; border: none;")
                empty_layout.addWidget(title_label)

                subtitle_label = QLabel("Run analysis to generate AI image prompts for this scene")
                subtitle_label.setFont(QFont("Inter", 12))
                subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                subtitle_label.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
                subtitle_label.setWordWrap(True)
                empty_layout.addWidget(subtitle_label)

                empty_widget.setLayout(empty_layout)
                layout.addWidget(empty_widget, 0, 0, 1, 3)
                return

            # Populate cards in 3-column grid
            for i, suggestion in enumerate(suggestions):
                row = i // 3
                col = i % 3

                card = MediaCard(suggestion, "ai_images", i)
                card.selection_changed.connect(self.on_media_selection_changed)
                layout.addWidget(card, row, col)
        except Exception as e:
            try:
                print(f"❌ Error rendering AI images grid: {e}")
            except Exception:
                pass
    
    def start_lazy_loading_for_scene(self, scene_index: int):
        """Start lazy loading for a specific scene"""
        if scene_index >= len(self.scenes_data):
            return
            
        # In snapshot mode: only skip lazy loading if scene already analyzed
        if getattr(self, '_is_viewing_history_snapshot', False):
            scene_data_check = self.scenes_data[scene_index] if scene_index < len(self.scenes_data) else {}
            if scene_data_check.get('analyzed', False):
                return

        # Don't start if already loading or ready
        if self.scene_loading_states.get(scene_index) in ['loading', 'ready']:
            return
            
        # Mark as loading
        self.scene_loading_states[scene_index] = 'loading'
        
        # Create and start smart lazy loading thread
        scene_data = self.scenes_data[scene_index]
        thread = SmartLazyLoadingThread(scene_data, scene_index, self.settings, 
                                       user_id=self.current_user.id if self.current_user else None,
                                       cost_tracking_service=self.cost_tracking_service,
                                       scene_cost_tracking_service=self.scene_cost_tracking_service)
        try:
            thread.setParent(self)
        except Exception:
            pass
        thread.scene_media_ready.connect(self.on_scene_media_ready)
        thread.scene_media_error.connect(self.on_scene_media_error)
        try:
            thread.finished.connect(lambda: thread.deleteLater())
        except Exception:
            pass
        
        # Store thread reference
        self.lazy_loading_threads[scene_index] = thread
        thread.start()
        
        print(f"Started lazy loading for scene {scene_index}")
    
    def start_background_lazy_loading(self):
        """Start loading next few analyzed micro-scenes in background"""
        # Load next 2 analyzed micro-scenes in background
        for i in range(1, min(3, len(self.scenes_data))):
            scene_data = self.scenes_data[i]
            if scene_data.get('analyzed', False) and self.scene_loading_states.get(i, 'pending') == 'pending':
                self.start_lazy_loading_for_scene(i)
    def on_scene_media_ready(self, scene_index: int, media_data: dict):
        """Handle scene media ready"""
        # Avoid updating from stale threads when scene index out of range
        if scene_index >= len(self.scenes_data):
            return
        # Cache the media data
        self.scene_media_cache[scene_index] = media_data
        self.scene_loading_states[scene_index] = 'ready'
        
        # Clean up dict reference; thread will deleteLater on finished
        if scene_index in self.lazy_loading_threads:
            try:
                del self.lazy_loading_threads[scene_index]
            except Exception:
                pass
        
        # Update UI if this is the current scene
        if scene_index == self.current_scene_index:
            self.update_current_tab()
        
        print(f"Scene {scene_index} media ready")
        
        # Start loading next scene in background (only if it's already analyzed)
        next_scene = scene_index + 1
        if next_scene < len(self.scenes_data):
            next_scene_data = self.scenes_data[next_scene]
            if next_scene_data.get('analyzed', False) and self.scene_loading_states.get(next_scene, 'pending') == 'pending':
                self.start_lazy_loading_for_scene(next_scene)
    
    def on_scene_media_error(self, scene_index: int, error_message: str):
        """Handle scene media error"""
        if scene_index >= len(self.scenes_data):
            return
        self.scene_loading_states[scene_index] = 'error'
        
        # Clean up dict reference; thread will deleteLater on finished
        if scene_index in self.lazy_loading_threads:
            try:
                del self.lazy_loading_threads[scene_index]
            except Exception:
                pass
        
        # Update UI if this is the current scene
        if scene_index == self.current_scene_index:
            self.update_current_tab()
        
        print(f"Scene {scene_index} media error: {error_message}")
    
    def create_video_thumbnail(self, video_path: str) -> str:
        """Create thumbnail for video file using ffmpeg"""
        try:
            # Create thumbnails directory if it doesn't exist
            thumbnails_dir = os.path.join(self.get_project_root(), "thumbnails")
            if not os.path.exists(thumbnails_dir):
                os.makedirs(thumbnails_dir)
            
            # Generate unique thumbnail filename using file path hash
            import hashlib
            video_hash = hashlib.md5(video_path.encode()).hexdigest()[:8]
            video_name = os.path.splitext(os.path.basename(video_path))[0]
            thumbnail_path = os.path.join(thumbnails_dir, f"{video_name}_{video_hash}_thumb.jpg")
            
            # Check if thumbnail already exists
            if os.path.exists(thumbnail_path):
                return thumbnail_path
            
            # Use ffmpeg to extract thumbnail
            import subprocess
            cmd = [
                'ffmpeg', '-i', video_path, 
                '-ss', '00:00:01',  # Extract frame at 1 second
                '-vframes', '1',    # Extract only 1 frame
                '-vf', 'scale=640:360',  # Scale to 640x360 (HD quality)
                '-q:v', '2',  # High quality JPEG
                '-y',  # Overwrite output file
                thumbnail_path
            ]
            
            # Suppress flashing console window on Windows
            import sys
            startupinfo = None
            creationflags = 0
            if sys.platform == "win32":
                try:
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    creationflags = subprocess.CREATE_NO_WINDOW
                except Exception:
                    startupinfo = None
                    creationflags = 0

            result = run_hidden(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
                startupinfo=startupinfo,
                creationflags=creationflags
            )
            
            if result.returncode == 0 and os.path.exists(thumbnail_path):
                print(f"✅ Video thumbnail created: {thumbnail_path}")
                return thumbnail_path
            else:
                print(f"❌ Failed to create video thumbnail: {result.stderr}")
                return ""
                
        except Exception as e:
            print(f"❌ Error creating video thumbnail: {e}")
            return ""
    
    def load_downloads_data(self) -> List[DownloadItem]:
        """Load downloads data from history only"""
        download_items = []
        
        # Load all files from downloads history (including missing files)
        if hasattr(self, 'downloads_history') and self.downloads_history:
            for item in self.downloads_history:
                # Add all items to the list, regardless of whether they exist
                # The UI will handle showing missing files appropriately
                download_items.append(item)
        
        # Sort by download date (newest first)
        download_items.sort(key=lambda x: x.download_date, reverse=True)
        
        return download_items
    
    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human readable format"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"
    
    def open_downloaded_file(self, file_path: str):
        """Open downloaded file with default application"""
        try:
            if os.path.exists(file_path):
                if sys.platform == "win32":
                    os.startfile(file_path)
                elif sys.platform == "darwin":
                    run_hidden(["open", file_path])
                else:
                    run_hidden(["xdg-open", file_path])
            else:
                QMessageBox.warning(self, "File", "We couldn't find this file on your computer.")
        except Exception as e:
            QMessageBox.critical(self, "File", "We couldn't open this file. Please try again.")
    
    def delete_downloaded_file(self, item_id: str):
        """Delete downloaded file"""
        try:
            # Find the download item
            if hasattr(self, 'downloads_page') and self.downloads_page:
                for item in self.downloads_page.download_items:
                    if item.id == item_id:
                        # Delete file from disk
                        file_deleted = False
                        if os.path.exists(item.file_path):
                            try:
                                os.remove(item.file_path)
                                file_deleted = True
                            except Exception as e:
                                print(f"Failed to delete file {item.file_path}: {e}")
                        
                        # Remove from list
                        self.downloads_page.download_items.remove(item)
                        
                        # Also remove from persisted downloads history and save
                        try:
                            removed_from_history = False
                            if hasattr(self, 'downloads_history'):
                                # Prefer remove by id, fallback to file_path match
                                for hist_item in list(self.downloads_history):
                                    if getattr(hist_item, 'id', None) == item.id or (
                                        getattr(hist_item, 'file_path', '') and os.path.normpath(hist_item.file_path) == os.path.normpath(item.file_path)
                                    ):
                                        self.downloads_history.remove(hist_item)
                                        removed_from_history = True
                                        break
                            if removed_from_history:
                                self.save_downloads_history_to_file()
                        except Exception as e:
                            print(f"⚠️ Error removing item from downloads history: {e}")

                        # Update UI and statistics
                        self.downloads_page.update_statistics()
                        self.downloads_page.populate_downloads()
                        
                        # Show success message (consider both disk and history removal)
                        success_message = None
                        if file_deleted:
                            success_message = f"File '{item.filename}' deleted successfully!"
                        else:
                            success_message = f"Entry removed from downloads. File not found on disk."
                        success_dialog = PremiumSuccessDialog(
                            self, 
                            "Success", 
                            success_message,
                            "✅"
                        )
                        success_dialog.exec()
                        break
        except Exception as e:
            QMessageBox.critical(self, "File", "We couldn't delete this file. Please try again.")
    
    def display_loading_state(self, tab_index: int):
        """Display loading state for a tab"""
        # Get the current tab's scroll area
        if tab_index == 0:
            tab_widget = self.stock_images_tab
        elif tab_index == 1:
            tab_widget = self.stock_videos_tab
        else:
            tab_widget = self.ai_images_tab
            
        scroll_area = tab_widget.findChild(QScrollArea)
        if not scroll_area:
            return
            
        grid_widget = scroll_area.widget()
        if not grid_widget:
            return
            
        layout = grid_widget.layout()
        if not layout:
            return
        
        # Clear existing content
        for i in reversed(range(layout.count())):
            child = layout.itemAt(i)
            if child:
                widget = child.widget()
                if widget:
                    widget.deleteLater()
        
        # Create loading widget
        loading_widget = QWidget()
        loading_layout = QVBoxLayout(loading_widget)
        loading_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Loading icon
        loading_icon = QLabel("🔄")
        loading_icon.setFont(QFont("Arial", 48))
        loading_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_icon.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
        loading_layout.addWidget(loading_icon)
        
        # Loading text
        loading_text = QLabel("Analyzing...")
        loading_text.setFont(QFont("Inter", 16, QFont.Weight.Medium))
        loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_text.setStyleSheet("color: #6B7280; background: transparent; border: none;")
        loading_layout.addWidget(loading_text)
        
        # Subtitle
        subtitle = QLabel("Finding the best media for this scene")
        subtitle.setFont(QFont("Inter", 12))
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
        loading_layout.addWidget(subtitle)
        
        layout.addWidget(loading_widget, 0, 0, 1, 3)  # Span all columns
    
    def display_error_state(self, tab_index: int):
        """Display error state for a tab"""
        # Get the current tab's scroll area
        if tab_index == 0:
            tab_widget = self.stock_images_tab
        elif tab_index == 1:
            tab_widget = self.stock_videos_tab
        else:
            tab_widget = self.ai_images_tab
            
        scroll_area = tab_widget.findChild(QScrollArea)
        if not scroll_area:
            return
            
        grid_widget = scroll_area.widget()
        if not grid_widget:
            return
            
        layout = grid_widget.layout()
        if not layout:
            return
        
        # Clear existing content
        for i in reversed(range(layout.count())):
            child = layout.itemAt(i)
            if child:
                widget = child.widget()
                if widget:
                    widget.deleteLater()
        
        # Create error widget
        error_widget = QWidget()
        error_layout = QVBoxLayout(error_widget)
        error_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Error icon
        error_icon = QLabel("⚠️")
        error_icon.setFont(QFont("Arial", 48))
        error_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_icon.setStyleSheet("color: #EF4444; background: transparent; border: none;")
        error_layout.addWidget(error_icon)
        
        # Error text
        error_text = QLabel("Failed to load media")
        error_text.setFont(QFont("Inter", 16, QFont.Weight.Medium))
        error_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        error_text.setStyleSheet("color: #6B7280; background: transparent; border: none;")
        error_layout.addWidget(error_text)
        
        # Retry button
        retry_btn = QPushButton("Retry")
        retry_btn.setFont(QFont("Inter", 12, QFont.Weight.Medium))
        retry_btn.setFixedSize(120, 40)
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
        retry_btn.clicked.connect(lambda: self.retry_scene_loading())
        error_layout.addWidget(retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        
        layout.addWidget(error_widget, 0, 0, 1, 3)  # Span all columns
    
    def retry_scene_loading(self):
        """Retry loading for current scene"""
        if self.current_scene_index in self.scene_loading_states:
            self.scene_loading_states[self.current_scene_index] = 'pending'
            self.start_lazy_loading_for_scene(self.current_scene_index)
            
    def on_media_selection_changed(self, suggestion: Dict[str, Any], selected: bool, media_type: str):
        """Handle media selection change"""
        if selected:
            if media_type == 'stock_images':
                self.selected_media['images'].append(suggestion)
            elif media_type == 'ai_images':
                self.selected_media['images'].append(suggestion)
            else:
                self.selected_media['videos'].append(suggestion)
        else:
            item_id = suggestion.get('id', '')
            if media_type == 'stock_images':
                self.selected_media['images'] = [x for x in self.selected_media['images'] if x.get('id', '') != item_id]
            elif media_type == 'ai_images':
                self.selected_media['images'] = [x for x in self.selected_media['images'] if x.get('id', '') != item_id]
            else:
                self.selected_media['videos'] = [x for x in self.selected_media['videos'] if x.get('id', '') != item_id]
        
        # Update download button
        has_selection = bool(self.selected_media['images'] or self.selected_media['videos'])
        self.download_btn.setEnabled(has_selection)
        
    def on_tab_changed(self, index: int):
        """Handle tab change"""
        # Check if AI Images tab is selected
        if index == 2:
            # Check if user can access AI Images (this will update based on current plan)
            if self.can_access_ai_image():
                # User can access AI Images - show normal content
                if hasattr(self, 'ai_images_tab_restricted'):
                    delattr(self, 'ai_images_tab_restricted')
                # Reset tab styling to normal
                if hasattr(self, 'tab_widget'):
                    pass
                self.update_current_tab()
            else:
                # User cannot access AI Images - show restricted content
                if not hasattr(self, 'ai_images_tab_restricted'):
                    self.ai_images_tab_restricted = True
                    self.apply_restricted_tab_styling()
                self.display_restricted_ai_images_content(self.ai_images_tab)
        else:
            self.update_current_tab()
        
    def prev_scene(self):
        """Go to previous scene"""
        # Debounce and guard reentrancy
        if getattr(self, '_nav_locked', False) or not self._debounce_navigation():
            return
        try:
            self._nav_locked = True
            self._update_navigation_buttons()
            if self.current_scene_index > 0:
                self.current_scene_index -= 1
                self.display_scene(self.current_scene_index)
        finally:
            # Release lock slightly later to allow UI update to settle
            try:
                from PyQt6.QtCore import QTimer as _QT
                _QT.singleShot(50, lambda: (setattr(self, '_nav_locked', False), self._update_navigation_buttons()))
            except Exception:
                self._nav_locked = False
                self._update_navigation_buttons()
            
    def next_scene(self):
        """Go to next scene"""
        # Debounce and guard reentrancy
        if getattr(self, '_nav_locked', False) or not self._debounce_navigation():
            return
        # Block forward navigation while current scene is analyzing to prevent piling up jobs
        if self._is_scene_analyzing(self.current_scene_index):
            try:
                print("⏳ Current scene still analyzing; forward navigation is temporarily disabled.")
            except Exception:
                pass
            self._update_navigation_buttons()
            return
        try:
            self._nav_locked = True
            self._update_navigation_buttons()
            if self.current_scene_index < len(self.scenes_data) - 1:
                self.current_scene_index += 1
                self.display_scene(self.current_scene_index)
        finally:
            # Release lock slightly later to allow UI update to settle
            try:
                from PyQt6.QtCore import QTimer as _QT
                _QT.singleShot(50, lambda: (setattr(self, '_nav_locked', False), self._update_navigation_buttons()))
            except Exception:
                self._nav_locked = False
                self._update_navigation_buttons()
            

                
    def download_selected_media(self):
        """Download selected media"""
        if not self.selected_media['images'] and not self.selected_media['videos']:
            QMessageBox.information(self, "Downloads", "Please select items to download.")
            return
        
        # Use default save path from settings
        directory = self.settings.get('default_save_path') or get_default_download_path()
        
        # Ensure the directory exists
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                QMessageBox.warning(self, "Downloads", "We couldn't create the chosen folder. Please try another location.")
                return
            
        # Simple and fast download without complex UI
        try:
            # Combine all media for download (remove duplicates)
            all_media = []
            seen_urls = set()
            
            # Add images with media_type
            for media in self.selected_media['images']:
                download_url = media.get('download_url')
                if download_url and download_url not in seen_urls:
                    media['media_type'] = 'image'
                    all_media.append(media)
                    seen_urls.add(download_url)
            
            # Add videos with media_type
            for media in self.selected_media['videos']:
                download_url = media.get('download_url')
                if download_url and download_url not in seen_urls:
                    media['media_type'] = 'video'
                    all_media.append(media)
                    seen_urls.add(download_url)
            
            if not all_media:
                QMessageBox.information(self, "Downloads", "Please select items to download.")
                return
            
            # Show simple progress dialog
            self.progress_dialog = QDialog(self)
            self.progress_dialog.setWindowTitle("Downloading Media")
            self.progress_dialog.setFixedSize(300, 100)
            self.progress_dialog.setModal(False)  # Non-modal so UI doesn't freeze
            
            layout = QVBoxLayout(self.progress_dialog)
            
            # Simple progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, len(all_media))
            self.progress_bar.setValue(0)
            layout.addWidget(self.progress_bar)
            
            # Status label
            self.status_label = QLabel(f"Downloading {len(all_media)} files...")
            layout.addWidget(self.status_label)
            
            # Show dialog immediately
            self.progress_dialog.show()
            QApplication.processEvents()
            
            # Start download thread
            self.download_thread = DownloadThread(all_media, directory)
            self.download_thread.download_progress.connect(self._on_download_progress)
            self.download_thread.download_complete.connect(self._on_download_complete)
            self.download_thread.download_error.connect(self._on_download_error)
            self.download_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Downloads", "We couldn't start the download. Please try again.")
    
    def _on_download_progress(self, current, total):
        """Handle download progress"""
        try:
            if hasattr(self, 'progress_bar') and self.progress_bar:
                self.progress_bar.setValue(current)
            # Status label removed - status bar no longer exists
            QApplication.processEvents()  # Keep UI responsive
        except Exception as e:
            print(f"Progress update error: {e}")
    
    def _on_download_complete(self, downloaded, failed):
        """Handle download completion"""
        try:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
            
            # Add downloaded files to history (only those downloaded via the program)
            if hasattr(self, 'download_thread') and self.download_thread:
                # Get the downloaded files from the thread
                downloaded_files = getattr(self.download_thread, 'downloaded_files', [])
                for file_info in downloaded_files:
                    file_path = file_info.get('file_path', '')
                    original_url = file_info.get('original_url', '')
                    chapter = file_info.get('chapter', '')
                    scene = file_info.get('scene', '')
                    
                    if file_path and os.path.exists(file_path):
                        self.add_to_downloads_history(file_path, original_url, chapter, scene)
            
            # Refresh downloads page if it exists
            if hasattr(self, 'downloads_page') and self.downloads_page:
                self.downloads_page.update_downloads_data(self.load_downloads_data())
            
            # Show results
            if failed == 0:
                QMessageBox.information(self, "Success", 
                    f"✅ {downloaded} files downloaded successfully!")
            else:
                QMessageBox.warning(self, "Download Complete", 
                    f"✅ {downloaded} files downloaded successfully\n❌ {failed} files failed")
        except Exception as e:
            print(f"Download complete error: {e}")
    
    def _on_download_error(self, error_message):
        """Handle download error"""
        try:
            if hasattr(self, 'progress_dialog') and self.progress_dialog:
                self.progress_dialog.close()
            QMessageBox.critical(self, "Download Error", f"Download failed: {error_message}")
        except Exception as e:
            print(f"Download error handler error: {e}")
    def download_selected_media_old(self):
        """Old download method - kept for reference"""
        if not self.selected_media['images'] and not self.selected_media['videos']:
            QMessageBox.information(self, "Info", "Please select media to download!")
            return
        
        # Use default save path from settings
        directory = self.settings.get('default_save_path', os.path.join(self.get_project_root(), "downloads"))
        
        # Ensure the directory exists
        if not os.path.exists(directory):
            try:
                os.makedirs(directory)
            except Exception as e:
                QMessageBox.warning(self, "Warning", f"Could not create directory: {str(e)}")
                return
            
        # Real download using stock service
        try:
            total_files = len(self.selected_media['images']) + len(self.selected_media['videos'])
            downloaded = 0
            failed = 0
            
            # Create modern progress dialog
            self.progress_dialog = QDialog(self)
            self.progress_dialog.setWindowTitle("Downloading Media")
            self.progress_dialog.setFixedSize(400, 200)
            self.progress_dialog.setModal(True)
            self.progress_dialog.setWindowFlags(Qt.WindowType.FramelessWindowHint)
            self.progress_dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            
            # Main container
            container = QWidget(self.progress_dialog)
            container.setStyleSheet("""
                QWidget {
                    background: white;
                    border-radius: 20px;
                    border: 1px solid #E5E7EB;
                }
            """)
            
            layout = QVBoxLayout(container)
            layout.setContentsMargins(32, 24, 32, 24)
            layout.setSpacing(20)
            
            # Header with icon and title
            header_layout = QHBoxLayout()
            header_layout.setSpacing(12)
            
            # Download icon
            icon_label = QLabel("📥")
            icon_label.setFont(QFont("Arial", 24))
            icon_label.setStyleSheet("color: #3B82F6; background: transparent; border: none;")
            header_layout.addWidget(icon_label)
            
            # Title
            title_label = QLabel("Downloading Media")
            title_label.setFont(QFont("Poppins", 18, QFont.Weight.DemiBold))
            title_label.setStyleSheet("color: #1F2937; background: transparent; border: none;")
            header_layout.addWidget(title_label)
            
            layout.addLayout(header_layout)
            
            # Progress bar
            self.progress_bar = QProgressBar()
            self.progress_bar.setRange(0, total_files)
            self.progress_bar.setValue(0)
            self.progress_bar.setStyleSheet("""
                QProgressBar {
                    border: 2px solid #E5E7EB;
                    border-radius: 10px;
                    text-align: center;
                    background: #F9FAFB;
                }
                QProgressBar::chunk {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3B82F6,
                        stop:1 #60A5FA);
                    border-radius: 8px;
                }
            """)
            layout.addWidget(self.progress_bar)
            
            # Status label
            self.status_label = QLabel(f"Preparing to download {total_files} files...")
            self.status_label.setFont(QFont("Arial", 12))
            self.status_label.setStyleSheet("color: #6B7280; background: transparent; border: none;")
            self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(self.status_label)
            
            # Set dialog layout
            dialog_layout = QVBoxLayout(self.progress_dialog)
            dialog_layout.addWidget(container)
            
            # Show progress dialog
            self.progress_dialog.show()
            
            # Process images
            for media in self.selected_media['images']:
                try:
                    # Check if this is an AI Image (has prompt but no download_url)
                    if media.get('prompt') and not media.get('download_url'):
                        # This is an AI Image - save as prompt file
                        source = media.get('source', 'ai')
                        media_id = media.get('id', 'unknown')
                        
                        # Get chapter and scene information from the media data
                        chapter_info = media.get('chapter', 'Chapter 1')
                        scene_info = media.get('scene', 'Scene 1')
                        media_type = 'AI_Image'
                        
                        # Clean chapter and scene names
                        chapter_clean = "".join(c for c in chapter_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        chapter_clean = chapter_clean.replace(' ', '_')[:20]
                        
                        scene_clean = "".join(c for c in scene_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        scene_clean = scene_clean.replace(' ', '_')[:20]
                        
                        # Get title and prompt
                        title = media.get('title', 'AI_Image')
                        prompt = media.get('prompt', '')
                        
                        # Clean title for filename
                        title_clean = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
                        title_clean = title_clean.replace(' ', '_')[:30]
                        
                        filename = f"{chapter_clean}_{scene_clean}_{media_type}_{title_clean}.txt"
                        filepath = os.path.join(directory, filename)
                        
                        # Save prompt as text file
                        with open(filepath, 'w', encoding='utf-8') as f:
                            f.write(f"AI Image Prompt: {title}\n")
                            f.write(f"Chapter: {chapter_info}\n")
                            f.write(f"Scene: {scene_info}\n")
                            f.write(f"Prompt: {prompt}\n")
                            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                        
                        downloaded += 1
                        print(f"✅ Saved AI Image prompt: {filename}")
                        # Update progress dialog
                        self.progress_bar.setValue(downloaded)
                        # Status label removed - status bar no longer exists
                        QApplication.processEvents()
                        continue
                    
                    # Regular image download
                    download_url = media.get('download_url')
                    if not download_url:
                        print(f"⚠️ No download URL for image: {media.get('title', 'Unknown')}")
                        failed += 1
                        continue
                    
                    # Generate meaningful filename with chapter and scene info
                    source = media.get('source', 'unknown')
                    media_id = media.get('id', 'unknown')
                    
                    # Get chapter and scene information from the media data
                    chapter_info = media.get('chapter', 'Chapter 1')
                    scene_info = media.get('scene', 'Scene 1')
                    media_type = 'Image'
                    
                    # Clean chapter and scene names
                    chapter_clean = "".join(c for c in chapter_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    chapter_clean = chapter_clean.replace(' ', '_')[:20]
                    
                    scene_clean = "".join(c for c in scene_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    scene_clean = scene_clean.replace(' ', '_')[:20]
                    
                    # Add unique identifier to prevent overwriting
                    unique_id = media.get('id', str(uuid.uuid4())[:8])
                    title_clean = media.get('title', 'Untitled')[:15]
                    title_clean = "".join(c for c in title_clean if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    title_clean = title_clean.replace(' ', '_')
                    
                    # Determine file extension based on URL or content type
                    if any(ext in download_url.lower() for ext in ['.jpg', '.jpeg']):
                        ext = '.jpg'
                    elif '.png' in download_url.lower():
                        ext = '.png'
                    elif '.webp' in download_url.lower():
                        ext = '.webp'
                    else:
                        ext = '.jpg'  # Default
                    
                    # Create base filename without unique_id to prevent duplicates
                    base_filename = f"{chapter_clean}_{scene_clean}_{media_type}_{title_clean}{ext}"
                    filepath = os.path.join(directory, base_filename)
                    
                    # Check if file already exists and add counter if needed
                    counter = 1
                    original_filepath = filepath
                    while os.path.exists(filepath):
                        name_without_ext = original_filepath.rsplit('.', 1)[0]
                        ext = original_filepath.rsplit('.', 1)[1] if '.' in original_filepath else ''
                        filepath = f"{name_without_ext}_{counter}.{ext}" if ext else f"{name_without_ext}_{counter}"
                        counter += 1
                        if counter > 100:  # Prevent infinite loop
                            break
                    
                    # Download using stock service with better async handling
                    import asyncio
                    try:
                        # Check if there's already an event loop running
                        try:
                            loop = asyncio.get_running_loop()
                            # If we're already in an event loop, use asyncio.create_task
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, stock_service.download_media(download_url, filepath))
                                success = future.result()
                        except RuntimeError:
                            # No event loop running, create new one
                            success = asyncio.run(stock_service.download_media(download_url, filepath))
                    except Exception as e:
                        print(f"❌ Async download error: {e}")
                        success = False
                    
                    if success:
                        downloaded += 1
                        print(f"✅ Downloaded: {os.path.basename(filepath)}")
                        # Update progress dialog
                        self.progress_bar.setValue(downloaded)
                        # Status label removed - status bar no longer exists
                        QApplication.processEvents()
                    else:
                        failed += 1
                        print(f"❌ Failed to download: {os.path.basename(filepath)}")
                        # Update progress dialog
                        self.progress_bar.setValue(downloaded)
                        # Status label removed - status bar no longer exists
                        QApplication.processEvents()
                        
                except Exception as e:
                    failed += 1
                    print(f"❌ Error downloading image: {e}")
                    # Update progress dialog
                    self.progress_bar.setValue(downloaded)
                    # Status label removed - status bar no longer exists
                    QApplication.processEvents()
            
            # Process videos
            for media in self.selected_media['videos']:
                try:
                    download_url = media.get('download_url')
                    if not download_url:
                        print(f"⚠️ No download URL for video: {media.get('title', 'Unknown')}")
                        failed += 1
                        continue
                    
                    # Generate meaningful filename with chapter and scene info
                    source = media.get('source', 'unknown')
                    media_id = media.get('id', 'unknown')
                    
                    # Get chapter and scene information from the media data
                    chapter_info = media.get('chapter', 'Chapter 1')
                    scene_info = media.get('scene', 'Scene 1')
                    media_type = 'Video'
                    
                    # Clean chapter and scene names
                    chapter_clean = "".join(c for c in chapter_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    chapter_clean = chapter_clean.replace(' ', '_')[:20]
                    
                    scene_clean = "".join(c for c in scene_info if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    scene_clean = scene_clean.replace(' ', '_')[:20]
                    
                    # Add unique identifier to prevent overwriting
                    unique_id = media.get('id', str(uuid.uuid4())[:8])
                    title_clean = media.get('title', 'Untitled')[:15]
                    title_clean = "".join(c for c in title_clean if c.isalnum() or c in (' ', '-', '_')).rstrip()
                    title_clean = title_clean.replace(' ', '_')
                    
                    # Determine file extension based on URL
                    if '.mp4' in download_url.lower():
                        ext = '.mp4'
                    elif '.mov' in download_url.lower():
                        ext = '.mov'
                    elif '.avi' in download_url.lower():
                        ext = '.avi'
                    else:
                        ext = '.mp4'  # Default
                    
                    # Create base filename without unique_id to prevent duplicates
                    base_filename = f"{chapter_clean}_{scene_clean}_{media_type}_{title_clean}{ext}"
                    filepath = os.path.join(directory, base_filename)
                    
                    # Check if file already exists and add counter if needed
                    counter = 1
                    original_filepath = filepath
                    while os.path.exists(filepath):
                        name_without_ext = original_filepath.rsplit('.', 1)[0]
                        ext = original_filepath.rsplit('.', 1)[1] if '.' in original_filepath else ''
                        filepath = f"{name_without_ext}_{counter}.{ext}" if ext else f"{name_without_ext}_{counter}"
                        counter += 1
                        if counter > 100:  # Prevent infinite loop
                            break
                    
                    # Download using stock service with better async handling
                    import asyncio
                    try:
                        # Check if there's already an event loop running
                        try:
                            loop = asyncio.get_running_loop()
                            # If we're already in an event loop, use asyncio.create_task
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                future = executor.submit(asyncio.run, stock_service.download_media(download_url, filepath))
                                success = future.result()
                        except RuntimeError:
                            # No event loop running, create new one
                            success = asyncio.run(stock_service.download_media(download_url, filepath))
                    except Exception as e:
                        print(f"❌ Async download error: {e}")
                        success = False
                    
                    if success:
                        downloaded += 1
                        print(f"✅ Downloaded: {os.path.basename(filepath)}")
                        # Update progress dialog
                        self.progress_bar.setValue(downloaded)
                        # Status label removed - status bar no longer exists
                        QApplication.processEvents()
                    else:
                        failed += 1
                        print(f"❌ Failed to download: {os.path.basename(filepath)}")
                        # Update progress dialog
                        self.progress_bar.setValue(downloaded)
                        # Status label removed - status bar no longer exists
                        QApplication.processEvents()
                        
                except Exception as e:
                    failed += 1
                    print(f"❌ Error downloading video: {e}")
                    # Update progress dialog
                    self.progress_bar.setValue(downloaded)
                    # Status label removed - status bar no longer exists
                    QApplication.processEvents()
            
            self.progress_dialog.close()
            
            # Refresh downloads page if it exists
            if hasattr(self, 'downloads_page') and self.downloads_page:
                self.downloads_page.update_downloads_data(self.load_downloads_data())
            
            # Show results
            if failed == 0:
                reply = QMessageBox.information(self, "Success", 
                    f"✅ {downloaded} files downloaded successfully to {directory}\n\nWould you like to open the downloads folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    import subprocess
                    import platform
                    if platform.system() == "Windows":
                        run_hidden(["explorer", directory])
                    elif platform.system() == "Darwin":  # macOS
                        run_hidden(["open", directory])
                    else:  # Linux
                        run_hidden(["xdg-open", directory])
            else:
                reply = QMessageBox.warning(self, "Download Complete", 
                    f"✅ {downloaded} files downloaded successfully\n❌ {failed} files failed\n\nLocation: {directory}\n\nWould you like to open the downloads folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    import subprocess
                    import platform
                    if platform.system() == "Windows":
                        run_hidden(["explorer", directory])
                    elif platform.system() == "Darwin":  # macOS
                        run_hidden(["open", directory])
                    else:  # Linux
                        run_hidden(["xdg-open", directory])
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Download failed: {str(e)}")
            
    def open_settings(self):
        """Open settings dialog"""
        try:
            print("🔧 Opening settings dialog...")
            
            # Check if dialog is already open
            if hasattr(self, '_settings_dialog') and self._settings_dialog is not None:
                print("⚠️ Settings dialog already open, bringing to front")
                self._settings_dialog.raise_()
                self._settings_dialog.activateWindow()
                return
            
            # Create new settings dialog
            self._settings_dialog = SettingsDialog(self, self.settings)
            
            # Set dialog as modal to ensure proper focus and behavior
            self._settings_dialog.setModal(True)
            
            # Connect dialog close event to clean up and handle settings
            self._settings_dialog.finished.connect(self._on_settings_dialog_finished)
            
            print("🔧 Showing settings dialog...")
            self._settings_dialog.show()
            self._settings_dialog.raise_()
            self._settings_dialog.activateWindow()
            
        except Exception as e:
            print(f"❌ Error opening settings dialog: {e}")
            QMessageBox.critical(self, "Error", f"Could not open settings dialog: {str(e)}")
            # Clean up dialog reference on error
            if hasattr(self, '_settings_dialog'):
                self._settings_dialog = None
            # Ensure main window regains focus
            self.raise_()
            self.activateWindow()
    
    def _on_settings_dialog_finished(self, result):
        """Handle settings dialog close event"""
        print(f"🔧 Settings dialog finished with result: {result}")
        
        try:
            if result == QDialog.DialogCode.Accepted:
                # Get updated settings from dialog
                updated_settings = self._settings_dialog.get_settings()
                if updated_settings:
                    # Update settings with new values
                    for key, value in updated_settings.items():
                        self.settings[key] = value
                    print(f"✅ Settings updated: {self.settings}")
                    
                    # Save settings to file for persistence
                    try:
                        import json
                        with open('data/settings.json', 'w') as f:
                            json.dump(self.settings, f, indent=2)
                        print("✅ Settings saved to file")
                        
                        # Verify settings were updated correctly
                        print(f"🔧 Settings verification:")
                        print(f"   stock_images_count: {self.settings.get('stock_images_count')}")
                        print(f"   stock_videos_count: {self.settings.get('stock_videos_count')}")
                        print(f"   ai_images_count: {self.settings.get('ai_images_count')}")
                        print(f"   highlight_color: {self.settings.get('highlight_color')}")
                        
                        # Apply the new highlight color to text input
                        self.apply_highlight_color_from_settings()
                        
                    except Exception as e:
                        print(f"⚠️ Could not save settings to file: {e}")
                else:
                    print("⚠️ No settings returned from dialog")
            else:
                print("❌ Settings dialog cancelled")
        except Exception as e:
            print(f"❌ Error handling settings dialog result: {e}")
        finally:
            # Clean up dialog reference
            if hasattr(self, '_settings_dialog'):
                self._settings_dialog = None
            
            # Ensure main window regains focus and is responsive
            self.raise_()
            self.activateWindow()
            
            # Restore the correct page title after settings dialog closes
            if hasattr(self, 'page_title_label'):
                # Check what page we're actually on and restore the correct title
                if hasattr(self, 'stacked_widget'):
                    current_widget = self.stacked_widget.currentWidget()
                    if current_widget:
                        # If we're on the analysis page (create page), restore "Create New Analysis"
                        if hasattr(current_widget, 'objectName') and current_widget.objectName() == 'main_page':
                            self.page_title_label.setText("Create New Analysis")
                            print("🔧 Restored page title to 'Create New Analysis'")
                        elif hasattr(self, 'current_page_id'):
                            # Use stored page ID to restore correct title
                            page_titles = {
                                "home": "Home",
                                "ai_review": "AI Review", 
                                "downloads": "Downloads",
                                "history": "History",
                                "info": "About",
                                "create": "Create New Analysis"
                            }
                            if self.current_page_id in page_titles:
                                self.page_title_label.setText(page_titles[self.current_page_id])
                                print(f"🔧 Restored page title to '{page_titles[self.current_page_id]}'")
                        else:
                            # Default fallback
                            self.page_title_label.setText("Create New Analysis")
                            print("🔧 Restored page title to default 'Create New Analysis'")
        
    def select_video_file(self):
        """Select video file for AI Review analysis"""
        # Check if user is on Free plan (only Free plan users are restricted)
        if self.is_free_plan_user():
            self.show_plan_restriction_dialog("AI Review", "Plus")
            return
        
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Video File for Analysis",
            "",
            "Video Files (*.mp4 *.avi *.mov *.mkv *.wmv *.flv);;All Files (*)"
        )
        
        if file_path:
            # Set loading state for AI Review upload container if it exists
            if hasattr(self, 'ai_review_upload_container') and hasattr(self.ai_review_upload_container, 'update_loading_state'):
                self.ai_review_upload_container.update_loading_state()
            self.analyze_video_quality(file_path)
    
    def update_analysis_content_processing(self, filename: str):
        """Update analysis content to show processing state with beautiful upload animation"""
        print(f"🔄 Starting analysis for: {filename}")
        
        # Just update the analysis content text, keep the beautiful upload animation
        if hasattr(self, 'analysis_content'):
            self.analysis_content.setText(f"🔄 Analyzing: {filename}\n\nAI analysis in progress...")
            print("🔄 Analysis content updated successfully!")
        else:
            print("❌ analysis_content not found!")
    
        # Features container will stay visible to show the beautiful upload animation
        print("✅ Using beautiful DragDropUploadWidget animation!")
    

    
    def analyze_video_quality(self, file_path: str):
        """Analyze video quality using real AI analysis"""
        try:
            # Check if user is on Free plan (only Free plan users are restricted)
            if self.is_free_plan_user():
                self.show_plan_restriction_dialog("AI Review", "Plus")
                # Reset upload containers to normal state if they exist
                if hasattr(self, 'upload_container') and hasattr(self.upload_container, 'update_normal_state'):
                    self.upload_container.update_normal_state()
                if hasattr(self, 'ai_review_upload_container') and hasattr(self.ai_review_upload_container, 'update_normal_state'):
                    self.ai_review_upload_container.update_normal_state()
                return
            
            import os
            filename = os.path.basename(file_path)
            
            # Set upload container to loading state if it exists and is DragDropUploadWidget
            if hasattr(self, 'upload_container') and hasattr(self.upload_container, 'update_loading_state'):
                self.upload_container.update_loading_state()
            # Also set AI Review upload container to loading state if it exists
            if hasattr(self, 'ai_review_upload_container') and hasattr(self.ai_review_upload_container, 'update_loading_state'):
                self.ai_review_upload_container.update_loading_state()
            
            # Show processing message
            self.update_analysis_content_processing(filename)
            
            # Start background AI analysis with timeout
            self.video_analysis_thread = VideoAnalysisThread(file_path, self.auth_service, timeout_seconds=300)  # 5 minutes timeout
            self.video_analysis_thread.analysis_complete.connect(self.on_video_analysis_complete)
            self.video_analysis_thread.analysis_error.connect(self.on_video_analysis_error)
            self.video_analysis_thread.start()
            
# No popup - results will show directly in panel
            
        except Exception as e:
            # Reset upload containers on error
            if hasattr(self, 'upload_container') and hasattr(self.upload_container, 'update_normal_state'):
                self.upload_container.update_normal_state()
            if hasattr(self, 'ai_review_upload_container') and hasattr(self.ai_review_upload_container, 'update_normal_state'):
                self.ai_review_upload_container.update_normal_state()
            QMessageBox.critical(
                self, 
                "Analysis Error", 
                f"Failed to start AI video analysis:\n{str(e)}"
            )
    
    def on_video_analysis_complete(self, result: dict):
        """Handle video analysis completion"""
        print("🎉 Video analysis completed successfully!")
        print(f"Result keys: {list(result.keys())}")
        print(f"Full result: {result}")

        # Fire-and-forget activity POST for video analysis completed
        try:
            self._post_activity_async(
                activity_type="analysis_completed",
                message="Video analysis completed",
                metadata={
                    "details": result.get("summary") if isinstance(result, dict) else None
                }
            )
        except Exception as _e:
            print(f"Activity post failed (video analysis): {_e}")
        
        if hasattr(self, 'analysis_content'):
            # Reset upload containers if they exist
            if hasattr(self, 'upload_container') and hasattr(self.upload_container, 'update_normal_state'):
                self.upload_container.update_normal_state()
            if hasattr(self, 'ai_review_upload_container') and hasattr(self.ai_review_upload_container, 'update_normal_state'):
                self.ai_review_upload_container.update_normal_state()
            
            # Hide upload container and features section to make room for results
            if hasattr(self, 'upload_container'):
                self.upload_container.hide()
                print("📤 Upload container hidden for analysis results")
            
            if hasattr(self, 'features_container'):
                self.features_container.hide()
                print("📦 Features section hidden for analysis results")
            
            # Remove loading container if it exists
            if hasattr(self, 'animated_loading_container') and self.animated_loading_container:
                parent_layout = self.animated_loading_container.parent().layout()
                if parent_layout:
                    parent_layout.removeWidget(self.animated_loading_container)
                    self.animated_loading_container.deleteLater()
                    self.animated_loading_container = None
                print("🗑️ Loading container removed")
            
            # Create advanced analysis dashboard
            self.create_advanced_analysis_dashboard(result)
            
            print("✅ Advanced analysis dashboard displayed successfully!")
        else:
            print("❌ analysis_content not found!")
    
    def on_video_analysis_error(self, error_msg: str):
        """Handle video analysis error"""
        print(f"❌ Video analysis error: {error_msg}")
        
        # Stop loading animation if it exists
        if hasattr(self, 'animated_ball') and self.animated_ball:
            self.animated_ball.stop_animation()
            print("🛑 Loading animation stopped due to error")
        
        if hasattr(self, 'analysis_content'):
            # Reset upload containers if they exist
            if hasattr(self, 'upload_container') and hasattr(self.upload_container, 'update_normal_state'):
                self.upload_container.update_normal_state()
            if hasattr(self, 'ai_review_upload_container') and hasattr(self.ai_review_upload_container, 'update_normal_state'):
                self.ai_review_upload_container.update_normal_state()
            
            # Hide upload container and features section to make room for error message
            if hasattr(self, 'upload_container'):
                self.upload_container.hide()
                print("📤 Upload container hidden for error message")
            
            if hasattr(self, 'features_container'):
                self.features_container.hide()
                print("📦 Features section hidden for error message")
            
            # Remove animated loading container if it exists
            if hasattr(self, 'animated_loading_container') and self.animated_loading_container:
                parent_layout = self.animated_loading_container.parent().layout()
                if parent_layout:
                    parent_layout.removeWidget(self.animated_loading_container)
                    self.animated_loading_container.deleteLater()
                    self.animated_loading_container = None
                print("🗑️ Animated loading container removed due to error")
            
            # Show detailed error message
            error_text = f"❌ Video Analysis Failed!\n\n"
            error_text += f"Error: {error_msg}\n\n"
            error_text += "🔧 Troubleshooting tips:\n"
            error_text += "• Ensure the video file is valid\n"
            error_text += "• Supported formats: MP4, AVI, MOV, MKV\n"
            error_text += "• Make sure file size is not too large\n"
            error_text += "• Check your internet connection"
            
            self.analysis_content.setText(error_text)
            self.analysis_content.setStyleSheet("""
                QLabel {
                    color: #EF4444;
                    background: #FEF2F2;
                    font-family: 'Inter 24pt', 'Inter', 'Arial', sans-serif;
                    font-size: 12px;
                    font-weight: bold;
                    padding: 30px;
                    border: 2px solid #EF4444;
                    border-radius: 12px;
                    margin: 20px;
                    text-align: left;
                    line-height: 1.5;
                    min-height: 300px;
                }
            """)
            
            print("❌ Error message displayed successfully!")
        else:
            print("❌ analysis_content not found!")

    def _display_ai_images_grid(self, tab_widget, suggestions):
        """Display AI Images grid with faster loading"""
        try:
            if not tab_widget:
                print("⚠️ AI Images: tab_widget is None")
                return
                
            scroll_area = tab_widget.findChild(QScrollArea)
            if not scroll_area:
                print("⚠️ AI Images: scroll_area not found")
                return
                
            grid_widget = scroll_area.widget()
            if not grid_widget:
                print("⚠️ AI Images: grid_widget not found")
                return
                
            layout = grid_widget.layout()
            if not layout:
                print("⚠️ AI Images: layout not found")
                return
        except Exception as e:
            print(f"❌ AI Images: Error in _display_ai_images_grid: {e}")
            return
        
        # Clear existing content
        for i in reversed(range(layout.count())):
            child = layout.itemAt(i)
            if child:
                widget = child.widget()
                if widget:
                    widget.deleteLater()
                
        if not suggestions:
            # Create empty state for AI Images
            empty_widget = QWidget()
            empty_layout = QVBoxLayout()
            empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_layout.setSpacing(16)
            
            icon_label = QLabel("🎨")
            icon_label.setFont(QFont("Arial", 48))
            icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_label.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
            empty_layout.addWidget(icon_label)
            
            title_label = QLabel("No AI Images available")
            title_label.setFont(QFont("Inter", 16, QFont.Weight.Medium))
            title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            title_label.setStyleSheet("color: #6B7280; background: transparent; border: none;")
            empty_layout.addWidget(title_label)
            
            subtitle_label = QLabel("AI images not available for this scene")
            subtitle_label.setFont(QFont("Inter", 12))
            subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            subtitle_label.setStyleSheet("color: #9CA3AF; background: transparent; border: none;")
            subtitle_label.setWordWrap(True)
            empty_layout.addWidget(subtitle_label)
            
            layout.addWidget(empty_widget)
            return
        
        # Create grid for AI Images with faster loading
        grid_layout = QGridLayout()
        grid_layout.setSpacing(16)
        
        # Calculate grid dimensions
        items_per_row = 3
        for i, suggestion in enumerate(suggestions):
            row = i // items_per_row
            col = i % items_per_row
            
            # Create AI image card with minimal loading
            card = MediaCard(suggestion, "ai_images", i)
            card.selection_changed.connect(self.on_media_selection_changed)
            
            # Sync state for in-progress and completed to keep button text consistent across navigation
            try:
                prompt_key = suggestion.get('prompt', suggestion.get('title', 'Beautiful landscape'))
                status = self.ai_generation_status.get(prompt_key)
                self.register_ai_generation_card(prompt_key, card)
                if status == 'completed':
                    # Ensure the card shows final image immediately and button is set to Created ✅
                    image_url = self.ai_generation_results.get(prompt_key)
                    if image_url and not getattr(card, 'has_final_image', False):
                        card.load_generated_ai_image(image_url)
                        card.has_final_image = True
                    # Always enforce created button state on re-entry
                    try:
                        card.update_created_button_state()
                    except Exception:
                        pass
                elif status == 'creating':
                    # Ensure creating indicator on re-entry
                    try:
                        card.show_ai_generation_loading()
                    except Exception:
                        pass
            except Exception as e:
                print(f"⚠️ Could not register AI card for sync: {e}")
            
            grid_layout.addWidget(card, row, col)
        
        # Add grid to layout
        grid_widget = QWidget()
        grid_widget.setLayout(grid_layout)
        layout.addWidget(grid_widget)
        
        # Force UI update to ensure AI image cards are visible
        try:
            tab_widget.update()
            tab_widget.repaint()
            print(f"✅ AI Images: Successfully displayed {len(suggestions)} AI image cards")
        except Exception as e:
            print(f"⚠️ AI Images: Error updating UI: {e}")
    
    def register_ai_generation_card(self, prompt: str, media_card):
        """Register a MediaCard for AI image generation status tracking"""
        if prompt not in self.ai_generation_media_cards:
            self.ai_generation_media_cards[prompt] = []
        if media_card not in self.ai_generation_media_cards[prompt]:
            self.ai_generation_media_cards[prompt].append(media_card)
            try:
                # Auto-unregister when card is destroyed
                media_card.destroyed.connect(lambda obj=None, p=prompt, m=media_card: self._unregister_media_card(p, m))
            except Exception as e:
                print(f"⚠️ Could not connect destroyed signal for MediaCard: {e}")
        
        # If we already have a known state, immediately sync the card
        status = self.ai_generation_status.get(prompt)
        if status == 'creating':
            try:
                media_card.show_ai_generation_loading()
            except Exception as e:
                print(f"❌ Error syncing loading state to MediaCard: {e}")
        elif status == 'completed':
            # Ensure button shows Created state on newly registered cards
            try:
                if hasattr(media_card, 'update_created_button_state'):
                    media_card.update_created_button_state()
            except Exception:
                pass
    
    def update_ai_generation_status(self, prompt: str, status: str, image_url: str = None):
        """Update AI image generation status and notify all related MediaCards"""
        # Idempotent guard: avoid re-emitting the same state repeatedly
        prev_status = self.ai_generation_status.get(prompt)
        prev_url = self.ai_generation_results.get(prompt)
        if prev_status == status and (status != 'completed' or prev_url == image_url):
            return

        self.ai_generation_status[prompt] = status
        if status == 'completed' and image_url:
            self.ai_generation_results[prompt] = image_url
            # Fire-and-forget activity POST for AI image generated
            try:
                self._post_activity_async(
                    activity_type="ai_image_generated",
                    message="AI image generated",
                    metadata={
                        "details": f"Prompt: {prompt[:60]}..." if isinstance(prompt, str) and len(prompt) > 60 else f"Prompt: {prompt}",
                        "prompt": prompt,
                        "image_url": image_url
                    }
                )
            except Exception as _e:
                print(f"Activity post failed (ai image): {_e}")
        
        # Notify all MediaCards with this prompt
        if prompt in self.ai_generation_media_cards:
            # Iterate over a copy and prune dead cards on failure
            for media_card in list(self.ai_generation_media_cards[prompt]):
                try:
                    if status == 'creating' and hasattr(media_card, 'show_ai_generation_loading'):
                        media_card.show_ai_generation_loading()
                    elif status == 'completed' and image_url and hasattr(media_card, 'on_ai_image_generated'):
                        media_card.on_ai_image_generated(image_url, prompt)
                    elif status == 'error' and hasattr(media_card, 'on_ai_image_error'):
                        media_card.on_ai_image_error("Generation failed")
                except Exception as e:
                    # Likely the card has been destroyed; unregister it
                    print(f"❌ Error updating MediaCard status: {e}")
                    try:
                        self._unregister_media_card(prompt, media_card)
                    except Exception:
                        pass
    
    def get_ai_generation_status(self, prompt: str) -> str:
        """Get current AI image generation status for a prompt"""
        return self.ai_generation_status.get(prompt, 'idle')

    def get_ai_generation_result(self, prompt: str) -> Optional[str]:
        """Get generated image URL for a prompt if completed"""
        return self.ai_generation_results.get(prompt)

    def _post_activity_async(self, activity_type: str, message: str, metadata: Dict[str, Any]):
        """Send activity event to dashboard API without blocking UI"""
        def _worker():
            try:
                # Resolve base URL from env or default localhost root (with sanitization)
                base_url = os.getenv("APP_BASE_URL") or os.getenv("API_BASE_URL") or "http://localhost:3000"
                try:
                    # Fix common mistakes like "https:dashboard..." (missing slashes)
                    base_url = (base_url or "").strip()
                    if base_url.startswith("https:") and not base_url.startswith("https://"):
                        base_url = "https://" + base_url[len("https:"):].lstrip("/")
                    elif base_url.startswith("http:") and not base_url.startswith("http://"):
                        base_url = "http://" + base_url[len("http:"):].lstrip("/")
                    # If scheme is missing entirely, default to https
                    if base_url and not (base_url.startswith("http://") or base_url.startswith("https://")):
                        base_url = "https://" + base_url.lstrip("/")
                    # Avoid trailing slash to prevent double slashes on join
                    base_url = base_url.rstrip("/") or "http://localhost:3000"
                except Exception:
                    base_url = "http://localhost:3000"
                url = f"{base_url}/api/activities"
                payload = {
                    "type": activity_type,
                    "message": message,
                    "metadata": metadata or {}
                }
                # Include userId explicitly if available (helps when Authorization is not used server-side)
                try:
                    if getattr(self, 'current_user', None) and getattr(self.current_user, 'id', None):
                        payload["userId"] = self.current_user.id
                except Exception:
                    pass

                headers = {"Content-Type": "application/json"}
                # Attach Supabase bearer if available
                try:
                    if self.auth_service:
                        token = self.auth_service.get_access_token()
                        if token:
                            headers["Authorization"] = f"Bearer {token}"
                except Exception:
                    pass

                # Non-blocking POST with fallback to localhost dashboard
                def _try_post(target_url: str) -> bool:
                    try:
                        r = requests.post(target_url, json=payload, headers=headers, timeout=7)
                        if r.status_code >= 300:
                            print(f"Activity POST failed: {r.status_code} {r.text}")
                            return False
                        print(f"Activity POST ok: {r.status_code}")
                        return True
                    except Exception as _e:
                        print(f"Activity POST exception to {target_url}: {_e}")
                        return False

                ok = _try_post(url)
                if not ok:
                    fallback_base = "http://localhost:3000"
                    if base_url != fallback_base:
                        fb_url = f"{fallback_base}/api/activities"
                        _try_post(fb_url)
            except Exception as e:
                print(f"Failed to post activity: {e}")

        t = _threading.Thread(target=_worker, daemon=True)
        t.start()

    def _unregister_media_card(self, prompt: str, media_card) -> None:
        """Remove a MediaCard from tracking for a prompt"""
        try:
            if prompt in self.ai_generation_media_cards:
                cards = self.ai_generation_media_cards[prompt]
                if media_card in cards:
                    cards.remove(media_card)
                if not cards:
                    del self.ai_generation_media_cards[prompt]
        except Exception as e:
            print(f"⚠️ Could not unregister MediaCard: {e}")
    
    def position_upgrade_button(self, background_widget, upgrade_button):
        """Position the upgrade button responsively below the background image"""
        if hasattr(background_widget, 'background_label'):
            # Get background image position and size
            bg_geometry = background_widget.background_label.geometry()
            img_x = bg_geometry.x()
            img_y = bg_geometry.y()
            img_width = bg_geometry.width()
            img_height = bg_geometry.height()
            
            # Button dimensions
            button_width = 200
            button_height = 48
            
            # Position button below the image, centered horizontally
            button_x = (background_widget.width() - button_width) // 2
            button_y = img_y + img_height + 20  # 20px below the image
            
            # Ensure button stays within widget bounds
            button_x = max(0, min(button_x, background_widget.width() - button_width))
            button_y = max(0, min(button_y, background_widget.height() - button_height))
            
            # Set button geometry
            upgrade_button.setGeometry(button_x, button_y, button_width, button_height)

def create_application():
    """Create and configure the PyQt6 application"""
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import QCoreApplication, Qt
    from PyQt6.QtGui import QGuiApplication
    # Enable HiDPI pixmaps and avoid rounding that causes blur
    try:
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps)
    except Exception:
        pass
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass
    
    app = QApplication(sys.argv)
    app.setApplicationName("Video Creator AI")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("Stuck AI")
    
    return app

def warn_if_high_scaling():
    """Show a pre-launch notice if any monitor scaling > 125%."""
    try:
        from PyQt6.QtGui import QGuiApplication
        from PyQt6.QtWidgets import QMessageBox, QDialog, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QFrame
        from PyQt6.QtGui import QIcon, QPixmap, QFont
        from PyQt6.QtCore import Qt
        screens = QGuiApplication.screens() or []
        max_scale = 1.0
        for s in screens:
            try:
                logical = float(s.logicalDotsPerInch()) / 96.0
            except Exception:
                logical = 1.0
            try:
                ratio = float(s.devicePixelRatio())
            except Exception:
                ratio = 1.0
            # Use the highest estimate per screen
            max_scale = max(max_scale, logical, ratio)
        if max_scale > 1.25:
            class HighScalingDialog(QDialog):
                def __init__(self, scale_value: float):
                    super().__init__()
                    self.setWindowTitle("High Display Scaling Detected")
                    self.setWindowModality(Qt.WindowModality.ApplicationModal)
                    self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
                    self.setMinimumWidth(520)
                    self.setStyleSheet(
                        """
                        QDialog { background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px; }
                        QLabel#Title { color: #111827; font-size: 18px; font-weight: 600; }
                        QLabel#Body { color: #4B5563; font-size: 13px; }
                        QPushButton#Primary { background: #3B82F6; color: white; border: none; padding: 8px 14px; border-radius: 8px; }
                        QPushButton#Primary:hover { background: #2563EB; }
                        QPushButton#Secondary { background: #F3F4F6; color: #111827; border: 1px solid #E5E7EB; padding: 8px 14px; border-radius: 8px; }
                        QPushButton#Secondary:hover { background: #E5E7EB; }
                        QFrame#Header { background: #F9FAFB; border-bottom: 1px solid #E5E7EB; border-top-left-radius: 12px; border-top-right-radius: 12px; }
                        """
                    )

                    main = QVBoxLayout(self)
                    main.setContentsMargins(0, 0, 0, 0)
                    main.setSpacing(0)

                    # Header
                    header = QFrame()
                    header.setObjectName("Header")
                    h_layout = QHBoxLayout(header)
                    h_layout.setContentsMargins(20, 16, 20, 16)
                    h_layout.setSpacing(12)
                    # Set window icon to app logo
                    try:
                        import os as _os
                        _logo_path = _os.path.join(self.get_project_root(), "ui", "assets", "logo.png")
                        if _logo_path and _os.path.exists(_logo_path):
                            self.setWindowIcon(QIcon(_logo_path))
                    except Exception:
                        pass

                    title = QLabel("High display scaling is enabled")
                    title.setObjectName("Title")
                    try:
                        title.setFont(QFont("Poppins", 16, QFont.Weight.DemiBold))
                    except Exception:
                        pass

                    h_layout.addWidget(title)
                    h_layout.addStretch()
                    main.addWidget(header)

                    # Body
                    body_wrap = QFrame()
                    body_layout = QVBoxLayout(body_wrap)
                    body_layout.setContentsMargins(20, 18, 20, 6)
                    body_layout.setSpacing(10)

                    body = QLabel(
                        "For the best experience, StuckAI is optimized for a display scale of 125% or lower.\n"
                        "Your current effective scale appears to be around {:.0f}%.\n\n"
                        "Consider reducing your system scale in Settings → Display → Scale.\n"
                        "You may continue, but some layouts could appear compact."
                        .format(scale_value * 100.0)
                    )
                    body.setWordWrap(True)
                    body.setObjectName("Body")
                    try:
                        body.setFont(QFont("Inter", 12))
                    except Exception:
                        pass

                    body_layout.addWidget(body)

                    # Buttons
                    btn_row = QHBoxLayout()
                    btn_row.addStretch()
                    learn_btn = QPushButton("Open Display Settings")
                    learn_btn.setObjectName("Secondary")
                    ok_btn = QPushButton("Continue")
                    ok_btn.setObjectName("Primary")
                    btn_row.addWidget(learn_btn)
                    btn_row.addWidget(ok_btn)
                    body_layout.addLayout(btn_row)
                    main.addWidget(body_wrap)

                    def _open_settings():
                        try:
                            import sys as _sys, os as _os
                            if _sys.platform.startswith("win"):
                                _os.startfile("ms-settings:display")  # type: ignore[attr-defined]
                        except Exception:
                            pass

                    learn_btn.clicked.connect(_open_settings)
                    ok_btn.clicked.connect(self.accept)

            dlg = HighScalingDialog(max_scale)
            dlg.exec()
    except Exception:
        pass

def run_application():
    """Run the application with login flow"""
    app = create_application()
    # Show scaling warning before any windows are displayed
    try:
        warn_if_high_scaling()
    except Exception:
        pass
    
    try:
        # Import login window here to avoid circular imports
        from ui.login_window import LoginWindow
        
        # Create and show login window
        login_window = LoginWindow()
        login_window.show()
        
        # Create main window (hidden initially)
        main_window = MainWindow(login_window.auth_service)
        
        # Connect login success signal
        def on_login_successful(auth_result):
            login_window.hide()
            main_window.current_user = auth_result["user"]
            main_window.current_profile = auth_result["profile"]
            
            # Call the MainWindow's on_login_successful method
            main_window.on_login_successful(auth_result["user"])
            
            # Enforce short-lived session token before showing the app
            try:
                auth = login_window.auth_service
                token = auth.get_short_lived_session_token() if auth else None
                print(f"[TokenGuard] first token present={bool(token)}")
                if not token:
                    from PyQt6.QtWidgets import QMessageBox
                    box = QMessageBox()
                    box.setIcon(QMessageBox.Icon.Warning)
                    box.setWindowTitle("Session Error")
                    box.setText("Giriş işlemi tamamlandı ancak oturum belirteci alınamadı. Lütfen tekrar deneyin.")
                    box.setStandardButtons(QMessageBox.StandardButton.Ok)
                    box.exec()
                    app.quit()
                    return

                # Start a guard timer to keep the token fresh; exit if refresh fails
                def _guard_refresh():
                    try:
                        t = auth.get_short_lived_session_token()
                        print(f"[TokenGuard] periodic refresh ok={bool(t)}")
                        if not t:
                            from PyQt6.QtWidgets import QMessageBox
                            box = QMessageBox()
                            box.setIcon(QMessageBox.Icon.Warning)
                            box.setWindowTitle("Session Error")
                            box.setText("Oturum belirteci yenilenemedi. Lütfen tekrar giriş yapın.")
                            box.setStandardButtons(QMessageBox.StandardButton.Ok)
                            box.exec()
                            app.quit()
                    except Exception as _token_err:
                        from PyQt6.QtWidgets import QMessageBox
                        box = QMessageBox()
                        box.setIcon(QMessageBox.Icon.Warning)
                        box.setWindowTitle("Session Error")
                        box.setText("Oturum belirteci yenileme sırasında bir hata oluştu.")
                        box.setDetailedText(str(_token_err))
                        box.setStandardButtons(QMessageBox.StandardButton.Ok)
                        box.exec()
                        app.quit()

                main_window._token_guard_timer = QTimer(main_window)
                main_window._token_guard_timer.setInterval(60 * 1000)  # check every 60s
                main_window._token_guard_timer.timeout.connect(_guard_refresh)
                main_window._token_guard_timer.start()
                
                # Integrity periodic guard (every 5 minutes by default)
                def _integrity_guard():
                    try:
                        from security.bootstrap import ensure_integrity_before_critical
                        # Force check each time (max_age_seconds=0)
                        ensure_integrity_before_critical(max_age_seconds=0)
                    except Exception:
                        try:
                            from PyQt6.QtWidgets import QMessageBox
                            box = QMessageBox()
                            box.setIcon(QMessageBox.Icon.Critical)
                            box.setWindowTitle("Integrity Error")
                            box.setText("Integrity check failed. Application will exit.")
                            box.setStandardButtons(QMessageBox.StandardButton.Ok)
                            box.exec()
                        finally:
                            app.quit()

                try:
                    import os as _os
                    # Default 5; allow env to DECREASE interval but not increase beyond default
                    _default_minutes = 5
                    _env_val = int(_os.getenv("INTEGRITY_PERIODIC_MINUTES", str(_default_minutes)))
                    period_minutes = max(1, min(_default_minutes, _env_val))
                except Exception:
                    period_minutes = 5
                main_window._integrity_timer = QTimer(main_window)
                main_window._integrity_timer.setInterval(max(1, period_minutes) * 60 * 1000)
                main_window._integrity_timer.timeout.connect(_integrity_guard)
                main_window._integrity_timer.start()
            except Exception as _startup_error:
                try:
                    from PyQt6.QtWidgets import QMessageBox
                    box = QMessageBox()
                    box.setIcon(QMessageBox.Icon.Critical)
                    box.setWindowTitle("Startup Error")
                    box.setText("Uygulama başlatılırken bir hata oluştu. Lütfen tekrar deneyin.")
                    box.setDetailedText(str(_startup_error))
                    box.setStandardButtons(QMessageBox.StandardButton.Ok)
                    box.exec()
                except Exception:
                    pass
                app.quit()
                return

            main_window.showMaximized()
            main_window.raise_()
            main_window.activateWindow()
            # After the window is visible, schedule the welcome tour prompt (guard inside prevents double)
            try:
                QTimer.singleShot(300, main_window.maybe_show_welcome_tour)
            except Exception:
                pass
    
        # Connect the signal from the login window
        login_window.login_successful.connect(on_login_successful)

        # Show login window
        login_window.show()
        login_window.raise_()
        login_window.activateWindow()

        return app.exec()
        
    except Exception as e:
        print(f"Error starting application: {e}")
        return 1 