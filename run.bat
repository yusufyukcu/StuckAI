@echo off
echo 🎬 Video Scene AI - Windows Başlatıcı
echo =====================================
echo.

REM Python'ın yüklü olup olmadığını kontrol et
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python bulunamadı! Lütfen Python 3.8+ yükleyin.
    echo    İndirme: https://python.org/downloads/
    pause
    exit /b 1
)

REM Sanal ortam var mı kontrol et
if exist "venv\Scripts\activate.bat" (
    echo 🔄 Sanal ortam etkinleştiriliyor...
    call venv\Scripts\activate.bat
) else (
    echo ⚠️  Sanal ortam bulunamadı. Ana Python kullanılıyor...
)

REM .env dosyası var mı kontrol et
if not exist ".env" (
    echo ⚠️  .env dosyası bulunamadı. Kurulum scripti çalıştırılıyor...
    python install.py
    if errorlevel 1 (
        echo ❌ Kurulum başarısız!
        pause
        exit /b 1
    )
    echo.
    echo 📝 Lütfen .env dosyasını düzenleyip API anahtarlarınızı ekleyin.
    echo    Sonra tekrar çalıştırın.
    pause
    exit /b 0
)

REM Gereklilikleri kontrol et
echo 📦 Paketler kontrol ediliyor...
python -c "import PyQt6, openai, dotenv" 2>nul
if errorlevel 1 (
    echo ⚠️  Bazı paketler eksik. Yükleniyor...
    pip install -r requirements.txt
)

REM Uygulamayı başlat
echo 🚀 Video Scene AI başlatılıyor...
echo.
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
python app.py

REM Hata durumunda bekle
if errorlevel 1 (
    echo.
    echo ❌ Uygulama hata ile sonlandı!
    echo 💡 Sorun giderme için: python install.py
    pause
) 