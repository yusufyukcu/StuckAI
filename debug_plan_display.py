#!/usr/bin/env python3
"""
Debug script to test plan display functionality
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton, QTextEdit
from PyQt6.QtCore import Qt

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import Sidebar

class DebugWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Plan Display Debug")
        self.setGeometry(100, 100, 1000, 700)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create layout
        layout = QVBoxLayout(central_widget)
        
        # Create sidebar
        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)
        
        # Create debug info
        debug_layout = QVBoxLayout()
        
        # Debug text area
        self.debug_text = QTextEdit()
        self.debug_text.setMaximumHeight(200)
        debug_layout.addWidget(self.debug_text)
        
        # Test buttons
        test_layout = QVBoxLayout()
        
        login_btn = QPushButton("Test Login (Free)")
        login_btn.clicked.connect(self.test_login_free)
        test_layout.addWidget(login_btn)
        
        login_btn2 = QPushButton("Test Login (Plus)")
        login_btn2.clicked.connect(self.test_login_plus)
        test_layout.addWidget(login_btn2)
        
        login_btn3 = QPushButton("Test Login (Elite)")
        login_btn3.clicked.connect(self.test_login_elite)
        test_layout.addWidget(login_btn3)
        
        logout_btn = QPushButton("Test Logout")
        logout_btn.clicked.connect(self.test_logout)
        test_layout.addWidget(logout_btn)
        
        debug_layout.addLayout(test_layout)
        layout.addLayout(debug_layout)
        
        # Mock main window
        self.mock_main_window = MockMainWindow()
        
        # Override find_main_window method
        def mock_find_main_window():
            return self.mock_main_window
        
        self.sidebar.find_main_window = mock_find_main_window
        
        # Initial debug info
        self.update_debug_info()
        
    def update_debug_info(self):
        """Update debug information"""
        debug_info = f"""
        Sidebar Plan Section Visible: {self.sidebar.plan_section.isVisible()}
        Plan Spacer Visible: {self.sidebar.plan_spacer.isVisible()}
        Plan Label Text: {self.sidebar.plan_info_label.text()}
        Plan Label Visible: {self.sidebar.plan_info_label.isVisible()}
        User Section Visible: {self.sidebar.user_section.isVisible()}
        Mock Profile: {self.mock_main_window.current_profile}
        Mock Plan Type: {self.mock_main_window.mock_plan_type}
        """
        self.debug_text.setText(debug_info)
        
    def test_login_free(self):
        """Test login with Free plan"""
        self.mock_main_window.current_profile = {'username': 'TestUser'}
        self.mock_main_window.mock_plan_type = 'Free'
        self.sidebar.update_user_display()
        self.update_debug_info()
        
    def test_login_plus(self):
        """Test login with Plus plan"""
        self.mock_main_window.current_profile = {'username': 'TestUser'}
        self.mock_main_window.mock_plan_type = 'Plus'
        self.sidebar.update_user_display()
        self.update_debug_info()
        
    def test_login_elite(self):
        """Test login with Elite plan"""
        self.mock_main_window.current_profile = {'username': 'TestUser'}
        self.mock_main_window.mock_plan_type = 'Elite'
        self.sidebar.update_user_display()
        self.update_debug_info()
        
    def test_logout(self):
        """Test logout"""
        self.mock_main_window.current_profile = None
        self.mock_main_window.mock_plan_type = 'Free'
        self.sidebar.update_user_display()
        self.update_debug_info()

class MockMainWindow:
    """Mock main window for testing"""
    def __init__(self):
        self.current_profile = None
        self.mock_plan_type = 'Free'
    
    def get_user_plan_info(self):
        return {'plan_type': self.mock_plan_type}

def main():
    app = QApplication(sys.argv)
    
    # Create debug window
    debug_window = DebugWindow()
    debug_window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 