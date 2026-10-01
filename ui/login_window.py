import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QPushButton, QStackedWidget, QMessageBox,
    QFrame, QSpacerItem, QSizePolicy, QCheckBox, QDialog
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont, QPixmap, QIcon, QPalette, QColor, QPainter, QPen, QBrush, QLinearGradient

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from logic.supabase_auth import SupabaseAuthService
from logic.user_config import UserConfig
from ui.update_required_dialog import UpdateRequiredDialog

class AuthThread(QThread):
    """Background thread for authentication operations"""
    auth_complete = pyqtSignal(dict)
    
    def __init__(self, auth_service: SupabaseAuthService, operation: str, **kwargs):
        super().__init__()
        self.auth_service = auth_service
        self.operation = operation
        self.kwargs = kwargs
    
    def run(self):
        if self.operation == "sign_in":
            result = self.auth_service.sign_in(**self.kwargs)
        elif self.operation == "sign_up":
            result = self.auth_service.sign_up(**self.kwargs)
        elif self.operation == "reset_password":
            result = self.auth_service.reset_password(**self.kwargs)
        else:
            result = {"success": False, "message": "Geçersiz işlem"}
        
        self.auth_complete.emit(result)

class ModernLineEdit(QLineEdit):
    """Modern styled line edit"""
    
    def __init__(self, placeholder: str = "", is_password: bool = False):
        super().__init__()
        self.setPlaceholderText(placeholder)
        if is_password:
            self.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.setup_style()
    
    def setup_style(self):
        self.setStyleSheet("""
            QLineEdit {
                background-color: #F9FAFB;
                border: 2px solid #E5E7EB;
                border-radius: 12px;
                padding: 16px 20px;
                font-size: 16px;
                font-weight: 500;
                color: #1F2937;
                selection-background-color: #3B82F6;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
                background-color: #FFFFFF;
            }
            QLineEdit:hover {
                border-color: #D1D5DB;
            }
        """)

class ModernButton(QPushButton):
    """Modern styled button"""
    
    def __init__(self, text: str, button_type: str = "primary"):
        super().__init__(text)
        self.button_type = button_type
        self.setup_style()
    
    def setup_style(self):
        if self.button_type == "primary":
            self.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #3B82F6, stop:1 #1D4ED8);
                    border: none;
                    border-radius: 12px;
                    padding: 12px 24px;
                    font-size: 16px;
                    font-weight: 600;
                    color: white;
                    min-height: 48px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #2563EB, stop:1 #1E40AF);
                }
                QPushButton:pressed {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 #1D4ED8, stop:1 #1E3A8A);
                }
                QPushButton:disabled {
                    background: #9CA3AF;
                    color: #6B7280;
                }
            """)
        else:  # secondary
            self.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    border: 2px solid #E5E7EB;
                    border-radius: 12px;
                    padding: 12px 24px;
                    font-size: 16px;
                    font-weight: 600;
                    color: #6B7280;
                    min-height: 48px;
                }
                QPushButton:hover {
                    border-color: #3B82F6;
                    color: #3B82F6;
                }
                QPushButton:pressed {
                    background-color: #F3F4F6;
                }
            """)

