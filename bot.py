#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GÜNDEM Haber Botu v2.1
======================
Çok kaynaklı, yapılandırma tabanlı haber toplama botu.

Yapı:
  - sources.json  : 9 köklü Türk haber kaynağı (AA, NTV, TRT Haber, Sabah,
                    Hürriyet, CNN Türk, Sözcü, BBC Türkçe, Habertürk) ve 48 RSS beslemesi
  - haberler.json : Birleştirilmiş, tekilleştirilmiş haber verisi (frontend için)
  - bot-raporu.json : Çalışma raporu (kaynak sağlığı, süre, sayaçlar)
  - feeds/*.xml   : Sitenin kendi kategori RSS akışları

Kullanım:
  python bot.py                     # Standart çalışma
  python bot.py --crawl 8           # İlk 8 haberin tam metnini de kazı
  python bot.py --limit 10          # Kaynak başına besleme limiti (test)
  python bot.py --no-feeds          # RSS akışı üretme
  python bot.py --verbose           # Ayrıntılı log

Bağımlılık: Sadece standart kütüphane. Tam metin kazımı için BeautifulSoup
mevcutsa kullanılır, yoksa yerleşik regex çözümleyici devreye girer.
"""

import argparse
import concurrent.futures
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

try:
    from bs4 import BeautifulSoup  # opsional
    BSAVULUMU_VAR = True
except ImportError:
    BSAVULUMU_VAR = False

KULLANICI_KIMLIK = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

# Ham kategori adları -> gösterim kategorisi
KATEGORI_ESLEME = {
    "gündem": "Gündem", "gundem": "Gündem", "türkiye": "Gündem", "turkiye": "Gündem",
    "son dakika": "Gündem", "sondakika": "Gündem", "tüm": "Gündem", "tum": "Gündem",
    "anavatan": "Gündem", "politika": "Gündem",
    "ekonomi": "Ekonomi", "finans": "Ekonomi", "borsa": "Ekonomi", "para": "Ekonomi",
    "spor": "Spor", "futbol": "Spor", "basketbol": "Spor", "voleybol": "Spor",
    "spor&skor": "Spor", "dün": "Spor",
    "dünya": "Dünya", "dunya": "Dünya", "yurt dışı": "Dünya", "dis politika": "Dünya",
    "teknoloji": "Teknoloji", "bilim-teknoloji": "Teknoloji", "bilim ve teknoloji": "Teknoloji",
    "bilim": "Teknoloji", "teknolojik": "Teknoloji",
    "sağlık": "Sağlık", "saglik": "Sağlık",
    "yaşam": "Yaşam & Sanat", "yasam": "Yaşam & Sanat", "yaşam & sanat": "Yaşam & Sanat",
    "yaşam&sanat": "Yaşam & Sanat", "kültür sanat": "Yaşam & Sanat", "kultur sanat": "Yaşam & Sanat",
    "kültür-sanat": "Yaşam & Sanat", "kulturel-sanat": "Yaşam & Sanat", "sinema": "Yaşam & Sanat",
    "magazin": "Magaza", "magazın": "Magaza", "günümüz magazin": "Magaza",
}

RE_TAG = re.compile(r"<[^>]+>")
RE_WHITESPACE = re.compile(r"\s+")

# Tam haber sayılması için asgari gövde uzunluğu (yalnızca görsel/video kelime sayılmaz)
MIN_HABER_KELIME = 70
MIN_PARAGRAF_KARAKTER = 28

# Reklam, paylaş, telif, ilgili-haber ve benzeri gürültü
RE_ILAN = re.compile(
    r"(abone\s*ol|yeni abone|ilgili haber|başka haber|reklam\b|izleyici|"
    r"tıklayarak|kaynak\s*:|haber kaynağı|copyright|telif hakkı|"
    r"iktibas edilemez|her t[üu]rl[üu] telif|t[üu]m haklar[ıi] sakl[ıi]|"
    r"facebook ile paylaş|messenger ile gönder|e-?posta ile gönder|"
    r"twitter.?da paylaş|whatsapp|telegram ile|linkedin|"
    r"yorum yaz|yorum yap|daha fazla haber|bunlar[ıi] da be[ğg]enebilirsiniz|"
    r"[öo]nerilen haber|[çc]erez politik|cookie politik|kvkk|"
    r"gizlilik politik|[üu]yelik|giri[şs] yap|kay[ıi]t ol|b[üu]lten|newsletter|"
    r"sitemizi takip|uygulamam[ıi]z[ıi] indir|app store|google play|"
    r"bildirimleri a[çc]|reklam[ıi] kapat|sponsored|advertisement|"
    r"taboola|outbrain|bu haberi paylaş|haberi kopyala|"
    r"www\.[a-z0-9.-]+\.(com|net|tr) internet sitesinde yay[ıi]nlanan)",
    re.I)

RE_PAYLAS = re.compile(
    r"^(facebook|twitter|x\.com|whatsapp|telegram|linkedin|messenger|"
    r"e-?posta|e-?mail|pinterest|kopyala|payla[şs]|tweet|payla[şs]im)\b",
    re.I)

RE_BOLUM_DUR = re.compile(
    r"^\s*(ilgili\s+haber(?:ler)?|ilginizi\s+[çc]ekebilir|"
    r"bunlar[ıi]\s+da\s+(?:oku|be[ğg]en|izle)|"
    r"[öo]nerilen(?:\s+haber(?:ler)?)?|edit[öo]r[üu]n\s+se[çc]tik|"
    r"[çc]ok\s+okunan|g[üu]ndem\s+haber(?:leri)?|son\s+dakika\s+haber(?:leri)?|"
    r"daha\s+fazla(?:\s+haber)?|yorumlar|yorum\s+yap|yorum\s+yaz|"
    r"etiketler|\btags\b|haberi\s+payla[şs]|sizin\s+i[çc]in\s+se[çc]tik|"
    r"abone\s+ol|b[üu]lten|newsletter|ke[şs]fet|benzer\s+haber(?:ler)?)\s*:?\s*$",
    re.I)

RE_GORSEL_GECERSIZ = re.compile(
    r"(logo|icon|pixel|sprite|1x1|avatar|badge|banner|tracking|favicon|\.svg)", re.I)
RE_GORSEL_GEcersiz = RE_GORSEL_GECERSIZ  # geriye dönük ad

RE_VIDEO_REKLAM = re.compile(
    r"(doubleclick|googlesyndication|adsystem|adservice|pagead|"
    r"taboola|outbrain|prebid|scorecardresearch|googletagmanager|"
    r"facebook\.com/plugins|platform\.twitter\.com/widgets|"
    r"instagram\.com/embed|recaptcha|/ads?/)",
    re.I)

RE_VIDEO_IPUCU = re.compile(
    r"(youtube|youtu\.be|vimeo|dailymotion|rumble|\.mp4|\.webm|\.m3u8|"
    r"/embed/|player\.|/video|video\.|twitter\.com/i/videos)",
    re.I)

RE_YOUTUBE_ID = re.compile(
    r"(?:youtube-nocookie\.com/embed/|youtube\.com/embed/|"
    r"youtube\.com/watch\?(?:[^#]*?&)?v=|youtu\.be/)([\w-]{11})",
    re.I)

RE_IFRAME_SRC = re.compile(
    r"<iframe[^>]+(?:src|data-src)\s*=\s*[\"']([^\"']+)[\"']", re.I)
RE_VIDEO_SRC = re.compile(
    r"<video[^>]+(?:src|data-src)\s*=\s*[\"']([^\"']+)[\"']", re.I)
RE_SOURCE_SRC = re.compile(
    r"<source[^>]+src\s*=\s*[\"']([^\"']+)[\"']", re.I)
RE_AMP_YT = re.compile(
    r"<amp-youtube[^>]+data-videoid\s*=\s*[\"']([\w-]{11})[\"']", re.I)

RE_icerik_sinif = re.compile(
    r"(icerik|content|story|detail|haber|article|post|metin|"
    r"text-body|article-body|body-text|news-body|entry-content)",
    re.I)

RE_ATILACAK_SINIF = re.compile(
    r"(related[-_ ]?news|ilgili[-_ ]?haber|onerilen|önerilen|"
    r"social[-_ ]?share|share[-_ ]?(bar|button|box|links)|paylas|paylaş-|"
    r"newsletter|bulten|bülten|reklam|advert|adsbox|ad-slot|ad_slot|"
    r"sponsor|cookie-banner|cerez|çerez|sidebar|widget|breadcrumb|"
    r"etiketler|article-tags|author-box|yazar-kut|"
    r"most-read|cok-okunan|çok-okunan|taboola|outbrain|"
    r"recommended|comments-box|yorumlar|pagination|"
    r"gallery-thumbs|video-playlist|footer-nav|header-nav)",
    re.I)

STOP_KELIME = {
    "son", "dakika", "haberi", "haber", "video", "analizi", "yorum",
    "nedir", "nasil", "nasıl", "neden", "hangi", "icin", "için",
    "ile", "gore", "göre", "kadar", "daha", "çok", "cok", "bir", "bu",
    "su", "şu", "da", "de", "ki", "ve", "veya", "ama", "fakat", "ancak",
    "gibi", "olarak", "uzerine", "üzerine", "sonra", "once", "önce",
    "ilgili", "arasinda", "arasında", "var", "yok", "degil", "değil",
    "olan", "oldu", "eden", "mi", "mu", "mı", "mü", "ne", "ya", "hem",
    "her", "tum", "tüm", "bazi", "bazı", "en", "az", "bugun", "bugün",
    "iste", "işte", "soz", "söz", "konu", "detay", "detaylar",
    "aciklama", "açıklama", "gundem", "gündem", "canli", "canlı",
    "ozel", "özel", "flas", "flaş", "breaking", "live", "devam",
}


def log(msg, verbose_only=False, args=None):
    if verbose_only and not (args and getattr(args, "verbose", False)):
        return
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def temiz_metin(ham):
    """HTML etiketlerini ve aşırı boşlukları temizle."""
    if not ham:
        return ""
    metin = html.unescape(ham)
    metin = RE_TAG.sub(" ", metin)
    metin = metin.replace("\u200b", " ").replace("\ufeff", "")
    return RE_WHITESPACE.sub(" ", metin).strip()


def kelime_sayisi(html_veya_metin):
    """Görsel/video etiketleri hariç düz metin kelime sayısı."""
    return len(temiz_metin(html_veya_metin).split())


def metin_yeterli(html_veya_metin, min_kelime=None):
    return kelime_sayisi(html_veya_metin) >= (min_kelime or MIN_HABER_KELIME)


def mutlak_yap(url, taban=None):
    """Bağlı/göreli URL'leri mutlak yap."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        taban = taban or ""
        try:
            parca = urllib.parse.urlparse(taban)
            return f"{parca.scheme or 'https'}://{parca.netloc}{url}"
        except Exception:
            return url
    return url


def tarihi_parsel(ham):
    """RSS/Atom tarih biçimlerini ISO-8601'e çevir."""
    if not ham:
        return None
    ham = ham.strip()
    try:
        return parsedate_to_datetime(ham).astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    try:
        dt = datetime.fromisoformat(ham.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    except Exception:
        return None


def norm_baslik(baslik):
    """Tekilleştirme için başlık normalizasyonu (Türkçe dostu)."""
    if not baslik:
        return ""
    b = baslik.casefold()
    b = b.replace("\u0069\u0307", "i")  # İ casefold artefaktı (i + birleşik nokta)
    b = re.sub(r"[\u200b\ufeff\u0307]", "", b)
    b = b.replace("'", "").replace("\u2019", "").replace("\u0060", "")
    b = b.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s")
    b = b.replace("ö", "o").replace("ç", "c")
    b = re.sub(r"[^a-z0-9]+", " ", b)
    return RE_WHITESPACE.sub(" ", b).strip()


def anahtar_kelimeler(baslik):
    """Başlıktan konu anahtarları (gürültü/ilgisiz blok süzmek için)."""
    if not baslik:
        return set()
    ham = norm_baslik(baslik)
    return {w for w in ham.split() if len(w) >= 4 and w not in STOP_KELIME}


def konu_ilgisi(metin, anahtarlar):
    if not anahtarlar:
        return 1.0
    t = norm_baslik(metin)
    if not t:
        return 0.0
    hit = sum(1 for a in anahtarlar if a in t)
    return hit / max(1, min(4, len(anahtarlar)))


def baslik_gibi_mi(metin):
    """Kısa, haber başlığı tarzı satır mı? (ilgili haber listeleri)."""
    if not metin:
        return False
    t = metin.strip()
    if len(t) > 140 or len(t) < 18:
        return False
    if t.count(".") >= 2:
        return False
    if t.endswith((".", "…")) and len(t) > 90:
        return False
    return True


# ═══════════════════════════════════════════════════════════
# VİDEO / MEDYA
# ═══════════════════════════════════════════════════════════

def video_embed_url(url):
    """YouTube/Vimeo/Dailymotion izleme linkini gömülebilir adrese çevir."""
    if not url:
        return ""
    url = html.unescape(url).strip()
    if url.startswith("//"):
        url = "https:" + url
    url = url.replace("&amp;", "&")
    m = RE_YOUTUBE_ID.search(url)
    if m:
        return f"https://www.youtube.com/embed/{m.group(1)}"
    m = re.search(r"dailymotion\.com/(?:embed/video|video)/([a-zA-Z0-9]+)", url, re.I)
    if m:
        return f"https://www.dailymotion.com/embed/video/{m.group(1)}"
    m = re.search(r"(?:player\.)?vimeo\.com/(?:video/)?(\d+)", url, re.I)
    if m:
        return f"https://player.vimeo.com/video/{m.group(1)}"
    return url


def haber_videosu_mu(url):
    """Reklam/widget değil, habere ait gömülebilir video mi?"""
    if not url:
        return False
    u = url.strip()
    if not re.match(r"^https?://", u, re.I):
        return False
    if RE_VIDEO_REKLAM.search(u):
        return False
    return bool(RE_VIDEO_IPUCU.search(u))


def video_html(url):
    url_e = html.escape(url, quote=True)
    if re.search(r"\.(mp4|webm|ogg|m3u8)(\?|$)", url, re.I):
        return f'<video class="haber-video" controls preload="metadata" src="{url_e}"></video>'
    return (
        f'<div class="video-frame"><iframe src="{url_e}" title="Haber videosu" '
        f'frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; '
        f'gyroscope; picture-in-picture; fullscreen" allowfullscreen loading="lazy">'
        f'</iframe></div>'
    )


def videolari_html(urls):
    return "\n".join(video_html(u) for u in urls if u)


def videolari_metinden_cek(html_metin, taban=None):
    """HTML/özet içinden haber videolarını (YouTube, mp4, iframe) çıkar."""
    if not html_metin:
        return []
    adaylar = []
    for rx in (RE_IFRAME_SRC, RE_VIDEO_SRC, RE_SOURCE_SRC):
        adaylar.extend(m.group(1) for m in rx.finditer(html_metin))
    for m in RE_AMP_YT.finditer(html_metin):
        adaylar.append(f"https://www.youtube.com/embed/{m.group(1)}")
    for m in RE_YOUTUBE_ID.finditer(html_metin):
        adaylar.append(f"https://www.youtube.com/embed/{m.group(1)}")
    sonuc, gorulen = [], set()
    for ham in adaylar:
        u = video_embed_url(mutlak_yap(html.unescape(ham), taban))
        if u and u not in gorulen and haber_videosu_mu(u):
            gorulen.add(u)
            sonuc.append(u)
    return sonuc


def videolari_metne_ekle(videolar, govde):
    """Eksik videoları gövdenin başına ekle (yinelenmesin)."""
    govde = govde or ""
    eksik = [u for u in (videolar or []) if u and u not in govde]
    if not eksik:
        return govde
    return (videolari_html(eksik) + ("\n" if govde else "") + govde).strip()


def videolari_birlestir(*listeler):
    sonuc, gorulen = [], set()
    for liste in listeler:
        for u in liste or []:
            eu = video_embed_url(mutlak_yap(u))
            if eu and eu not in gorulen and haber_videosu_mu(eu):
                gorulen.add(eu)
                sonuc.append(eu)
    return sonuc


# ═══════════════════════════════════════════════════════════
# AĞ İŞLEMLERİ
# ═══════════════════════════════════════════════════════════

def http_cek(url, zaman_asimi=15, tekrar=1):
    """GET isteği; hatalarda basit yeniden deneme."""
    son_hata = None
    for deneme in range(tekrar + 1):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": KULLANICI_KIMLIK,
                "Accept": "application/rss+xml, application/xml, text/xml, text/html, */*",
                "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
            })
            with urllib.request.urlopen(req, timeout=zaman_asimi) as cev:
                return cev.read()
        except Exception as hata:
            son_hata = hata
            if deneme < tekrar:
                time.sleep(1.2 * (deneme + 1))
    raise son_hata


