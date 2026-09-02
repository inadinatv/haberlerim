#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bot.py fonksiyonlarının ağsız ünite testleri.

Çalıştır: python3 tests/test_bot.py
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import bot  # noqa: E402


def test_temiz_metin():
    assert bot.temiz_metin("<p>Merhaba <b>dünya</b></p>") == "Merhaba dünya"
    assert bot.temiz_metin("a b") == "a b"
    assert bot.temiz_metin(None) == ""


def test_norm_baslik():
    a = bot.norm_baslik("SON DAKİKA: Erdoğan'dan Açıklama!")
    b = bot.norm_baslik("son dakika: erdogandan aciklama")
    assert a == b


def test_tarih():
    iso = bot.tarihi_parsel("Wed, 02 Sep 2026 19:04:21 +0300")
    assert iso and iso.startswith("2026-09-02T16:04:21")
    iso2 = bot.tarihi_parsel("2026-09-02T16:04:21+00:00")
    assert iso2.startswith("2026-09-02T16:04:21")
    assert bot.tarihi_parsel("çöp") is None


def test_paragraflara_bol():
    metin = "İlk paragraf biraz uzun olsun ki bölünmesin ve cümlelerle devam etsin." * 3 + \
            "\n\nİkinci paragraf ayrı bir blok olarak gelsin ve yine yeterince uzun olsun."
    parcalar = bot.paragraflara_bol(metin)
    assert len(parcalar) == 2
    assert parcalar[0].startswith("İlk paragraf")
    assert parcalar[1].startswith("İkinci paragraf")


def test_aciklamadan_tam_metin():
    uzun = "Bu açıklama yeterince uzun ki tam metin olarak değerlendirilsin ve birkaç paragrafa bölünebilsin. " * 6 + \
           "\n\nİkinci blokta da uzun bir metin var ki ayrışma test edilebilsin ve sonuç kontrol edilebilsin."
    html_metin = bot.aciklamadan_tam_metin(uzun)
    assert html_metin.count("<p>") >= 2
    assert bot.aciklamadan_tam_metin("Kısa özet.") == ""


def test_icerik_kabini_bul():
    html_doc = """
    <html><body>
      <div id="menu"><p>Kısa</p><p>Menü maddesi burada biraz uzun olacak şekilde yazıldı test için.</p></div>
      <article>
        <p>İçerik paragraflarının ilki burada ve otuz karakterden uzun olduğunda geçerli sayılır.</p>
        <p>İkinci içerik paragrafı da yeterince uzun ve testin doğru kabı seçtiğini kanıtlıyor.</p>
        <p>Üçüncü paragraf yine uzun ve içerik sayfasının gerçek gövdesini temsil ediyor.</p>
        <p>Dördüncü ve son paragraf içerik yoğunluğunu artırarak seçim skorunu yükseltiyor.</p>
      </article>
      <div class="footer"><p>Alt bilgi metni burada ve uzun ama içerikten az paragrafı var.</p></div>
    </body></html>"""
    if not bot.BSAVULUMU_VAR:
        print("  (bs4 yok — atlandı)")
        return
    soup = bot.BeautifulSoup(html_doc, "html.parser")
    kabi = bot._icerik_kabini_bul(soup)
    metin = kabi.get_text()
    assert "İçerik paragraflarının ilki" in metin
    assert "İkinci içerik paragrafı" in metin


def test_besleme_cozyu_uzun_aciklama():
    """Hürriyet tarzı uzun açıklamalı besleme -> tam_metin üretilmeli."""
    with open(os.path.join(os.path.dirname(__file__),
                           "test_data", "http_www_hurriyet_com_tr_rss_gundem.xml"), encoding="utf-8") as f:
        ham = f.read()
    haberler = bot.beslemeyi_cozyu(ham, {"kategori": "Gündem", "limit": 10},
                                   {"ad": "Hürriyet", "id": "hurriyet", "resim_tabani": None})
    assert len(haberler) >= 1
    h = haberler[0]
    assert h["tam_metin"].count("<p>") >= 3, "uzun açıklama tam metine dönüşmedi"
    assert h["tam"] is True
    assert h["kategori"] == "Gündem"


