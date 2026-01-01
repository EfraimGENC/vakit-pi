# Raspberry Pi 4 - Bluetooth Hoparlör Otomatik Bağlantı Rehberi

Bu rehber, Raspberry Pi 4 (Bookworm Lite) üzerinde SSH veya kullanıcı oturumu olmadan Bluetooth hoparlöre otomatik bağlanma ve varsayılan ses çıkışı yapma adımlarını içerir.

---

## Ön Koşullar

- Raspberry Pi 4 + Raspberry Pi OS Bookworm Lite
- Bluetooth hoparlör (örn: Behringer C210)
- Hoparlör önceden eşleştirilmiş olmalı

---

## 1. Bluetooth Cihazını Eşleştir ve Güvenilir Yap

```bash
# Bluetooth MAC adresini bul
bluetoothctl devices

# Cihazı güvenilir yap (MAC adresini değiştir)
bluetoothctl trust 41:42:86:EF:B4:62
```

---

## 2. Kullanıcı PulseAudio'yu Devre Dışı Bırak

System-wide PulseAudio kullanacağımız için kullanıcı servislerini kapatıyoruz:

```bash
systemctl --user disable pulseaudio.service pulseaudio.socket
systemctl --user mask pulseaudio.service pulseaudio.socket
```

---

## 3. Linger'ı Aktifleştir

```bash
sudo loginctl enable-linger $USER
```

---

## 4. System-Wide PulseAudio Ayarları

### 4.1 PulseAudio Config Dosyasını Düzenle

```bash
sudo nano /etc/pulse/system.pa
```

En alta ekle:
```
load-module module-bluetooth-policy
load-module module-bluetooth-discover
set-default-sink bluez_sink.41_42_86_EF_B4_62.a2dp_sink
```

> **Not:** MAC adresindeki `:` karakterleri `_` ile değiştirilir.

### 4.2 PulseAudio System Servisi Oluştur

```bash
sudo nano /etc/systemd/system/pulseaudio.service
```

İçeriği:
```ini
[Unit]
Description=PulseAudio System-Wide Server
After=bluetooth.target

[Service]
Type=simple
ExecStart=/usr/bin/pulseaudio --system --disallow-exit --disallow-module-loading=0
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 4.3 Kullanıcıyı Gerekli Gruplara Ekle

```bash
sudo usermod -aG pulse-access $USER
sudo usermod -aG audio $USER
```

---

## 5. Bluetooth Autoconnect Script'i Oluştur

```bash
sudo nano /usr/local/bin/bluetooth-autoconnect.sh
```

İçeriği:
```bash
#!/bin/bash

MAC="41:42:86:EF:B4:62"

while true; do
    if ! bluetoothctl info $MAC | grep -q "Connected: yes"; then
        echo "$(date): Bağlı değil, bağlanılıyor..."
        bluetoothctl connect $MAC
    fi
    sleep 30
done
```

Çalıştırılabilir yap:
```bash
sudo chmod +x /usr/local/bin/bluetooth-autoconnect.sh
```

---

## 6. Bluetooth Autoconnect Servisi Oluştur

```bash
sudo nano /etc/systemd/system/bluetooth-autoconnect.service
```

İçeriği:
```ini
[Unit]
Description=Auto-connect Bluetooth Speaker
After=pulseaudio.service bluetooth.target
Wants=pulseaudio.service

[Service]
Type=simple
ExecStart=/usr/local/bin/bluetooth-autoconnect.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## 7. Servisleri Aktifleştir

```bash
sudo systemctl daemon-reload
sudo systemctl enable bluetooth
sudo systemctl enable pulseaudio.service
sudo systemctl enable bluetooth-autoconnect.service
```

---

## 8. Yeniden Başlat ve Test Et

```bash
sudo reboot
```

Reboot sonrası SSH **bağlanmadan** hoparlörden bağlantı sesini bekle.

---

## Sorun Giderme Komutları

```bash
# Bluetooth bağlantı durumu
bluetoothctl info 41:42:86:EF:B4:62 | grep Connected

# Servis durumları
systemctl status bluetooth-autoconnect.service
systemctl status pulseaudio.service

# Servis logları
journalctl -u bluetooth-autoconnect.service -b
journalctl -u pulseaudio.service -b

# Ses çıkışlarını listele
PULSE_SERVER=/var/run/pulse/native pactl list sinks short

# Manuel ses testi
PULSE_SERVER=/var/run/pulse/native paplay /usr/share/sounds/alsa/Front_Center.wav

# Manuel bağlantı
bluetoothctl connect 41:42:86:EF:B4:62
```

---

## Özet: Dosya Konumları

| Dosya | Konum |
|-------|-------|
| Autoconnect Script | `/usr/local/bin/bluetooth-autoconnect.sh` |
| Autoconnect Service | `/etc/systemd/system/bluetooth-autoconnect.service` |
| PulseAudio Service | `/etc/systemd/system/pulseaudio.service` |
| PulseAudio Config | `/etc/pulse/system.pa` |

---

## Notlar

- MAC adresi her cihaz için farklıdır, kendi cihazının MAC adresini kullan
- Script her 30 saniyede bağlantıyı kontrol eder
- Hoparlör kapalıysa bağlantı kurulamaz, açık olduğundan emin ol
- Elektrik gidip gelse bile otomatik bağlanır
