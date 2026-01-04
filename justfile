# Vakit-Pi Justfile
# https://github.com/casey/just

# Varsayılan tarif: mevcut tarifleri listele
default:
    @just --list

# ─────────────────────────────────────────────────────────────
# 🚀 Deployment
# ─────────────────────────────────────────────────────────────

# Sunucuda güncelleme: git pull, sync, restart
update:
    @echo "📥 Güncellemeler çekiliyor..."
    git pull origin main
    @echo "📦 Bağımlılıklar senkronize ediliyor..."
    uv sync
    @echo "🔄 Servis yeniden başlatılıyor..."
    sudo systemctl restart vakit-pi
    @echo "✅ Güncelleme tamamlandı!"
    @just status

# Temiz güncelleme: cache temizliği dahil
clean-update: clean update

# Servisi yeniden başlat
restart:
    sudo systemctl restart vakit-pi

# Servis durumunu göster
status:
    sudo systemctl status vakit-pi --no-pager

# Logları izle
logs:
    sudo journalctl -u vakit-pi -f

# Son N satır log göster (varsayılan: 50)
logs-tail n="50":
    sudo journalctl -u vakit-pi -n {{n}} --no-pager

# Servisi durdur
stop:
    sudo systemctl stop vakit-pi

# Servisi başlat
start:
    sudo systemctl start vakit-pi

# ─────────────────────────────────────────────────────────────
# 🛠️ Geliştirme
# ─────────────────────────────────────────────────────────────

# Geliştirme sunucusunu başlat
serve:
    uv run vakit-pi serve

# Bağımlılıkları kur
sync:
    uv sync

# Tüm ekstralarla bağımlılıkları kur
sync-all:
    uv sync --all-extras

# Namaz vakitlerini göster (İstanbul)
times lat="41.0082" lng="28.9784" days="7":
    uv run vakit-pi times --lat {{lat}} --lng {{lng}} --days {{days}}

# Ses testi
test-audio volume="80":
    uv run vakit-pi test-audio --volume {{volume}}

# ─────────────────────────────────────────────────────────────
# 🧪 Test & Kalite
# ─────────────────────────────────────────────────────────────

# Testleri çalıştır
test:
    uv run pytest

# Testleri verbose modda çalıştır
test-v:
    uv run pytest -v

# Lint kontrolü
lint:
    uv run ruff check src/

# Lint hatalarını düzelt
lint-fix:
    uv run ruff check src/ --fix

# Kod formatlama
format:
    uv run ruff format src/

# Formatlama kontrolü (değişiklik yapmadan)
format-check:
    uv run ruff format src/ --check

# Type kontrolü
typecheck:
    uv run mypy src/

# Tüm kalite kontrollerini çalıştır
check: lint format-check typecheck test
    @echo "✅ Tüm kontroller başarılı!"

# ─────────────────────────────────────────────────────────────
# 🔧 Kurulum
# ─────────────────────────────────────────────────────────────

# İlk kurulum
install:
    chmod +x deploy/install.sh
    ./deploy/install.sh

# Systemd servisini kur
install-service:
    sudo cp deploy/vakit-pi.service /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable vakit-pi
    @echo "✅ Servis kuruldu ve etkinleştirildi"

# ─────────────────────────────────────────────────────────────
# 🧹 Temizlik
# ─────────────────────────────────────────────────────────────

# Python cache dosyalarını temizle
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    find . -type f -name "*.pyc" -delete 2>/dev/null || true
    find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
    find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
    @echo "🧹 Cache dosyaları temizlendi"
