/* ═════════════════════════════════════════════════════════════
   GÜNDEM — Premium Haber v2
   Uygulama mantığı: veri, görünüm, piyasa, ayarlar
   ═════════════════════════════════════════════════════════════ */
'use strict';

/* ── Sabitler ──────────────────────────────────────────────── */
const KATEGORILER = [
    { ad: 'Gündem',         ikon: '📰' },
    { ad: 'Ekonomi',        ikon: '💹' },
    { ad: 'Spor',           ikon: '⚽' },
    { ad: 'Dünya',          ikon: '🌍' },
    { ad: 'Teknoloji',      ikon: '🤖' },
    { ad: 'Sağlık',         ikon: '🩺' },
    { ad: 'Yaşam & Sanat',  ikon: '🎭' },
    { ad: 'Magaza',         ikon: '✨' },
];
const KAYNAK_ADLARI = {
    aa: 'AA', ntv: 'NTV', trt: 'TRT Haber', sabah: 'Sabah', hurriyet: 'Hürriyet',
    cnnturk: 'CNN Türk', sozcu: 'Sözcü', bbcturkce: 'BBC Türkçe', haberturk: 'Habertürk',
};
const AYARLAR_VARSAVLANAN = {
    tema: 'koyu',
    vurgu: 'cyan',
    yazi: 'orta',
    gorsel: true,
    ticker: true,
    piyasa: true,
    partikuler: true,
    yenile: 'kapali',
};
const SAAT_KURALLARI = { timeZone: 'Europe/Istanbul' };

/* ── Durum ─────────────────────────────────────────────────── */
let haberler = [];
let rapor = null;
let aktifKategori = 'Tümü';
let aramaMetni = '';
let sirala = 'yeni';
let gorunum = 'izgara';
let seciliDetay = null;
let ayarlar = {};
let yenileZamanlayici = null;
let veriYukleniyor = false;
let sonFiltre = [];

/* ── Yardımcılar ───────────────────────────────────────────── */
const $ = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));

