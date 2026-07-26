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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. BAŞLIK ÇEKME (AA'nın SEO veya H1 etiketleri)
        sayfa_basligi = None
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            sayfa_basligi = meta_title.get('content').strip()
        else:
            h1 = soup.find('h1')
            if h1: sayfa_basligi = h1.get_text(strip=True)

        # 2. VİDEO VE MEDYA ÇEKME
        videolar_html = ""
        eklenen_videolar = set()

        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if src and not any(x in src for x in ['doubleclick', 'google', 'adsystem', 'facebook', 'twitter']):
                if src.startswith('//'): src = 'https:' + src
                elif src.startswith('/'): src = 'https://www.aa.com.tr' + src
                
                if src not in eklenen_videolar:
                    videolar_html += f'<div class="relative w-full overflow-hidden rounded-2xl mb-8 shadow-lg border border-gray-100" style="padding-top: 56.25%;"><iframe class="absolute top-0 left-0 w-full h-full" src="{src}" frameborder="0" allowfullscreen></iframe></div>'
                    eklenen_videolar.add(src)

        # Ham video linkleri (.mp4)
        for mp4 in set(re.findall(r'https?://[^\s<>"\'\]\[]+\.mp4', html)):
            if mp4 not in eklenen_videolar:
                videolar_html += f'<div class="w-full rounded-2xl overflow-hidden mb-8 shadow-lg"><video controls class="w-full" src="{mp4}"></video></div>'
                eklenen_videolar.add(mp4)

        # 3. HABER METNİ ÇEKME
        metin_html = ""
        # AA haber metinlerinin bulunduğu ana içerik alanı
        icerik_alani = soup.find('div', class_=v for v in ['detay-icerik', 'content-detail', 'story']) or soup
        
        for p in icerik_alani.find_all('p'):
            metin = p.get_text(strip=True)
            if len(metin) > 50 and not any(x in metin for x in ["Anadolu Ajansı", "Abone Ol", "İlgili Haber"]):
                metin_html += f"<p class='mb-4'>{metin}</p>"
                
        tam_icerik = videolar_html + metin_html
        return sayfa_basligi, tam_icerik
    except Exception as e:
        print(f"Hata ({url}): {e}")
        return None, ""

def aa_haber_cek():
    # Anadolu Ajansı Son Dakika ve Manşet RSS adresi
    url = "https://www.aa.com.tr/tr/rss/default?cat=guncel"
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
        else:
            # AA bazen resmi description içinde html olarak verir, onu yakalayalım
            desc_text = aciklama.text if aciklama is not None else ""
            img_match = re.search(r'src="([^"]+)"', desc_text)
            if img_match:
                resim_url = img_match.group(1)
        
        haber_linki = link.text if link is not None else "#"
        nihai_baslik = rss_baslik.text if rss_baslik is not None else "Başlıksız"
        uzun_metin = ""
        
        if haber_linki != "#":
            sayfa_basligi, tam_icerik = haber_detayini_cek(haber_linki)
            
            if sayfa_basligi and len(sayfa_basligi) > 10:
                nihai_baslik = sayfa_basligi
            if tam_icerik:
                uzun_metin = tam_icerik
                
            time.sleep(0.8)
        
        # Temiz açıklama (HTML etiketlerinden arındırılmış)
        temiz_ozet = temiz_metin(aciklama.text if aciklama is not None else "")
        
        if not uzun_metin:
            uzun_metin = f"<p>{temiz_ozet}</p>"
        
        haberler.append({
            "baslik": nihai_baslik,
            "link": haber_linki,
            "aciklama": temiz_ozet,
            "tam_metin": uzun_metin,
            "resim": resim_url,
            "tarih": pubDate.text if pubDate is not None else ""
        })
        
    with open('haberler.json', 'w', encoding='utf-8') as f:
        json.dump(haberler, f, ensure_ascii=False, indent=4)
        
    print(f"Anadolu Ajansı'ndan {len(haberler)} adet güncel haber başarıyla çekildi.")

if __name__ == "__main__":
    aa_haber_cek()
