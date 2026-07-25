import urllib.request
import xml.etree.ElementTree as ET
import json
import re

def temiz_metin(html_metin):
    # Metindeki olası hatalı HTML etiketlerini temizler
    if not html_metin: return ""
    return re.sub('<[^<]+>', '', html_metin).strip()

def trt_haber_cek():
    url = "https://www.trthaber.com/manset_articles.rss"
    
    # TRT Haber RSS verisini çekiyoruz
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req) as response:
        xml_data = response.read()
        
    root = ET.fromstring(xml_data)
    haberler = []
    
    # Bütün 'item' (haber) etiketlerini dönüyoruz
    for item in root.findall('.//item'):
        baslik = item.find('title')
        link = item.find('link')
        aciklama = item.find('description')
        pubDate = item.find('pubDate')
        
        # Resim bulma (RSS yapısındaki enclosure etiketinden)
        resim_url = "https://via.placeholder.com/400x200?text=Görsel+Yok"
        enclosure = item.find('enclosure')
        if enclosure is not None and enclosure.get('url'):
            resim_url = enclosure.get('url')
        
        haberler.append({
            "baslik": baslik.text if baslik is not None else "Başlıksız",
            "link": link.text if link is not None else "#",
            "aciklama": temiz_metin(aciklama.text if aciklama is not None else ""),
            "resim": resim_url,
            "tarih": pubDate.text if pubDate is not None else ""
        })
        
    # Veriyi statik bir JSON dosyası olarak kaydediyoruz
    with open('haberler.json', 'w', encoding='utf-8') as f:
        json.dump(haberler, f, ensure_ascii=False, indent=4)
        
    print(f"{len(haberler)} adet TRT haberi başarıyla çekildi.")

if __name__ == "__main__":
    trt_haber_cek()