# ═══════════════════════════════════════════════════════════
# RSS / ATOM ÇÖZÜMLEME
# ═══════════════════════════════════════════════════════════

def _yerel_adi(etiket):
    return etiket.rsplit("}", 1)[-1].lower()


def _medya_url_kaydet(url, typ, alanlar, videolar):
    if not url:
        return
    typ = (typ or "").lower()
    if "video" in typ or haber_videosu_mu(url):
        videolar.append(url)
    else:
        alanlar.setdefault("media", url)


def beslemeyi_cozyu(ham, besleme, kaynak):
    """Bir XML beslemesinden haber dict listesi üret."""
    haberler = []
    try:
        kok = ET.fromstring(ham)
    except ET.ParseError as hata:
        raise RuntimeError(f"XML çözümlenemedi: {hata}")

    ogeler = [c for c in kok.iter() if _yerel_adi(c.tag) in ("item", "entry")]
    limit = besleme.get("limit", 10)
    taban = kaynak.get("resim_tabani")

    for oge in ogeler[:limit]:
        try:
            alanlar = {}
            videolar_rss = []
            icin = [oge] + list(oge.iter())
            for og in icin:
                if og.tag is None or isinstance(og.tag, type(ET.Comment)):
                    continue
                ad = _yerel_adi(og.tag)
                if ad in ("item", "entry", "channel", "feed"):
                    continue
                ns_media = "media" in (og.tag or "")
                if ad == "link":
                    href = og.attrib.get("href") or og.attrib.get("url") or (og.text or "")
                    if og.attrib.get("rel", "alternate") == "alternate" or href:
                        alanlar.setdefault("link", (og.text or "") or href or "")
                elif ad == "image" and not ns_media:
                    continue
                elif ad == "enclosure":
                    _medya_url_kaydet(
                        og.attrib.get("url", ""),
                        og.attrib.get("type") or og.attrib.get("medium"),
                        alanlar, videolar_rss)
                elif ns_media and ad in ("content", "thumbnail", "player"):
                    _medya_url_kaydet(
                        og.attrib.get("url") or og.attrib.get("href") or "",
                        og.attrib.get("type") or og.attrib.get("medium") or ad,
                        alanlar, videolar_rss)
                    metin = (og.text or "").strip()
                    if len(metin) > len((alanlar.get("html") or "").strip()):
                        alanlar["html"] = metin
                        alanlar["desc"] = metin
                elif ad in ("content", "contentencoded", "encoded"):
                    metin = og.text or ""
                    if len(metin.strip()) > len((alanlar.get("html") or "").strip()):
                        alanlar["html"] = metin
                        alanlar["desc"] = metin
                elif ad == "description":
                    metin = og.text or ""
                    alanlar.setdefault("desc", metin)
                    if len(metin.strip()) > len((alanlar.get("html") or "").strip()):
                        alanlar["html"] = metin
                elif ad == "summary":
                    alanlar.setdefault("summary", og.text or "")
                elif ad == "title":
                    alanlar.setdefault("title", og.text or "")
                elif ad in ("pubdate", "published", "updated", "date"):
                    alanlar.setdefault("tarih", (og.text or "").strip())
                elif ad == "category":
                    alanlar.setdefault("kategorya", (og.text or "").strip())
            baslik = temiz_metin(alanlar.get("title", ""))
            link = (alanlar.get("link") or "").strip()
            if not baslik or not link:
                continue
            link = mutlak_yap(link, taban)
            desc = alanlar.get("html") or alanlar.get("desc") or alanlar.get("summary") or ""
            temiz_desc = temiz_metin(desc)
            aciklama = temiz_desc[:400]
            resim = _resmi_bul(desc) or mutlak_yap(
                alanlar.get("media") or alanlar.get("enclosure"), taban)
            ham_kat = (alanlar.get("kategorya") or "").strip().lower()
            kategori = KATEGORI_ESLEME.get(ham_kat) or besleme.get("kategori", "Gündem")
            tam_metin, videolar, yeterli = _rss_govde_uret(desc, temiz_desc, baslik, taban)
            videolar = videolari_birlestir(videolar, videolar_rss)
            tam_metin = videolari_metne_ekle(videolar, tam_metin)
            haberler.append({
                "kategori": kategori,
                "baslik": baslik,
                "link": link,
                "aciklama": aciklama,
                "tam_metin": tam_metin,
                "tam": yeterli and metin_yeterli(tam_metin),
                "videolar": videolar,
                "resim": resim,
                "tarih": tarihi_parsel(alanlar.get("tarih")) or datetime.now(timezone.utc).isoformat(),
                "kaynak": kaynak["ad"],
                "kaynak_id": kaynak["id"],
            })
        except Exception:
            continue
    return haberler


