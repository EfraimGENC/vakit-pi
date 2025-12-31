#!/bin/bash
# Vakit-Pi Raspberry Pi Kurulum Scripti
# Bu script Raspberry Pi OS Bookworm Lite 64-bit için hazırlanmıştır.

set -euo pipefail

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Kullanıcı kontrolü
if [[ $EUID -eq 0 ]]; then
    log_error "Bu script root olarak çalıştırılmamalı!"
    log_info "Normal kullanıcı ile çalıştırın: ./install.sh"
    exit 1
fi

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║               Vakit-Pi Kurulum Scripti                         ║"
echo "║         Raspberry Pi için Namaz Vakti ve Ezan Uygulaması       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo

# 1. Sistem güncelleme
log_info "Sistem paketleri güncelleniyor..."
sudo apt update && sudo apt upgrade -y

# 2. Gerekli paketleri kur
log_info "Gerekli sistem paketleri kuruluyor..."
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    mpg123 \
    alsa-utils \
    pulseaudio \
    pulseaudio-module-bluetooth \
    bluetooth \
    bluez \
    bluez-tools

# 3. uv kurulumu
log_info "uv paket yöneticisi kontrol ediliyor..."
if ! command -v uv &> /dev/null; then
    log_info "uv kuruluyor..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source ~/.bashrc
    log_success "uv kuruldu!"
else
    log_success "uv zaten kurulu."
fi

# 4. Proje dizini oluştur
PROJECT_DIR="/home/pi/vakit-pi"
log_info "Proje dizini hazırlanıyor: $PROJECT_DIR"

if [[ -d "$PROJECT_DIR" ]]; then
    log_warn "Proje dizini zaten var. Güncelleniyor..."
    cd "$PROJECT_DIR"
    git pull || log_warn "Git pull başarısız, devam ediliyor..."
else
    log_info "Proje klonlanıyor..."
    git clone https://github.com/vakit-pi/vakit-pi.git "$PROJECT_DIR" || {
        log_warn "Git clone başarısız, manuel kurulum gerekebilir."
        mkdir -p "$PROJECT_DIR"
    }
    cd "$PROJECT_DIR"
fi

# 5. Bağımlılıkları kur
log_info "Python bağımlılıkları kuruluyor..."
uv sync

# 6. Ayar dizinini oluştur
CONFIG_DIR="/home/pi/.config/vakit-pi"
log_info "Ayar dizini oluşturuluyor: $CONFIG_DIR"
mkdir -p "$CONFIG_DIR"

# 7. Ezan ses dosyalarını kopyala
AUDIO_DIR="$PROJECT_DIR/src/vakit_pi/assets/audio"
if [[ ! -d "$AUDIO_DIR" ]]; then
    mkdir -p "$AUDIO_DIR"
    log_warn "Ezan ses dosyaları dizini oluşturuldu: $AUDIO_DIR"
    log_warn "Lütfen ezan MP3 dosyalarını bu dizine kopyalayın:"
    log_warn "  - adhan_istanbul.mp3"
    log_warn "  - adhan_makkah.mp3"
    log_warn "  - adhan_madinah.mp3"
fi

# 8. Bluetooth ayarları
log_info "Bluetooth servisi yapılandırılıyor..."
sudo systemctl enable bluetooth
sudo systemctl start bluetooth

# PulseAudio'yu kullanıcı servisi olarak etkinleştir
log_info "PulseAudio yapılandırılıyor..."
systemctl --user enable pulseaudio
systemctl --user start pulseaudio

# 9. Systemd servisi kur
log_info "Systemd servisi kuruluyor..."
sudo cp "$PROJECT_DIR/deploy/vakit-pi.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vakit-pi

# 10. Servis başlat
log_info "Vakit-Pi servisi başlatılıyor..."
sudo systemctl start vakit-pi

# Durum kontrolü
sleep 3
if systemctl is-active --quiet vakit-pi; then
    log_success "Vakit-Pi servisi başarıyla başlatıldı!"
else
    log_error "Servis başlatılamadı. Logları kontrol edin:"
    log_info "  sudo journalctl -u vakit-pi -f"
fi

# Tamamlandı
echo
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Kurulum Tamamlandı!                         ║"
echo "╠════════════════════════════════════════════════════════════════╣"
echo "║  Web Arayüzü: http://$(hostname -I | awk '{print $1}'):8080    ║"
echo "║                                                                 ║"
echo "║  Servis Yönetimi:                                              ║"
echo "║    sudo systemctl status vakit-pi   # Durum                    ║"
echo "║    sudo systemctl restart vakit-pi  # Yeniden başlat           ║"
echo "║    sudo journalctl -u vakit-pi -f   # Logları izle             ║"
echo "║                                                                 ║"
echo "║  Bluetooth Hoparlör Eşleştirme:                                ║"
echo "║    bluetoothctl                                                ║"
echo "║    > scan on                                                   ║"
echo "║    > pair XX:XX:XX:XX:XX:XX                                    ║"
echo "║    > connect XX:XX:XX:XX:XX:XX                                 ║"
echo "║    > trust XX:XX:XX:XX:XX:XX                                   ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo
log_info "Lütfen ezan ses dosyalarını $AUDIO_DIR dizinine kopyalamayı unutmayın!"
