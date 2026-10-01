# 🎬 StuckAI

**StuckAI**, video içerik üreticileri için geliştirilmiş, yapay zekâ destekli bir **video senaryo / sahne analiz** masaüstü uygulamasıdır. Bir metni (senaryo, seslendirme metni, makale) sahnelere ayırır, her sahne için anahtar kelime, ton ve görsel prompt üretir; ardından stok görsel/video kaynaklarından uygun medyayı bulur ve gerekirse **AI ile görsel üretir**.

Uygulama yalnızca bir AI aracı değil, aynı zamanda **çok katmanlı bir istemci güvenliği (client-side hardening)** çalışmasıdır: kod bütünlüğü doğrulama, TLS sertifika sabitleme (pinning), tekrar saldırısına (replay) karşı korumalı RPC çağrıları, uzaktan kill-switch, Cython ile derlenmiş kritik modüller ve daha fazlası.

> Platform: **Windows 10/11 (x64)** · Dil: **Python 3.10** · Arayüz: **PyQt6** · Backend: **Supabase**

---

## 📑 İçindekiler

- [Özellikler](#-özellikler)
- [Mimari](#-mimari)
- [Siber Güvenlik Mimarisi](#-siber-güvenlik-mimarisi)
- [Proje Yapısı](#-proje-yapısı)
- [Kurulum](#-kurulum)
- [Derleme ve Dağıtım](#-derleme-ve-dağıtım)
- [Teknolojiler](#-teknolojiler)

---

## ✨ Özellikler

### 🧠 Akıllı Sahne Analizi
- Girilen metni otomatik olarak **ana bölümler ve alt sahneler** halinde böler.
- Her sahne için **başlık, özet, anahtar kelimeler, ton (duygu)** ve **görsel prompt** üretir.
- "Smart scene analysis" ile sahneye en uygun medya tipini (görsel / video) belirler.
- Karakter limiti, plan tipi ve kredi kontrolü sunucu tarafında doğrulanır.

### 🖼️ Medya Bulma ve Üretme
- Stok görsel ve video servislerinden sahneye uygun içerikleri listeler.
- **AI görsel üretimi** (farklı en-boy oranlarıyla: 1:1, 16:9, 9:16 …).
- Video önizleme, oynatma ve kalite seçimi (FFmpeg tabanlı).
- Arka planda **lazy loading** ve thumbnail üretimi ile akıcı arayüz.

### ⬇️ İndirme Yöneticisi
- Seçilen medyaları toplu ya da tek tek indirme.
- İndirme geçmişi, thumbnail önizlemeleri ve dosya adı temizleme.

### 🕘 Geçmiş ve Hesap
- Geçmiş analizleri kaydetme ve tekrar açma.
- Supabase ile **kayıt / giriş**, profil, plan (Free / Premium) ve kredi sistemi.
- Cihaz kısıtlaması (bir hesabın izinsiz çoklu cihazda kullanımına karşı).

### 🎨 Modern Arayüz
- PyQt6 ile tamamen özel tasarlanmış, animasyonlu modern UI.
- Sürükle-bırak dosya yükleme, animasyonlu istatistik kartları, sidebar navigasyonu.
- Bakım, güncelleme zorunluluğu ve internet bağlantısı hata diyalogları.

---

## 🏗️ Mimari

```
┌────────────────────────────────────────────────────────────┐
│                     StuckAI (PyQt6 UI)                     │
│  ui/main_window.py · login_window.py · dialoglar · thread'ler│
└───────────────┬────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────┐
│           logic/  (iş mantığı — Cython ile derlenmiş)      │
│  scene_analysis · smart_scene_analysis · video_analysis    │
│  stock_api_service · leonardo_ai_service · cost_tracking   │
│  supabase_auth · session_token_service · api_key_service   │
└───────────────┬────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────┐
│     security/  (bütünlük doğrulama — Cython ile derlenmiş) │
│  bootstrap · integrity_manifest · integrity_hash           │
└───────────────┬────────────────────────────────────────────┘
                │  HTTPS (SPKI pinned)
┌───────────────▼────────────────────────────────────────────┐
│  Supabase: Auth · PostgREST · RLS · SECURITY DEFINER RPC'ler│
│  (kredi düşümü, oturum token'ı, bakım modu, build allowlist)│
└────────────────────────────────────────────────────────────┘
```

---

## 🔐 Siber Güvenlik Mimarisi

StuckAI, istemci tarafında çalışan ve kullanıcının bilgisayarına dağıtılan bir uygulama olduğu için **"istemciye güvenme" (never trust the client)** prensibiyle tasarlandı. Güvenlik, birbirini tamamlayan katmanlar halinde uygulanır (**defense-in-depth**) ve hata durumunda uygulama **fail-closed** davranır — yani bir kontrol yapılamıyorsa uygulama *açılmaz*.

### Başlangıç zinciri (`app.py`)

Uygulama arayüzü açılmadan önce aşağıdaki kontroller sırayla çalışır; herhangi biri başarısız olursa süreç sonlandırılır:

```
1. Subprocess yaması        → konsol pencerelerini gizle
2. Log redaksiyonu          → hassas URL/sağlayıcı adlarını maskele
3. Bütünlük kontrolü        → imzalı manifest + SHA-256 doğrulama   (fail-closed)
4. Bakım kill-switch'i      → uzaktan bakım modu kontrolü           (fail-closed)
5. Build guard              → TLS pin + build allowlist             (fail-closed)
6. UI başlatılır
```

### 1. 🧾 Kod Bütünlüğü Doğrulama (Code Integrity / Anti-Tamper)

`security/bootstrap`, `security/integrity_manifest`, `security/integrity_hash`, `tools/make_integrity_manifest.py`

- Dağıtılan her kritik dosyanın (`.exe`, `.pyd`, `.dll`, `app.py` …) **SHA-256 özeti** bir manifest dosyasında (`files.json`) tutulur.
- Manifest, geliştiricinin **özel anahtarıyla dijital olarak imzalanır** (RSA PKCS#1 v1.5 + SHA-256 veya ECDSA P-256 + SHA-256).
- İmza, `signature` alanı hariç tutulmuş **kanonik JSON** (`sort_keys=True`, `separators=(",", ":")`) üzerinden hesaplanır; böylece alan sırası değişse bile imza deterministik kalır.
- Her imza bir **key id (`kid`)** taşır → anahtar rotasyonu (key rotation) desteklenir; istemci yalnızca `INTEGRITY_PUBKEYS_JSON` içindeki güvenilen açık anahtarları kabul eder.
- Manifest uzaktan (`INTEGRITY_MANIFEST_URL`) indirilir, yerelde önbelleklenir ve önbelleğin yaşı sınırlandırılır.
- Dosya özetleri **paralel** hesaplanır (`INTEGRITY_MAX_PARALLEL_HASH`), sonuçlar önbelleklenir.
- **Periyodik yeniden doğrulama:** Kritik RPC çağrılarından önce `ensure_integrity_before_critical(max_age_seconds=300)` çalışır; son kontrol 5 dakikadan eskiyse bütünlük tekrar doğrulanır (runtime tamper'a karşı).
- **Devre dışı bırakılamaz:** `DISABLE_INTEGRITY` ortam değişkeni ve `disable_integrity` dosyası gibi bypass yolları bilinçli olarak yok sayılır; production build'lerde manifest sistemi kalıcı olarak açıktır.

### 2. 📌 TLS Sertifika Sabitleme (SPKI Pinning)

`logic/build_guard`, `debug_tls_pins.py`

- Backend'e bağlanırken sunucunun yaprak sertifikasının **SubjectPublicKeyInfo (SPKI)** alanının SHA-256 özeti hesaplanır ve uygulamaya gömülü beklenen pin ile karşılaştırılır.
- Sertifikanın tamamı yerine **açık anahtar** sabitlendiği için sertifika yenilemelerinde (aynı anahtar korunduğu sürece) pin bozulmaz.
- Pin uyuşmazlığında `SECURITY ALERT: TLS Pin mismatch` ile uygulama başlatılmaz → **MITM (Man-in-the-Middle)**, sahte kök sertifika ve proxy ile trafik dinleme (Burp/Fiddler vb.) saldırıları engellenir.
- `debug_tls_pins.py` aracı, sertifika değişimlerinde yeni pin değerini doğru hesaplamak için kullanılır.

### 3. 🚦 Build Allowlist ve Uzaktan Kill-Switch

`logic/build_guard`, `logic/maintenance_guard`

- Her derlemenin benzersiz bir `BUILD_ID`'si vardır. Uygulama açılışta sunucudaki **izinli build listesini (allowlist)** kontrol eder; listede olmayan (eski, sızdırılmış veya kurcalanmış) sürümler çalışmaz ve kullanıcıya **güncelleme zorunlu** diyaloğu gösterilir.
- **Bakım modu kill-switch'i:** Supabase REST üzerinden okunan bir bayrak ile tüm istemciler anında bakım moduna alınabilir (`MaintenanceDialog`). Bir güvenlik açığı tespit edildiğinde tüm kullanıcıları uzaktan durdurma imkânı sağlar.
- İnternet yoksa veya kontrol yapılamazsa uygulama **fail-closed** davranır.

### 4. 🔁 Replay Korumalı Güvenli RPC (Anti-Replay)

`logic/supabase_auth.py` → `secure_rpc()`, `logic/session_token_service`

Kredi düşümü, AI görsel üretimi gibi **kritik işlemler** doğrudan tablo erişimiyle değil, sunucu tarafında doğrulanan RPC fonksiyonları üzerinden yapılır. Her çağrıya otomatik olarak şunlar eklenir:

| Parametre   | Amaç |
|-------------|------|
| `p_token`   | **Kısa ömürlü (≤ 15 dk) oturum token'ı** — sunucudan `issue_session_token` RPC'si ile alınır, bellekte tutulur, süresi dolunca şeffaf şekilde yenilenir |
| `p_build_id`| İsteği yapan build'in allowlist'te olduğunun sunucu tarafında doğrulanması |
| `p_fp`      | Cihaz parmak izi — token'ın başka bir cihazda kullanılmasını engeller |
| `p_nonce`   | Tek kullanımlık rastgele değer — **aynı isteğin tekrar gönderilmesini (replay)** engeller |
| `p_ts`      | Milisaniye zaman damgası — eski/geciktirilmiş isteklerin reddedilmesi |

- PostgREST çağrıları her zaman kullanıcının **JWT**'si ile yapılır; Row Level Security (RLS) politikaları kullanıcının yalnızca kendi verisine erişmesini sağlar.
- Token alınamazsa veya JWT yoksa çağrı yapılmaz (**fail-closed**: `auth_required`, `auth_jwt_missing`).
- Kritik RPC'den önce bütünlük yeniden doğrulanır; başarısızsa `integrity_failed` döner.
- Kredi/limit hesaplaması istemcide değil **sunucuda** yapılır; istemci tarafı değerleri değiştirmek bir avantaj sağlamaz.

### 5. 🖥️ Cihaz Parmak İzi (Device Fingerprinting)

`logic/utils.py` → `generate_device_fingerprint()`

- Windows `MachineGuid`, disk birim seri numarası, MAC adresi, işlemci/mimari ve OS bilgileri birleştirilerek **SHA-256** ile kararlı bir cihaz kimliği üretilir.
- Ham donanım bilgisi sunucuya gönderilmez; yalnızca hash gönderilir (gizlilik).
- Hesap paylaşımı ve izinsiz çoklu cihaz kullanımına karşı **cihaz kısıtlaması** uygulanır.

### 6. 🧱 Tersine Mühendisliğe Karşı Sertleştirme (Anti-Reverse Engineering)

`tools/build_logic_cython.py`

- `logic/` ve `security/` paketlerindeki tüm iş mantığı **Cython ile native C eklentilerine (`.pyd`)** derlenir; dağıtımda `.py` kaynak kodu bulunmaz.
- Agresif optimizasyon (`/O2 /Ob2`, `-O3 -fvisibility=hidden`), `embedsignature=False`, `emit_code_comments=False`, `binding=False` ile fonksiyon imzaları ve yorumlar binary'den çıkarılır.
- Derleme sonrası üretilen `.c` dosyaları silinir, sembol tabloları `strip` ile temizlenir.
- Linker'da `/OPT:REF /OPT:ICF` ile kullanılmayan kod atılır.
- Derlenmiş modüller ayrıca bütünlük manifestine dahil olduğu için **binary patch'leme** tespit edilir.

### 7. 🙈 Hassas Bilgi Redaksiyonu (Log Redaction)

`logic/redaction`

- Global `print` fonksiyonu sarmalanır; konsol/log çıktısındaki **API sağlayıcı adları ve URL'ler otomatik olarak maskelenir**.
- Böylece log dosyalarından ya da ekran görüntülerinden altyapı bilgisi sızdırılamaz.

### 8. 🔑 Gizli Anahtar Yönetimi (Secret Management)

`logic/api_key_service`, `.env`

- Üçüncü parti API anahtarları (AI, stok medya servisleri) **istemciye gömülmez**; yetkili kullanıcı oturumuyla sunucudan alınır.
- İstemcide yalnızca **public** Supabase anon key bulunur; gerçek yetkilendirme RLS ve RPC kontrolleriyle sunucuda yapılır.
- `.env`, imzalama anahtarı (`private.pem`) ve diğer gizli dosyalar `.gitignore` ile repodan hariç tutulur.

### 9. 🪟 Windows Süreç Sertleştirme

`logic/windows_subprocess.py`

- `subprocess` çağrıları global olarak yamalanır (`CREATE_NO_WINDOW`), FFmpeg vb. alt süreçlerin konsol penceresi açması ve kullanıcıya iç komutları göstermesi engellenir.
- Kurulum (Inno Setup) sırasında yalnızca gerekli klasörlere (`data`, `downloads`, `history`) kullanıcı yazma izni verilir; uygulama dosyaları `Program Files` altında korunur.

### Tehdit Modeli Özeti

| Tehdit | Önlem |
|---|---|
| Uygulama dosyalarının değiştirilmesi / crack | İmzalı SHA-256 manifest, periyodik yeniden doğrulama, fail-closed |
| MITM / trafik dinleme / proxy | TLS SPKI pinning |
| Eski veya sızdırılmış build kullanımı | Build allowlist + zorunlu güncelleme |
| Kritik açık tespiti | Uzaktan bakım kill-switch'i |
| İstek tekrarlama (replay) ile kredi suistimali | Nonce + timestamp + kısa ömürlü token |
| Token çalınması | Cihaz parmak izine bağlı token, ≤ 15 dk ömür |
| Kaynak kod / iş mantığı sızdırma | Cython native derleme + strip |
| İstemci tarafı kredi manipülasyonu | Sunucu tarafı RPC + RLS |
| Log üzerinden bilgi sızıntısı | Otomatik redaksiyon |
| Hesap paylaşımı | Cihaz kısıtlaması |

---

## 📁 Proje Yapısı

```
StuckAI/
├── app.py                      # Giriş noktası + güvenlik başlangıç zinciri
├── StuckAI.spec                # PyInstaller yapılandırması
├── files.json                  # İmzalı bütünlük manifesti
├── requirements.txt
├── run.bat                     # Windows başlatıcı
├── install.py                  # Kurulum yardımcısı
├── .env.example                # Ortam değişkeni şablonu
│
├── ui/                         # PyQt6 arayüzü
│   ├── main_window.py          # Ana pencere, sayfalar, medya kartları
│   ├── login_window.py         # Giriş / kayıt ekranı
│   ├── maintenance_dialog.py   # Bakım modu diyaloğu
│   ├── update_required_dialog.py
│   ├── wifi_error_dialog.py
│   ├── download_thread.py, smart_analysis_thread.py
│   └── assets/                 # İkonlar, logolar, animasyonlar
│
├── logic/                      # İş mantığı (çoğu Cython .pyd)
│   ├── supabase_auth.py        # Kimlik doğrulama + secure_rpc
│   ├── session_token_service   # Kısa ömürlü oturum token'ları
│   ├── build_guard             # TLS pinning + build allowlist
│   ├── maintenance_guard       # Uzaktan kill-switch
│   ├── redaction               # Log redaksiyonu
│   ├── api_key_service         # Sunucu taraflı anahtar yönetimi
│   ├── scene_analysis / smart_scene_analysis / video_analysis
│   ├── stock_api_service / leonardo_ai_service
│   ├── cost_tracking_service / scene_cost_tracking_service
│   ├── utils.py                # Cihaz parmak izi, nonce, yardımcılar
│   └── windows_subprocess.py   # Gizli subprocess yaması
│
├── security/                   # Bütünlük doğrulama (Cython .pyd)
│   ├── bootstrap               # Başlangıç & periyodik kontrol
│   ├── integrity_manifest      # Manifest indirme, imza doğrulama
│   └── integrity_hash          # Paralel SHA-256 doğrulama
│
├── tools/
│   ├── build_logic_cython.py   # Cython derleme + strip + staging
│   └── make_integrity_manifest.py  # Manifest üretme ve imzalama
│
├── installer/StuckAI.iss       # Inno Setup kurulum betiği
└── fonts/                      # Poppins, Inter
```

---

## 🚀 Kurulum

> Not: Uygulama çalışmak için yapılandırılmış bir Supabase backend'ine ve imzalı bütünlük manifestine ihtiyaç duyar (fail-closed tasarım).

```powershell
git clone https://github.com/<kullanici-adi>/StuckAI.git
cd StuckAI

python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

copy .env.example .env      # değerleri doldurun
```

FFmpeg ikili dosyalarını (`ffmpeg.exe`, `ffprobe.exe` ve DLL'ler) proje köküne koyun ([ffmpeg.org](https://ffmpeg.org/download.html)), ardından:

```powershell
run.bat
# veya
python app.py
```

---

## 📦 Derleme ve Dağıtım

```powershell
# 1) Kritik modülleri Cython ile derle (kaynak kodsuz staging ağacı)
py tools\build_logic_cython.py --out build_cython --stage-out stage

# 2) İmzalama anahtarı üret (bir kez)
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out private.pem
openssl rsa -in private.pem -pubout -out public.pem

# 3) Bütünlük manifestini oluştur ve imzala
python tools\make_integrity_manifest.py --root . --kid k1 --private-key .\private.pem --output .\files.json

# 4) Tek dosya exe
pyinstaller StuckAI.spec

# 5) Windows kurulum paketi
iscc installer\StuckAI.iss
```

⚠️ `private.pem` asla repoya eklenmemeli; yalnızca derleme makinesinde tutulmalıdır.

---

## 🛠️ Teknolojiler

| Alan | Teknoloji |
|---|---|
| Arayüz | PyQt6, PyQt6-QtSvg |
| Backend / Auth | Supabase (Auth, PostgREST, RLS, RPC) |
| AI | OpenAI, Leonardo AI, Whisper |
| Medya | FFmpeg, OpenCV, Pillow |
| Kriptografi | `cryptography` (RSA / ECDSA / SHA-256), SPKI pinning |
| Derleme | Cython, PyInstaller, Inno Setup |

---

## 👤 Geliştirici

**Yusuf Eren Yükcü**

© 2025 StuckAI — Tüm hakları saklıdır.
