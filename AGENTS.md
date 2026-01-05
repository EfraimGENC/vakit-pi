# AGENTS.md

Raspberry Pi için Namaz Vakti ve Ezan Uygulaması (Vakit-Pi) hakkında AI kodlama ajanları için rehber.

## Proje Genel Bakış

**Vakit-Pi**, Raspberry Pi üzerinde çalışan, namaz vakitlerini otomatik hesaplayan ve Bluetooth hoparlör üzerinden ezan çalan bir Python uygulamasıdır.

- **Dil**: Python 3.12+
- **Framework**: FastAPI + uvicorn
- **Mimari**: Hexagonal (Ports & Adapters)
- **Paket Yönetimi**: `uv` (astral.sh)
- **Hedef Platform**: Raspberry Pi 4 / Raspberry Pi OS Debian Bookworm 64-Bit

## Dizin Yapısı

```
src/vakit_pi/
├── api/           # FastAPI endpoint'leri ve şemalar
├── assets/audio/  # Ezan ses dosyaları (.mp3)
├── domain/        # Domain modelleri ve event'ler
├── infrastructure/# Altyapı: ses, scheduler, repository
├── services/      # Business logic katmanı
├── web/           # Statik dosyalar (frontend)
├── cli.py         # Komut satırı arayüzü
├── config.py      # Uygulama konfigürasyonu
└── main.py        # Uygulama entry point
```

## Geliştirme Ortamı

### Bağımlılıkları Kurma

```bash
# uv kurulumu (gerekirse)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Bağımlılıkları sync et
uv sync

# Dev bağımlılıkları ile birlikte
uv sync --all-extras
```

### Geliştirme Sunucusunu Başlatma

```bash
uv run vakit-pi serve
# veya
just serve
```

Web arayüzü: `http://localhost:8080`

## Test Komutları

```bash
# Testleri çalıştır
uv run pytest
# veya
just test

# Verbose mod
just test-v

# Tüm kalite kontrollerini çalıştır (lint, format, typecheck, test)
just check
```

Testler `tests/` dizininde bulunur. Yeni özellik eklerken ilgili testleri de yazın veya güncelleyin.

## Kod Stili ve Linting

- **Linter/Formatter**: Ruff
- **Type Checker**: MyPy (strict mode)
- **Line Length**: 100 karakter
- **Quote Style**: Double quotes

```bash
# Lint kontrolü
just lint

# Lint hatalarını düzelt
just lint-fix

# Format kontrolü
just format-check

# Formatla
just format

# Type kontrolü
just typecheck
```

### Önemli Ruff Kuralları

- `E`, `W`: pycodestyle
- `F`: Pyflakes
- `I`: isort (import sıralama)
- `B`: flake8-bugbear
- `UP`: pyupgrade
- `ASYNC`: async/await kuralları
- `PTH`: pathlib kullanımı tercih edilir

### Göz Ardı Edilen Kurallar

- `RUF001`, `RUF002`, `RUF003`: Türkçe karakter uyarıları devre dışı

## Deployment (Raspberry Pi)

### Hedef Cihaz

- **SSH Bağlantısı**: `ssh efraim@192.168.1.22`
- **OS**: Raspberry Pi OS Debian Bookworm 64-Bit
- **Proje Dizini**: `~/vakit-pi` (git clone ile)

### Uzak Sunucuda Güncelleme

```bash
# SSH ile bağlan
ssh efraim@192.168.1.22

# Proje dizinine git
cd ~/vakit-pi

# Güncelle (git pull + uv sync + service restart)
just update

# veya manuel:
git pull origin main
uv sync
sudo systemctl restart vakit-pi
```

### Servis Yönetimi

```bash
# Servis durumu
just status
# veya: sudo systemctl status vakit-pi

# Logları izle (canlı)
just logs
# veya: sudo journalctl -u vakit-pi -f

# Son N satır log
just logs-tail n=100

# Servisi yeniden başlat
just restart

# Servisi durdur/başlat
just stop
just start
```

### Log Kontrolü ve Debugging

Raspberry Pi üzerinde logları kontrol etmek için:

```bash
# SSH bağlantısı
ssh efraim@192.168.1.22

# Canlı log takibi
sudo journalctl -u vakit-pi -f

# Son 100 satır
sudo journalctl -u vakit-pi -n 100 --no-pager

# Hata logları
sudo journalctl -u vakit-pi -p err
```

## Ortam Değişkenleri

| Değişken | Varsayılan | Açıklama |
|----------|------------|----------|
| `VAKIT_PI_HOST` | `0.0.0.0` | Sunucu host adresi |
| `VAKIT_PI_PORT` | `8080` | Sunucu portu |
| `VAKIT_PI_LOG_LEVEL` | `INFO` | Log seviyesi |
| `VAKIT_PI_SETTINGS_PATH` | `~/.config/vakit-pi/settings.json` | Ayarlar dosyası |
| `VAKIT_PI_AUDIO_DIR` | `src/vakit_pi/assets/audio/` | Ses dosyaları dizini |

## CLI Komutları

```bash
# Sunucuyu başlat
uv run vakit-pi serve

# Namaz vakitlerini göster
uv run vakit-pi times --lat 41.0082 --lng 28.9784 --days 7

# Ses testi
uv run vakit-pi test-audio --volume 80
```

## Önemli Bağımlılıklar

- `fastapi`: Web API framework
- `uvicorn`: ASGI sunucu
- `islam`: Namaz vakti hesaplama (pyIslam)
- `apscheduler`: Zamanlama
- `pydantic`: Veri validasyonu
- `timezonefinder`: Timezone belirleme
- `babel`: Uluslararasılaştırma

## Commit ve PR Kuralları

1. Tüm testlerin geçtiğinden emin ol: `just check`
2. Kod formatlanmış olmalı: `just format`
3. Type hataları olmamalı: `just typecheck`
4. Yeni özellikler için test yaz
5. Türkçe commit mesajları kabul edilir

## Güvenlik Notları

- Ses dosyaları `.mp3` formatında `assets/audio/` altında bulunur
- Ayarlar JSON formatında `~/.config/vakit-pi/settings.json` dosyasında saklanır
- API authentication yok (yerel ağ kullanımı için tasarlandı)
- Raspberry Pi'ye SSH erişimi parola korumalı

## Sık Karşılaşılan Sorunlar

### Bluetooth Hoparlör Bağlantısı

Bluetooth hoparlör kurulumu için: `docs/bluetooth-speaker-setup.md`

### Ses Çalmıyor

1. `mpg123` kurulu mu kontrol et: `which mpg123`
2. PulseAudio çalışıyor mu: `pactl info`
3. Ses dosyaları mevcut mu: `ls src/vakit_pi/assets/audio/`

### Servis Başlamıyor

1. Logları kontrol et: `just logs-tail n=50`
2. Python versiyonu: `python3 --version` (3.12+ olmalı)
3. Bağımlılıklar: `uv sync`