class ModernCheckBox(QCheckBox):
    """Modern styled checkbox with custom checkmark"""
    
    def __init__(self, text: str = ""):
        super().__init__(text)
        self.setup_style()
    
    def setup_style(self):
        self.setStyleSheet("""
            QCheckBox {
                font-size: 14px;
                color: #6B7280;
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #E5E7EB;
                border-radius: 4px;
                background-color: #F8F9FA;
                background: #F8F9FA;
            }
            QCheckBox::indicator:checked {
                background-color: #3B82F6;
                background: #3B82F6;
                border-color: #3B82F6;
            }
        """)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if self.isChecked():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            # Set up the pen for the checkmark
            pen = QPen(QColor(255, 255, 255))  # White color
            pen.setWidth(2)
            painter.setPen(pen)
            
            # Calculate the position for the checkmark
            rect = self.rect()
            indicator_width = 20
            indicator_height = 20
            spacing = 8
            
            # Position the checkmark in the center of the indicator area
            x = spacing
            y = (rect.height() - indicator_height) // 2
            
            # Calculate the exact center of the indicator
            center_x = x + (indicator_width // 2)  # 8 + 10 = 18 (center of 20px width)
            center_y = y + (indicator_height // 2)  # y + 10 (center of 20px height)
            
            # Draw a modern checkmark design
            # Create a more elegant checkmark with rounded appearance
            checkmark_left_x = center_x - 12  # 12px left from center (even more to the left)
            checkmark_left_y = center_y       # center vertically
            checkmark_mid_x = center_x - 6    # 6px left from center (even more to the left)
            checkmark_mid_y = center_y + 4    # 4px down from center
            checkmark_right_x = center_x + 2  # 2px right from center (even less to the right)
            checkmark_right_y = center_y - 4  # 4px up from center
            
            # Draw the checkmark with thicker lines for better visibility
            pen.setWidth(3)
            painter.setPen(pen)
            
            # Draw the checkmark in two parts for a more natural look
            painter.drawLine(checkmark_left_x, checkmark_left_y, checkmark_mid_x, checkmark_mid_y)
            painter.drawLine(checkmark_mid_x, checkmark_mid_y, checkmark_right_x, checkmark_right_y)

class LoginPage(QWidget):
    """Login page widget"""
    
    auth_complete = pyqtSignal(dict)
    
    def __init__(self, auth_service: SupabaseAuthService):
        super().__init__()
        self.auth_service = auth_service
        self.user_config = UserConfig()
        self.setup_ui()
        self.load_saved_credentials()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedSize(120, 120)
        logo_label.setScaledContents(False)
        logo_path = str(project_root / "ui" / "assets" / "login_logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # HiDPI-aware scaling with primary screen fallback
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
            target_w, target_h = int(120 * dpr), int(120 * dpr)
            scaled_pixmap = pixmap.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            try:
                scaled_pixmap.setDevicePixelRatio(dpr)
            except Exception:
                pass
            logo_label.setPixmap(scaled_pixmap)
        else:
            # Fallback to text if logo not found
            logo_label.setText("🎬 Stuck AI")
            logo_label.setStyleSheet("""
                QLabel {
                    font-size: 32px;
                    font-weight: 700;
                    color: #1F2937;
                }
            """)
        
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("""
            QLabel {
                margin-bottom: 16px;
            }
        """)
        
        # Title
        title_label = QLabel("Stuck AI")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 700;
                color: #1F2937;
                margin-bottom: 8px;
            }
        """)
        
        subtitle_label = QLabel("Sign in to your account")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 500;
                color: #6B7280;
                margin-bottom: 32px;
            }
        """)
        
        layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        
        # Email input
        self.email_input = ModernLineEdit("Your email address")
        layout.addWidget(self.email_input)
        
        # Password input
        self.password_input = ModernLineEdit("Your password", is_password=True)
        layout.addWidget(self.password_input)
        
        # Remember me checkbox
        self.remember_checkbox = ModernCheckBox("Remember me")
        self.remember_checkbox.stateChanged.connect(self.on_remember_me_changed)
        layout.addWidget(self.remember_checkbox)
        
        # Login button
        self.login_button = ModernButton("Sign In", "primary")
        self.login_button.clicked.connect(self.on_login)
        layout.addWidget(self.login_button)
        
        # Forgot password link
        forgot_password_btn = QPushButton("Forgot password?")
        forgot_password_btn.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: #3B82F6;
                font-size: 14px;
                font-weight: 500;
                text-decoration: underline;
            }
            QPushButton:hover {
                color: #2563EB;
            }
        """)
        forgot_password_btn.clicked.connect(self.on_forgot_password)
        layout.addWidget(forgot_password_btn)
        
        # Spacer
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # Sign up link
        signup_layout = QHBoxLayout()
        signup_layout.addStretch()
        
        signup_label = QLabel("Don't have an account?")
        signup_label.setStyleSheet("font-size: 14px; color: #6B7280;")
        
        signup_btn = QPushButton("Sign up")
        signup_btn.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: #3B82F6;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #2563EB;
            }
        """)
        signup_btn.clicked.connect(self.open_signup_in_browser)
        
        signup_layout.addWidget(signup_label)
        signup_layout.addWidget(signup_btn)
        signup_layout.addStretch()
        
        layout.addLayout(signup_layout)
    
    def on_login(self):
        email = self.email_input.text().strip()
        password = self.password_input.text()
        
        if not email or not password:
            QMessageBox.warning(self, "Warning", "Please fill in both email and password fields.")
            return
        
        self.login_button.setEnabled(False)
        self.login_button.setText("Signing in...")
        
        # Start authentication thread
        self.auth_thread = AuthThread(self.auth_service, "sign_in", email=email, password=password)
        self.auth_thread.auth_complete.connect(self.on_auth_complete)
        self.auth_thread.start()
    
    def on_auth_complete(self, result: Dict[str, Any]):
        self.login_button.setEnabled(True)
        self.login_button.setText("Sign In")
        
        if result["success"]:
            print(f"Login successful, remember me checked: {self.remember_checkbox.isChecked()}")
            # Save credentials if remember me is checked
            if self.remember_checkbox.isChecked():
                email = self.email_input.text().strip()
                password = self.password_input.text()
                self.user_config.save_credentials(email, password)
            else:
                # Clear saved credentials if remember me is unchecked
                self.user_config.clear_credentials()
            
            self.auth_complete.emit(result)
        else:
            QMessageBox.warning(self, "Login Error", result["message"])
    
    def on_remember_me_changed(self):
        """Handle remember me checkbox state change"""
        print(f"Remember me checkbox changed to: {self.remember_checkbox.isChecked()}")
        if not self.remember_checkbox.isChecked():
            # If user unchecks remember me, clear saved credentials
            self.user_config.clear_credentials()
    
    def load_saved_credentials(self):
        """Load saved credentials if remember me was enabled"""
        print("Loading saved credentials...")
        # Check if remember me was enabled and credentials exist
        if self.user_config.is_remember_me_enabled():
            print("Remember me is enabled, loading credentials...")
            credentials = self.user_config.load_credentials()
            if credentials and credentials.get("email") and credentials.get("password"):
                self.email_input.setText(credentials["email"])
                self.password_input.setText(credentials["password"])
                self.remember_checkbox.setChecked(True)
                print(f"Loaded credentials for: {credentials['email']}")
            else:
                print("No valid credentials found")
        else:
            print("Remember me is not enabled")
    
    def on_forgot_password(self):
        import webbrowser
        webbrowser.open("https://dashboard.stuckai.net/signin/forgot_password")
    
    def on_reset_complete(self, result: Dict[str, Any]):
        if result["success"]:
            QMessageBox.information(self, "Success", result["message"])
        else:
            QMessageBox.warning(self, "Error", result["message"])
    
    def open_signup_in_browser(self):
        import webbrowser
        webbrowser.open("https://dashboard.stuckai.net/signin/signup")

