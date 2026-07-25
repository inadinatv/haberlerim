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
        # Haberin içine giriyoruz
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            html = response.read()
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Sayfadaki tüm paragrafları (<p> etiketlerini) topluyoruz
        paragraflar = soup.find_all('p')
        tam_metin = ""
        
        for p in paragraflar:
            metin = p.get_text(strip=True)
            # 60 karakterden kısa metinleri (menü butonları, "bizi takip edin" gibi gereksiz yazıları) eliyoruz
            if len(metin) > 60: 
                tam_metin += "<p class='mb-4'>" + metin + "</p>"
                
        return tam_metin
    except Exception as e:
        return "" # Site engellerse veya hata olursa boş döner

def trt_haber_cek():
    url = "https://www.trthaber.com/manset_articles.rss"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        
    root = ET.fromstring(xml_data)
    haberler = []
    
    for item in root.findall('.//item'):
        baslik = item.find('title')
        link = item.find('link')
        aciklama = item.find('description')
        pubDate = item.find('pubDate')
        
        resim_url = "https://via.placeholder.com/400x200?text=Görsel+Yok"
        enclosure = item.find('enclosure')
        if enclosure is not None and enclosure.get('url'):
            resim_url = enclosure.get('url')
        
        haber_linki = link.text if link is not None else "#"
        
        # SİHİRLİ KISIM: Botumuz haberin linkine gidip uzun metni okuyor
        uzun_metin = ""
        if haber_linki != "#":
            uzun_metin = haber_detayini_cek(haber_linki)
            # Hedef siteyi bot saldırısı sanıp bizi engellemesin diye her tıklama arası yarım saniye dinleniyoruz
            time.sleep(0.5) 
        
        # Eğer kazıma başarısız olursa, RSS'teki kısa açıklamayı yedek olarak koyuyoruz
        if not uzun_metin:
            uzun_metin = "<p>" + temiz_metin(aciklama.text if aciklama is not None else "") + "</p>"
        
        haberler.append({
            "baslik": baslik.text if baslik is not None else "Başlıksız",
            "link": haber_linki,
            "aciklama": temiz_metin(aciklama.text if aciklama is not None else ""), # Ana sayfadaki kartlar için kısa metin
            "tam_metin": uzun_metin, # Haberin içine girince okunacak dev metin
            "resim": resim_url,
            "tarih": pubDate.text if pubDate is not None else ""
        })
        
    with open('haberler.json', 'w', encoding='utf-8') as f:
        json.dump(haberler, f, ensure_ascii=False, indent=4)
        
    print(f"{len(haberler)} adet haber tüm detaylarıyla satır satır kazındı.")

if __name__ == "__main__":
    trt_haber_cek()
