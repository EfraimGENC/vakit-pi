# Ezan Ses Dosyaları

Bu dizine ezan MP3 dosyalarını yerleştirin.

## Varsayılan Dosyalar

Her ezan tipi için bir varsayılan dosya gereklidir:

- `adhan_istanbul.mp3` - İstanbul Ezanı
- `adhan_makkah.mp3` - Mekke Ezanı  
- `adhan_madinah.mp3` - Medine Ezanı

## Vakite Özel Dosyalar (Opsiyonel)

Her vakit için farklı bir ezan kullanmak isterseniz, vakite özel dosyalar ekleyebilirsiniz.
Vakite özel dosya bulunamazsa varsayılan dosya çalınır.

**Format:** `adhan_{ezan_tipi}_{vakit}.mp3`

### İstanbul Ezanı Örneği

| Vakit   | Dosya Adı                    |
|---------|------------------------------|
| İmsak   | `adhan_istanbul_imsak.mp3`   |
| Öğle    | `adhan_istanbul_ogle.mp3`    |
| İkindi  | `adhan_istanbul_ikindi.mp3`  |
| Akşam   | `adhan_istanbul_aksam.mp3`   |
| Yatsı   | `adhan_istanbul_yatsi.mp3`   |

### Mekke Ezanı Örneği

| Vakit   | Dosya Adı                   |
|---------|-----------------------------|
| İmsak   | `adhan_makkah_imsak.mp3`    |
| Öğle    | `adhan_makkah_ogle.mp3`     |
| İkindi  | `adhan_makkah_ikindi.mp3`   |
| Akşam   | `adhan_makkah_aksam.mp3`    |
| Yatsı   | `adhan_makkah_yatsi.mp3`    |

### Medine Ezanı Örneği

| Vakit   | Dosya Adı                    |
|---------|------------------------------|
| İmsak   | `adhan_madinah_imsak.mp3`    |
| Öğle    | `adhan_madinah_ogle.mp3`     |
| İkindi  | `adhan_madinah_ikindi.mp3`   |
| Akşam   | `adhan_madinah_aksam.mp3`    |
| Yatsı   | `adhan_madinah_yatsi.mp3`    |

## Müezzin Varyantları (Opsiyonel)

Aynı stil ve vakit için birden fazla ezan dosyası eklenebilir. Sistem bu dosyalar
arasından rastgele seçim yapar.

**Format:** `adhan_{ezan_tipi}_{vakit}_{varyant}.mp3`

### Örnek

```
adhan_istanbul_ikindi.mp3
adhan_istanbul_ikindi_ahmet.mp3
adhan_istanbul_ikindi_mehmet_hoca.mp3
adhan_istanbul_ikindi_müezzin_ali.mp3
```

Bu durumda "istanbul" stilinde "ikindi" vaktinde ezan çalınacağı zaman,
yukarıdaki dört dosyadan biri rastgele seçilir.

Varyant adı serbesttir ve alt çizgi içerebilir. Vakite özel dosya olmadan
da sadece varsayılan dosya için varyant eklenebilir:

```
adhan_istanbul.mp3
adhan_istanbul_hafız_mehmet.mp3
```

## Dosya Kaynakları

Ezan ses dosyalarını yasal kaynaklardan temin edebilirsiniz:
- Diyanet İşleri Başkanlığı
- İslami içerik siteleri (lisans koşullarına dikkat edin)

## Dosya Formatı

- Format: MP3
- Önerilen kalite: 128-320 kbps
- Boyut: Tipik olarak 3-8 MB