def _resmi_bul(html_metin):
    """Açıklama HTML'inden ilk uygun görseli çıkar."""
    if not html_metin:
        return None
    for m in re.finditer(r"<img[^>]+>", html_metin, re.I):
        etiket = m.group(0)
        src = re.search(r"(?:src|data-src)\s*=\s*[\"']([^\"']+)[\"']", etiket, re.I)
        if src:
            url = html.unescape(src.group(1)).strip()
            if url and not RE_GORSEL_GECERSIZ.search(url):
                return url
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html_metin, re.I)
    if m:
        return html.unescape(m.group(1)).strip()
    return None


def _html_paragraflari(html_metin, baslik=""):
    """RSS HTML açıklamasındaki <p> bloklarını gürültü süzerek al."""
    if not html_metin or not re.search(r"<p[>\s]", html_metin, re.I):
        return ""
    anahtarlar = anahtar_kelimeler(baslik)
    parcalar, kelime_toplam = [], 0
    for b in re.findall(r"<p[^>]*>(.*?)</p>", html_metin, re.I | re.S):
        metin = temiz_metin(b)
        if len(metin) < MIN_PARAGRAF_KARAKTER or RE_ILAN.search(metin):
            continue
        if (kelime_toplam >= MIN_HABER_KELIME and baslik_gibi_mi(metin)
                and konu_ilgisi(metin, anahtarlar) < 0.2):
            continue
        parcalar.append(f"<p>{html.escape(metin)}</p>")
        kelime_toplam += len(metin.split())
    return "\n".join(parcalar)