def test_besleme_cozyu_kisayla():
    """Kısa açıklamalı besleme -> tam_metin boş olmalı (kazıma bekler)."""
    with open(os.path.join(os.path.dirname(__file__),
                           "test_data", "https_www_ntv_com_tr_son_dakika_rss.xml"), encoding="utf-8") as f:
        ham = f.read()
    haberler = bot.beslemeyi_cozyu(ham, {"kategori": "Gündem", "limit": 10},
                                   {"ad": "NTV", "id": "ntv", "resim_tabani": None})
    assert len(haberler) >= 1
    assert haberler[0]["tam_metin"] == ""
    assert haberler[0]["tam"] is False


def test_haber_detayini_cek():
    """Tam sayfa kazımı: og alanları, içerik kabı, görsel, video, sınır."""
    sayfa = """<html><head>
      <meta property="og:title" content="Test Haber Başlığı Uzun Sürsün Şöyle">
      <meta property="og:image" content="https://example.com/resim.jpg">
      <meta property="og:description" content="Test özet metni burada duruyor ve elli karakterden uzun olsun ki kabul edilsin.">
    </head><body>
      <nav><p>Menü paragrafı ve biraz uzun metin menü tuzağı oluşturmak için yazıldı.</p></nav>
      <div class="haber-detail-icerik">
        <p>İçerik birinci paragrafı ve otuz karakterden uzun bir cümle ile devam ediyor burada.</p>
        <iframe src="https://video.haber.com.tr/embed/xyz"></iframe>
        <p>İçerik ikinci paragrafı ve yine uzun bir metin ile devam ediyor test doğrulama için.</p>
        <img src="https://cdn.example.com/haber/foto.jpg" alt="">
        <img src="https://cdn.example.com/images/logo.png" alt="">
      </div>
      <div class="related-news">
        <p>İlgili haberler bloğu ve uzun metin içerir ama içerik kabından ayrı bir yapıda durur.</p>
      </div>
    </body></html>"""
    if not bot.BSAVULUMU_VAR:
        print("  (bs4 yok — atlandı)")
        return
    orijinal = bot.http_cek
    bot.http_cek = lambda url, *a, **k: sayfa.encode("utf-8")
    try:
        baslik, icerik, resim, ozet, kisitli = bot.haber_detayini_cek("https://ornek.test/haber")
    finally:
        bot.http_cek = orijinal
    assert baslik and "Test Haber" in baslik, baslik
    assert resim == "https://example.com/resim.jpg"
    assert icerik.count("<p>") >= 2
    assert "foto.jpg" in icerik, "içerik görseli çekilmedi"
    assert "logo.png" not in icerik, "logo süzülmedi"
    assert "video.haber.com.tr" in icerik, "video embed çekilmedi"
    assert "Menü paragrafı" not in icerik, "menü içeriğe sızdı"
    assert not kisitli


def test_metin_siniri():
    """Uzun sayfa -> metin sinirinde kesilmeli, kisitli=True."""
    if not bot.BSAVULUMU_VAR:
        return
    paragraf = "<p>Uzun paragraf metni ve otuz karakterden fazla uzunlukta cümleler içeriyor.</p>" * 400
    sayfa = f"<html><body><article>{paragraf}</article></body></html>"
    orijinal = bot.http_cek
    bot.http_cek = lambda url, *a, **k: sayfa.encode("utf-8")
    try:
        _, icerik, _, _, kisitli = bot.haber_detayini_cek("https://ornek.test/uzun", metin_siniri=5000)
    finally:
        bot.http_cek = orijinal
    assert kisitli
    assert len(icerik) <= 5000


def main():
    basari, hata = 0, 0
    for ad, fn in sorted({k: v for k, v in globals().items() if k.startswith("test_")}.items()):
        try:
            fn()
            print(f"  ✓ {ad}")
            basari += 1
        except Exception as e:
            print(f"  ✗ {ad}: {e}")
            hata += 1
    print(f"\n{basari} geçti, {hata} başarısız")
    return 1 if hata else 0


if __name__ == "__main__":
    sys.exit(main())
