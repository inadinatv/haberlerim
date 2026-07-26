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
        # TRT'nin güvenlik duvarını aşmak için çok daha gerçekçi tarayıcı kimlikleri kullanıyoruz
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.google.com/'
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            html_bayt = response.read()
            html = html_bayt.decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # ---------------------------------------------------------
        # 1. KUSURSUZ BAŞLIK ÇEKME (JSON-LD ve Title Taraması)
        # ---------------------------------------------------------
        sayfa_basligi = None
        
        # Taktik A: Google SEO kodları içinden kesin başlığı alma (En garantisi)
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, list): data = data[0]
                if data.get('@type') in ['NewsArticle', 'Article'] and data.get('headline'):
                    sayfa_basligi = data['headline']
                    break
            except:
                continue
                
        # Taktik B: Eğer SEO kodu yoksa, <title> etiketini alıp site adını silme
        if not sayfa_basligi:
            title_tag = soup.find('title')
            if title_tag:
                sayfa_basligi = title_tag.get_text(strip=True).split(' - ')[0].split(' | ')[0]

        # Taktik C: Klasik H1 arayışı
        if not sayfa_basligi:
            h1 = soup.find('h1')
            if h1: sayfa_basligi = h1.get_text(strip=True)

        # ---------------------------------------------------------
        # 2. VİDEO ÇEKME (Regex ve İframe Taraması)
        # ---------------------------------------------------------
        videolar_html = ""
        eklenen_videolar = set() # Aynı videoyu iki kere eklememek için

        # TRT Haber'in dışarıdan çektiği tüm özel iframe videoları
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            # Reklam ağlarını kesin olarak eliyoruz
            if src and not any(x in src for x in ['doubleclick', 'google', 'adsystem', 'facebook', 'twitter']):
                if src.startswith('//'): src = 'https:' + src
                elif src.startswith('/'): src = 'https://www.trthaber.com' + src
                
                if src not in eklenen_videolar:
                    videolar_html += f'<div class="relative w-full overflow-hidden rounded-2xl mb-8 shadow-lg border border-gray-100" style="padding-top: 56.25%;"><iframe class="absolute top-0 left-0 w-full h-full" src="{src}" frameborder="0" allowfullscreen></iframe></div>'
                    eklenen_videolar.add(src)

        # Sitenin JavaScript kodlarına gizlenmiş ham .mp4 linklerini Regex ile sökme (Nükleer Taktik)
        mp4_linkler = set(re.findall(r'https?://[^\s<>"\'\]\[]+\.mp4', html))
        for mp4 in mp4_linkler:
            if mp4 not in eklenen_videolar:
                videolar_html += f'<div class="w-full rounded-2xl overflow-hidden mb-8 shadow-lg"><video controls class="w-full" src="{mp4}"></video></div>'
                eklenen_videolar.add(mp4)

        # ---------------------------------------------------------
        # 3. TEMİZ METİN ÇEKME
        # ---------------------------------------------------------
        metin_html = ""
        # Sadece asıl haberin olduğu kutuyu bul (footer/header hariç)
        haber_alani = soup.find('div', class_=re.compile(r'news-content|news-detail|post-content|article')) or soup
        
        for p in haber_alani.find_all('p'):
            metin = p.get_text(strip=True)
            # 60 karakterden kısa menü metinlerini ve iç bağlantıları çöpe at
            if len(metin) > 60 and not any(x in metin for x in ["DAHA FAZLA OKU", "İlgili Haber", "Bizi takip edin", "TRT Haber"]): 
                metin_html += f"<p class='mb-4'>{metin}</p>"
                
        tam_icerik = videolar_html + metin_html
        
        return sayfa_basligi, tam_icerik
    except Exception as e:
        print(f"Hata ({url}): {e}")
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
            sayfa_basligi, tam_icerik = haber_detayini_cek(haber_linki)
            
            # Bulduğumuz uzun ve detaylı başlık başarılıysa, RSS'in verdiği kısa başlığı silip onu yazıyoruz
            if sayfa_basligi and len(sayfa_basligi) > 10:
                nihai_baslik = sayfa_basligi
            
            if tam_icerik:
                uzun_metin = tam_icerik
                
            time.sleep(1) # IP ban yememek için süreyi biraz uzattık
        
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
        
    print(f"{len(haberler)} adet haber tüm başlık ve videolarıyla çekildi.")

if __name__ == "__main__":
    trt_haber_cek()
