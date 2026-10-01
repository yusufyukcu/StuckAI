"""
Utility functions for Video Scene Analyzer
"""
import json
import os
import platform
import sys
import hashlib
import uuid
import requests
from typing import Dict, Any, Optional, List
import socket
import subprocess
from .windows_subprocess import run_hidden
from pathlib import Path
import time


def read_input_file(file_path: str = "data/input.txt") -> str:
    """
    Input text dosyasını okur
    
    Args:
        file_path: Okunacak dosya yolu
        
    Returns:
        Dosya içeriği (string)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"⚠️  Dosya bulunamadı: {file_path}")
        return ""
    except Exception as e:
        print(f"⚠️  Dosya okuma hatası: {e}")
        return ""


def write_json_output(data, filename: str = "data/scene_output.json") -> bool:
    """Write data to JSON file - accepts both dict and list"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"⚠️  JSON yazma hatası: {e}")
        return False


def read_json_output(file_path: str = "data/scene_output.json") -> List[Dict[str, Any]]:
    """
    JSON çıktı dosyasını okur
    
    Args:
        file_path: Okunacak dosya yolu
        
    Returns:
        JSON verisi (liste)
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return json.load(file)
    except FileNotFoundError:
        print(f"⚠️  JSON dosyası bulunamadı: {file_path}")
        return []
    except json.JSONDecodeError:
        print(f"⚠️  JSON formatı hatalı: {file_path}")
        return []
    except Exception as e:
        print(f"⚠️  JSON okuma hatası: {e}")
        return []


def get_project_root() -> Path:
    """
    Proje kök dizinini döndürür
    
    Returns:
        Proje kök dizini (Path)
    """
    # Try to get the directory where the executable is located
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return Path(sys.executable).parent
    else:
        # Running as script
        return Path(__file__).parent.parent


def get_asset_path(asset_name: str) -> str:
    """
    Asset dosya yolunu döndürür
    
    Args:
        asset_name: Asset dosya adı
        
    Returns:
        Asset dosya yolu
    """
    return str(get_project_root() / "ui" / "assets" / asset_name)


def get_default_download_path() -> str:
    """Return a sensible per-user default download directory.

    - Windows/macOS: ~/Downloads
    - Linux: $XDG_DOWNLOAD_DIR if available, else ~/Downloads
    Falls back to a project-local "downloads" if the above cannot be resolved.
    The directory is created if it does not exist.
    """
    try:
        home = Path.home()
        candidate: Path | None = None

        if sys.platform.startswith("win") or sys.platform == "darwin":
            candidate = home / "Downloads"
        else:
            # XDG spec
            xdg_config = home / ".config" / "user-dirs.dirs"
            download_dir: Path | None = None
            try:
                if xdg_config.exists():
                    content = xdg_config.read_text(encoding="utf-8", errors="ignore")
                    import re as _re
                    m = _re.search(r"XDG_DOWNLOAD_DIR=\"([^\"]+)\"", content)
                    if m:
                        val = m.group(1)
                        val = val.replace("$HOME", str(home))
                        download_dir = Path(val)
            except Exception:
                download_dir = None
            candidate = download_dir or (home / "Downloads")

        if not candidate:
            candidate = Path(os.getcwd()) / "downloads"
        candidate.mkdir(parents=True, exist_ok=True)
        return str(candidate)
    except Exception:
        fallback = Path(os.getcwd()) / "downloads"
        try:
            fallback.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
        return str(fallback)


def ensure_directory_exists(directory_path: str) -> bool:
    """
    Dizinin var olduğundan emin olur, yoksa oluşturur
    
    Args:
        directory_path: Dizin yolu
        
    Returns:
        Başarılı olup olmadığı (bool)
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception as e:
        print(f"⚠️  Dizin oluşturma hatası: {e}")
        return False


