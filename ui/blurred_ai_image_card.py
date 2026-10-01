#!/usr/bin/env python3
"""
Blurred AI Image Card Component
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSignal as Signal
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QIcon
import os
import requests
from io import BytesIO

class BlurredAIImageCard(QWidget):
    """Card widget for displaying blurred AI images with Create button"""
    
    create_clicked = pyqtSignal(int)  # Signal emitted when Create button is clicked
    
    def __init__(self, index: int, prompt: str, parent=None):
        super().__init__(parent)
        self.index = index
        self.prompt = prompt
        self.is_created = False
        self.image_url = None
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the card UI"""
        self.setFixedSize(280, 320)
        self.setStyleSheet("""
            QWidget {
                background: #F8F9FA;
                border: 1px solid #E5E7EB;
                border-radius: 25px;
            }
            QWidget:hover {
                border: 2px solid #3B82F6;
                box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            }
        """)
        
        # Main layout
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        self.setLayout(layout)
        
        # Image container
        self.image_container = QWidget()
        self.image_container.setFixedSize(256, 200)
        self.image_container.setStyleSheet("""
            QWidget {
                background: #F3F4F6;
                border-radius: 8px;
                border: 1px solid #E5E7EB;
            }
        """)
        
        # Image label
        self.image_label = QLabel()
        self.image_label.setFixedSize(256, 200)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background: transparent;
                border: none;
                border-radius: 8px;
            }
        """)
        
        # Create blurred placeholder
        self.create_blurred_placeholder()
        
        # Create button
        self.create_button = QPushButton("Create")
        self.create_button.setFixedHeight(36)
        self.create_button.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #3B82F6, stop:1 #2563EB);
                color: white;
                border: none;
                border-radius: 8px;
                font-family: 'Inter', 'Arial', sans-serif;
                font-size: 14px;
                font-weight: 600;
                padding: 8px 16px;
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
                color: #6B7280;
            }
        """)
        self.create_button.clicked.connect(self.on_create_clicked)
        
        # Prompt label
        self.prompt_label = QLabel(self.prompt)
        self.prompt_label.setWordWrap(True)
        self.prompt_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.prompt_label.setStyleSheet("""
            QLabel {
                color: #374151;
                background: transparent;
                font-family: 'Inter', 'Arial', sans-serif;
                font-size: 12px;
                line-height: 1.4;
                padding: 0px;
            }
        """)
        self.prompt_label.setMaximumHeight(60)
        
        # Add widgets to layout
        layout.addWidget(self.image_container)
        layout.addWidget(self.create_button)
        layout.addWidget(self.prompt_label)
        
        # Add image label to container
        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.image_label)
        self.image_container.setLayout(container_layout)
    
    def create_blurred_placeholder(self):
        """Create a blurred placeholder image"""
        # Create a simple gradient placeholder
        pixmap = QPixmap(256, 200)
        pixmap.fill(QColor("#F3F4F6"))
        
        # Add some visual elements to make it look like a blurred image
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw some blurred circles
        for i in range(3):
            color = QColor(139, 92, 246, 30)  # Purple with transparency
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(50 + i * 60, 80 + i * 20, 40 + i * 10, 40 + i * 10)
        
        # Add "AI Image" text
        painter.setPen(QColor("#6B7280"))
        font = QFont("Inter", 14, QFont.Weight.Medium)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "AI Image")
        
        painter.end()
        
        self.image_label.setPixmap(pixmap)
    
    def on_create_clicked(self):
        """Handle Create button click"""
        if not self.is_created:
            self.create_clicked.emit(self.index)
    
    def set_created(self, created: bool, image_url: str = None):
        """Set the card as created and optionally load the real image"""
        self.is_created = created
        
        if created:
            self.create_button.setText("Created")
            self.create_button.setEnabled(False)
            self.create_button.setStyleSheet("""
                QPushButton {
                    background: #10B981;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-family: 'Inter', 'Arial', sans-serif;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 8px 16px;
                }
            """)
            
            if image_url:
                self.load_real_image(image_url)
        else:
            self.create_button.setText("Create")
            self.create_button.setEnabled(True)
            self.create_button.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #3B82F6, stop:1 #2563EB);
                    color: white;
                    border: none;
                    border-radius: 8px;
                    font-family: 'Inter', 'Arial', sans-serif;
                    font-size: 14px;
                    font-weight: 600;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                        stop:0 #2563EB, stop:1 #1D4ED8);
                }
            """)
            
            # Reset to blurred placeholder
            self.create_blurred_placeholder()
    
    def load_real_image(self, image_url: str):
        """Load and display the real AI-generated image"""
        try:
            # Download image
            response = requests.get(image_url)
            if response.status_code == 200:
                # Load image data
                image_data = BytesIO(response.content)
                pixmap = QPixmap()
                pixmap.loadFromData(image_data.getvalue())
                
                # Scale to fit the container while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(
                    256, 200,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                
                self.image_label.setPixmap(scaled_pixmap)
                self.image_url = image_url
                
        except Exception as e:
            print(f"Error loading AI image: {e}")
            # Keep the blurred placeholder if loading fails 