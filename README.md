# Vakit-Pi

Raspberry Pi için Namaz Vakti ve Ezan Uygulaması 🕌

## Özellikler

- 📅 Günlük namaz vakitlerini otomatik hesaplama (Diyanet metoduyla)
- 🔊 Namaz vakitlerinde Bluetooth hoparlörden ezan çalma
- 🌐 Modern web arayüzü ile ayar ve bilgi yönetimi
- ⏰ Vakit bazlı ses seviyesi ayarı
- 🔔 Ön uyarı bildirimleri
- 🌙 Hicri takvim desteği
- 🔄 Raspberry Pi yeniden başlasa bile otomatik çalışma

## Gereksinimler

### Donanım
- Raspberry Pi 4 (veya 3B+)
- Bluetooth hoparlör
- SD Kart (en az 8GB)

### Yazılım
- Raspberry Pi OS Bookworm Lite 64-bit
- Python 3.12+
- mpg123 veya benzeri ses çalma aracı

## Hızlı Kurulum

```bash
# Projeyi klonla
git clone https://github.com/vakit-pi/vakit-pi.git
cd vakit-pi

# Kurulum scriptini çalıştır
chmod +x deploy/install.sh
./deploy/install.sh
```

## Manuel Kurulum

### 1. Sistem Paketleri

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip mpg123 alsa-utils \
    pulseaudio pulseaudio-module-bluetooth bluetooth bluez
```

### 2. uv Kurulumu

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

### 3. Proje Kurulumu

```bash
cd vakit-pi
uv sync
```

### 4. Ezan Ses Dosyaları

Ezan ses dosyalarını `src/vakit_pi/assets/audio/` dizinine kopyalayın:
- `adhan_istanbul.mp3`
- `adhan_makkah.mp3`
- `adhan_madinah.mp3`

### 5. Systemd Servisi

```bash
sudo cp deploy/vakit-pi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vakit-pi
sudo systemctl start vakit-pi
```

## Kullanım

### Web Arayüzü

Tarayıcınızdan `http://<raspberry-pi-ip>:8080` adresine gidin.

### Komut Satırı

```bash
# Sunucuyu başlat
uv run vakit-pi serve

# Namaz vakitlerini göster (İstanbul için)
uv run vakit-pi times --lat 41.0082 --lng 28.9784 --days 7

# Ses testi
uv run vakit-pi test-audio --volume 80
```

### Servis Yönetimi

```bash
# Durum kontrolü
sudo systemctl status vakit-pi

# Yeniden başlatma
sudo systemctl restart vakit-pi

# Logları izleme
sudo journalctl -u vakit-pi -f
```

## Bluetooth Hoparlör Eşleştirme

```bash
bluetoothctl
> power on
> agent on
> scan on
# Hoparlörünüzün MAC adresini bulun
> pair XX:XX:XX:XX:XX:XX
> connect XX:XX:XX:XX:XX:XX
> trust XX:XX:XX:XX:XX:XX
> quit
```

## Konfigürasyon

Ayarlar `~/.config/vakit-pi/settings.json` dosyasında saklanır:

```json
{
  "location": {
    "latitude": 41.0082,
    "longitude": 28.9784,
    "city": "İstanbul"
  },
  "adhan_type": "istanbul",
  "volume": {
    "default": 80,
    "fajr": 60
  },
  "enabled_prayers": ["imsak", "ogle", "ikindi", "aksam", "yatsi"],
  "pre_alert_minutes": 15
}
```

### Environment Variables

| Değişken | Varsayılan | Açıklama |
|----------|-----------|----------|
| `VAKIT_PI_HOST` | `0.0.0.0` | Sunucu adresi |
| `VAKIT_PI_PORT` | `8080` | Sunucu portu |
| `VAKIT_PI_LOG_LEVEL` | `INFO` | Log seviyesi |
| `VAKIT_PI_SETTINGS_PATH` | `~/.config/vakit-pi/settings.json` | Ayar dosyası yolu |

## API Endpoints

| Method | Endpoint | Açıklama |
|--------|----------|----------|
| GET | `/api/status` | Sistem durumu |
| GET | `/api/current` | Mevcut durum (saat, vakit, geri sayım) |
| GET | `/api/times/today` | Bugünün namaz vakitleri |
| GET | `/api/times/week` | Haftalık namaz vakitleri |
| GET | `/api/settings` | Mevcut ayarlar |
| PUT | `/api/settings` | Ayarları güncelle |
| POST | `/api/audio/test` | Ses testi |
| POST | `/api/audio/stop` | Sesi durdur |

## Proje Yapısı

```
vakit-pi/
├── src/vakit_pi/
│   ├── domain/           # İş kuralları ve modeller
│   │   ├── models.py     # Domain modelleri
│   │   └── events.py     # Domain eventleri
│   ├── services/         # İş mantığı servisleri
│   │   ├── ports.py      # Arayüzler (ports)
│   │   ├── prayer_service.py
│   │   ├── adhan_service.py
│   │   └── scheduler_service.py
│   ├── infrastructure/   # Dış sistemler (adaptörler)
│   │   ├── audio.py      # Ses oynatıcılar
│   │   ├── scheduler.py  # APScheduler adaptörü
│   │   └── settings_repository.py
│   ├── api/              # Web API
│   │   ├── app.py        # FastAPI uygulama
│   │   ├── routes.py     # API endpointleri
│   │   └── schemas.py    # Pydantic şemaları
│   ├── web/              # Frontend
│   │   └── index.html
│   ├── assets/audio/     # Ezan ses dosyaları
│   ├── config.py
│   ├── cli.py
│   └── main.py
├── deploy/
│   ├── vakit-pi.service  # Systemd servis dosyası
│   └── install.sh        # Kurulum scripti
├── tests/
└── pyproject.toml
```

## Mimari

Bu proje **Hexagonal Architecture (Ports & Adapters)** ve **Clean Architecture** prensipleriyle tasarlanmıştır:

- **Domain Layer**: İş kuralları ve modeller (`PrayerTimes`, `PrayerSettings`, vb.)
- **Service Layer**: İş mantığı (`PrayerService`, `AdhanService`, `SchedulerService`)
- **Infrastructure Layer**: Dış sistemlerle iletişim (`Mpg123Player`, `APSchedulerAdapter`, vb.)
- **API Layer**: Web arayüzü (FastAPI)

### SOLID Prensipleri

- **S**ingle Responsibility: Her sınıf tek bir sorumluluğa sahip
- **O**pen/Closed: Port/Adapter pattern ile genişletilebilir
- **L**iskov Substitution: Tüm adaptörler arayüzlere uygun
- **I**nterface Segregation: Küçük, odaklı arayüzler
- **D**ependency Inversion: Servisler arayüzlere bağımlı

## Geliştirme

```bash
# Geliştirme bağımlılıklarını kur
uv sync --all-extras

# Lint ve format
uv run ruff check src/
uv run ruff format src/

# Type check
uv run mypy src/

# Testler
uv run pytest
```

## Lisans

MIT License - Detaylar için [LICENSE](LICENSE) dosyasına bakın.

## Katkıda Bulunma

Pull request'ler memnuniyetle karşılanır. Büyük değişiklikler için önce bir issue açın.