def validate_scene_data(scene_data: Dict[str, Any]) -> bool:
    """
    Sahne verisinin geçerliliğini kontrol eder
    
    Args:
        scene_data: Kontrol edilecek sahne verisi
        
    Returns:
        Geçerli olup olmadığı (bool)
    """
    required_fields = ['scene_id', 'scene_title', 'summary', 'keywords', 'visual_prompt', 'tone']
    
    for field in required_fields:
        if field not in scene_data:
            print(f"⚠️  Eksik alan: {field}")
            return False
    
    return True


def format_scene_for_export(scene_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sahne verisini export için formatlar
    
    Args:
        scene_data: Formatlanacak sahne verisi
        
    Returns:
        Formatlanmış veri
    """
    formatted = {
        'scene_id': scene_data.get('scene_id', 0),
        'scene_title': scene_data.get('scene_title', ''),
        'summary': scene_data.get('summary', ''),
        'keywords': scene_data.get('keywords', []),
        'visual_prompt': scene_data.get('visual_prompt', ''),
        'tone': scene_data.get('tone', ''),
        'original_text': scene_data.get('original_text', ''),
        'stock_images': scene_data.get('stock_images', []),
        'stock_videos': scene_data.get('stock_videos', []),
        'ai_images': scene_data.get('ai_images', [])
    }
    
    return formatted


def get_scene_statistics(scenes_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Sahne verilerinden istatistikler çıkarır
    
    Args:
        scenes_data: Sahne verileri listesi
        
    Returns:
        İstatistikler
    """
    if not scenes_data:
        return {}
    
    stats = {
        'total_scenes': len(scenes_data),
        'total_chapters': len(set(scene.get('main_scene_id', 1) for scene in scenes_data)),
        'total_stock_images': sum(len(scene.get('stock_images', [])) for scene in scenes_data),
        'total_stock_videos': sum(len(scene.get('stock_videos', [])) for scene in scenes_data),
        'total_ai_images': sum(len(scene.get('ai_images', [])) for scene in scenes_data),
        'tone_distribution': {}
    }
    
    # Tone dağılımı
    for scene in scenes_data:
        tone = scene.get('tone', 'Unknown')
        stats['tone_distribution'][tone] = stats['tone_distribution'].get(tone, 0) + 1
    
    return stats


def create_backup(file_path: str) -> bool:
    """
    Dosyanın yedeğini oluşturur
    
    Args:
        file_path: Yedeklenecek dosya yolu
        
    Returns:
        Başarılı olup olmadığı (bool)
    """
    try:
        if os.path.exists(file_path):
            backup_path = f"{file_path}.backup"
            import shutil
            shutil.copy2(file_path, backup_path)
            return True
        return False
    except Exception as e:
        print(f"⚠️  Yedekleme hatası: {e}")
        return False


def clean_temp_files(temp_dir: str = "temp") -> bool:
    """
    Geçici dosyaları temizler
    
    Args:
        temp_dir: Temizlenecek geçici dosya dizini
        
    Returns:
        Başarılı olup olmadığı (bool)
    """
    try:
        if os.path.exists(temp_dir):
            import shutil
            shutil.rmtree(temp_dir)
        return True
    except Exception as e:
        print(f"⚠️  Geçici dosya temizleme hatası: {e}")
        return False


def generate_device_fingerprint() -> str:
    """Generate a stable device fingerprint using hardware/OS identifiers."""
    try:
        system_info = {
            'platform': platform.system(),
            'platform_version': platform.version(),
            'machine': platform.machine(),
            'processor': platform.processor(),
            'node': platform.node(),
            'python_version': platform.python_version(),
            'architecture': platform.architecture()[0]
        }

        try:
            mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> elements) & 0xff)
                                  for elements in range(0, 2*6, 2)][::-1])
            system_info['mac_address'] = mac_address
        except Exception:
            system_info['mac_address'] = 'unknown'

        try:
            system_info['hostname'] = socket.gethostname()
        except Exception:
            system_info['hostname'] = 'unknown'

        # Windows MachineGuid (stable across runs)
        try:
            if platform.system().lower() == 'windows':
                import winreg  # type: ignore
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\\Microsoft\\Cryptography")
                machine_guid, _ = winreg.QueryValueEx(key, "MachineGuid")
                winreg.CloseKey(key)
                if machine_guid:
                    system_info['machine_guid'] = str(machine_guid)
        except Exception:
            pass

        # Disk/volume serial (best-effort, platform specific)
        try:
            if platform.system().lower() == 'windows':
                # Use VOL command for system drive
                result = run_hidden(["cmd", "/C", "vol C:"], timeout=2, capture_output=True)
                out = (result.stdout or "") + (result.stderr or "")
                for token in out.replace("-", " ").split():
                    if len(token) >= 4 and token.strip().isalnum():
                        system_info['volume_serial'] = token.strip()
                        break
        except Exception:
            pass

        # Create a hash of the collected identifiers (exclude cwd/username for stability)
        fingerprint_data = json.dumps(system_info, sort_keys=True)
        device_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()
        return device_hash

    except Exception as e:
        print(f"Error generating device fingerprint: {e}")
        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()

