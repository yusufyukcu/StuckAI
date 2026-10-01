#!/usr/bin/env python3
"""
Video Scene AI - Installation and Setup Script
Bu script gerekli bağımlılıkları yükler ve yapılandırma sorunlarını kontrol eder.
"""

import subprocess
import sys
import os
from pathlib import Path

def check_python_version():
    """Python versiyonunu kontrol et"""
    print("🐍 Python versiyonu kontrol ediliyor...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✅ Python {version.major}.{version.minor}.{version.micro} - Uygun")
        return True
    else:
        print(f"❌ Python {version.major}.{version.minor}.{version.micro} - Python 3.8+ gerekli")
        return False 

def install_requirements():
    """Requirements.txt'den paketleri yükle"""
    print("\n📦 Gerekli paketler yükleniyor...")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
        ])
        print("✅ Paketler başarıyla yüklendi")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Paket yükleme hatası: {e}")
        return False

def check_env_file():
    """Environment dosyasını kontrol et"""
    print("\n🔑 .env dosyası kontrol ediliyor...")
    env_path = Path(".env")
    
    if not env_path.exists():
        print("⚠️  .env dosyası bulunamadı. Örnek dosya oluşturuluyor...")
        create_env_template()
        return False
    
    # .env dosyasındaki anahtarları kontrol et
    with open(env_path, 'r') as f:
        content = f.read()
    
    required_keys = ["OPENAI_API_KEY"]
    optional_keys = ["UNSPLASH_ACCESS_KEY", "PEXELS_API_KEY", "PIXABAY_API_KEY"]
    
    for key in required_keys:
        if key not in content or f"{key}=your-" in content:
            print(f"❌ {key} ayarlanmamış")
            return False
        else:
            print(f"✅ {key} ayarlanmış")
    
    for key in optional_keys:
        if key not in content or f"{key}=your-" in content:
            print(f"⚠️  {key} ayarlanmamış (isteğe bağlı)")
        else:
            print(f"✅ {key} ayarlanmış")
    
    return True

def create_env_template():
    """Örnek .env dosyası oluştur"""
    template = """# OpenAI API Key (Required)
OPENAI_API_KEY=your-openai-api-key-here

# Stock API Keys (Optional but recommended)
UNSPLASH_ACCESS_KEY=your-unsplash-access-key
PEXELS_API_KEY=your-pexels-api-key
PIXABAY_API_KEY=your-pixabay-api-key

# Note: Replace the placeholder values above with your actual API keys
# Get OpenAI API key from: https://platform.openai.com/api-keys
# Get Unsplash API key from: https://unsplash.com/developers
# Get Pexels API key from: https://www.pexels.com/api/
# Get Pixabay API key from: https://pixabay.com/api/docs/
"""
    
    with open(".env", "w") as f:
        f.write(template)
    print("📝 .env şablon dosyası oluşturuldu")

def test_imports():
    """Kritik modülleri test et"""
    print("\n🧪 Modül importları test ediliyor...")
    
    modules_to_test = [
        ("PyQt6", "PyQt6.QtWidgets"),
        ("OpenAI", "openai"),
        ("Python-dotenv", "dotenv"),
        ("Requests", "requests"),
        ("Pillow", "PIL"),
        ("Asyncio", "asyncio")
    ]
    
    all_good = True
    for name, module in modules_to_test:
        try:
            __import__(module)
            print(f"✅ {name}")
        except ImportError:
            print(f"❌ {name} - pip install gerekli")
            all_good = False
    
    return all_good

def check_directories():
    """Gerekli dizinleri kontrol et"""
    print("\n📁 Dizin yapısı kontrol ediliyor...")
    
    required_dirs = ["ui", "logic", "data", "ui/assets"]
    
    for directory in required_dirs:
        dir_path = Path(directory)
        if dir_path.exists():
            print(f"✅ {directory}/")
        else:
            print(f"⚠️  {directory}/ bulunamadı, oluşturuluyor...")
            dir_path.mkdir(parents=True, exist_ok=True)
    
    return True

def run_quick_test():
    """Hızlı uygulama testi"""
    print("\n🔍 Hızlı test çalıştırılıyor...")
    
    try:
        # Test GPT-4o connection
        from logic.test_gpt4o import test_openai_import, test_api_key
        
        if not test_openai_import():
            return False
            
        if not test_api_key():
            print("⚠️  OpenAI API anahtarı ayarlanmamış")
            return False
            
        print("✅ Temel testler başarılı")
        return True
        
    except Exception as e:
        print(f"❌ Test hatası: {e}")
        return False

def main():
    """Ana kurulum fonksiyonu"""
    print("🎬 Video Scene AI - Kurulum ve Kontrol Scripti")
    print("=" * 50)
    
    success_count = 0
    total_checks = 6
    
    # Kontroller
    if check_python_version():
        success_count += 1
    
    if install_requirements():
        success_count += 1
    
    if check_env_file():
        success_count += 1
    
    if test_imports():
        success_count += 1
    
    if check_directories():
        success_count += 1
    
    if run_quick_test():
        success_count += 1
    
    # Sonuç
    print("\n" + "=" * 50)
    print(f"📊 Sonuç: {success_count}/{total_checks} kontrol başarılı")
    
    if success_count == total_checks:
        print("✅ Kurulum tamamlandı! Uygulamayı şu komutla başlatabilirsiniz:")
        print("   python app.py")
    else:
        print("⚠️  Bazı sorunlar var. Yukarıdaki hataları düzeltin.")
        print("\n💡 Yardım:")
        print("   1. .env dosyasında API anahtarlarınızı ayarlayın")
        print("   2. pip install -r requirements.txt komutunu çalıştırın")
        print("   3. Python 3.8+ kullandığınızdan emin olun")

if __name__ == "__main__":
    main() 