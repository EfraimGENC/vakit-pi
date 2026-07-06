# Anti-Gate Ses Oynatım Katmanı — Tasarım

**Tarih:** 2026-07-06
**Durum:** Onaylandı, uygulanıyor

## Problem

Bluetooth üzerinden bağlı Behringer C210 hoparlörde bir noise gate / auto-mute
bulunuyor. Sinyal seviyesi eşiğin altına düşünce gate kapanıyor ve tekrar sinyal
gelince fade-in ile açılıyor. Sonuç:

- **Baş kesilmesi:** TTS bildirimlerinin başı kayboluyor ("Sayın cemati" → "yın cemati").
- **Orta kesilmesi:** Ezanda sessizlik/nefesten sonra gelen yumuşak başlangıçlı
  kelimeler kısılıyor ("Hayyalesselah" → "ayyalesselah").

İkincil olası neden: Bluetooth linkinin (PulseAudio/SBC) sessizlikte veri akışını
kesmesi, bu da gate/standby'ı tetikliyor.

## Kısıt

Hoparlör 7/24 açık; ancak **sessiz saatlerde tam sessizlik şart** — sürekli çalan
duyulabilir bir pilot ton kabul edilemez. Bu yüzden çözüm, gate'i **yalnızca
oynatım süresince** açık tutmalı; oynatım bitince tam sessizliğe dönmeli.

## Ortam (doğrulandı)

Pi'de (`ssh zeyd`): `ffmpeg 5.1.9` kurulu, `-f pulse` çıkışı destekli.
`mpg123`, `paplay`, `aplay` mevcut (fallback için).

## Çözüm — Oynatım-içi anti-gate işleme (Yaklaşım A)

Her ezan ve TTS oynatımı bir ffmpeg filtre zincirinden geçer. Filtre üç bileşenden
oluşur; hiçbiri toplam süre bilgisi gerektirmez, böylece hem statik dosya hem de
canlı TTS stream'i için aynı zincir çalışır:

1. **Lead-in ısıtma tonu:** Asıl sesin önüne, sessizden içeri `afade` ile yükselen
   ~1.5 sn'lik düşük seviyeli bir ton `concat` edilir. Gate/Bluetooth linki, ilk
   hece gelmeden açılır → baş kesilmesi çözülür.
2. **Dinamik sıkıştırma:** Asıl sese `dynaudnorm` (veya `acompressor`) uygulanır;
   yumuşak/sessiz kısımlar yükselir → ortadaki kelime başları gate eşiğinin
   üstünde kalır → orta kesilmesi çözülür.
3. **Opsiyonel taban tonu (varsayılan KAPALI):** Gerekirse `amix` ile çok düşük
   seviyeli, duyulamayan alt-frekans tonu tüm parçaya karıştırılır → nefes
   anlarında bile gate tam kapanmaz. Önce lead-in + sıkıştırma denenir; yetmezse
   env ile açılır.

Ses yalnızca oynatım süresince üretilir; oynatım bitince tam sessizlik → gece
kısıtı korunur.

## Mimari

- **Yeni adapter** `FfmpegAntiGatePlayer(BaseAudioPlayer)` — `src/vakit_pi/infrastructure/audio.py`
  - `_get_command(file_path, volume)`: ffmpeg komutunu kurar, çıkış `-f pulse default`.
  - `_is_available()`: `ffmpeg` PATH'te mi.
  - `stop()`, `is_playing()`, volume davranışı `BaseAudioPlayer`'dan miras (tek subprocess).
- **`get_best_player()`** sıralaması: ffmpeg + anti-gate açık → `FfmpegAntiGatePlayer`
  en üstte; aksi halde mevcut `mpg123 → ffplay → paplay → aplay` zinciri korunur.
- **`speak_tts()`** güncellemesi: edge-tts stream `mpg123` yerine aynı ffmpeg filtre
  zincirine (`-i pipe:0`) pipe edilir.
- **Saf yardımcılar** (birim test edilebilir):
  - `AntiGateConfig` (frozen dataclass) + `AntiGateConfig.from_env()` — parametreler.
  - `build_antigate_filter(config) -> str` — env'den bağımsız, config alıp filtre
    string'i üretir. Player ve TTS paylaşır.

## Konfigürasyon (env var + sabit varsayılanlar)

| Env | Varsayılan | İşlev |
|-----|-----------|-------|
| `VAKIT_PI_ANTIGATE` | `1` | Anti-gate aç/kapa (`0` → düz ffmpeg, filtresiz) |
| `VAKIT_PI_ANTIGATE_LEADIN` | `1.5` | Lead-in süresi (saniye) |
| `VAKIT_PI_ANTIGATE_TONE_HZ` | `55` | Lead-in / taban ton frekansı (Hz) |
| `VAKIT_PI_ANTIGATE_COMPRESS` | `1` | Dinamik sıkıştırma aç/kapa |
| `VAKIT_PI_ANTIGATE_FLOOR_DB` | `off` | Taban ton seviyesi (ör. `-48`); `off` → kapalı |

Behringer'ın eşiği bilinmediğinden parametreler Pi'de restart ederek denenip
ayarlanır.

## Güvenlik / Geri Uyumluluk

- `ffmpeg` yoksa `FfmpegAntiGatePlayer` seçilmez → mevcut davranış aynen korunur.
- `VAKIT_PI_ANTIGATE=0` ile anti-gate tamamen devre dışı bırakılabilir (acil çıkış).
- Volume, mevcut 0-100 ölçeğiyle ffmpeg `volume` filtresi üzerinden uygulanır.

## Test

- `build_antigate_filter()` birim testleri: env kombinasyonları → beklenen filtre
  bileşenleri (lead-in var/yok, sıkıştırma var/yok, taban açık/kapalı).
- `AntiGateConfig.from_env()` parse testleri (varsayılanlar, `off`, geçersiz değer).
- `get_best_player()` seçim testleri (ffmpeg var/yok, anti-gate 0/1).
- Pi'de gerçek ezan + TTS ile kulak testi ve parametre ince ayarı.

## Kapsam Dışı (YAGNI)

- Web UI ayar alanları (env var yeterli).
- Ezan dosyalarının ön-işlenip cache'lenmesi (gerçek zamanlı yeterince hızlı).
- Süre ölçümü / ffprobe (filtre süre bilgisi gerektirmiyor).