class SignupPage(QWidget):
    """Signup page widget"""
    
    def __init__(self, auth_service: SupabaseAuthService):
        super().__init__()
        self.auth_service = auth_service
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)
        
        # Title
        # Logo
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setFixedSize(120, 120)
        logo_label.setScaledContents(False)
        logo_path = str(project_root / "ui" / "assets" / "logo.png")
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            # HiDPI-aware scaling with primary screen fallback
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
            target_w, target_h = int(120 * dpr), int(120 * dpr)
            scaled_pixmap = pixmap.scaled(target_w, target_h, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            try:
                scaled_pixmap.setDevicePixelRatio(dpr)
            except Exception:
                pass
            logo_label.setPixmap(scaled_pixmap)
        else:
            # Fallback to text if logo not found
            logo_label.setText("🎬 Stuck AI")
            logo_label.setStyleSheet("""
                QLabel {
                    font-size: 32px;
                    font-weight: 700;
                    color: #1F2937;
                }
            """)
        
        logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo_label.setStyleSheet("""
            QLabel {
                margin-bottom: 16px;
            }
        """)
        
        # Title
        title_label = QLabel("Stuck AI")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setStyleSheet("""
            QLabel {
                font-size: 28px;
                font-weight: 700;
                color: #1F2937;
                margin-bottom: 8px;
            }
        """)
        
        subtitle_label = QLabel("Create a new account")
        subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 500;
                color: #6B7280;
                margin-bottom: 32px;
            }
        """)
        
        layout.addWidget(logo_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        
        # Username input
        self.username_input = ModernLineEdit("Your username")
        layout.addWidget(self.username_input)
        
        # Email input
        self.email_input = ModernLineEdit("Your email address")
        layout.addWidget(self.email_input)
        
        # Password input
        self.password_input = ModernLineEdit("Your password", is_password=True)
        layout.addWidget(self.password_input)
        
        # Confirm password input
        self.confirm_password_input = ModernLineEdit("Confirm your password", is_password=True)
        layout.addWidget(self.confirm_password_input)
        
        # Terms checkbox
        self.terms_checkbox = ModernCheckBox("I accept the terms of service and privacy policy")
        layout.addWidget(self.terms_checkbox)
        
        # Signup button
        self.signup_button = ModernButton("Sign Up", "primary")
        self.signup_button.clicked.connect(self.on_signup)
        layout.addWidget(self.signup_button)
        
        # Spacer
        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # Login link
        login_layout = QHBoxLayout()
        login_layout.addStretch()
        
        login_label = QLabel("Already have an account?")
        login_label.setStyleSheet("font-size: 14px; color: #6B7280;")
        
        login_btn = QPushButton("Sign in")
        login_btn.setStyleSheet("""
            QPushButton {
                background: none;
                border: none;
                color: #3B82F6;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                color: #2563EB;
            }
        """)
        login_btn.clicked.connect(self.on_show_login)
        
        login_layout.addWidget(login_label)
        login_layout.addWidget(login_btn)
        login_layout.addStretch()
        
        layout.addLayout(login_layout)
    
    def on_signup(self):
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        
        if not username or not email or not password or not confirm_password:
            QMessageBox.warning(self, "Warning", "Please fill in all fields.")
            return
        
        if password != confirm_password:
            QMessageBox.warning(self, "Warning", "Passwords do not match.")
            return
        
        if not self.terms_checkbox.isChecked():
            QMessageBox.warning(self, "Warning", "You must accept the terms of service.")
            return
        
        self.signup_button.setEnabled(False)
        self.signup_button.setText("Creating account...")
        
        # Start authentication thread
        self.auth_thread = AuthThread(self.auth_service, "sign_up", 
                                     email=email, password=password, username=username)
        self.auth_thread.auth_complete.connect(self.on_auth_complete)
        self.auth_thread.start()
    
    def on_auth_complete(self, result: Dict[str, Any]):
        self.signup_button.setEnabled(True)
        self.signup_button.setText("Sign Up")
        
        if result["success"]:
            QMessageBox.information(self, "Success", result["message"])
            self.on_show_login()  # Switch back to login page
        else:
            QMessageBox.warning(self, "Registration Error", result["message"])
    
    def on_show_login(self):
        self.parent().setCurrentIndex(0)  # Switch to login page

class LoginWindow(QMainWindow):
    """Main login window"""
    
    login_successful = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        self.auth_service = None
        self.setup_auth_service()
        self.setup_ui()
        self.setup_style()
    
    def setup_auth_service(self):
        """Initialize Supabase auth service"""
        # Check WiFi connection first
        from logic.network_utils import check_wifi_connection
        
        # Quick check for internet connection
        connection_ok = check_wifi_connection()
        
        if not connection_ok:
            # Show WiFi error dialog
            from ui.wifi_error_dialog import WifiErrorDialog
            wifi_dialog = WifiErrorDialog(self)
            
            # No signal connection needed - we handle reinitialization directly
            
            result = wifi_dialog.exec()
            if result == QDialog.DialogCode.Accepted:
                # WiFi is now connected, proceed with auth service setup
                print("🔧 WiFi dialog accepted - reinitializing Supabase service")
                # Reinitialize the auth service since WiFi is now connected
                self.auth_service = None  # Clear the old service
                self.initialize_supabase_service()
            else:
                # User cancelled
                sys.exit(1)
        else:
            # WiFi is connected, proceed directly
            self.initialize_supabase_service()
    

    
    def initialize_supabase_service(self):
        """Initialize Supabase auth service after WiFi check"""
        try:
            self.auth_service = SupabaseAuthService()
        except Exception as e:
            # Check if it's a network-related error
            error_msg = str(e).lower()
            if "getaddrinfo" in error_msg or "connection" in error_msg or "timeout" in error_msg:
                # Network error, show WiFi dialog again
                from ui.wifi_error_dialog import WifiErrorDialog
                wifi_dialog = WifiErrorDialog(self)
                
                # No signal connection needed - we handle reinitialization directly
                
                if wifi_dialog.exec() == QDialog.DialogCode.Accepted:
                    # Try again - reinitialize the entire auth service
                    self.auth_service = None  # Clear the old service
                    self.initialize_supabase_service()
                else:
                    sys.exit(1)
            else:
                # Other configuration error
                QMessageBox.critical(self, "Configuration Error", 
                                   f"Supabase configuration error:\n{str(e)}\n\n"
                                   "Please check your .env file settings.")
                sys.exit(1)
    
    def setup_ui(self):
        self.setWindowTitle("Stuck AI - Login")
        self.setFixedSize(480, 720)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowCloseButtonHint)
        
        # Set window icon
        icon_path = os.path.join(project_root, "ui", "assets", "logo.png")
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            self.setWindowIcon(icon)
        
        # Center window
        self.center_window()
        
        # Create stacked widget for login/signup pages
        self.stacked_widget = QStackedWidget()
        self.setCentralWidget(self.stacked_widget)
        
        # Add login page
        self.login_page = LoginPage(self.auth_service)
        self.stacked_widget.addWidget(self.login_page)
        
        # Add signup page
        self.signup_page = SignupPage(self.auth_service)
        self.stacked_widget.addWidget(self.signup_page)
        
        # Connect signals
        self.login_page.auth_complete.connect(self.on_login_page_auth_complete)

        # Before showing, ensure OpenAI API key can be obtained
        # Prefer the global APIKeyService (env or Supabase), fall back to secure RPC
        try:
            try:
                from logic.api_key_service import get_api_key as _get_api_key_global
                fallback_key = _get_api_key_global('OPENAI_API_KEY')
            except Exception:
                fallback_key = None
            api_key = self.auth_service.get_openai_api_key() if self.auth_service else None
            if not (api_key or fallback_key):
                from PyQt6.QtWidgets import QMessageBox
                box = QMessageBox()
                box.setIcon(QMessageBox.Icon.Warning)
                box.setWindowTitle("API Key Missing")
                box.setText("OpenAI API anahtarı bulunamadı. Devam ediliyor; bazı özellikler çalışmayabilir.")
                box.setStandardButtons(QMessageBox.StandardButton.Ok)
                box.exec()
        except Exception:
            pass
    
    def on_login_page_auth_complete(self, result: Dict[str, Any]):
        """Handle authentication result from login page"""
        self.login_successful.emit(result)
    
    def setup_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 #F8FAFC, stop:1 #E2E8F0);
            }
        """)
    
    def center_window(self):
        """Center the window on screen"""
        screen = QApplication.primaryScreen().geometry()
        x = (screen.width() - self.width()) // 2
        y = (screen.height() - self.height()) // 2
        self.move(x, y)
    
    def closeEvent(self, event):
        """Handle window close event"""
        event.accept()
        sys.exit(0) 