def _rss_govde_uret(desc, temiz_desc, baslik="", taban=None):
    """RSS açıklamasından (1) videolar (2) haber paragrafları.

    Yalnızca görsel/video tam metin SAYILMAZ — aksi halde sayfa kazısı atlanır.
    """
    videolar = videolari_metinden_cek(desc, taban)
    govde = _html_paragraflari(desc, baslik)
    if kelime_sayisi(govde) < MIN_HABER_KELIME:
        uzun = aciklamadan_tam_metin(temiz_desc)
        if kelime_sayisi(uzun) > kelime_sayisi(govde):
            govde = uzun
    yeterli = metin_yeterli(govde)
    # Görseller kahraman görsel olarak kartta durur; gövdeye yalnız metin+video
    tam_metin = govde if yeterli else ""
    return tam_metin, videolar, yeterli


def _html_icerik(html_metin):
    """Geriye dönük: açıklama HTML'inden video/görsel gömümü (metin değil)."""
    if not html_metin:
        return ""
    videolar = videolari_metinden_cek(html_metin)
    parcalar = [videolari_html(videolar)] if videolar else []
    for m in re.finditer(r"<img[^>]+>", html_metin, re.I):
        src = re.search(r"(?:src|data-src)\s*=\s*[\"']([^\"']+)[\"']", m.group(0), re.I)
        if not src:
            continue
        url = html.unescape(src.group(1))
        if re.match(r"^https?://", url) and not RE_GORSEL_GECERSIZ.search(url):
            parcalar.append(f'<img class="inline-article-img" src="{html.escape(url, quote=True)}" alt="">')
            break
    return "\n".join(p for p in parcalar if p)


def paragraflara_bol(metin):
    """Düz metni okunabilir paragraflara ayırır (RSS açıklamaları için)."""
    parcalar = [p.strip() for p in re.split(r"\n\s*\n+", metin) if len(p.strip()) > 20]
    if len(parcalar) <= 1:
        tek = (parcalar or [metin])[0]
        cumleler = re.split(r"(?<=[.!?])\s+(?=[A-ZÇĞİÖŞÜ\"'(])", tek)
        gruplar, g = [], []
        for c in cumleler:
            g.append(c)
            if len(" ".join(g)) > 350:
                gruplar.append(" ".join(g).strip())
                g = []
        if g:
            gruplar.append(" ".join(g).strip())
        parcalar = gruplar
    return parcalar


def aciklamadan_tam_metin(temiz):
    """Uzun RSS açıklamasını (ör. Hürriyet tam metin beslemesi) <p> bloklarına çevirir."""
    if not temiz or len(temiz) < 500:
        return ""
    parcalar = paragraflara_bol(temiz)
    return "\n".join(f"<p>{html.escape(p)}</p>" for p in parcalar if len(p) > 20)


def metni_html_paragraf(metin):
    """JSON-LD articleBody gibi düz metni paragraf HTML'ine çevir (500 eşiği yok)."""
    t = temiz_metin(metin)
    if not t or len(t) < 80:
        return ""
    if "<p" in (metin or "").lower():
        return _html_paragraflari(metin)
    if len(t) >= 500:
        return aciklamadan_tam_metin(t)
    return "\n".join(f"<p>{html.escape(p)}</p>" for p in paragraflara_bol(t) if len(p) > 20)


# ═══════════════════════════════════════════════════════════
# TAM METİN KAZIMI (akıllı, alan adı seçmez)
# ═══════════════════════════════════════════════════════════

