import os
from PyQt6.QtGui import QFontDatabase, QFont
from PyQt6.QtCore import QDir

class FontManager:
    """Font yönetimi için sınıf"""
    
    def __init__(self):
        self.fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fonts")
        self.loaded_fonts = {}
        self.load_fonts()
    
    def load_fonts(self):
        """Fonts klasöründeki tüm font dosyalarını yükle"""
        if not os.path.exists(self.fonts_dir):
            print(f"Fonts klasörü bulunamadı: {self.fonts_dir}")
            return
        
        # Font dosyası uzantıları
        font_extensions = ['.ttf', '.otf', '.woff', '.woff2']
        
        for filename in os.listdir(self.fonts_dir):
            if any(filename.lower().endswith(ext) for ext in font_extensions):
                font_path = os.path.join(self.fonts_dir, filename)
                self.load_font_file(font_path)
    
    def load_font_file(self, font_path: str):
        """Tek bir font dosyasını yükle"""
        try:
            font_id = QFontDatabase.addApplicationFont(font_path)
            if font_id != -1:
                font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
                self.loaded_fonts[font_family] = font_path
                print(f"✅ Font yüklendi: {font_family} ({os.path.basename(font_path)})")
            else:
                print(f"❌ Font yüklenemedi: {os.path.basename(font_path)}")
        except Exception as e:
            print(f"❌ Font yükleme hatası: {os.path.basename(font_path)} - {e}")
    
    def get_font(self, family: str, size: int = 12, weight: int = QFont.Weight.Normal) -> QFont:
        """Belirtilen font ailesini döndür"""
        font = QFont(family, size, weight)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        return font
    
    def get_available_fonts(self) -> list:
        """Yüklenen fontların listesini döndür"""
        return list(self.loaded_fonts.keys())
    
    def is_font_loaded(self, family: str) -> bool:
        """Font yüklenip yüklenmediğini kontrol et"""
        return family in self.loaded_fonts
    
    def reload_fonts(self):
        """Fontları yeniden yükle"""
        self.loaded_fonts.clear()
        self.load_fonts()

# Global font manager instance
font_manager = FontManager() 