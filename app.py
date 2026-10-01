#!/usr/bin/env python3
"""
Video Scene AI - Main Application
PyQt6 tabanlı modern video sahne analiz uygulaması
"""

import sys
import os
from pathlib import Path

# Proje kök dizinini Python path'ine ekle
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# UI modülünü import et
from ui.main_window import run_application
from logic.build_guard import enforce_or_exit
from security.bootstrap import run_integrity_check_or_exit
from logic.redaction import install_print_redaction
from logic.maintenance_guard import enforce_maintenance_window_or_exit
from logic.windows_subprocess import install_global_no_console_patch


def main():
    """Ana uygulama fonksiyonu"""
    print("🎬 Stuck AI (PyQt6) başlatılıyor...")
    
    # Install subprocess patch after core modules are loaded
    try:
        install_global_no_console_patch()
    except Exception as e:
        print(f"⚠️  Could not install subprocess patch: {e}")
    
    # Redact sensitive provider names/URLs from prints
    try:
        install_print_redaction()
    except Exception:
        pass
    
    # Gerekli klasörlerin varlığını kontrol et
    required_dirs = ["ui", "logic", "data", "ui/assets"]
    for directory in required_dirs:
        dir_path = project_root / directory
        if not dir_path.exists():
            print(f"⚠️  Klasör bulunamadı: {directory}")
            print(f"   Klasör oluşturuluyor: {dir_path}")
            dir_path.mkdir(parents=True, exist_ok=True)
    
    try:
        print("🔍 DEBUG: Starting checks...")
        
        # TLS Pin Debug (doğru SPKI hesaplama)
        print("🔍 DEBUG: Checking TLS pin...")
        try:
            import ssl, socket, hashlib, base64
            from cryptography import x509
            from cryptography.hazmat.primitives import serialization
            
            context = ssl.create_default_context()
            with socket.create_connection(('wehrnwyaefwnzwrwxicq.supabase.co', 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname='wehrnwyaefwnzwrwxicq.supabase.co') as ssock:
                    der_cert = ssock.getpeercert(binary_form=True)
                    cert = x509.load_der_x509_certificate(der_cert)
                    spki = cert.public_key().public_bytes(
                        serialization.Encoding.DER,
                        serialization.PublicFormat.SubjectPublicKeyInfo,
                    )
                    digest = hashlib.sha256(spki).digest()
                    pin = base64.b64encode(digest).decode()
                    print(f"🔍 DEBUG: TLS Pin (SPKI): {pin}")
        except Exception as e:
            print(f"⚠️ DEBUG: TLS Pin check failed: {e}")
        
        # Integrity check (fail-closed)
        print("🔍 DEBUG: Running integrity check...")
        run_integrity_check_or_exit()
        print("✅ DEBUG: Integrity check passed")
        
        # Remote maintenance kill-switch
        print("🔍 DEBUG: Running maintenance check...")
        enforce_maintenance_window_or_exit()
        print("✅ DEBUG: Maintenance check passed")
        
        # Build allowlist + kill-switch check (fail closed)
        print("🔍 DEBUG: Running build guard check...")
        enforce_or_exit()
        print("✅ DEBUG: Build guard check passed")
        
        print("🔍 DEBUG: All checks passed, starting application...")
        # PyQt6 uygulamasını başlat
        exit_code = run_application()
        sys.exit(exit_code)
    except ImportError as e:
        print(f"❌ PyQt6 yüklenmemiş: {e}")
        print("   Lütfen şu komutu çalıştırın: pip install PyQt6")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Uygulama hatası: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 