def _og_degisken(html_ham, ad):
    m = re.search(
        rf'<meta[^>]+(?:property|name)\s*=\s*["\']{ad}["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
        html_ham, re.I) or re.search(
        rf'<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]+(?:property|name)\s*=\s*["\']{ad}["\']',
        html_ham, re.I)
    return html.unescape(m.group(1)).strip() if m else None


def _jsonld_nesneler(data):
    if data is None:
        return
    if isinstance(data, list):
        for x in data:
            yield from _jsonld_nesneler(x)
        return
    if not isinstance(data, dict):
        return
    yield data
    if "@graph" in data:
        yield from _jsonld_nesneler(data["@graph"])


def _jsonld_tip(obj):
    t = obj.get("@type") or obj.get("type") or ""
    if isinstance(t, list):
        t = " ".join(str(x) for x in t)
    return str(t).lower()


def _jsonld_video_url(obj):
    for anahtar in ("embedUrl", "embedURL", "contentUrl", "contentURL", "url"):
        v = obj.get(anahtar)
        if isinstance(v, str) and v:
            return v
        if isinstance(v, dict):
            u = v.get("url") or v.get("@id")
            if u:
                return u
    return None


def _jsonld_haber(html_ham):
    """schema.org NewsArticle / VideoObject alanlarını topla."""
    govde, videolar, resim = "", [], None
    for m in re.finditer(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html_ham, re.I | re.S):
        ham = html.unescape(m.group(1)).strip()
        ham = re.sub(r"/\*.*?\*/", "", ham, flags=re.S)
        try:
            data = json.loads(ham)
        except Exception:
            continue
        for obj in _jsonld_nesneler(data):
            tip = _jsonld_tip(obj)
            if "newsarticle" in tip or tip == "article" or "reportage" in tip:
                body = obj.get("articleBody") or obj.get("articlebody") or obj.get("text")
                if isinstance(body, dict):
                    body = body.get("@value") or body.get("value")
                if isinstance(body, str) and kelime_sayisi(body) > kelime_sayisi(govde):
                    govde = metni_html_paragraf(body) or govde
                img = obj.get("image")
                if isinstance(img, str):
                    resim = resim or img
                elif isinstance(img, dict):
                    resim = resim or img.get("url")
                elif isinstance(img, list) and img:
                    ilk = img[0]
                    resim = resim or (ilk if isinstance(ilk, str) else (ilk or {}).get("url"))
                vid = obj.get("video")
                adaylar = vid if isinstance(vid, list) else ([vid] if vid else [])
                for v in adaylar:
                    if isinstance(v, str):
                        videolar.append(v)
                    elif isinstance(v, dict):
                        u = _jsonld_video_url(v)
                        if u:
                            videolar.append(u)
            if "videoobject" in tip:
                u = _jsonld_video_url(obj)
                if u:
                    videolar.append(u)
    return govde, videolari_birlestir(videolar), resim


def _medya_cek(soup, taban=None):
    """Sayfadaki haber videolarını toplar (YouTube dahil, reklam hariç)."""
    medya, eklenen = [], set()

    def ekle(src):
        if not src:
            return
        src = video_embed_url(mutlak_yap(src.strip(), taban))
        if src and src not in eklenen and haber_videosu_mu(src):
            eklenen.add(src)
            medya.append(src)

    for iframe in soup.find_all(["iframe", "amp-iframe"]):
        ekle(iframe.get("src") or iframe.get("data-src") or iframe.get("data-lazy-src"))
    for amp in soup.find_all("amp-youtube"):
        vid = amp.get("data-videoid") or amp.get("data-video-id")
        if vid:
            ekle(f"https://www.youtube.com/embed/{vid}")
    for vid in soup.find_all(["video", "amp-video"]):
        src = vid.get("src") or vid.get("data-src")
        if not src:
            s = vid.find("source")
            src = (s.get("src") if s else None) or (s.get("data-src") if s else None)
        ekle(src)
    for el in soup.find_all(attrs={"data-youtube": True}):
        ekle(el.get("data-youtube"))
    for el in soup.find_all(attrs={"data-videoid": True}):
        v = el.get("data-videoid")
        if v and re.match(r"^[\w-]{11}$", v):
            ekle(f"https://www.youtube.com/embed/{v}")
    return medya


def _gecerli_p_sayisi(kabi):
    return sum(1 for p in kabi.find_all("p")
               if len(p.get_text(strip=True)) >= MIN_PARAGRAF_KARAKTER
               and not RE_ILAN.search(p.get_text(strip=True)))


def _govde_skoru(el):
    if el is None:
        return -1
    text = el.get_text(" ", strip=True)
    n = len(text)
    if n < 60:
        return 0
    link_len = sum(len(a.get_text(strip=True)) for a in el.find_all("a"))
    density = link_len / max(n, 1)
    ps = _gecerli_p_sayisi(el)
    score = n * 0.12 + ps * 90
    score *= max(0.08, 1 - min(density, 0.92))
    ipucu = " ".join([el.get("id") or ""] + list(el.get("class") or []) + [el.get("itemprop") or ""])
    if (el.get("itemprop") or "").lower() == "articlebody":
        score *= 2.2
    if RE_icerik_sinif.search(ipucu):
        score *= 1.25
    if RE_ATILACAK_SINIF.search(ipucu):
        score *= 0.15
    return score


def _gurultu_kabini_at(soup):
    """Paylaş / ilgili haber / reklam / çerez kaplarını haber gövdesinden ayır."""
    atilacak = []
    for el in soup.find_all(True):
        if not getattr(el, "attrs", None):
            continue
        if el.get("itemprop") and "articlebody" in str(el.get("itemprop")).lower():
            continue
        ipucu = " ".join([el.get("id") or ""] + list(el.get("class") or []))
        if ipucu and RE_ATILACAK_SINIF.search(ipucu):
            atilacak.append(el)
    for el in atilacak:
        if getattr(el, "parent", None) is not None:
            el.decompose()


def _icerik_kabini_bul(soup):
    """Haber gövdesinin kabını seçer (alan adı seçmez, kademeli strateji).

    1) itemprop=articleBody
    2) class/id ipucu + metin yoğunluğu (bağlantı cezası)
    3) <article> / <main> / body
    """
    body = soup.find(attrs={"itemprop": re.compile(r"articleBody", re.I)})
    if body is not None and (_gecerli_p_sayisi(body) >= 1 or len(body.get_text(strip=True)) > 200):
        return body

    adaylar = []
    for el in soup.find_all(["div", "section", "article", "main"]):
        ipucu = " ".join([el.get("id") or ""] + list(el.get("class") or []))
        if RE_icerik_sinif.search(ipucu) or el.name in ("article", "main"):
            adaylar.append(el)
    if not adaylar:
        adaylar = [a for a in (soup.find("article"), soup.find("main"), soup.body) if a is not None]
    if not adaylar:
        return soup.body or soup
    return max(adaylar, key=_govde_skoru)


