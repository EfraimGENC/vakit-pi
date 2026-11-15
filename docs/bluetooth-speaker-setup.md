# Raspberry Pi 4 - Bluetooth Hoparlör Kurulum Rehberi

Bu rehber, Raspberry Pi 4 (Bookworm Lite) üzerinde SSH veya kullanıcı oturumu olmadan
Bluetooth hoparlöre ses çıkışı için sistem tarafındaki hazırlığı anlatır.

Hoparlörü **seçme, eşleştirme, bağlanma ve elektrik kesintisinden sonra yeniden bağlanma**
artık uygulamanın kendisi tarafından yapılır (web arayüzü → Bluetooth kartı).
Eski sürümlerdeki MAC adresi sabit `bluetooth-autoconnect` script/servisine ve
`system.pa` içindeki `set-default-sink` satırına **gerek yoktur**.

---

## Ön Koşullar

- Raspberry Pi 4 + Raspberry Pi OS Bookworm Lite
- Bluetooth hoparlör (örn: Behringer C210)
- `bluez`, `pulseaudio`, `pulseaudio-module-bluetooth` paketleri (`deploy/install.sh` kurar)

---

## 1. Kullanıcı PulseAudio'yu Devre Dışı Bırak

System-wide PulseAudio kullanacağımız için kullanıcı servislerini kapatıyoruz:

```bash
systemctl --user disable pulseaudio.service pulseaudio.socket
systemctl --user mask pulseaudio.service pulseaudio.socket
```

## 2. Linger'ı Aktifleştir

```bash
sudo loginctl enable-linger $USER
```

## 3. System-Wide PulseAudio

`/etc/pulse/system.pa` dosyasının sonuna ekleyin (MAC **yazmayın**):

```
load-module module-bluetooth-policy
load-module module-bluetooth-discover
```

`/etc/systemd/system/pulseaudio.service`:

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

Kullanıcıyı gerekli gruplara ekleyin:

```bash
sudo usermod -aG pulse-access,audio,bluetooth $USER
```

## 4. Servisleri Aktifleştir

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bluetooth pulseaudio.service
sudo systemctl restart vakit-pi
```

## 5. Hoparlörü Bağla (Arayüzden)

1. Web arayüzünde **Bluetooth** kartındaki anahtarla Bluetooth'u açın.
2. Hoparlörü eşleşme moduna alın, **🔍 Hoparlör Tara**'ya basın (~8 sn).
3. Listeden hoparlörü seçip **Eşleştir ve Bağlan**'a basın.

Bağlanınca uygulama, hoparlörün ses çıkışını (`pactl set-default-sink`) otomatik olarak
varsayılan yapar. Seçim ve durum `settings.json` içinde kalıcı saklanır.

## Elektrik Kesintisi Sonrası Davranış

| Kesinti öncesi durum | Elektrik gelince |
|---|---|
| Bluetooth açık + hoparlöre bağlı | Aynı hoparlöre süresiz yeniden bağlanmayı dener (3 sn → en çok 60 sn aralıkla) |
| Bluetooth açık, **Bağlantıyı Kes** yapılmış | Bluetooth açılır, bağlanılmaz |
| Bluetooth kapalı | Bluetooth kapalı kalır |

Hoparlör gün içinde kapanıp açılırsa (30 sn'lik kontrolle) yeniden bağlanılır.
Bluetooth çıkışı bekleniyorken hoparlör bağlı değilse ezan çalınmaz; journal'a
`Bluetooth hoparlör bağlı değil; ezan çalınmadı` uyarısı yazılır.

---

## Eski Kurulumdan Geçiş

Daha önce `bluetooth-autoconnect` servisi kurduysanız, uygulamayla çakışmaması için kaldırın:

```bash
sudo systemctl disable --now bluetooth-autoconnect.service
sudo rm /etc/systemd/system/bluetooth-autoconnect.service /usr/local/bin/bluetooth-autoconnect.sh
sudo systemctl daemon-reload
```

`/etc/pulse/system.pa` içindeki `set-default-sink bluez_sink.XX_...` satırını da silin.
Ayar dosyasında kayıtlı bir `bluetooth_device_mac` varsa, ilk açılışta o hoparlöre bağlanma
davranışı korunur.

---

## Sorun Giderme

```bash
# Uygulama logları (bağlantı hatasının gerçek nedeni burada)
sudo journalctl -u vakit-pi -f | grep -i bluetooth

# Bluetooth durumu ve cihaz bilgisi
bluetoothctl show | grep Powered
bluetoothctl info XX:XX:XX:XX:XX:XX

# Ses çıkışlarını listele
PULSE_SERVER=/var/run/pulse/native pactl list sinks short

# Manuel ses testi
PULSE_SERVER=/var/run/pulse/native paplay /usr/share/sounds/alsa/Front_Center.wav
```

## Notlar

- Hoparlör kapalıysa bağlantı kurulamaz; açık ve eşleşme modunda olduğundan emin olun.
- Tarama sırasında ses akışı kısa süre bozulabilir; yayın sırasında taramayın.
