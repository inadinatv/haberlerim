#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test verisi üretir: sources.json'daki her besleme için örnek RSS XML dosyası.

Linkler 02.09.2026'da canlı beslemelerden alınan GERÇEK haber adresleridir
(kısmi test ortamı — GitHub Actions ilk çalışmasında gerçek veriyle değiştirir).

Kullanım:
    python3 tests/gen_fixtures.py
    python3 bot.py --fixture tests/test_data --crawl 0 -v
"""
import json
import os
import re

YENI = "Wed, 02 Sep 2026 18:55:00 +0300"
ESKI = "Wed, 02 Sep 2026 12:10:00 +0300"

# URL -> örnek maddeler (başlık, link, açıklama, tarih, [kategori])
ornekler = {
    "https://www.aa.com.tr/tr/rss/default?cat=guncel": [
        ("İsrail basınına göre, Tel Aviv'in çekilmeyi reddetmesi nedeniyle Suriye ile güvenlik anlaşması yapılamadı",
         "https://www.aa.com.tr/tr/dunya/israil-basinina-gore-tel-avivin-cekilmeyi-reddetmesi-nedeniyle-suriye-ile-guvenlik-anlasmasi-yapilamadi/4045635",
         "İsrail basınında, Tel Aviv yönetiminin Suriye'de işgal edilen bölgelerden çekilmeyi reddetmesi nedeniyle güvenlik anlaşmasına şu ana kadar varılamadığı öne sürüldü.",
         YENI, None),
        ("KKTC'deki gemi kazasında kaybolan 20 kişiden birinin cenazesi bulundu",
         "https://www.aa.com.tr/tr/gundem/kktcdeki-gemi-kazasinda-kaybolan-20-kisiden-birinin-cenazesi-bulundu/4045620",
         "Girne açıklarında alabora olan yolcu gemisinden kaybolan 20 kişiden birinin cenazesine ulaşıldığı bildirildi.",
         "Wed, 02 Sep 2026 19:04:21 +0300", "Gündem"),
        ("Cumhurbaşkanı Erdoğan, Diyanet İşleri Başkanı Arpaguş'u kabul etti",
         "https://www.aa.com.tr/tr/gundem/cumhurbaskani-erdogan-diyanet-isleri-baskani-arpagusu-kabul-etti/4045602",
         "Cumhurbaşkanı Recep Tayyip Erdoğan, Diyanet İşleri Başkanı Safi Arpaguş'u kabul etti.",
         "Wed, 02 Sep 2026 18:34:07 +0300", "Gündem"),
    ],
    "https://www.aa.com.tr/tr/rss/default?cat=ekonomi": [
        ("Havacılık sektörünün liderleri İstanbul'da buluştu",
         "https://www.aa.com.tr/tr/ekonomi/havacilik-sektorunun-liderleri-istanbulda-bulustu/4045609",
         "Uluslararası Havalimanları Konseyi (ACI World) tarafından düzenlenen Dünya Havalimanları Deneyim Zirvesi 2026, küresel havacılığın liderlerini İstanbul'da bir araya getirdi.",
         "Wed, 02 Sep 2026 18:44:45 +0300", "Ekonomi"),
        ("Borsa günü düşüşle tamamladı",
         "https://www.aa.com.tr/tr/ekonomi/borsa-gunu-dususle-tamamladi/4045596",
         "Borsa İstanbul'da BIST 100 endeksi, günü yüzde 1,25 değer kaybederek 14.050,56 puandan tamamladı.",
         "Wed, 02 Sep 2026 18:26:16 +0300", "Ekonomi"),
    ],
    "https://www.aa.com.tr/tr/rss/default?cat=spor": [
        ("A Milli Erkek Basketbol Takımı, dünya sıralamasında 2 basamak yükseldi",
         "https://www.aa.com.tr/tr/spor/a-milli-erkek-basketbol-takimi-dunya-siralamasinda-2-basamak-yukseldi/4045606",
         "A Milli Erkek Basketbol Takımı, FIBA dünya klasmanında 2 basamak yükselerek 9. sıraya çıktı.",
         "Wed, 02 Sep 2026 18:38:26 +0300", "Spor"),
    ],
    "https://www.aa.com.tr/tr/rss/default?cat=dunya": [
        ("Trump'tan Hürmüz Boğazı'nın adını değiştirme önerisi",
         "https://www.aa.com.tr/tr/dunya/trumptan-hurmuz-bogazinin-adini-trump-bogazi-olarak-degistirme-onerisi/4045625",
         "ABD Başkanı Donald Trump, Hürmüz Boğazı'nın ABD kontrolü altında olduğunu savunarak adını değiştirme önerdi.",
         "Wed, 02 Sep 2026 19:09:06 +0300", "Dünya"),
        ("Rusya: Almanya'nın eylemlerine sert karşılık verilecek",
         "https://www.aa.com.tr/tr/dunya/rusya-almanyanin-eylemlerine-sert-karsilik-verilecek/4045588",
         "Rusya Dışişleri Bakanlığı, Leipzig-Halle Havalimanı'nda insansız hava aracı (İHA) bulunması nedeniyle Rusya'ya yönelik kararlara sert karşılık verileceğini bildirdi.",
         "Wed, 02 Sep 2026 18:20:34 +0300", "Dünya"),
    ],
    "https://www.aa.com.tr/tr/rss/default?cat=bilim-teknoloji": [
        ("Palantir CEO'su Karp, eski Ukrayna Savunma Bakanı Fedorov'un şirketine yatırım yapacak",
         "https://www.aa.com.tr/tr/bilim-teknoloji/palantir-ceosu-karp-eski-ukrayna-savunma-bakani-fedorovun-savunma-sirketine-yatirim-yapacak/4045611",
         "ABD merkezli veri analizi şirketi Palantir'in kurucu ortaklarından Alex Karp'ın, Fedorov'un savunma teknolojileri şirketinin ana yatırımcısı olacağı duyuruldu.",
         "Wed, 02 Sep 2026 18:46:18 +0300", "Bilim Teknoloji"),
        ("Milli elektrikli hızlı tren 250 km/s hızına ulaştı",
         "https://www.aa.com.tr/tr/bilim-teknoloji/milli-elektrikli-hizli-tren-saatte-250-kilometreye-ulasarak-rekorunu-gelistirdi/4043307",
         "Ulaştırma ve Altyapı Bakanı Uraloğlu, Türkiye'nin ilk milli elektrikli hızlı treninin test süreçlerinde 250 kilometre saate ulaştığını bildirdi.",
         ESKI, "Bilim Teknoloji"),
    ],
    "https://www.aa.com.tr/tr/rss/default?cat=yasam": [
        ("Cumhurbaşkanlığı Hukuk Politikaları Kurulu Çankaya Köşkü'nde toplandı",
         "https://www.aa.com.tr/tr/gundem/cumhurbaskanligi-hukuk-politikalari-kurulu-cankaya-kosunde-toplandi/4045575",
         "Sağlık Bakanı Kemal Memişoğlu, Çankaya Köşkü'ndeki Cumhurbaşkanlığı Hukuk Politikaları Kurulu Toplantısı'na katıldı.",
         "Wed, 02 Sep 2026 18:05:08 +0300", "Gündem"),
    ],
    "https://www.ntv.com.tr/son-dakika.rss": [
        ("Gemi kazasında kayıp sayısı belli oldu",
         "https://www.ntv.com.tr/turkiye/gemi-kazasi-kayip-sayisi,abcd1234",
         "Marmara Denizi'nde çarpışan iki gemiden biri battı, 10 denizci kayıp. Arama kurtarma çalışmaları sürüyor.",
         YENI, "Türkiye"),
        ("Borsa İstanbul çarşamba gününü düşüşle tamamladı",
         "https://www.ntv.com.tr/ekonomi/borsa-dusus-ntv,abcd1235",
         "BIST 100 endeksi günü yüzde 1,25 değer kaybıyla kapattı.",
         "Wed, 02 Sep 2026 18:03:00 +0300", "Ekonomi"),
    ],
    "https://www.ntv.com.tr/turkiye.rss": [
        ("Üsküdar Belediyesi'ne operasyon: 2 başkan yardımcısı gözaltında",
         "https://www.ntv.com.tr/turkiye/uskudar-operasyon,abcd1236",
         "İstanbul Cumhuriyet Başsavcılığı'nın başlattığı soruşturma kapsamında 2 başkan yardımcısı gözaltına alındı.",
         YENI, "Türkiye"),
    ],
    "https://www.ntv.com.tr/ekonomi.rss": [
        ("Motorin, benzin ve LPG'ye zam geliyor",
         "https://www.ntv.com.tr/ekonomi/yakit-zami,abcd1237",
         "Akaryakıt fiyatlarına bu gece geçerli olmak üzere zam yapılması bekleniyor.",
         YENI, "Ekonomi"),
    ],
    "https://www.ntv.com.tr/dunya.rss": [
        ("Suudi Arabistan: Hürmüz'deki tanker saldırısını İran düzenledi",
         "https://www.ntv.com.tr/dunya/suudi-iran-aciklamasi,abcd1238",
         "Suudi Dışişleri, SIDR tankerine yönelik saldırıdan İran'ı sorumlu tuttu.",
         "Wed, 02 Sep 2026 17:11:00 +0300", "Dünya"),
    ],
    "https://www.ntv.com.tr/sporskor.rss": [
        ("Galatasaray, Victor Nelsson'un sözleşmesini feshetti",
         "https://www.ntv.com.tr/spor/galatasaray-nelsson,abcd1239",
         "Sarı-kırmızılı kulüp, Nijeryalı defans oyuncusu Victor Nelsson ile yollarını ayırdı.",
         YENI, "Spor"),
    ],
    "https://www.ntv.com.tr/teknoloji.rss": [
        ("Türkiye, Artemis Anlaşmaları'na katıldı, ABD tebrik etti",
         "https://www.ntv.com.tr/teknoloji/artemis-anlasmalari,abcd1240",
         "Türkiye, uluslararası uzay işbirliği programı Artemis Anlaşmaları'na imza attı.",
         ESKI, "Teknoloji"),
    ],
    "https://www.ntv.com.tr/saglik.rss": [
        ("Uzmanlar gece düşünenlere uyardı: Yanıltıcı olabilir",
         "https://www.ntv.com.tr/saglik/telefon-uyku,abcd1241",
         "Uyku uzmanları, gece saatlerinde yoğun düşünce aktivitesinin uykuyu bölerek sağlığı olumsuz etkilediği konusunda uyarıyor.",
         YENI, "Sağlık"),
    ],
    "https://www.ntv.com.tr/yasam.rss": [
        ("Eylül sofralarını renklendiren mevsimlik tarifler",
         "https://www.ntv.com.tr/yasam/eylul-tarifleri,abcd1242",
         "Sonbahara geçişte sofranıza lezzet katacak pratik tarifleri derledik.",
         ESKI, "Yaşam"),
    ],
    "https://www.trthaber.com/sondakika.rss": [
        ("MHP Genel Başkanı Bahçeli: Spor kisvesiyle Terörsüz Türkiye hedefini zehirlemeye kimsenin hakkı yok",
         "https://www.trthaber.com/haber/gundem/mhp-genel-baskani-bahceli-spor-kisvesiyle-terorsuz-turkiye-hedefini-zehirlemeye-kimsinin-hakki-yok-955702.html",
         "Bahçeli, Amedspor araştırmasına tepki gösterdi: \"Spor; barışın, huzurun ve kardeşliğin en güçlü aracıdır.\"",
         "Wed, 02 Sep 2026 19:07:00 +0300", "Gündem"),
        ("Karanlık maddenin ilk doğrudan kanıtı bulunmuş olabilir",
         "https://www.trthaber.com/haber/dunya/karanlik-maddenin-ilk-dogrudan-kaniti-bulunmus-olabilir-955695.html",
         "Bilim insanları, karanlık maddenin ilk doğrudan kanıtına ulaşılmış olabileceğini açıkladı.",
         "Wed, 02 Sep 2026 17:48:00 +0300", "Dünya"),
        ("Engelli ve eski hükümlülerin projelerine 161,5 milyon lira destek",
         "https://www.trthaber.com/haber/ekonomi/engelli-ve-eski-hukumlulerin-projelerine-1615-milyon-lira-destek-955696.html",
         "Sosyal projelere destek paketinde 161,5 milyon liralık kaynak ayrıldı.",
         "Wed, 02 Sep 2026 18:04:00 +0300", "Ekonomi"),
        ("Üsküdar Belediyesi soruşturmasında 2 şüpheli daha gözaltına alındı",
         "https://www.trthaber.com/haber/turkiye/uskudar-belediyesi-sorusturmasinda-2-supheli-daha-gozaltina-alindi-955694.html",
         "Soruşturma kapsamında 2 şüpheli daha gözaltına alındı.",
         "Wed, 02 Sep 2026 17:39:00 +0300", "Türkiye"),
    ],
    "https://www.sabah.com.tr/rss/gundem.xml": [
        ("Başsavcı Fatih Dönmez yeni adli yılda meslektaşlarına seslendi: Suç örgütlerinin ekonomik damarları hedefte",
         "https://www.sabah.com.tr/yasam/bassavci-fatih-donmez-yeni-adli-yilda-meslektaslarina-seslendi-suc-orgutlerinin-ekonomik-damarlari-hedefte-7653139",
         "Başsavcı Dönmez: \"Suç örgütlerinin ekonomik damarları hedefte.\"",
         "Wed, 02 Sep 2026 19:31:46 +0300", "Gündem"),
        ("Fındık işçilerini taşıyan traktör devrildi: 18 yaralı",
         "https://www.sabah.com.tr/yasam/findik-iscilerini-tasiyan-tractr-devrildi-18-yarali-7653161",
         "Fındık hasadı için çalışmaya giden fındık işçilerini taşıyan traktörün devrilmesi sonucu 18 kişi yaralandı.",
         "Wed, 02 Sep 2026 19:15:21 +0300", "Gündem"),
        ("Muğla'da erkek arkadaşı tarafından katledilen Berfin Malatya'da toprağa verildi",
         "https://www.sabah.com.tr/yasam/muglada-erkek-arkadasi-tarafindan-katledilen-28-yasindaki-berfin-zelal-kaya-malatyada-topraga-verildi-7653158",
         "Muğla'da 28 yaşındaki Berfin Zelal Kaya'nın cenazesi, Malatya'da son yolculuğuna uğurlandı.",
         "Wed, 02 Sep 2026 19:14:02 +0300", "Gündem"),
    ],
    "https://www.sabah.com.tr/rss/ekonomi.xml": [
        ("Bakan Işıkhan: Engelli ve eski hükümlü vatandaşlarımızın yanında oluyoruz",
         "https://www.sabah.com.tr/ekonomi/bakan-istikhan-7653155",
         "Bakan Işıkhan, sosyal destek paketinin detaylarını paylaştı.",
         "Wed, 02 Sep 2026 18:05:00 +0300", "Ekonomi"),
    ],
    "https://www.sabah.com.tr/rss/spor.xml": [
        ("Batman Petrolspor, Vanspor'u 2 golle devirdi",
         "https://www.sabah.com.tr/spor/futbol/2026-09-02/batman-petrolspor-vansporu-2-golle-devirdi",
         "Trendyol 1. Lig'de Batman Petrolspor sahasında Vanspor'u 2-0 mağlup etti.",
         "Wed, 02 Sep 2026 19:22:20 +0300", "Spor"),
        ("Galatasaray, Victor Nelsson'un sözleşmesini feshetti",
         "https://www.sabah.com.tr/spor/futbol/2026-09-02/son-dakika-haberi-galatasaray-victor-nelssonun-sozlesmesini-feshetti",
         "Sarı-kırmızılı kulüp, Nijeryalı defans oyuncusu Victor Nelsson ile yollarını ayırdı.",
         "Wed, 02 Sep 2026 19:24:52 +0300", "Spor"),
    ],
    "https://www.sabah.com.tr/rss/dunya.xml": [
        ("Trump'tan dikkat çeken Hürmüz açıklaması: 'Trump Boğazı olarak değiştirmeli miyiz?'",
         "https://www.sabah.com.tr/dunya/trumptan-dikkat-ceken-hurmuz-aciklamasi-trump-bogazi-olarak-degistirmeli-miyiz-7653164",
         "ABD Başkanı Trump'ın Hürmüz Boğazı adıyla ilgili açıklaması gündemde.",
         "Wed, 02 Sep 2026 19:24:33 +0300", "Dünya"),
        ("İranlı yetkili, ABD'nin 'sivilleri asla hedef almayız' açıklamasını reddetti",
         "https://www.sabah.com.tr/dunya/iranli-yetkili-abdnin-sivilleri-asla-hedef-almayiz-aciklamasini-reddetti-7653159",
         "İran Dışişleri Sözcüsü Bekayi, ABD'nin açıklamasına tepki gösterdi.",
         "Wed, 02 Sep 2026 19:12:48 +0300", "Dünya"),
    ],
    "https://www.sabah.com.tr/rss/teknoloji.xml": [
        ("Yapay zekaya güvendi, ekinini kaybetti",
         "https://www.sabah.com.tr/teknoloji/yapay-zeka-ciftci-7653190",
         "Çin'de bir çiftçi, yapay zekanın önerdiği ilaç karışımını uzmana danışmadan uygulayınca 100 bin metrekarelik ekinini kaybetti.",
         "Wed, 02 Sep 2026 09:16:11 +0300", "Teknoloji"),
    ],
    "https://www.sabah.com.tr/rss/yasam.xml": [
        ("KKTC Başbakanı Ünal Üstel'den önemli açıklamalar",
         "https://www.sabah.com.tr/video/haber/kuzey-kibris-turk-cumhuriyeti-kktc-basbakani-unal-ustelden-onemli-aciklamalar",
         "KKTC Başbakanı Üstel, gemi kazasına ilişkin açıklamalarda bulundu.",
         "Wed, 02 Sep 2026 19:13:21 +0300", "Yaşam"),
        ("Girne'deki gemi kazasında yeni gelişme: Bir kişinin cenazesine ulaşıldı",
         "https://www.sabah.com.tr/yasam/girnedeki-gemi-kazasinda-yeni-gelisme-kktc-basbakani-ustel-acikladi-bir-kisinin-cenazesine-ulasildi-7653160",
         "Arama kurtarma ekipleri kayıp kişiden birinin cenazesine ulaştı.",
         "Wed, 02 Sep 2026 19:12:48 +0300", "Yaşam"),
    ],
    "https://www.cnnturk.com/feed/rss/turkiye/news": [
        ("SON DAKİKA HABERİ: Bahçeli'den Terörsüz Türkiye açıklaması",
         "https://www.cnnturk.com/turkiye/son-dakika-haberi-bahceliden-terorsuz-turkiye-aciklamasi-3462050",
         "MHP lideri Bahçeli, Amedspor araştırmalarına sert tepki gösterdi.",
         "Wed, 02 Sep 2026 19:29:58 GMT", "Türkiye"),
        ("Gemi kazasında ölenlere veda: Asker kardeşini ziyarete gitmiş",
         "https://www.cnnturk.com/turkiye/gemi-kazasinda-olenlere-veda-asker-kardesini-ziyarete-gitmis-3462010",
         "Marmara'da batan gemide hayatını kaybeden denizciler son yolculuklarına uğurlandı.",
         "Wed, 02 Sep 2026 17:52:01 GMT", "Türkiye"),
        ("Erhan Arıklı kimdir, nereli ve kaç yaşında? KKTC Ulaştırma Bakanı görevden alındı",
         "https://www.cnnturk.com/turkiye/erhan-arikli-kimdir-nereli-ve-kac-yasinda-kktc-ulastirma-bakani-erhan-arikli-gorevden-alindi-3462046",
         "KKTC Ulaştırma Bakanı Erhan Arıklı görevden alındı.",
         "Wed, 02 Sep 2026 18:55:46 GMT", "Türkiye"),
    ],
    "https://www.cnnturk.com/feed/rss/ekonomi/news": [
        ("Orta Vadeli Program 6 Eylül Pazar günü açıklanacak",
         "https://www.cnnturk.com/video/ekonomi/orta-vadeli-program-6-eylul-pazar-gunu-aciklanacak-3462039",
         "Hazine ve Maliye Bakanlığı'nın 2027-2029 Orta Vadeli Programı 6 Eylül'de kamuoyuyla paylaşılacak.",
         "Wed, 02 Sep 2026 18:40:05 GMT", "Ekonomi"),
        ("SON DAKİKA | Borsa İstanbul çarşamba gününü düşüşle tamamladı",
         "https://www.cnnturk.com/ekonomi/son-dakika-borsa-istanbul-carsamba-gununu-dususle-tamamladi-3462048",
         "BIST 100 endeksi günü yüzde 1,25 değer kaybıyla kapattı.",
         "Wed, 02 Sep 2026 19:03:43 GMT", "Ekonomi"),
    ],
    "https://www.cnnturk.com/feed/rss/dunya/news": [
        ("Nepal'de felaket göz göre göre mi geldi?",
         "https://www.cnnturk.com/video/dunya/nepalde-felaket-goz-gore-gore-mi-geldi-3462049",
         "Nepal'de çöken tünelde mahsur kalan işçiler için kurtarma çalışmaları devam ediyor.",
         "Wed, 02 Sep 2026 19:05:33 GMT", "Dünya"),
        ("SON DAKİKA HABERİ: KKTC Ulaştırma Bakanı görevden alındı",
         "https://www.cnnturk.com/dunya/son-dakika-haberi-kktc-ulastirma-bakani-gorevden-alindi-3462045",
         "Gemi kazasının ardından KKTC Ulaştırma Bakanı Erhan Arıklı görevden alındı.",
         "Wed, 02 Sep 2026 19:22:31 GMT", "Dünya"),
    ],
    "https://www.cnnturk.com/feed/rss/spor/news": [
        ("GÜNÜN MAÇLARI 2 EYLÜL 2026: Bugün kimlerin maçları var?",
         "https://www.cnnturk.com/spor/gunun-maclari-2-eylul-2026-bugun-kimlerin-maclar-var-bugunku-maclar-neler-iste-2-eylul-gunun-maclari-3461829",
         "Trendyol 1. Lig'de 5. hafta heyecanı bugün oynanacak 3 maçla devam ediyor.",
         "Wed, 02 Sep 2026 17:42:23 GMT", "Spor"),
    ],
    "https://www.cnnturk.com/feed/rss/bilim-teknoloji/news": [
        ("Palantir CEO'su Karp'ın yeni yatırım hamlesi",
         "https://www.cnnturk.com/bilim-teknoloji/palantir-karp-yatirim-3462020",
         "Veri analizi devi Palantir'in yeni yatırımları gündemde.",
         "Wed, 02 Sep 2026 18:46:00 GMT", "Bilim Teknoloji"),
    ],
    "https://www.cnnturk.com/feed/rss/saglik/news": [
        ("Gece çok düşünenler dikkat! Uzman isim 'Yanıltıcı olabilir' diyerek uyardı",
         "https://www.cnnturk.com/saglik/gece-cok-dusunenler-dikkat-uzman-isim-yaniltici-olabilir-diyerek-uyardi-3462051",
         "Uyku uzmanları gece saatlerinde zihinsel aktivitenin uykuyu bozduğunu söyledi.",
         "Wed, 02 Sep 2026 19:11:07 GMT", "Sağlık"),
    ],
    "https://www.cnnturk.com/feed/rss/kultur-sanat/news": [
        ("Günün film önerileri: Sinema salonlarında bu hafta",
         "https://www.cnnturk.com/kultur-sanat/gunun-film-onerileri-3462060",
         "Bu hafta vizyona giren filmler ve dizi gündemi.",
         "Wed, 02 Sep 2026 15:27:55 GMT", "Kültür Sanat"),
    ],
    "https://www.cnnturk.com/feed/rss/magazin/news": [
        ("MasterChef eleme adayı 2 Eylül 2026 | MasterChef'te eleme adayı kim oldu?",
         "https://www.cnnturk.com/magazin/masterchef-eleme-adayi-2-eylul-2026-masterchefte-eleme-adayi-kim-oldu-dokunulmazligi-hangi-takim-kazandi-3462043",
         "MasterChef Türkiye'de eleme adayı belli oldu, dokunulmazlığı bir takım kazandı.",
         "Wed, 02 Sep 2026 18:48:26 GMT", "Magazin"),
    ],
    "https://www.sozcu.com.tr/feeds-son-dakika": [
        ("Girne'deki deniz faciasında bir kişinin cesedine ulaşıldı",
         "https://www.sozcu.com.tr/girne-deki-deniz-faciasinda-bir-kisinin-cesedine-ulasildi-p354850",
         "Arama kurtarma ekipleri, alabora olan gemiden bir kişinin cesedine ulaştı.",
         "Wed, 02 Sep 2026 18:46:50 +0300", None),
        ("KKTC'li Bakan'dan Türkiye'de örneğine ender rastlanacak karar",
         "https://www.sozcu.com.tr/kktcli-bakandan-turkiyede-ornegine-ender-rastlanacak-karar-p354846",
         "Ulaştırma Bakanı Erhan Arıklı görevden alındı.",
         "Wed, 02 Sep 2026 19:16:58 +0300", None),
        ("Bursa'da fabrika yangını: İtfaiye ekipleri kurtarmak için çalışıyor",
         "https://www.sozcu.com.tr/bursada-fabrika-yangini-itfaiye-ekipleri-kurtarmak-icin-calisiyor-p354771",
         "Bursa'da bir fabrikada çıkan yangına müdahale sürüyor.",
         "Wed, 02 Sep 2026 14:10:24 +0300", None),
        ("Cumhurbaşkanı Erdoğan'dan Yunanistan'a sert uyarı! 'Gerekeni yaparız'",
         "https://www.sozcu.com.tr/erdogan-dan-yunanistan-a-sert-uyari-gerekeni-yapariz-p354758",
         "Cumhurbaşkanı Erdoğan, Yunanistan'a yönelik sert uyarılarda bulundu.",
         "Wed, 02 Sep 2026 13:32:18 +0300", None),
    ],
    "https://www.sozcu.com.tr/feeds-rss-category-ekonomi": [
        ("ABD saldırdı, piyasa hareketlendi: Altın düştü, petrol fırladı",
         "https://www.sozcu.com.tr/abd-saldirdi-piyasa-hareketlendi-altin-dustu-petrol-firladi-p354575",
         "Orta Doğu'daki gerilimle petrol fiyatları yükseldi, altın geriledi.",
         "Tue, 01 Sep 2026 20:35:24 +0300", "Ekonomi"),
        ("Motorin, benzin LPG... Üçüne birden zam geliyor",
         "https://www.sozcu.com.tr/lpg-ye-dev-zam-geliyor-p354677",
         "Akaryakıt fiyatlarına yeni zam bekleniyor.",
         "Wed, 02 Sep 2026 09:32:03 +0300", "Ekonomi"),
    ],
    "https://www.sozcu.com.tr/feeds-rss-category-dunya": [
        ("Dünya yeni bir sıcak krizle karşı karşıya: Almanya ile Rusya arasında büyük gerilim",
         "https://www.sozcu.com.tr/almanya-dan-zehir-zemberek-rusya-ya-cikisi-p354556",
         "Leipzig-Halle Havalimanı'ndaki İHA krizi Avrupa'yı germeye devam ediyor.",
         "Tue, 01 Sep 2026 20:16:50 +0300", "Dünya"),
    ],
    "https://www.sozcu.com.tr/feeds-rss-category-spor": [
        ("Cumhur İttifakı ortağından zehir zemberek 'Amedspor' tepkisi",
         "https://www.sozcu.com.tr/cumhur-ittifaki-ortagindan-zehir-zemberek-amedspor-tepkisi-p354762",
         "Araştırma, spor dünyasında geniş yankı buldu.",
         "Wed, 02 Sep 2026 14:35:00 +0300", "Spor"),
    ],
    "https://www.sozcu.com.tr/feeds-rss-category-bilim-teknoloji": [
        ("Türk mobil oyun sektörü dünyada büyük oynuyor",
         "https://www.sozcu.com.tr/turk-mobil-oyun-sektoru-dunyada-buyuk-oynuyor-p3543421",
         "1 milyar dolar değerlemeyi aşan 'Turcorn' şirketlerin üçü oyun sektöründen.",
         "Tue, 01 Sep 2026 11:02:30 +0300", "Bilim Teknoloji"),
    ],
    "https://www.sozcu.com.tr/feeds-rss-category-saglik": [
        ("Kene vakaları arttı: Uzmanlardan aşı çalışması açıklaması",
         "https://www.sozcu.com.tr/kene-aasi-calismasi-p354600",
         "Kene ısırmaları sonrası vakalarda artış görülüyor, aşı çalışmaları sürüyor.",
         "Wed, 02 Sep 2026 10:00:00 +0300", "Sağlık"),
    ],
    "https://www.sozcu.com.tr/feeds-rss-category-magazin": [
        ("Cem Yılmaz taburcu oldu, ilk o fotoğrafı paylaştı",
         "https://www.sozcu.com.tr/cem-yilmaz-taburcu-oldu-ilk-o-fotografi-paylasti-p354592",
         "Cem Yılmaz, hastanedeki tedavisinin ardından taburcu olduğunu sosyal medyadan duyurdu.",
         "Tue, 01 Sep 2026 22:03:09 +0300", "Magazin"),
    ],
    "https://feeds.bbci.co.uk/turkce/rss.xml": [
        ("Türkiye-İsrail gerilimi: Bölgesel rekabette çatışma riski var mı?",
         "https://www.bbc.com/turkce/articles/cyvzenl81eno",
         "Türkiye ile İsrail arasındaki ilişkilerde son gelişmeler ve bölgesel etkileri.",
         "Wed, 02 Sep 2026 11:28:39 GMT", None),
        ("İran: ABD düğüne saldırarak savaş suçu işledi",
         "https://www.bbc.com/turkce/articles/c750znwyye5o",
         "İran Dışişleri Bakanlığı, ABD'nin düğüne yönelik saldırısını savaş suçu olarak nitelendirdi.",
         "Wed, 02 Sep 2026 14:45:50 GMT", None),
        ("Marmara Denizi'nde çarpışan iki gemiden biri battı, 10 denizci kayıp",
         "https://www.bbc.com/turkce/articles/cx2z034d3pdo",
         "İstanbul Marmara Denizi'nde iki geminin çarpışması sonucu bir gemi battı.",
         "Wed, 02 Sep 2026 09:11:02 GMT", None),
        ("Kademeli emeklilik nedir, hükümetin bu yönde bir hazırlığı var mı?",
         "https://www.bbc.com/turkce/articles/c7708zr3p5eo",
         "Kademeli emeklilik tartışmaları ve hükümetin hazırlıkları.",
         "Wed, 02 Sep 2026 13:40:31 GMT", None),
    ],
    "https://www.haberturk.com/rss": [
        ("İlk Evim konut kredisi başvuru takvimi",
         "https://www.haberturk.com/120-faizli-ilk-evim-konut-kredisi-basvurulari-ne-zaman-baslayacak-120-faizli-ilk-evim-konut-kredisi-sartlari-neler-3909844",
         "Yüzde 1,20 faizli İlk Evim konut kredisinin başvuru takvimi ve şartları gündemde.",
         "Wed, 02 Sep 2026 16:19:53 GMT", None),
        ("Mars'ta gizemli 'denizanası' görüntüsü",
         "https://www.haberturk.com/mars-ta-denizanasi-gorundu-curiosity-nin-karesi-yillar-sonra-viral-oldu-3909800",
         "Curiosity'nin 2023'te çektiği karedeki denizanası biçimli şekil viral oldu.",
         "Wed, 02 Sep 2026 12:45:31 GMT", None),
        ("500 öğrenciye aylık 13 bin 750 TL burs verilecek",
         "https://www.haberturk.com/tenmak-burs-basvuru-ekrani-2026-500-ogrenciye-aylik-13-bin-750-tl-burs-verilecek-enerji-bakanligi-burs-basvurusu-nasil-yapilir-sartlari-neler-3909711",
         "Enerji Bakanlığı'nın TENMAK bursu başvuruları 1 Eylül'de başladı.",
         "Wed, 02 Sep 2026 13:45:43 GMT", None),
        ("Intikam Vakti filmi Show TV'de",
         "https://www.haberturk.com/intikam-vakti-wrath-of-man-filmi-konusu-nedir-oyunculari-kimler-intikam-vakti-ne-zaman-cekildi-3909833",
         "Jason Statham'ın başrolünde yer aldığı Wrath of Man filmi bu akşam Show TV'de.",
         "Wed, 02 Sep 2026 15:27:55 GMT", None),
    ],
    "http://www.hurriyet.com.tr/rss/gundem": [
        ("MHP Lideri Bahçeli: Spor kisvesiyle Terörsüz Türkiye hedefini ve kardeşlik iklimini zehirlemeye kimsenin hakkı yok",
         "https://www.hurriyet.com.tr/gundem/mhp-lideri-devlet-bahceli-spor-kisvesiyle-terorsuz-turkiye-hedefini-ve-kardeslik-iklimini-zehirlemeye-kimsenin-hakki-yok-43293838",
         "Milliyetçi Hareket Partisi Genel Başkanı Devlet Bahçeli, Kürt Çalışmaları Merkezi (KSC) ile Rawest Araştırma işbirliği ve Friedrich-Ebert-Stiftung tarafından yürütülen \"Kürtlerde Amedspor Algısı ve Taraftarlığı\" başlıklı araştırmaya tepki gösterdi.\n\n"
         "Bahçeli, \"Spor; barışın, huzurun, dayanışma ve toplumsal bütünleşmenin en güçlü araçlarından biridir. Bu nedenle spor alanının kimlik siyaseti, ayrıştırıcı söylem ve siyasi amaçlar için kullanımdan özenle kaçınmalıdır. Bu çerçevede Amedspor dahil olmak üzere bütün spor kulüpleri, sporun bütünleştirici ruhuna uygun davranmalı, toplumsal gerilimleri artıracak tutum ve söylemlerden uzak durmalıdır\" ifadelerini kullandı.\n\n"
         "Araştırmanın, terörsüz Türkiye hedefinin oluşturduğu barış ve kardeşlik iklimini zehirlemeye yönelik bir girişim olduğunu savunan Bahçeli, çalışmanın 28 Ağustos 2026 tarihinde kamuoyuna yansıdığını ve taraftarlık ile kimlik arasındaki bağın manipüle edilmeye çalışıldığını öne sürdü.\n\n"
         "Bahçeli, \"Türkiye terörün tasfiye edildiği, güvenliğin kalıcı olarak sağlandığı, şehirlerin ve kırsalın huzur ikliminde yeşerdiği terörsüz Türkiye'de kalkınma iradesinin önündeki en büyük engellerden birinin ortadan kalkacaktır. Terörsüz Türkiye, milletin barış, huzur ve refah ümidinin, Türk asırlarının müjdesidir\" dedi.",
         "Wed, 02 Sep 2026 16:06:00 Z", "Gündem"),
    ],
    "http://www.hurriyet.com.tr/rss/ekonomi": [
        ("TCMB faiz kararını açıkladı",
         "https://www.hurriyet.com.tr/ekonomi/tcmb-faiz-karari-43293900",
         "Merkez Bankası, faiz kararını açıkladı.",
         "Wed, 02 Sep 2026 14:00:00 Z", "Ekonomi"),
    ],
    "http://www.hurriyet.com.tr/rss/spor": [
        ("Süper Lig'de 4. hafta perdesi açılıyor",
         "https://www.hurriyet.com.tr/spor/super-lig-4-hafta-43293950",
         "Trendyol Süper Lig'de 4. hafta maçlarının programı belli oldu.",
         "Wed, 02 Sep 2026 10:00:00 Z", "Spor"),
    ],
    "http://www.hurriyet.com.tr/rss/dunya": [
        ("Zürih'te başörtüsü yasağı önergesi kabul edildi",
         "https://www.hurriyet.com.tr/dunya/zurich-basortusu-43294000",
         "İsviçre'nin Zürih Kanton Meclisi kamu kurumlarında başörtüsü yasağı önergesini kabul etti.",
         "Wed, 02 Sep 2026 13:00:00 Z", "Dünya"),
    ],
    "http://www.hurriyet.com.tr/rss/teknoloji": [
        ("Microsoft'un küresel e-posta aksaklığı giderildi",
         "https://www.hurriyet.com.tr/teknoloji/microsoft-aksaklik-43294050",
         "Bulut altyapısındaki sorun nedeniyle durma noktasına gelen e-posta trafiği normale döndü.",
         "Tue, 01 Sep 2026 09:40:32 Z", "Teknoloji"),
    ],
    "http://www.hurriyet.com.tr/rss/saglik": [
        ("Sonbaharda grip mevsimi: Aşı takvimi belli oldu",
         "https://www.hurriyet.com.tr/saglik/grip-asi-43294100",
         "Sağlık Bakanlığı, sezonluk grip aşısının dağıtım takvimini açıkladı.",
         "Wed, 02 Sep 2026 08:00:00 Z", "Sağlık"),
    ],
    "http://www.hurriyet.com.tr/rss/magazin": [
        ("MasterChef'te dokunulmazlığı kim kazandı?",
         "https://www.hurriyet.com.tr/magazin/masterchef-43294150",
         "MasterChef Türkiye'de haftanın dokunulmazlık oyunu heyecan dolu anlara sahne oldu.",
         "Wed, 02 Sep 2026 12:00:00 Z", "Magazin"),
    ],
}


def xml_maddeleri(ogeler):
    parcalar = []
    for baslik, link, aciklama, tarih, kat in ogeler:
        kat_etiket = f"\n      <category>{kat}</category>" if kat else ""
        parcalar.append(
            f"    <item>\n"
            f"      <title><![CDATA[{baslik}]]></title>\n"
            f"      <link>{link}</link>\n"
            f"      <description><![CDATA[{aciklama}]]></description>\n"
            f"{kat_etiket}\n"
            f"      <pubDate>{tarih}</pubDate>\n"
            f"    </item>")
    return "\n".join(parcalar)


def ana():
    with open("sources.json", encoding="utf-8") as f:
        yapılandırma = json.load(f)

    os.makedirs("tests/test_data", exist_ok=True)
    uretilen, eksik = 0, []
    for kaynak in yapılandırma["kaynaklar"]:
        for besleme in kaynak["beslemeler"]:
            url = besleme["url"]
            if url not in ornekler:
                eksik.append(url)
                continue
            dosya_adı = re.sub(r"[^a-z0-9]+", "_", url.lower()).strip("_")[:80] + ".xml"
            icerik = (
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<rss version="2.0">\n'
                "  <channel>\n"
                f"    <title>{kaynak['ad']} Test</title>\n"
                f"    <link>https://www.example.com</link>\n"
                f"    <description>{kaynak['ad']} test beslemesi</description>\n"
                "    <language>tr</language>\n"
                + xml_maddeleri(ornekler[url]) +
                "\n  </channel>\n</rss>\n")
            with open(os.path.join("tests/test_data", dosya_adı), "w", encoding="utf-8") as f2:
                f2.write(icerik)
            uretilen += 1
    print(f"{uretilen} test beslemesi üretildi.")
    if eksik:
        print("Örnek verisi OLMAYAN beslemeler (hata yolunu test eder):")
        for u in eksik:
            print(" -", u)


if __name__ == "__main__":
    ana()
