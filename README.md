# ⚡ GÜNDEM — Premium Haber

**9 köklü haber kaynağından, her 30 dakikada bir otomatik güncellenen, anlık piyasa verili, çok temalı premium haber sitesi.**

```
RSS beslemeleri ──► bot.py (birleştirme, tekilleştirme, tam metin kazımı)
                                │
        ┌───────────────────────┼────────────────────────┐
        ▼                       ▼                        ▼
  haberler.json          bot-raporu.json            feeds/*.xml
        │                       │                        │
        └───────────►  index.html + assets/ (frontend)  ◄┘
```

---

## 📡 Haber Kaynakları (canlı test edilmiş)

| Kaynak | Besleme | Kategoriler |
|---|---|---|
| **Anadolu Ajansı** (aa.com.tr) | 6 | Gündem, Ekonomi, Spor, Dünya, Teknoloji, Yaşam & Sanat |
| **NTV** (ntv.com.tr) | 8 | Gündem, Ekonomi, Spor, Dünya, Teknoloji, Sağlık, Yaşam & Sanat |
| **TRT Haber** (trthaber.com) | 1 | Gündem (madde madde kategori) |
| **Sabah** (sabah.com.tr) | 6 | Gündem, Ekonomi, Spor, Dünya, Teknoloji, Yaşam & Sanat |
| **Hürriyet** (hurriyet.com.tr) | 7 | Gündem, Ekonomi, Spor, Dünya, Teknoloji, Sağlık, Magaza |
| **CNN Türk** (cnnturk.com) | 8 | Gündem, Ekonomi, Spor, Dünya, Teknoloji, Sağlık, Yaşam & Sanat, Magaza |
| **Sözcü** (sozcu.com.tr) | 7 | Gündem, Ekonomi, Spor, Dünya, Teknoloji, Sağlık, Magaza |
| **BBC Türkçe** (bbc.co.uk/turkce) | 1 | Gündem |
| **Habertürk** (haberturk.com) | 1 | Gündem |

**Toplam 46 RSS beslemesi** — `sources.json` içinde tek satırla açılıp kapanabilir.

## ⚙️ Gelişmiş Bot Sistemi (`bot.py`)

- **Yapılandırma tabanlı**: Tüm kaynaklar/beslemeler/limitler `sources.json` dosyasında
- **Paralel indirme**: 8 işçilik `ThreadPoolExecutor`, 15 sn zaman aşımı, otomatik yeniden deneme
- **Tekilleştirme**: Türkçe karakter normalizasyonlu başlık + link eşleşmesi
- **Kategori haritalama**: Kaynakların kendi kategori etiketleri (Türkiye→Gündem, Bilim Teknoloji→Teknoloji vb.) otomatik normalize edilir
- **Tam metin kazanımı (akıllı, iki kademeli)**: (1) Uzun açıklamalı beslemeler (ör. Hürriyet) doğrudan paragraflara bölünür; (2) metni yetersiz kalanların (yalnızca görsel içeren RSS dahil) sayfası kazılır. JSON-LD `articleBody`, `itemprop=articleBody`, yoğunluk skoru ve gürültü süzgeci (paylaşım düğmeleri, telif, ilgili haber listeleri, reklam) ile yalnızca haberle ilgili yazı alınır. Özetten ve sayfadan YouTube/Vimeo/mp4 videoları çıkarılıp haber sayfasına gömülür. Alan adı seçmez, her kaynağa çalışır
- **Son dakika işareti**: Son 45 dakikadaki haberler `son_dakika: true` alır
- **Kaynak sağlığı raporu**: Kaynak başına başarılı/hatalı besleme sayısı, süre, hata listesi
- **Kendi RSS akışlarını üretir**: `feeds/*.xml` — site kendi kategorilerine göre RSS sunar
- **Saf standart kütüphane** çalışır; BeautifulSoup varsa tam metin kazımında kullanılır, yoksa regex çözücü devreye girer

### Kullanım