def get_public_ip_address() -> str:
    """Get the public IP address of the current device"""
    try:
        # Try multiple IP services for reliability
        ip_services = [
            'https://api.ipify.org',
            'https://httpbin.org/ip',
            'https://ipinfo.io/ip',
            'https://icanhazip.com'
        ]
        
        for service in ip_services:
            try:
                response = requests.get(service, timeout=5)
                if response.status_code == 200:
                    ip = response.text.strip()
                    # Validate IP format
                    if is_valid_ip(ip):
                        return ip
            except:
                continue
        
        # Fallback to local IP if public IP cannot be determined
        return get_local_ip_address()
        
    except Exception as e:
        print(f"Error getting public IP address: {e}")
        return get_local_ip_address()

def get_local_ip_address() -> str:
    """Get the local IP address of the current device"""
    try:
        # Get local IP address
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        print(f"Error getting local IP address: {e}")
        return "127.0.0.1"

def is_valid_ip(ip: str) -> bool:
    """Check if the given string is a valid IP address"""
    try:
        socket.inet_aton(ip)
        return True
    except socket.error:
        return False

def get_user_agent() -> str:
    """Get a user agent string for the current system"""
    try:
        system = platform.system()
        if system == "Windows":
            return "VideoSceneAI/1.0 (Windows)"
        elif system == "Darwin":
            return "VideoSceneAI/1.0 (macOS)"
        elif system == "Linux":
            return "VideoSceneAI/1.0 (Linux)"
        else:
            return "VideoSceneAI/1.0 (Unknown)"
    except:
        return "VideoSceneAI/1.0 (Unknown)"


def generate_nonce() -> str:
    """Generate a UUIDv4 nonce for anti-replay."""
    return str(uuid.uuid4())


def current_timestamp_ms() -> int:
    """Return current UTC timestamp in milliseconds."""
    return int(time.time() * 1000)

# Test fonksiyonu
def test_utils():
    """Utils fonksiyonlarını test eder"""
    print("🧪 Utils fonksiyonları test ediliyor...")
    
    # Test verisi
    test_data = [
        {
            'scene_id': 1,
            'scene_title': 'Test Scene',
            'summary': 'Test summary',
            'keywords': ['test', 'scene'],
            'visual_prompt': 'Test visual prompt',
            'tone': 'Test'
        }
    ]
    
    # JSON yazma/okuma testi
    if write_json_output(test_data, "test_output.json"):
        print("✅ JSON yazma başarılı")
        
        read_data = read_json_output("test_output.json")
        if read_data:
            print("✅ JSON okuma başarılı")
        else:
            print("❌ JSON okuma başarısız")
            
        # Test dosyasını sil
        try:
            os.remove("test_output.json")
        except:
            pass
    else:
        print("❌ JSON yazma başarısız")
    
    # İstatistik testi
    stats = get_scene_statistics(test_data)
    print(f"📊 Test istatistikleri: {stats}")
    
    print("🎉 Utils testi tamamlandı!")


if __name__ == "__main__":
    test_utils() 