function escapeHtml(metin) {
    return (metin || '')
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

function norm(metin) {
    return (metin || '')
        .toLocaleLowerCase('tr-TR')
        .replace(/ı/g, 'i').replace(/ğ/g, 'g').replace(/ü/g, 'u')
        .replace(/ş/g, 's').replace(/ö/g, 'o').replace(/ç/g, 'c')
        .replace(/[^a-z0-9çğıöşü]+/g, ' ')
        .trim();
}

function kategoriIkonu(ad) {
    const k = KATEGORILER.find((x) => x.ad === ad);
    return k ? k.ikon : '📰';
}

function relativeZaman(iso) {
    if (!iso) return '';
    const fark = Date.now() - new Date(iso).getTime();
    const dk = Math.floor(fark / 60000);
    if (dk < 1) return 'az önce';
    if (dk < 60) return dk + ' dk önce';
    const sa = Math.floor(dk / 60);
    if (sa < 24) return sa + ' sa önce';
    const gun = Math.floor(sa / 24);
    if (gun < 7) return gun + ' gün önce';
    return new Date(iso).toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
}

function uzunTarih(iso) {
    if (!iso) return '';
    const d = new Date(iso);
    return d.toLocaleDateString('tr-TR', { day: 'numeric', month: 'long', year: 'numeric' }) +
        ' • ' + d.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function tutucuUri(emoji, kaynakAd, genis) {
    const w = genis ? 1200 : 640, h = genis ? 600 : 360;
    const svg =
        '<svg xmlns="http://www.w3.org/2000/svg" width="' + w + '" height="' + h + '">' +
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">' +
        '<stop offset="0" stop-color="#141433"/><stop offset="0.55" stop-color="#1d1040"/>' +
        '<stop offset="1" stop-color="#0e0e26"/></linearGradient></defs>' +
        '<rect width="' + w + '" height="' + h + '" fill="url(#g)"/>' +
        '<circle cx="' + (w * 0.85) + '" cy="' + (h * 0.2) + '" r="' + (w * 0.3) + '" fill="rgba(0,245,255,0.05)"/>' +
        '<circle cx="' + (w * 0.1) + '" cy="' + (h * 0.85) + '" r="' + (w * 0.25) + '" fill="rgba(181,55,242,0.06)"/>' +
        '<text x="50%" y="50%" font-size="' + (genis ? 150 : 92) + '" text-anchor="middle" dominant-baseline="middle">' + emoji + '</text>' +
        '<text x="50%" y="' + (h * 0.78) + '" font-family="Inter, sans-serif" font-size="' + (genis ? 24 : 19) +
        '" font-weight="700" letter-spacing="4" text-anchor="middle" fill="rgba(255,255,255,0.5)">' +
        escapeHtml((kaynakAd || 'GÜNDEM').toUpperCase()) + '</text>' +
        '</svg>';
    return 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
}

function toast(mesaj, tip) {
    const t = $('#toast');
    t.textContent = mesaj;
    t.classList.toggle('hata', tip === 'hata');
    t.classList.add('goster');
    clearTimeout(t._z);
    t._z = setTimeout(() => t.classList.remove('goster'), 2600);
}

/* ── Ayarlar ───────────────────────────────────────────────── */
function ayarlarYukle() {
    try {
        const kayitli = JSON.parse(localStorage.getItem('gundem-ayarlar') || '{}');
        ayarlar = Object.assign({}, AYARLAR_VARSAVLANAN, kayitli);
    } catch (e) {
        ayarlar = Object.assign({}, AYARLAR_VARSAVLANAN);
    }
}

function ayarlarKaydet() {
    localStorage.setItem('gundem-ayarlar', JSON.stringify(ayarlar));
}

function ayarlariUygula() {
    const r = document.documentElement;
    r.setAttribute('data-tema', ayarlar.tema);
    r.setAttribute('data-vurgu', ayarlar.vurgu);
    r.setAttribute('data-yazi', ayarlar.yazi);
    $('#btn-tema').textContent = ayarlar.tema === 'koyu' ? '🌙' : '☀️';
    $('#market-strip').classList.toggle('gizli', !ayarlar.piyasa);
    if (!ayarlar.ticker) $('#ticker-wrap').style.display = 'none';
    if (!ayarlar.partikuler) {
        $('#partikuller').innerHTML = '';
    } else {
        partikullerOlustur();
    }
    /* seçili durumları düğmelere işaretle */
    $$('[data-ayar]').forEach((grup) => {
        const anahtar = grup.dataset.ayar;
        if (grup.classList.contains('anahtar')) {
            grup.setAttribute('aria-checked', String(!!ayarlar[anahtar]));
            return;
        }
        grup.querySelectorAll('button[data-deger]').forEach((b) => {
            b.classList.toggle('secili', b.dataset.deger === String(ayarlar[anahtar]));
        });
    });
}

function partikullerOlustur() {
    const kutu = $('#partikuller');
    kutu.innerHTML = '';
    if (!ayarlar.partikuler) return;
    const renkler = ['var(--accent)', 'var(--accent-2)', 'var(--neon-pink)'];
    for (let i = 0; i < 18; i++) {
        const p = document.createElement('div');
        p.className = 'partikul';
        const boyut = 2 + Math.floor(Math.random() * 5);
        p.style.left = Math.random() * 100 + '%';
        p.style.width = p.style.height = boyut + 'px';
        p.style.background = renkler[Math.floor(Math.random() * renkler.length)];
        p.style.boxShadow = '0 0 ' + (4 + Math.random() * 8) + 'px currentColor';
        p.style.animationDuration = (10 + Math.random() * 16) + 's';
        p.style.animationDelay = (Math.random() * 12) + 's';
        kutu.appendChild(p);
    }
}

function yenileZamanlamayiKur() {
    clearInterval(yenileZamanlayici);
    yenileZamanlayici = null;
    if (ayarlar.yenile !== 'kapali') {
        yenileZamanlayici = setInterval(verileriYenile, Number(ayarlar.yenile) * 60000);
    }
}

/* ── Veri yükleme ──────────────────────────────────────────── */
async function veriGetir(dizin, cacheBuster) {
    const url = dizin + (cacheBuster ? '?ts=' + Date.now() : '');
    const cev = await fetch(url, { cache: 'no-store' });
    if (!cev.ok) throw new Error(dizin + ' → ' + cev.status);
    return cev.json();
}

async function verileriYenile(manuel) {
    if (veriYukleniyor) return;
    veriYukleniyor = true;
    const btn = $('#btn-yenile');
    btn.classList.add('donuyor');
    try {
        const [h, r] = await Promise.all([
            veriGetir('haberler.json', true),
            veriGetir('bot-raporu.json', true).catch(() => null),
        ]);
        haberler = Array.isArray(h) ? h : [];
        rapor = r;
        renderHepsi();
        if (manuel) toast(haberler.length ? '⚡ ' + haberler.length + ' haber güncellendi' : 'Haber güncellendi');
    } catch (e) {
        if (haberler.length === 0) {
            durumPaneli('haberler-bulunamadi');
            if (manuel) toast('Haberler yüklenemedi. Bot henüz çalışmamış olabilir.', 'hata');
        } else if (manuel) {
            toast('Bağlantı hatası — son veri gösteriliyor.', 'hata');
        }
    } finally {
        veriYukleniyor = false;
        btn.classList.remove('donuyor');
    }
}

/* ── Saat ──────────────────────────────────────────────────── */
function saatCalistir() {
    const fmtS = new Intl.DateTimeFormat('tr-TR', { hour: '2-digit', minute: '2-digit', second: '2-digit', ...SAAT_KURALLARI });
    const fmtT = new Intl.DateTimeFormat('tr-TR', { day: 'numeric', month: 'short', weekday: 'short', ...SAAT_KURALLARI });
    const guncelle = () => {
        const simdi = new Date();
        $('#saat').textContent = fmtS.format(simdi);
        $('#tarih-gun').textContent = fmtT.format(simdi);
    };
    guncelle();
    setInterval(guncelle, 1000);
}

/* ── Piyasa verileri (anlık) ───────────────────────────────── */
function sayiyaDonus(s) {
    if (typeof s === 'number') return s;
    return parseFloat(String(s).replace(/\./g, '').replace(',', '.')) || 0;
}

function degisimEtiketi(deger, raw) {
    let d = 0;
    if (raw && /%/.test(String(raw))) {
        d = sayiyaDonus(raw.replace('%', '').replace(/\s/g, ''));
    }
    const sinif = d > 0.001 ? 'yukari' : d < -0.001 ? 'asagi' : 'duz';
    const ok = d > 0.001 ? '▲' : d < -0.001 ? '▼' : '—';
    const yaz = raw ? String(raw).trim() : '';
    return '<span class="market-degisim ' + sinif + '">' + ok + ' ' + escapeHtml(yaz) + '</span>';
}

async function piyasayiGetir() {
    const ic = $('#market-strip-inner');
    const maddeler = [];
    let doviz = null;

    try {
        const cev = await fetch('https://doviz-api.onrender.com/api', { cache: 'no-store' });
        const d = await cev.json();
        doviz = d.data && d.data[0];
    } catch (e) { doviz = null; }

    /* Döviz yedeği: open.er-api.com */
    let usdTry = doviz ? sayiyaDonus(doviz.Dolar) : 0;
    if (!usdTry) {
        try {
            const d = await (await fetch('https://open.er-api.com/v6/latest/USD')).json();
            usdTry = d.rates && d.rates.TRY || 0;
        } catch (e) { usdTry = 0; }
    }

    if (doviz) {
        maddeler.push({ sinif: 'bist', ikon: 'BIST', ad: 'BIST 100', deger: (doviz.Bist100 || '—').replace(',', '.'), degisim: degisimEtiketi(0, doviz.Bist100Degisim) });
        maddeler.push({ sinif: 'usd', ikon: '$', ad: 'USD/TRY', deger: sayiyaDonus(doviz.Dolar) ? sayiyaDonus(doviz.Dolar).toFixed(4) : '—', degisim: degisimEtiketi(0, doviz.DolarDegisim) });
        maddeler.push({ sinif: 'eur', ikon: '€', ad: 'EUR/TRY', deger: sayiyaDonus(doviz.Euro) ? sayiyaDonus(doviz.Euro).toFixed(4) : '—', degisim: degisimEtiketi(0, doviz.EuroDegisim) });
        maddeler.push({ sinif: 'altin', ikon: 'Au', ad: 'Gram Altın', deger: sayiyaDonus(doviz.Altin) ? sayiyaDonus(doviz.Altin).toLocaleString('tr-TR') : '—', degisim: degisimEtiketi(0, doviz.AltinDegisim) });
        maddeler.push({ sinif: 'petrol', ikon: '⛽', ad: 'Petrol (varil)', deger: sayiyaDonus(doviz.Petrol) ? sayiyaDonus(doviz.Petrol).toLocaleString('tr-TR') + '$' : '—', degisim: degisimEtiketi(0, doviz.PetrolDegisim) });
    } else {
        maddeler.push({ sinif: 'usd', ikon: '$', ad: 'USD/TRY', deger: usdTry ? usdTry.toFixed(4) : '—', degisim: '' });
    }

    /* Altın yedeği */
    if (!doviz || !sayiyaDonus(doviz.Altin)) {
        try {
            const d = await (await fetch('https://api.gold-api.com/price/XAU')).json();
            const gram = d.price && usdTry ? d.price * usdTry / 31.1035 : 0;
            if (gram && !maddeler.find((m) => m.ad === 'Gram Altın')) {
                maddeler.splice(2, 0, { sinif: 'altin', ikon: 'Au', ad: 'Gram Altın', deger: gram.toLocaleString('tr-TR'), degisim: '' });
            }
        } catch (e) { /* sessiz */ }
    }

    /* Kripto: CoinGecko */
    try {
        const d = await (await fetch('https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum&vs_currencies=try&include_24hr_change=true')).json();
        const btc = d.bitcoin && d.bitcoin.try;
        const eth = d.ethereum && d.ethereum.try;
        const btcD = d.bitcoin && d.bitcoin.try_24h_change;
        const ethD = d.ethereum && d.ethereum.try_24h_change;
        if (btc) maddeler.push({ sinif: 'btc', ikon: '₿', ad: 'Bitcoin', deger: Math.round(btc).toLocaleString('tr-TR') + ' ₺', degisim: degisimEtiketi(btcD || 0, (btcD >= 0 ? '%' : '') + Math.abs(btcD || 0).toFixed(2) + '%') });
        if (eth) maddeler.push({ sinif: 'eth', ikon: 'Ξ', ad: 'Ethereum', deger: Math.round(eth).toLocaleString('tr-TR') + ' ₺', degisim: degisimEtiketi(ethD || 0, (ethD >= 0 ? '%' : '') + Math.abs(ethD || 0).toFixed(2) + '%') });
    } catch (e) { /* sessiz */ }

    /* Hava durumu: Open-Meteo (İstanbul) */
    try {
        const d = await (await fetch('https://api.open-meteo.com/v1/forecast?latitude=41.0082&longitude=28.9784&current=temperature_2m,weather_code,wind_speed_10m&timezone=auto')).json();
        const c = d.current || {};
        const ikonlar = { 0: '☀️', 1: '🌤', 2: '🌤', 3: '☁️', 45: '🌫', 48: '🌫', 51: '🌦', 53: '🌦', 55: '🌧', 61: '🌧', 63: '🌧', 65: '🌧', 71: '🌨', 73: '🌨', 75: '🌨', 80: '🌦', 81: '🌧', 82: '🌧', 95: '⛈', 96: '⛈', 99: '⛈' };
        maddeler.push({ sinif: 'hava', ikon: ikonlar[c.weather_code] || '🌡', ad: 'İstanbul', deger: Math.round(c.temperature_2m) + '°C', degisim: '' });
    } catch (e) { /* sessiz */ }

    const parc = maddeler.map((m) =>
        '<div class="market-item">' +
        '<div class="market-icon ' + m.sinif + '">' + m.ikon + '</div>' +
        '<div class="market-bilgi">' +
        '<span class="market-adi">' + m.ad + '</span>' +
        '<span class="market-deger">' + escapeHtml(m.deger) + ' ' + (m.degisim || '') + '</span>' +
        '</div></div>'
    ).join('');
    ic.innerHTML = parc + parc; /* kusursuz döngü için 2 kopya */
}

/* ── Kategoriler ───────────────────────────────────────────── */
function renderKategoriNav() {
    const nav = $('#category-nav');
    const adetler = {};
    haberler.forEach((h) => { adetler[h.kategori] = (adetler[h.kategori] || 0) + 1; });
    const butonlar = [{ ad: 'Tümü', ikon: '⚡' }].concat(KATEGORILER);
    nav.innerHTML = butonlar.map((k) => {
        const sayi = k.ad === 'Tümü' ? haberler.length : (adetler[k.ad] || 0);
        const sinif = 'cat-btn' + (k.ad === aktifKategori ? ' active' : '');
        return '<button class="' + sinif + '" role="tab" aria-selected="' + (k.ad === aktifKategori) + '" data-kat="' + escapeHtml(k.ad) + '">' +
            '<span class="cat-icon">' + k.ikon + '</span>' + escapeHtml(k.ad) +
            (sayi ? '<span class="cat-sayac">' + sayi + '</span>' : '') + '</button>';
    }).join('');
    nav.querySelectorAll('.cat-btn').forEach((b) => b.addEventListener('click', () => kategoriSec(b.dataset.kat)));
}

function kategoriSec(ad) {
    aktifKategori = ad;
    renderKategoriNav();
    renderIcerik();
    $('#ana-sayfa').scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/* ── Son dakika bandı ──────────────────────────────────────── */
function renderBant() {
    const sari = haberler.filter((h) => h.son_dakika).slice(0, 12);
    const kutu = $('#ticker-wrap');
    if (!sari.length) { kutu.style.display = 'none'; return; }
    if (!ayarlar.ticker) { kutu.style.display = 'none'; return; }
    const parc = sari.map((h) =>
        '<span class="ticker-item" data-link="' + escapeHtml(h.link) + '">' + escapeHtml(h.baslik) + '</span>'
    ).join('');
    $('#ticker-track').innerHTML = parc + parc;
    kutu.style.display = 'flex';
}

/* ── Haber ızgarası ────────────────────────────────────────── */
function filtrele() {
    let liste = haberler.slice();
    if (aktifKategori !== 'Tümü') liste = liste.filter((h) => h.kategori === aktifKategori);
    if (aramaMetni) {
        const a = norm(aramaMetni);
        liste = liste.filter((h) => norm(h.baslik + ' ' + h.aciklama).includes(a));
    }
    if (sirala === 'eski') liste.reverse();
    return liste;
}

function iskeletCiz() {
    $('#haberler-listesi').classList.remove('liste-modu');
    let h = '';
    for (let i = 0; i < 6; i++) {
        h += '<div class="iskelet"><div class="iskelet-kenar"></div><div class="iskelet-govde">' +
            '<div class="iskelet-cizgi kisa"></div><div class="iskelet-cizgi"></div>' +
            '<div class="iskelet-cizgi orta"></div></div></div>';
    }
    $('#haberler-listesi').innerHTML = h;
}

function durumPaneli(tip) {
    const kutu = $('#haberler-listesi');
    kutu.classList.remove('liste-modu');
    let icerik = '';
    if (tip === 'bos') {
        icerik = '<div class="durum-panel"><div class="durum-emoji">🔍</div>' +
            '<div class="durum-baslik">Haber bulunamadı</div>' +
            '<div class="durum-metin">Bu filtrelerle eşleşen haber yok. Arama terimini değiştirin veya farklı bir kategori deneyin.</div></div>';
    } else {
        icerik = '<div class="durum-panel"><div class="durum-emoji">📡</div>' +
            '<div class="durum-baslik">Haberler henüz yüklenmedi</div>' +
            '<div class="durum-metin">Otomatik haber botu ilk çalışmasında haberleri buraya aktaracak. GitHub Actions her 30 dakikada bir güncelleme yapar.</div>' +
            '<button class="neon-btn" style="width:auto" onclick="verileriYenile(true)"><span>⚡ Tekrar Dene</span></button></div>';
    }
    kutu.innerHTML = icerik;
}

function renderIcerik() {
    const kutu = $('#haberler-listesi');
    kutu.classList.toggle('liste-modu', gorunum === 'liste');
    const liste = filtrele();
    sonFiltre = liste;

    $('#sonuc-sayac').textContent = aramaMetni
        ? liste.length + ' sonuç • "' + aramaMetni + '"'
        : liste.length + ' haber';

    if (!haberler.length) { durumPaneli('haberler-bulunamadi'); return; }
    if (!liste.length) { durumPaneli('bos'); return; }

    kutu.innerHTML = liste.map((h, i) => kartHtml(h, i)).join('');
    kutu.querySelectorAll('.news-card').forEach((k, i) => {
        k.addEventListener('click', () => detayAc(liste[i]));
    });
    /* görsel yüklenemezse yer tutucuya geç */
    kutu.querySelectorAll('.kart-resim-kenar img').forEach((img) => {
        img.addEventListener('error', () => {
            const kart = img.closest('.news-card');
            const idx = Array.prototype.indexOf.call(kutu.children, kart);
            const h = liste[idx];
            if (!h) { img.remove(); return; }
            const div = document.createElement('div');
            div.className = 'kart-tutucu';
            div.style.backgroundImage = 'url(' + tutucuUri(kategoriIkonu(h.kategori), h.kaynak) + ')';
            div.style.backgroundSize = 'cover';
            div.setAttribute('data-kaynak', h.kaynak);
            img.replaceWith(div);
        });
    });
}

function kartHtml(h, i) {
    const gorsel = ayarlar.gorsel && h.resim
        ? '<img src="' + escapeHtml(h.resim) + '" alt="" loading="lazy">'
        : '<div class="kart-tutucu" style="background-image:url(' + tutucuUri(kategoriIkonu(h.kategori), h.kaynak) + ');background-size:cover" data-kaynak="' + escapeHtml(h.kaynak) + '"></div>';
    return '<article class="news-card gir-animasyon" data-index="' + i + '" style="animation-delay:' + (i % 10) * 0.05 + 's">' +
        '<div class="kart-resim-kenar">' + gorsel + '<div class="kart-ust-banti"></div>' +
        '<div class="kart-rozetler">' +
        '<span class="kaynak-rozet kaynak-renk" data-kaynak="' + escapeHtml(h.kaynak_id || '') + '"><span class="kaynak-nokta"></span>' + escapeHtml(h.kaynak) + '</span>' +
        (h.son_dakika ? '<span class="son-dakika-rozet">⚡ SON DAKİKA</span>' : '') +
        '</div></div>' +
        '<div class="kart-govde">' +
        '<div class="kart-meta"><span class="kart-kategori">' + kategoriIkonu(h.kategori) + ' ' + escapeHtml(h.kategori) + '</span>' +
        '<span class="kart-zaman">' + relativeZaman(h.tarih) + '</span></div>' +
        '<h2 class="kart-baslik">' + escapeHtml(h.baslik) + '</h2>' +
        '<p class="kart-aciklama">' + escapeHtml(h.aciklama) + '</p>' +
        '<div class="kart-dip">' +
        '<span class="kart-oku">Devamını Oku <svg width="13" height="13" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M9 5l7 7-7 7"/></svg></span>' +
        '<span class="kart-link-bas">' + escapeHtml(h.kaynak_url || '') + '</span>' +
        '</div></div></article>';
}

/* ── Detay görünümü ────────────────────────────────────────── */
function detayAc(h) {
    if (!h) return;
    seciliDetay = h;
    window.scrollTo({ top: 0 });

    const resim = $('#detay-resim');
    const hero = $('#detay-hero');
    const varOl = tutucuUri(kategoriIkonu(h.kategori), h.kaynak, true);
    if (ayarlar.gorsel && h.resim) {
        hero.style.backgroundImage = '';
        hero.style.backgroundSize = '';
        hero.style.backgroundPosition = '';
        resim.src = h.resim;
        resim.style.display = 'block';
        resim.onerror = function () {
            this.style.display = 'none';
            hero.style.backgroundImage = 'url(' + varOl + ')';
            hero.style.backgroundSize = 'cover';
            hero.style.backgroundPosition = 'center';
        };
    } else {
        resim.style.display = 'none';
        resim.removeAttribute('src');
        hero.style.backgroundImage = 'url(' + varOl + ')';
        hero.style.backgroundSize = 'cover';
        hero.style.backgroundPosition = 'center';
    }

    $('#detay-baslik').textContent = h.baslik;
    $('#detay-meta').innerHTML =
        '<span class="detay-rozet kategori">' + kategoriIkonu(h.kategori) + ' ' + escapeHtml(h.kategori) + '</span>' +
        '<span class="detay-rozet kaynak kaynak-renk" data-kaynak="' + escapeHtml(h.kaynak_id || '') + '"><span class="kaynak-nokta"></span>' + escapeHtml(h.kaynak) + '</span>' +
        '<span class="detay-rozet zaman">🕐 ' + uzunTarih(h.tarih) + '</span>';

    let govde = '';
    if (h.tam_metin) {
        govde = h.tam_metin;
    }
    if (h.aciklama && !h.tam_metin) {
        govde += '<p>' + escapeHtml(h.aciklama) + '</p>';
    }
    govde += '<div class="kaynak-notu">📄 Bu haber <strong>' + escapeHtml(h.kaynak) + '</strong> kaynağından toplanmıştır. Tam metni ve güncel gelişmeleri: <a href="' + escapeHtml(h.link) + '" target="_blank" rel="noopener">kaynağa git →</a></div>';
    $('#detay-icerik').innerHTML = govde;

    $('#detay-aksiyonlar').innerHTML =
        '<a class="aksiyon-btn prim" href="' + escapeHtml(h.link) + '" target="_blank" rel="noopener">🔗 Kaynağa Git</a>' +
        '<button class="aksiyon-btn" id="pay-wa">💬 WhatsApp</button>' +
        '<button class="aksiyon-btn" id="pay-x">𝕏 Paylaş</button>' +
        '<button class="aksiyon-btn" id="pay-kopya">📋 Linki Kopyala</button>';
    $('#pay-wa').onclick = () => window.open('https://wa.me/?text=' + encodeURIComponent(h.baslik + ' ' + h.link), '_blank');
    $('#pay-x').onclick = () => window.open('https://twitter.com/intent/tweet?text=' + encodeURIComponent(h.baslik) + '&url=' + encodeURIComponent(h.link), '_blank');
    $('#pay-kopya').onclick = () => {
        navigator.clipboard.writeText(h.link).then(
            () => toast(' Link kopyalandı'),
            () => toast('Kopyalama başarısız', 'hata')
        );
    };

    /* Benzer haberler */
    const benzer = haberler.filter((x) => x.kategori === h.kategori && x.link !== h.link).slice(0, 4);
    const blok = $('#ilgili-blok');
    blok.classList.toggle('bos', !benzer.length);
    $('#ilgili-liste').innerHTML = benzer.map((b) =>
        '<div class="ilgili-kart" data-link="' + escapeHtml(b.link) + '"><h4>' + escapeHtml(b.baslik) + '</h4>' +
        '<div class="ilgili-meta">' + escapeHtml(b.kaynak) + ' • ' + relativeZaman(b.tarih) + '</div></div>'
    ).join('');
    $('#ilgili-liste').querySelectorAll('.ilgili-kart').forEach((k) => {
        k.addEventListener('click', () => {
            const b = haberler.find((x) => x.link === k.dataset.link);
            if (b) detayAc(b);
        });
    });

    document.title = h.baslik + ' — GÜNDEM';
    $('#ana-sayfa').style.display = 'none';
    $('#category-nav').style.display = 'none';
    $('#detay-sayfasi').style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function detayYenidenCiz() {
    if (!seciliDetay) return;
    const b = haberler.find((x) => x.link === seciliDetay.link);
    if (b) detayAc(b);
}

function detayKapat() {
    if ($('#detay-sayfasi').style.display === 'none') return;
    seciliDetay = null;
    document.title = 'GÜNDEM — Premium Haber';
    $('#detay-sayfasi').style.display = 'none';
    $('#ana-sayfa').style.display = 'block';
    $('#category-nav').style.display = 'flex';
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

/* ── Alt bilgi + bot durumu ────────────────────────────────── */
function feedSlug(ad) {
    let t = ad.toLocaleLowerCase('tr-TR');
    t = t.replace(/ş/g, 's').replace(/ğ/g, 'g').replace(/ü/g, 'u').replace(/ı/g, 'i').replace(/ö/g, 'o').replace(/ç/g, 'c');
    return t.replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'tum';
}

function renderRapor() {
    /* alt bilgi kaynak listesi */
    const liste = $('#kaynak-liste');
    if (rapor && rapor.kaynaklar) {
        liste.innerHTML = Object.entries(rapor.kaynaklar).map(([ad, d]) =>
            '<li><span class="k-durum ' + (d.durum === 'aktif' ? '' : 'hata') + '"></span>' + escapeHtml(ad) + '</li>'
        ).join('');
    }
    const linkler = $('#alt-linkler');
    linkler.innerHTML =
        '<li><a href="feeds/tum.xml" target="_blank" rel="noopener">📡 Tüm Haberler (RSS)</a></li>' +
        KATEGORILER.map((k) => '<li><a href="feeds/' + feedSlug(k.ad) + '.xml" target="_blank" rel="noopener">📡 ' + escapeHtml(k.ad) + ' (RSS)</a></li>').join('');

    if (rapor) {
        const sure = relativeZaman(rapor.son_guncelleme);
        $('#bot-bilgi').textContent =
            'Bot v' + rapor.surum + ' • Son çalışma ' + sure +
            ' • ' + rapor.toplam_haber + ' haber • ' +
            rapor.aktif_kaynak + '/' + rapor.kaynak_sayisi + ' kaynak aktif • ' +
            rapor.sure_saniye + ' sn';
        $('#son-guncelleme').innerHTML = '<span class="nabiz-nokta"></span> güncellendi: ' + sure;
        $('#bot-son-guncelleme').textContent = uzunTarih(rapor.son_guncelleme);
        $('#bot-toplam').textContent = rapor.toplam_haber + ' haber';
        $('#bot-kaynak').textContent = rapor.aktif_kaynak + ' / ' + rapor.kaynak_sayisi;
        $('#bot-sure').textContent = rapor.sure_saniye + ' sn';
    } else {
        $('#bot-bilgi').textContent = 'Bot raporu henüz mevcut değil.';
        $('#son-guncelleme').textContent = '';
    }
}

/* ── Toplu render ──────────────────────────────────────────── */
function renderHepsi() {
    renderKategoriNav();
    renderBant();
    renderIcerik();
    renderRapor();
}

/* ── Olay bağlama ──────────────────────────────────────────── */
function olaylariBagla() {
    /* tema hızlı düğmesi */
    $('#btn-tema').addEventListener('click', () => {
        ayarlar.tema = ayarlar.tema === 'koyu' ? 'acik' : 'koyu';
        ayarlarKaydet(); ayarlariUygula();
    });

    /* yenile */
    $('#btn-yenile').addEventListener('click', () => verileriYenile(true));
    $('#btn-cerceve-yenile').addEventListener('click', () => verileriYenile(true));

    /* arama */
    const arama = $('#arama');
    const saraci = $('#arama-saraci');
    let aramaZ = null;
    arama.addEventListener('input', () => {
        clearTimeout(aramaZ);
        aramaZ = setTimeout(() => {
            aramaMetni = arama.value.trim();
            renderIcerik();
        }, 220);
    });
    arama.addEventListener('focus', () => saraci.classList.add('aktif'));
    arama.addEventListener('blur', () => { if (!arama.value) saraci.classList.remove('aktif'); });
    saraci.addEventListener('click', (e) => {
        if (e.target !== arama) arama.focus();
    });

    /* sıralama */
    $('#sirala').addEventListener('change', (e) => {
        sirala = e.target.value;
        renderIcerik();
    });

    /* görünüm */
    $$('.gorunum-btn').forEach((b) => b.addEventListener('click', () => {
        gorunum = b.dataset.gorunum;
        $$('.gorunum-btn').forEach((x) => x.classList.toggle('active', x === b));
        renderIcerik();
    }));

    /* geri */
    $('#btn-geri').addEventListener('click', detayKapat);
    $('#marka').addEventListener('click', (e) => { e.preventDefault(); detayKapat(); aktifKategori = 'Tümü'; renderKategoriNav(); renderIcerik(); window.scrollTo({ top: 0, behavior: 'smooth' }); });

    /* bant tıklamaları (delegasyon) */
    $('#ticker-track').addEventListener('click', (e) => {
        const el = e.target.closest('.ticker-item');
        if (!el) return;
        const h = haberler.find((x) => x.link === el.dataset.link);
        if (h) detayAc(h);
    });

    /* çekmece */
    const cerceve = $('#ayarlar-cercevesi');
    const arka = $('#drawer-arki');
    const cerceveAc = () => { arka.hidden = false; requestAnimationFrame(() => arka.classList.add('goster')); cerceve.classList.add('acik'); };
    const cerceveKapat = () => { cerceve.classList.remove('acik'); arka.classList.remove('goster'); setTimeout(() => { arka.hidden = true; }, 350); };
    $('#btn-ayarlar').addEventListener('click', cerceveAc);
    $('#btn-cerceve-kapat').addEventListener('click', cerceveKapat);
    arka.addEventListener('click', cerceveKapat);

    /* ayar seçimleri */
    $$('[data-ayar]').forEach((grup) => {
        const anahtar = grup.dataset.ayar;
        if (grup.classList.contains('anahtar')) {
            grup.addEventListener('click', () => {
                ayarlar[anahtar] = !ayarlar[anahtar];
                ayarlarKaydet(); ayarlariUygula();
                if (anahtar === 'ticker') renderBant();
                if (anahtar === 'gorsel') renderIcerik();
                if (anahtar === 'piyasa' && ayarlar.piyasa) piyasayiGetir();
            });
            return;
        }
        grup.querySelectorAll('button[data-deger]').forEach((b) => b.addEventListener('click', () => {
            ayarlar[anahtar] = b.dataset.deger;
            ayarlarKaydet(); ayarlariUygula();
            if (anahtar === 'yenile') yenileZamanlamayiKur();
            if (anahtar === 'gorsel') renderIcerik();
        }));
    });

    /* klavye */
    document.addEventListener('keydown', (e) => {
        const yazidaMi = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
        if (e.key === '/' && !yazidaMi) {
            e.preventDefault();
            arama.focus();
        } else if (e.key === 'Escape') {
            if (cerceve.classList.contains('acik')) cerceveKapat();
            else if (document.activeElement === arama) { arama.value = ''; aramaMetni = ''; renderIcerik(); arama.blur(); }
            else detayKapat();
        } else if ((e.key === 'r' || e.key === 'R') && !yazidaMi) {
            verileriYenile(true);
        }
    });

    /* okuma ilerlemesi */
    window.addEventListener('scroll', () => {
        const st = window.scrollY;
        const dh = document.documentElement.scrollHeight - window.innerHeight;
        $('#ilerleme-cubugu').style.width = (dh > 0 ? (st / dh) * 100 : 0) + '%';
    });

    /* sekmeye dönüşte yenile */
    document.addEventListener('visibilitychange', () => {
        if (!document.hidden && haberler.length) {
            const son = rapor ? new Date(rapor.son_guncelleme).getTime() : 0;
            if (Date.now() - son > 5 * 60000) verileriYenile(false);
        }
    });
}

/* ── Başlatma ──────────────────────────────────────────────── */
function baslat() {
    ayarlarYukle();
    ayarlariUygula();
    saatCalistir();
    olaylariBagla();
    iskeletCiz();
    verileriYenile(false);
    piyasayiGetir();
    yenileZamanlamayiKur();
    setInterval(() => { if (ayarlar.piyasa) piyasayiGetir(); }, 5 * 60000);
    setTimeout(() => $('#splash').classList.add('gizli'), 2100);
}

document.addEventListener('DOMContentLoaded', baslat);