def _icerik_cek(icerik_kabi, baslik=""):
    """Seçili kabın içinden yalnızca haberle ilgili blokları toplar."""
    parcalar = []
    kelime_toplam = 0
    anahtarlar = anahtar_kelimeler(baslik)
    gorulen = set()

    for og_ele in icerik_kabi.find_all(["p", "h2", "h3", "h4", "ul", "ol", "blockquote"]):
        ad = og_ele.name
        if ad == "p" and og_ele.find_parent(["ul", "ol", "blockquote", "li"]):
            continue
        if ad in ("ul", "ol") and og_ele.find_parent(["ul", "ol"]):
            continue

        metin = og_ele.get_text(" ", strip=True)
        if ad in ("h2", "h3", "h4") and RE_BOLUM_DUR.search(metin or ""):
            break
        if not metin:
            continue
        if RE_ILAN.search(metin):
            continue

        min_len = 12 if ad in ("h2", "h3", "h4") else MIN_PARAGRAF_KARAKTER
        if len(metin) < min_len:
            continue

        anahtar = norm_baslik(metin)[:180]
        if anahtar in gorulen:
            continue

        if ad in ("ul", "ol"):
            maddeler = []
            for li in og_ele.find_all("li"):
                t = li.get_text(" ", strip=True)
                if not t or RE_ILAN.search(t) or RE_PAYLAS.search(t):
                    continue
                maddeler.append(t)
            if not maddeler:
                continue
            paylas_say = sum(1 for t in maddeler if RE_PAYLAS.search(t))
            if paylas_say >= max(2, int(len(maddeler) * 0.6)):
                continue
            if len(maddeler) >= 3 and kelime_toplam >= MIN_HABER_KELIME:
                kisa = sum(1 for t in maddeler if len(t) < 120)
                ilgili = sum(1 for t in maddeler if konu_ilgisi(t, anahtarlar) >= 0.2)
                if kisa >= len(maddeler) - 1 and ilgili <= 1:
                    continue
            liseler = "".join(
                f"<li>{html.escape(t)}</li>" for t in maddeler if len(t) >= 12)
            if liseler:
                parcalar.append(f"<{ad}>{liseler}</{ad}>")
                gorulen.add(anahtar)
                kelime_toplam += kelime_sayisi(" ".join(maddeler))
            continue

        # İlgili haber başlığı gibi kısa, konudan kopuk satırlar (gövde yeterince dolduktan sonra)
        if (kelime_toplam >= MIN_HABER_KELIME and len(parcalar) >= 2
                and baslik_gibi_mi(metin) and konu_ilgisi(metin, anahtarlar) < 0.2):
            continue

        gorulen.add(anahtar)
        if ad in ("h2", "h3", "h4"):
            parcalar.append(f"<{ad}>{html.escape(metin)}</{ad}>")
        elif ad == "blockquote":
            parcalar.append(f"<blockquote>{html.escape(metin)}</blockquote>")
        else:
            parcalar.append(f"<p>{html.escape(metin)}</p>")
        kelime_toplam += len(metin.split())
    return "\n".join(parcalar)


def _sinirda_kes(html_metin, sinir):
    if len(html_metin) <= sinir:
        return html_metin, False
    kes = html_metin[:sinir]
    son = kes.rfind("</p>")
    if son >= int(sinir * 0.5):
        kes = kes[:son + 4]
    return kes, True


def haber_detayini_cek(url, zaman_asimi=12, metin_siniri=20000):
    """Haber sayfasından başlık, özet, görsel, video ve paragrafları çıkar.

    Dönüş: (baslik, tam_metin_html, resim, ozet, kisitli)
    """
    try:
        html_ham = http_cek(url, zaman_asimi).decode("utf-8", errors="ignore")
    except Exception:
        return None, "", None, None, False

    baslik = _og_degisken(html_ham, "og:title")
    resim = _og_degisken(html_ham, "og:image") or _og_degisken(html_ham, "twitter:image")
    ozet = _og_degisken(html_ham, "og:description") or _og_degisken(html_ham, "description")
    ozet = temiz_metin(ozet)[:400] if ozet else None

    jsonld_govde, jsonld_videolar, jsonld_resim = _jsonld_haber(html_ham)
    if jsonld_resim and not resim:
        resim = jsonld_resim

    og_videolar = []
    for ad in ("og:video:secure_url", "og:video:url", "og:video", "twitter:player"):
        v = _og_degisken(html_ham, ad)
        if v:
            og_videolar.append(v)

    sayfa_videolar = videolari_metinden_cek(html_ham, url)
    icerik_html = ""
    medya = []

    if BSAVULUMU_VAR:
        soup = BeautifulSoup(html_ham, "html.parser")
        for t in soup(["script", "style", "noscript", "form", "nav", "footer", "aside", "header"]):
            t.decompose()
        _gurultu_kabini_at(soup)

        medya = _medya_cek(soup, url)
        icerik_kabi = _icerik_kabini_bul(soup)
        icerik_html = _icerik_cek(icerik_kabi, baslik or "")

        gorseller = []
        for img in icerik_kabi.find_all("img"):
            src = img.get("src") or img.get("data-src") or img.get("data-lazy-src") or ""
            src = mutlak_yap(src, url)
            if re.match(r"^https?://", src) and not RE_GORSEL_GECERSIZ.search(src) \
                    and src != (resim or "") and src not in gorseller:
                gorseller.append(
                    f'<img class="inline-article-img" src="{html.escape(src, quote=True)}" alt="">')
            if len(gorseller) >= 2:
                break
        if gorseller:
            icerik_html = "\n".join(gorseller[:1]) + "\n" + icerik_html
    else:
        icerik_html = _html_paragraflari(html_ham, baslik or "")
        if not icerik_html:
            for p in re.findall(r"<p[^>]*>(.*?)</p>", html_ham, re.S | re.I):
                metin = temiz_metin(p)
                if len(metin) >= MIN_PARAGRAF_KARAKTER and not RE_ILAN.search(metin):
                    icerik_html += f"<p>{html.escape(metin)}</p>\n"

    # JSON-LD gövdesi daha uzun ve temizse onu tercih et (HTML yapısı yetmezse)
    if kelime_sayisi(jsonld_govde) > kelime_sayisi(icerik_html) * 1.15 \
            and kelime_sayisi(jsonld_govde) >= MIN_HABER_KELIME:
        # HTML'den gelen görseli koru
        gorsel_html = ""
        mimg = re.search(r'<img class="inline-article-img"[^>]+>', icerik_html or "")
        if mimg:
            gorsel_html = mimg.group(0) + "\n"
        icerik_html = gorsel_html + jsonld_govde
    elif not metin_yeterli(icerik_html) and jsonld_govde:
        icerik_html = (icerik_html + "\n" + jsonld_govde).strip()

    videolar = videolari_birlestir(medya, jsonld_videolar, og_videolar, sayfa_videolar)
    tam = videolari_metne_ekle(videolar, icerik_html).strip()
    tam, kisitli = _sinirda_kes(tam, metin_siniri)
    return baslik, tam, resim, ozet, kisitli


