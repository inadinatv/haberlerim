#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GÜNDEM Haber Botu v2.0
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


def beslemeyi_cozyu(ham, besleme, kaynak):
    """Bir XML beslemesinden haber dict listesi üret."""
    haberler = []
    try:
        kok = ET.fromstring(ham)
    except ET.ParseError as hata:
        raise RuntimeError(f"XML çözümlenemedi: {hata}")

    ogeler = [c for c in kok.iter() if _yerel_adi(c.tag) in ("item", "entry")]
    limit = besleme.get("limit", 10)

    for oge in ogeler[:limit]:
        try:
            alanlar = {}
            icin = [oge] + list(oge.iter())
            for og in icin:
                if og.tag is None or isinstance(og.tag, type(ET.Comment)):
                    continue
                ad = _yerel_adi(og.tag)
                if ad in ("item", "entry", "channel", "feed"):
                    continue
                if ad not in alanlar:
                    if ad == "link":
                        # Atom: <link href="...">, RSS: <link>url</link>
                        href = og.attrib.get("href") or og.attrib.get("url") or (og.text or "")
                        if og.attrib.get("rel", "alternate") == "alternate" or href:
                            alanlar["link"] = (og.text or "") or href or ""
                    elif ad == "image":
                        continue
                    elif ad in ("content", "contentencoded", "encoded"):
                        alanlar.setdefault("desc", og.text or "")
                        alanlar.setdefault("html", og.text or "")
                    elif ad == "description":
                        alanlar.setdefault("desc", og.text or "")
                        alanlar.setdefault("html", og.text or "")
                    elif ad == "summary":
                        alanlar.setdefault("summary", og.text or "")
                    elif ad == "title":
                        alanlar.setdefault("title", og.text or "")
                    elif ad in ("pubdate", "published", "updated", "date"):
                        alanlar.setdefault("tarih", (og.text or "").strip())
                    elif ad == "category":
                        alanlar.setdefault("kategorya", (og.text or "").strip())
                    elif ad == "enclosure":
                        alanlar.setdefault("enclosure", og.attrib.get("url", ""))
                    elif ad in ("content", "thumbnail") and "media" in og.tag:
                        alanlar.setdefault("media", og.attrib.get("url", ""))
            baslik = temiz_metin(alanlar.get("title", ""))
            link = (alanlar.get("link") or "").strip()
            if not baslik or not link:
                continue
            link = mutlak_yap(link, kaynak.get("resim_tabani"))
            desc = alanlar.get("html") or alanlar.get("desc") or alanlar.get("summary") or ""
            temiz_desc = temiz_metin(desc)
            aciklama = temiz_desc[:400]
            resim = _resmi_bul(desc) or mutlak_yap(
                alanlar.get("media") or alanlar.get("enclosure"), kaynak.get("resim_tabani"))
            ham_kat = (alanlar.get("kategorya") or "").strip().lower()
            kategori = KATEGORI_ESLEME.get(ham_kat) or besleme.get("kategori", "Gündem")
            # 1) açıklamadaki görsel/video embed'leri
            tam_metin = _html_icerik(desc)
            # 2) açıklama uzunsa (ör. Hürriyet tam metin beslemesi) paragraflara böl
            if not tam_metin:
                tam_metin = aciklamadan_tam_metin(temiz_desc)
            haberler.append({
                "kategori": kategori,
                "baslik": baslik,
                "link": link,
                "aciklama": aciklama,
                "tam_metin": tam_metin,
                "tam": bool(tam_metin),
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
            if url and "logo" not in url.lower() and "icon" not in url.lower() \
                    and "pixel" not in url.lower() and "1x1" not in url:
                return url
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html_metin, re.I)
    if m:
        return html.unescape(m.group(1)).strip()
    return None


def _html_icerik(html_metin):
    """Açıklama HTML'inde görsel/video varsa temizlenmiş bir tam_metin üret."""
    if not html_metin:
        return ""
    if not re.search(r"<(img|video|iframe)[^>]*src", html_metin, re.I):
        return ""
    parcalar = []
    for m in re.finditer(r"<(img|video|iframe)[^>]*>", html_metin, re.I):
        etiket = m.group(0)
        src = re.search(r"src\s*=\s*[\"']([^\"']+)[\"']", etiket, re.I)
        if not src:
            continue
        url = html.unescape(src.group(1))
        if re.match(r"^https?://", url) and "pixel" not in url.lower():
            if m.group(1).lower() == "img":
                parcalar.append(f'<img class="inline-article-img" src="{url}" alt="">')
            elif m.group(1).lower() == "iframe":
                parcalar.append(
                    f'<div class="video-frame"><iframe src="{url}" frameborder="0" '
                    f'allowfullscreen></iframe></div>')
            else:
                parcalar.append(f'<video controls src="{url}"></video>')
    return "".join(parcalar)


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
    return "\n".join(f"<p>{html.escape(p)}</p>" for p in parcalar)


# ═══════════════════════════════════════════════════════════
# TAM METİN KAZIMI (genel amaçlı, alan adı seçmez)
# ═══════════════════════════════════════════════════════════

RE_ILAN = re.compile(
    r"(abone ol|ilgili haber|başka haber|reklam|izleyici|yeni abone|tıklayarak|kaynak:|haber kaynağı|copyright)",
    re.I)


RE_GORSEL_GEcersiz = re.compile(r"(logo|icon|pixel|sprite|1x1|avatar|badge|banner|tracking|favicon|\.svg)", re.I)


def _og_degisken(html_ham, ad):
    m = re.search(
        rf'<meta[^>]+(?:property|name)\s*=\s*["\']{ad}["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
        html_ham, re.I) or re.search(
        rf'<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]+(?:property|name)\s*=\s*["\']{ad}["\']',
        html_ham, re.I)
    return html.unescape(m.group(1)).strip() if m else None


def _medya_cek(soup):
    """Sayfadaki video embed'lerini ve mp4'leri toplar."""
    medya, eklenen = "", set()
    for iframe in soup.find_all("iframe"):
        src = (iframe.get("src") or "").strip()
        if src and not re.search(
                r"(doubleclick|googlesyndication|adsystem|facebook\.com|twitter\.com|youtube\.com/embed)",
                src, re.I) and src not in eklenen:
            medya += (f'<div class="video-frame"><iframe src="{src}" frameborder="0" '
                      f'allowfullscreen></iframe></div>')
            eklenen.add(src)
    for vid in soup.find_all("video"):
        src = vid.get("src")
        if not src:
            s = vid.find("source")
            src = s.get("src") if s else None
        if src and src not in eklenen:
            medya += f'<video controls src="{src}"></video>'
            eklenen.add(src)
    return medya


RE_icerik_sinif = re.compile(
    r"(icerik|content|story|detail|haber|article|post|metin|text-body|article-body|body-text)", re.I)


def _gecerli_p_sayisi(kabi):
    return sum(1 for p in kabi.find_all("p")
               if len(p.get_text(strip=True)) >= 40 and not RE_ILAN.search(p.get_text(strip=True)))


def _icerik_kabini_bul(soup):
    """Haber gövdesinin kabını seçer (alan adı seçmez, kademeli strateji).

    1) class/id'i içerik ipucuna uyan div/section (en çok geçerli p olan)
    2) <article>  3) <main>  4) body (son çare)
    """
    adaylar = []
    for el in soup.find_all(["div", "section"]):
        siniflar = " ".join([el.get("id") or ""] + list(el.get("class") or []))
        if RE_icerik_sinif.search(siniflar):
            adaylar.append(el)
    en_iyi = max(adaylar, key=_gecerli_p_sayisi, default=None)
    if en_iyi is not None and _gecerli_p_sayisi(en_iyi) >= 2:
        return en_iyi

    for aday in [soup.find("article"), soup.find("main")]:
        if aday is not None and _gecerli_p_sayisi(aday) >= 2:
            return aday
    if en_iyi is not None and _gecerli_p_sayisi(en_iyi) >= 1:
        return en_iyi

    v = soup.find("article")
    if v is not None and _gecerli_p_sayisi(v) >= 1:
        return v
    m = soup.find("main")
    if m is not None and _gecerli_p_sayisi(m) >= 1:
        return m
    return soup.body or soup


def _icerik_cek(icerik_kabi):
    """Seçili kabın içinden paragraf/başlık/liste bloklarını toplar."""
    parcalar = []
    for og_ele in icerik_kabi.find_all(["p", "h2", "h3", "h4", "ul", "ol", "blockquote"]):
        metin = og_ele.get_text(strip=True)
        if len(metin) < 40 or RE_ILAN.search(metin):
            continue
        ad = og_ele.name
        if ad in ("h2", "h3", "h4"):
            parcalar.append(f"<{ad}>{html.escape(metin)}</{ad}>")
        elif ad in ("ul", "ol"):
            liseler = "".join(f"<li>{html.escape(li.get_text(strip=True))}</li>"
                              for li in og_ele.find_all("li") if li.get_text(strip=True))
            if liseler:
                parcalar.append(f"<{ad}>{liseler}</{ad}>")
        elif ad == "blockquote":
            parcalar.append(f"<blockquote>{html.escape(metin)}</blockquote>")
        else:
            parcalar.append(f"<p>{html.escape(metin)}</p>")
    return "\n".join(parcalar)


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
    medya, icerik_html = "", ""

    if BSAVULUMU_VAR:
        soup = BeautifulSoup(html_ham, "html.parser")
        for t in soup(["script", "style", "noscript", "form", "nav", "footer", "aside"]):
            t.decompose()

        medya = _medya_cek(soup)
        icerik_kabi = _icerik_kabini_bul(soup)
        icerik_html = _icerik_cek(icerik_kabi)

        # içerik görselleri (ilk 3, izleme pikselleri hariç)
        gorseller = []
        for img in icerik_kabi.find_all("img"):
            src = img.get("src") or img.get("data-src") or ""
            if src.startswith("//"):
                src = "https:" + src
            if re.match(r"^https?://", src) and not RE_GORSEL_GEcersiz.search(src) \
                    and src not in gorseller:
                gorseller.append(f'<img class="inline-article-img" src="{html.escape(src)}" alt="">')
            if len(gorseller) >= 3:
                break
        icerik_html = "\n".join(gorseller[:1]) + "\n" + icerik_html if gorseller else icerik_html
    else:
        for p, h, hm in re.findall(r"<p[^>]*>(.*?)</p>|<h([2-4])[^>]*>(.*?)</h[2-4]>",
                                   html_ham, re.S | re.I):
            metin = temiz_metin(p)
            if len(metin) >= 40 and not RE_ILAN.search(metin):
                icerik_html += f"<p>{html.escape(metin)}</p>\n"

    tam = (medya + "\n" + icerik_html).strip()
    kisitli = False
    if len(tam) > metin_siniri:
        tam = tam[:metin_siniri]
        kisitli = True
    return baslik, tam, resim, ozet, kisitli


def kazi_tam_metin(haberler, sinir, zaman_asimi, metin_siniri, calisan, args):
    """Tam metni olmayan haberlerin sayfasını kazır.

    sinir: 0 veya negatif = sınırsız (tümü).
    """
    hedefler = [h for h in haberler if not h["tam_metin"]]
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
            if icerik:
                h["tam_metin"] = (icerik + "\n" + h["tam_metin"]).strip()
                h["tam"] = not kisitli
            if resim:
                h["resim"] = resim
            if ozet and len(ozet) > len(h.get("aciklama") or ""):
                h["aciklama"] = ozet
            if icerik or resim:
                kazinan += 1
            time.sleep(getattr(args, "kaydirma", 0.15))
    return kazinan


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
    rapor = {
        "surum": ayarlar.get("surum", "2.0"),
        "son_guncelleme": simdi.isoformat(),
        "sure_saniye": round(time.time() - baslangic, 1),
        "toplam_haber": len(benzersiz),
        "kaynak_sayisi": len(kaynaklar),
        "aktif_kaynak": sum(1 for d in kaynak_durumu.values() if d["durum"] == "aktif"),
        "besleme_sayisi": len(görevler),
        "kazanilan_tam_metin": kazinan,
        "kategoriler": {k: 0 for k in kategoriler},
        "kaynaklar": kaynak_durumu,
        "hatalar": hatalar,
    }
    for h in benzersiz:
        if h["kategori"] in rapor["kategoriler"]:
            rapor["kategoriler"][h["kategori"]] += 1
    with open(args.rapor, "w", encoding="utf-8") as f:
        json.dump(rapor, f, ensure_ascii=False, indent=2)
    log(f"→ {args.rapor}: {rapor['aktif_kaynak']}/{rapor['kaynak_sayisi']} kaynak aktif", False, args)

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
