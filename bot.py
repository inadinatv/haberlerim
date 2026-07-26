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
        # SİHİRLİ KISIM: TRT'nin güvenlik duvarını aşmak için botumuzu gerçek bir tarayıcı gibi gösteriyoruz
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as response:
            html = response.read()
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # 1. TAM BAŞLIĞI ÇEKME (Artık h1 yerine, sitenin en doğru başlığı tuttuğu og:title SEO etiketini kullanıyoruz)
        sayfa_basligi = None
        meta_title = soup.find('meta', property='og:title')
        if meta_title and meta_title.get('content'):
            sayfa_basligi = meta_title.get('content').strip()
        else:
            h1_etiketi = soup.find('h1')
            if h1_etiketi:
                sayfa_basligi = h1_etiketi.get_text(strip=True)
        
        # 2. VİDEOLARI ÇEKME (Eksik veya farklı formatlı video linklerini onarıp çekiyoruz)
        videolar_html = ""
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            if src:
                # TRT bazen linklerin başına https koymaz, bunları tespit edip onarıyoruz
                if src.startswith('//'):
                    src = 'https:' + src
                elif src.startswith('/'):
                    src = 'https://www.trthaber.com' + src
                    
                # Sadece video içeren çerçeveleri alıyoruz (reklamları veya gereksiz eklentileri eliyoruz)
                if 'video' in src.lower() or 'embed' in src.lower() or 'youtube' in src.lower():
                    videolar_html += f'<div class="relative w-full overflow-hidden rounded-2xl mb-8 shadow-lg border border-gray-100" style="padding-top: 56.25%;"><iframe class="absolute top-0 left-0 w-full h-full" src="{src}" frameborder="0" allowfullscreen></iframe></div>'
        
        # 3. UZUN METİNLERİ (Paragrafları) ÇEKME
        paragraflar = soup.find_all('p')
        metin_html = ""
        for p in paragraflar:
            metin = p.get_text(strip=True)
            # 80 karakterden kısa olanları ve "İlgili Haber" yazan diğer sayfa yönlendirmelerini eliyoruz
            if len(metin) > 80 and not ("İlgili Haber" in metin or "DAHA FAZLA OKU" in metin): 
                metin_html += "<p class='mb-4'>" + metin + "</p>"
                
        # Videolar üstte, metin altta olacak şekilde birleştir
        tam_icerik = videolar_html + metin_html
        
        return sayfa_basligi, tam_icerik
    except Exception as e:
        # Eğer site bizi yine engellerse GitHub loglarında sebebi görebilmek için hata kodunu yazdırıyoruz
        print(f"Habere girerken hata oluştu ({url}): {e}") 
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
            
            # İçeriden aldığımız başlık başarılıysa ve mantıklı bir uzunluktaysa, kısa RSS başlığını eziyoruz
            if sayfa_basligi and len(sayfa_basligi) > 10:
                nihai_baslik = sayfa_basligi
                
            time.sleep(0.5) 
        
        # Eğer bot yine başarısız olursa, sayfa boş kalmasın diye RSS özetini koyuyoruz
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
        
    print(f"{len(haberler)} adet haber işlendi.")

if __name__ == "__main__":
    trt_haber_cek()