def kazi_tam_metin(haberler, sinir, zaman_asimi, metin_siniri, calisan, args):
    """Metni yetersiz haberlerin sayfasını kazır.

    sinir: 0 = sınırsız (tümü). Negatif çağırılmaz.
    Yalnızca görsel içeren RSS gövdesi 'tam' sayılmaz.
    """
    hedefler = [h for h in haberler if not h.get("tam") or not metin_yeterli(h.get("tam_metin"))]
    hedefler.sort(key=lambda h: h["tarih"], reverse=True)
    if sinir and sinir > 0:
        hedefler = hedefler[:sinir]
    if not hedefler:
        return 0
    log(f"Tam metin kazımı: {len(hedefler)} haber ({calisan} işçi)...", False, args)
    kazinan = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=calisan) as havuz:
        futures = {havuz.submit(haber_detayini_cek, h["link"], zaman_asimi, metin_siniri): h
                   for h in hedefler}
        for fut in concurrent.futures.as_completed(futures):
            h = futures[fut]
            try:
                baslik, icerik, resim, ozet, kisitli = fut.result()
            except Exception:
                continue
            if baslik and len(baslik) > 8:
                h["baslik"] = baslik
            videolar_yeni = videolari_metinden_cek(icerik)
            h["videolar"] = videolari_birlestir(h.get("videolar"), videolar_yeni)
            if icerik:
                eski = h.get("tam_metin") or ""
                if kelime_sayisi(icerik) >= kelime_sayisi(eski):
                    h["tam_metin"] = videolari_metne_ekle(h["videolar"], icerik)
                else:
                    h["tam_metin"] = videolari_metne_ekle(h["videolar"], eski)
                h["tam"] = (not kisitli) and metin_yeterli(h["tam_metin"])
            if resim:
                h["resim"] = resim
            if ozet and len(ozet) > len(h.get("aciklama") or ""):
                h["aciklama"] = ozet
            if icerik or resim or videolar_yeni:
                kazinan += 1
            time.sleep(getattr(args, "kaydirma", 0.15))
    return kazinan


def haberleri_son_isle(haberler):
    """Boş gövde kalmasın, videolar sayfaya gömülsün, 'tam' tutarlı olsun."""
    for h in haberler:
        videolar = videolari_birlestir(
            h.get("videolar"),
            videolari_metinden_cek(h.get("tam_metin") or ""),
            videolari_metinden_cek(h.get("aciklama") or ""),
        )
        h["videolar"] = videolar
        govde = h.get("tam_metin") or ""
        govde = videolari_metne_ekle(videolar, govde)
        if kelime_sayisi(govde) < 12 and h.get("aciklama"):
            acik = temiz_metin(h["aciklama"])
            if acik and acik not in temiz_metin(govde):
                govde = (govde + f"\n<p>{html.escape(acik)}</p>").strip()
        h["tam_metin"] = govde.strip()
        h["tam"] = metin_yeterli(h["tam_metin"])
    return haberler


# ═══════════════════════════════════════════════════════════
# ANA AKIŞ
# ═══════════════════════════════════════════════════════════

def besleme_cek(besleme, kaynak, ayarlar, args, fixture_dir=None):
    """Tek bir beslemeyi indir + çözümler (fixture modu destekler)."""
    url = besleme["url"]
    ham = None
    if fixture_dir:
        dosya_adı = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:80]
        adaylar = [os.path.join(fixture_dir, dosya_adı + ".xml"),
                   os.path.join(fixture_dir, dosya_adı + ".rss"),
                   os.path.join(fixture_dir, dosya_adı)]
        for aday in adaylar:
            if os.path.exists(aday):
                with open(aday, "rb") as f:
                    ham = f.read()
                break
    if ham is None:
        ham = http_cek(url, ayarlar["zaman_asimi_saniye"], ayarlar.get("tekrar_dene", 1))
    return beslemeyi_cozyu(ham, besleme, kaynak)


