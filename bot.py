import urllib.request
import xml.etree.ElementTree as ET
import json
import re
import time
from bs4 import BeautifulSoup

def temiz_metin(html_metin):
    if not html_metin: return ""
    return re.sub('<[^<]+>', '', html_metin).strip()

def haber_detayini_cek(url):
    try:
        # Haberin asıl sayfasına gizlice giriyoruz
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            html = response.read()
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. TAM BAŞLIĞI ÇEKME (Sayfadaki asıl h1 etiketini buluyoruz)
        h1_etiketi = soup.find('h1')
        sayfa_basligi = h1_etiketi.get_text(strip=True) if h1_etiketi else None
        
        # 2. VİDEOLARI ÇEKME (iframe ve video etiketleri)
        videolar_html = ""
        
        # YouTube veya diğer gömülü iframe videoları
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if src and ("youtube" in src or "trt" in src or "video" in src):
                # Videoyu senin arayüzüne uyumlu ve responsive (16:9) yapmak için özel CSS class'ları ekliyoruz
                videolar_html += f'<div class="relative w-full overflow-hidden rounded-2xl mb-8 shadow-lg border border-gray-100" style="padding-top: 56.25%;"><iframe class="absolute top-0 left-0 w-full h-full" src="{src}" frameborder="0" allowfullscreen></iframe></div>'
        
        # Standart HTML5 videoları
        videos = soup.find_all('video')
        for video in videos:
            src = video.get('src', '')
            if not src:
                # Bazen video linki <source> etiketinin içinde olur
                source = video.find('source')
                if source:
                    src = source.get('src', '')
            if src:
                videolar_html += f'<div class="w-full rounded-2xl overflow-hidden mb-8 shadow-lg"><video controls class="w-full"><source src="{src}" type="video/mp4"></video></div>'
        
        # 3. UZUN METİNLERİ (Paragrafları) ÇEKME
        paragraflar = soup.find_all('p')
        metin_html = ""
        for p in paragraflar:
            metin = p.get_text(strip=True)
            # Menü, footer gibi gereksiz kısa yazıları eledik
            if len(metin) > 60: 
                metin_html += "<p class='mb-4'>" + metin + "</p>"
                
        # Önce videolar, altına haber metni gelecek şekilde birleştiriyoruz
        tam_icerik = videolar_html + metin_html
        
        return sayfa_basligi, tam_icerik
    except Exception as e:
        return None, "" 

def trt_haber_cek():
    url = "https://www.trthaber.com/manset_articles.rss"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        
    root = ET.fromstring(xml_data)
    haberler = []
    
    for item in root.findall('.//item'):
        rss_baslik = item.find('title')
        link = item.find('link')
        aciklama = item.find('description')
        pubDate = item.find('pubDate')
        
        resim_url = "https://via.placeholder.com/400x200?text=Görsel+Yok"
        enclosure = item.find('enclosure')
        if enclosure is not None and enclosure.get('url'):
            resim_url = enclosure.get('url')
        
        haber_linki = link.text if link is not None else "#"
        nihai_baslik = rss_baslik.text if rss_baslik is not None else "Başlıksız"
        uzun_metin = ""
        
        if haber_linki != "#":
            sayfa_basligi, uzun_metin = haber_detayini_cek(haber_linki)
            
            # Eğer sayfanın içinden tam başlığı (H1) başarıyla çektiysek, kısa olan RSS başlığını eziyoruz
            if sayfa_basligi:
                nihai_baslik = sayfa_basligi
                
            time.sleep(0.5) # Siteyi yormamak için kısa bekleme
        
        if not uzun_metin:
            uzun_metin = "<p>" + temiz_metin(aciklama.text if aciklama is not None else "") + "</p>"
        
        haberler.append({
            "baslik": nihai_baslik,
            "link": haber_linki,
            "aciklama": temiz_metin(aciklama.text if aciklama is not None else ""), 
            "tam_metin": uzun_metin,
            "resim": resim_url,
            "tarih": pubDate.text if pubDate is not None else ""
        })
        
    with open('haberler.json', 'w', encoding='utf-8') as f:
        json.dump(haberler, f, ensure_ascii=False, indent=4)
        
    print(f"{len(haberler)} adet haber, tam başlıkları ve video linkleriyle kazındı.")

if __name__ == "__main__":
    trt_haber_cek()
