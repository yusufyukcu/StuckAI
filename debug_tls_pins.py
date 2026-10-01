#!/usr/bin/env python3
"""
TLS Pin Debug Tool
Farklı PC'lerde hangi TLS pin'lerin alındığını toplamak için kullanılır.
Bu bilgiyi kullanarak güvenli pin listesi oluşturabilirsiniz.
"""

import ssl
import socket
import hashlib
import base64
from cryptography import x509
from cryptography.hazmat.primitives import serialization
import json
import sys
from datetime import datetime

def get_tls_pin_info(hostname):
    """Belirtilen hostname için TLS pin bilgilerini al"""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                # Sertifika detayları
                cert_info = ssock.getpeercert()
                der_cert = ssock.getpeercert(binary_form=True)
                
                # Pin hesaplama
                cert = x509.load_der_x509_certificate(der_cert)
                spki = cert.public_key().public_bytes(
                    serialization.Encoding.DER,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                digest = hashlib.sha256(spki).digest()
                pin = base64.b64encode(digest).decode()
                
                return {
                    'hostname': hostname,
                    'pin': pin,
                    'issuer': cert_info.get('issuer', 'Unknown'),
                    'subject': cert_info.get('subject', 'Unknown'),
                    'serial': cert_info.get('serialNumber', 'Unknown'),
                    'not_before': cert_info.get('notBefore', 'Unknown'),
                    'not_after': cert_info.get('notAfter', 'Unknown'),
                    'timestamp': datetime.now().isoformat(),
                    'success': True
                }
    except Exception as e:
        return {
            'hostname': hostname,
            'error': str(e),
            'timestamp': datetime.now().isoformat(),
            'success': False
        }

def main():
    if len(sys.argv) != 2:
        print("Kullanım: python debug_tls_pins.py <hostname>")
        print("Örnek: python debug_tls_pins.py wehrnwyaefwnzwrwxicq.supabase.co")
        sys.exit(1)
    
    hostname = sys.argv[1]
    print(f"TLS Pin bilgileri alınıyor: {hostname}")
    
    result = get_tls_pin_info(hostname)
    
    if result['success']:
        print("\n=== TLS PIN BİLGİLERİ ===")
        print(f"Hostname: {result['hostname']}")
        print(f"TLS Pin: {result['pin']}")
        print(f"Issuer: {result['issuer']}")
        print(f"Subject: {result['subject']}")
        print(f"Serial: {result['serial']}")
        print(f"Not Before: {result['not_before']}")
        print(f"Not After: {result['not_after']}")
        print(f"Timestamp: {result['timestamp']}")
        
        # JSON dosyasına kaydet
        filename = f"tls_pin_debug_{hostname.replace('.', '_')}.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nBilgiler {filename} dosyasına kaydedildi.")
        
    else:
        print(f"Hata: {result['error']}")
        sys.exit(1)

if __name__ == "__main__":
    main()