```bash
python bot.py                     # Yapılandırmaya göre çalışır
python bot.py --crawl 8           # Sadece 8 haberin tam metnini kazı
python bot.py --crawl 0           # Sınırsız (varsayılan — tümü)
python bot.py --crawl -1          # Tam metin kazımını kapat
python bot.py --limit 5           # Besleme başına 5 haber (test)
python bot.py --no-feeds          # RSS akışı üretme
python bot.py --verbose           # Ayrıntılı log
python bot.py --fixture tests/test_data   # Ağsız test (test beslemeleri)
```

### Test

```bash
python3 tests/gen_fixtures.py                 # örnek XML beslemeleri üret
python3 bot.py --fixture tests/test_data --crawl 0 -v   # ağsız uçtan uca
python3 tests/test_bot.py                     # ünite testleri (ağsız)
```

## 🎨 Frontend — Bol Seçenekli Deneyim

**Kullanıcı seçenekleri** (ayarlarda saklanır, `localStorage`):
- 🌙 Koyu / ☀️ Açık tema
- 🎨 5 vurgu rengi: camgöbeği, mor, pembe, yeşil, turuncu
- 🔤 3 yazı boyutu
- 🖼 Haber görselleri aç/kapa (performans modu)
- ⚡ Son dakika bandı aç/kapa
- 📈 Piyasa bandı aç/kapa
- ✨ Partikül animasyonları aç/kapa
- ⏱ Otomatik yenileme: kapalı / 1 dk / 5 dk / 15 dk
- 🔍 Canlı arama (`/` kısayolu), kategori filtreleri + sayaçlar
- ↕️ Sıralama (en yeni / en eski), ızgara / liste görünümü
- ⌨️ Klavye: `/` ara, `Esc` geri/kapat, `R` yenile

**İçerik**:
- 8 kategori + Tümü, kaynak rozetleri (kaynak başına renk), "SON DAKİKA" nabız rozetleri
- Detay görünümü: hero görsel, meta rozetleri, tam metin, kaynağa git, paylaş (WhatsApp / X / kopyala), benzer haberler
- İskelet yükleme, boşluk/hata durumları, toast bildirimleri, okuma ilerleme çubuğu, İstanbul canlı saati
- Açılış animasyonu, neon ızgara arka plan, partiküller, tarama çizgisi

## 📊 Anlık Veri (piyasa bandı)

| Veri | API | Yedek |
|---|---|---|
| BIST 100, USD, EUR, Altın, Petrol + değişim | `doviz-api.onrender.com` (Milliyet) | `open.er-api.com`, `api.gold-api.com` |
| Bitcoin, Ethereum (₺ + 24s değişim) | CoinGecko | — |
| İstanbul hava durumu | Open-Meteo | — |

Tüm istekler tarayıcıdan, anahtarsız ve CORS dostu endpoint'lerden yapılır; biri düşerse yedeğe geçer.

## 🚀 Otomatik Güncelleme

`.github/workflows/haber-bot.yml` her **30 dakikada** bir:
1. `bot.py --crawl 8` çalıştırır
2. `haberler.json`, `bot-raporu.json`, `feeds/` dosyalarını commit'ler
3. Değişim yoksa sessizce atlar

Manuel tetiklemek için GitHub → Actions → "Haberleri Guncelle" → Run workflow.

## 📁 Dosya Yapısı

```
├── index.html               # İskelet (CSS/JS ayrı dosyada)
├── assets/
│   ├── css/style.css        # Tasarım sistemi (tema/vurgu değişkenleri)
│   └── js/app.js            # Uygulama mantığı
├── bot.py                   # Haber botu (v2)
├── sources.json             # Kaynak & besleme yapılandırması
├── haberler.json            # Üretilen veri (bot tarafından yazılır)
├── bot-raporu.json          # Bot çalışma raporu
├── feeds/                   # Sitenin kendi RSS akışları (bot tarafından yazılır)
├── tests/
│   ├── gen_fixtures.py      # Ağsız test verisi üreticisi
│   └── test_data/           # Örnek XML beslemeleri
└── .github/workflows/haber-bot.yml
```

##  Not

Haber metinleri ilgili kurumlara aittir; bot özet/metinlerini telif gereği kaynak linkiyle birlikte sunar. Tam metin kazımı yalnızca okuma amaçlıdır ve kaynak sayfalara geri döner.