def calisdir(args):
    baslangic = time.time()
    with open(args.config, encoding="utf-8") as f:
        yapılandırma = json.load(f)

    ayarlar = yapılandırma.get("bot", {})
    kategoriler = yapılandırma.get("kategoriler", [])
    kaynaklar = [k for k in yapılandırma.get("kaynaklar", []) if k.get("aktif", True)]

    log(f"== {ayarlar.get('ad', 'Haber Botu')} v{ayarlar.get('surum', '?')} ==", False, args)
    log(f"{len(kaynaklar)} kaynak aktif", True, args)

    görevler = []
    for kaynak in kaynaklar:
        for besleme in kaynak.get("beslemeler", []):
            if args.limit:
                besleme = dict(besleme, limit=args.limit)
            görevler.append((kaynak, besleme))
    log(f"{len(görevler)} RSS beslemesi kuyruğa alındı", False, args)

    tüm_haberler = []
    kaynak_durumu = {}
    hatalar = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=ayarlar.get("calisan_sayisi", 8)) as havuz:
        futures = {}
        for kaynak, besleme in görevler:
            fut = havuz.submit(besleme_cek, besleme, kaynak, ayarlar, args, args.fixture)
            futures[fut] = (kaynak, besleme)
        for fut in concurrent.futures.as_completed(futures):
            kaynak, besleme = futures[fut]
            durum = kaynak_durumu.setdefault(
                kaynak["ad"], {"haber": 0, "durum": "aktif", "basarili": 0, "hatali": 0, "hata": None})
            try:
                haberler = fut.result()
                durum["haber"] += len(haberler)
                durum["basarili"] += 1
                tüm_haberler.extend(haberler)
                log(f"✓ {kaynak['ad']} / {besleme['kategori']}: {len(haberler)} haber", True, args)
            except Exception as hata:
                durum["hatali"] += 1
                durum["hata"] = str(hata)[:200]
                hatalar.append(f"{kaynak['ad']} ({besleme['url']}): {hata}")
                log(f"✗ {kaynak['ad']} ({besleme['url']}): {hata}", False, args)
    for durum in kaynak_durumu.values():
        durum["durum"] = "aktif" if durum["basarili"] > 0 else "hata"

    # ── Tekilleştirme ─────────────────────────────────────
    görülen = set()
    benzersiz = []
    for h in tüm_haberler:
        anahtar = (norm_baslik(h["baslik"]), h["link"])
        if anahtar in görülen:
            continue
        görülen.add(anahtar)
        benzersiz.append(h)

    benzersiz.sort(key=lambda h: h["tarih"], reverse=True)
    benzersiz = benzersiz[:ayarlar.get("maksimum_haber", 250)]

    # ── Tam metin kazımı ─────────────────────────────────
    kazinan = 0
    if ayarlar.get("tam_metin_kazimi") and args.crawl is not None and args.crawl >= 0:
        kazinan = kazi_tam_metin(
            benzersiz, args.crawl,
            ayarlar.get("zaman_asimi_saniye", 12),
            ayarlar.get("sayfa_metin_siniri", 20000),
            ayarlar.get("kazimi_calisani", 8),
            args)

    haberleri_son_isle(benzersiz)

    # ── Son dakika işareti + kimlik ──────────────────────
    sd_dakika = ayarlar.get("son_dakika_suresi_dakika", 45)
    simdi = datetime.now(timezone.utc)
    for i, h in enumerate(benzersiz):
        h["id"] = hashlib.md5(h["link"].encode()).hexdigest()[:12]
        h["sirala"] = i
        try:
            yayim = datetime.fromisoformat(h["tarih"])
            h["son_dakika"] = (simdi - yayim).total_seconds() <= sd_dakika * 60
        except Exception:
            h["son_dakika"] = False

    # ── Çıktılar ─────────────────────────────────────────
    for h in benzersiz:
        h["kaynak_url"] = urllib.parse.urlparse(h["link"]).netloc

    with open(args.cikti, "w", encoding="utf-8") as f:
        json.dump(benzersiz, f, ensure_ascii=False, indent=2)
    log(f"→ {args.cikti}: {len(benzersiz)} haber", False, args)

    # Rapor
    video_haber = sum(1 for h in benzersiz if h.get("videolar"))
    tam_haber = sum(1 for h in benzersiz if h.get("tam"))
    rapor = {
        "surum": ayarlar.get("surum", "2.1"),
        "son_guncelleme": simdi.isoformat(),
        "sure_saniye": round(time.time() - baslangic, 1),
        "toplam_haber": len(benzersiz),
        "kaynak_sayisi": len(kaynaklar),
        "aktif_kaynak": sum(1 for d in kaynak_durumu.values() if d["durum"] == "aktif"),
        "besleme_sayisi": len(görevler),
        "kazanilan_tam_metin": kazinan,
        "tam_metin_haber": tam_haber,
        "video_haber": video_haber,
        "kategoriler": {k: 0 for k in kategoriler},
        "kaynaklar": kaynak_durumu,
        "hatalar": hatalar,
    }
    for h in benzersiz:
        if h["kategori"] in rapor["kategoriler"]:
            rapor["kategoriler"][h["kategori"]] += 1
    with open(args.rapor, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    log(f"→ {args.rapor}: {rapor['aktif_kaynak']}/{rapor['kaynak_sayisi']} kaynak aktif, "
        f"{tam_haber} tam metin, {video_haber} videolu", False, args)

    # Sitenin kendi RSS akışları
    if ayarlar.get("feed_uret") and not args.no_feeds:
        os.makedirs(args.feed_dizini, exist_ok=True)
        akislar = {"tum": benzersiz}
        for k in kategoriler:
            akislar[k] = [h for h in benzersiz if h["kategori"] == k]
        for ad, liste in akislar.items():
            dosya = os.path.join(args.feed_dizini, feed_slug(ad) + ".xml")
            with open(dosya, "w", encoding="utf-8") as f:
                f.write(_feed_olustur(ad, liste))
        log(f"→ {args.feed_dizini}/: {len(akislar)} RSS akışı üretildi", False, args)

    log(f"Tamamlandı: {rapor['sure_saniye']} sn, {len(benzersiz)} haber, "
        f"{len(hatalar)} hata", False, args)
    return 0


def feed_slug(ad):
    """Kategori adından URL dostu dosya adı üret: 'Yaşam & Sanat' -> 'yasam-sanat'."""
    t = ad.lower()
    for k, v in [("ş", "s"), ("ğ", "g"), ("ü", "u"), ("ı", "i"), ("ö", "o"),
                 ("ç", "c"), ("â", "a"), ("î", "i")]:
        t = t.replace(k, v)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "tum"


def _feed_olustur(ad, haberler):
    import datetime as _dt
    an = _dt.datetime.now(_dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    g = lambda s: (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    ogeler = []
    for h in haberler[:40]:
        ogeler.append(
            f"    <item>\n"
            f"      <title>{g(h['baslik'])}</title>\n"
            f"      <link>{g(h['link'])}</link>\n"
            f"      <guid isPermaLink=\"true\">{g(h['link'])}</guid>\n"
            f"      <category>{g(h['kategori'])}</category>\n"
            f"      <description>{g(h['aciklama'][:300])} — {g(h['kaynak'])}</description>\n"
            f"      <pubDate>{g(h['tarih'])}</pubDate>\n"
            f"    </item>")
    isim = "GÜNDEM Tüm Haberler" if ad == "tum" else f"GÜNDEM {ad}"
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0">\n'
        "  <channel>\n"
        f"    <title>{isim}</title>\n"
        "    <link>./</link>\n"
        f"    <description>{isim} RSS akışı</description>\n"
        "    <language>tr</language>\n"
        f"    <lastBuildDate>{an}</lastBuildDate>\n"
        + "\n".join(ogeler) +
        "\n  </channel>\n</rss>\n")


def main():
    p = argparse.ArgumentParser(description="GÜNDEM Haber Botu")
    p.add_argument("--config", default="sources.json")
    p.add_argument("--cikti", default="haberler.json")
    p.add_argument("--rapor", default="bot-raporu.json")
    p.add_argument("--feed-dizini", default="feeds")
    p.add_argument("--crawl", type=int, default=None,
                   help="Kaç haberin tam metni kazılsın (0=sınırsız, -1=kapalı, varsayılan: yapılandırma)")
    p.add_argument("--limit", type=int, default=None, help="Besleme başına haber limiti (test)")
    p.add_argument("--no-feeds", action="store_true", help="RSS akışı üretme")
    p.add_argument("--fixture", default=None,
                   help="Ağ yerine bu dizindeki XML dosyalarını kullan (test)")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args()
    args.kaydirma = 0.15
    if args.crawl is None:
        args.crawl = 0
        try:
            with open(args.config, encoding="utf-8") as f:
                bot = json.load(f).get("bot", {})
            if bot.get("tam_metin_kazimi"):
                args.crawl = int(bot.get("tam_metin_siniri", 0))
        except Exception:
            pass
    sys.exit(calisdir(args))


if __name__ == "__main__":
    main()
