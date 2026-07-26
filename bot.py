import urllib.request
import xml.etree.ElementTree as ET
import json
import re
import time
from bs4 import BeautifulSoup

def temiz_metin(html_metin):
    if not html_metin: return ""
    # HTML etiketlerini ve RSS resim taglerini temizle
    temiz = re.sub('<[^<]+?>', '', html_metin)
    return temiz.replace('&nbsp;', ' ').strip()

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
        
        # 1. Başlık Çekme
        sayfa_basligi = None
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            sayfa_basligi = meta_title.get('content').strip()
        else:
            h1 = soup.find('h1')
            if h1: sayfa_basligi = h1.get_text(strip=True)

        # 2. Video ve Medya Çekme
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

        for mp4 in set(re.findall(r'https?://[^\s<>"\'\]\[]+\.mp4', html)):
            if mp4 not in eklenen_videolar:
                videolar_html += f'<div class="w-full rounded-2xl overflow-hidden mb-8 shadow-lg"><video controls class="w-full" src="{mp4}"></video></div>'
                eklenen_videolar.add(mp4)

        # 3. Haber Metni Çekme
        metin_html = ""
        icerik_alani = soup.find('div', class_=lambda x: x and any(c in x for c in ['detay-icerik', 'content-detail', 'story', 'detail'])) or soup
        
        for p in icerik_alani.find_all('p'):
            metin = p.get_text(strip=True)
            if len(metin) > 40 and not any(x in metin for x in ["Anadolu Ajansı", "Abone Ol", "İlgili Haber", "KAYNAK"]):
                metin_html += f"<p class='mb-4'>{metin}</p>"
                
        tam_icerik = videolar_html + metin_html
        return sayfa_basligi, tam_icerik
    except Exception as e:
        return None, ""

def aa_haber_cek():
    url = "https://www.aa.com.tr/tr/rss/default?cat=guncel"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            xml_data = response.read()
    except Exception as e:
        print(f"RSS akışına bağlanılamadı: {e}")
        return
        
    try:
        root = ET.fromstring(xml_data)
    except Exception as e:
        print(f"XML parse hatası: {e}")
        return
        
    haberler = []
    
    for item in root.findall('.//item'):
        try:
            rss_baslik = item.find('title')
            link = item.find('link')
            aciklama = item.find('description')
            pubDate = item.find('pubDate')
            
            resim_url = "https://via.placeholder.com/400x200?text=Görsel+Yok"
            
            # Enclosure kontrolü
            enclosure = item.find('enclosure')
            if enclosure is not None and enclosure.get('url'):
                resim_url = enclosure.get('url')
            elif aciklama is not None and aciklama.text:
                # Description içindeki resmi yakala
                img_match = re.search(r'src="([^"]+)"', aciklama.text)
                if img_match:
                    resim_url = img_match.group(1)
            
            haber_linki = link.text if link is not None and link.text else "#"
            nihai_baslik = rss_baslik.text if rss_baslik is not None and rss_baslik.text else "Başlıksız"
            uzun_metin = ""
            
            if haber_linki != "#":
                sayfa_basligi, tam_icerik = haber_detayini_cek(haber_linki)
                
                if sayfa_basligi and len(sayfa_basligi) > 5:
                    nihai_baslik = sayfa_basligi
                if tam_icerik:
                    uzun_metin = tam_icerik
                    
                time.sleep(0.5)
            
            temiz_ozet = temiz_metin(aciklama.text if aciklama is not None else "")
            
            if not uzun_metin:
                uzun_metin = f"<p>{temiz_ozet}</p>"
            
            tarih_str = pubDate.text if pubDate is not None and pubDate.text else ""
            
            haberler.append({
                "baslik": nihai_baslik,
                "link": haber_linki,
                "aciklama": temiz_ozet,
                "tam_metin": uzun_metin,
                "resim": resim_url,
                "tarih": tarih_str
            })
        except Exception as item_err:
            print(f"Bir haber işlenirken atlandı: {item_err}")
            continue
        
    with open('haberler.json', 'w', encoding='utf-8') as f:
        json.dump(haberler, f, ensure_ascii=False, indent=4)
        
    print(f"Anadolu Ajansı'ndan {len(haberler)} adet haber başarıyla işlendi ve kaydedildi.")

if __name__ == "__main__":
    aa_haber_cek()
