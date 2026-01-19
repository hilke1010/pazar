import streamlit as st
import pandas as pd
import os
import gc
import psutil
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from thefuzz import process, fuzz
import plotly.express as px
import plotly.graph_objects as go
import re
from dateutil.relativedelta import relativedelta
import datetime

# --- GÜVENLİ IMPORT ---
try:
    import yfinance as yf
    DOLAR_MODULU_VAR = True
except ImportError:
    DOLAR_MODULU_VAR = False

# --- AYARLAR ---
DOSYA_KLASORU = 'raporlar'
LIKITGAZ_NAME = "LİKİTGAZ DAĞITIM VE ENDÜSTRİ A.Ş."
LIKITGAZ_COLOR = "#DC3912" 
OTHER_COLORS = px.colors.qualitative.Set2

TR_AYLAR = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran', 7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}
TR_AYLAR_KISA = {1: 'Oca', 2: 'Şub', 3: 'Mar', 4: 'Nis', 5: 'May', 6: 'Haz', 7: 'Tem', 8: 'Ağu', 9: 'Eyl', 10: 'Eki', 11: 'Kas', 12: 'Ara'}
DOSYA_AY_MAP = {'ocak': 1, 'subat': 2, 'mart': 3, 'nisan': 4, 'mayis': 5, 'haziran': 6, 'temmuz': 7, 'agustos': 8, 'eylul': 9, 'ekim': 10, 'kasim': 11, 'aralik': 12}
BAYRAMLAR = [{"Tarih": f"{y}-{m:02d}-01", "Isim": n} for y in range(2022, 2026) for m, n in [(4, "Ramazan B."), (6, "Kurban B.")]]

# ÖZEL DÜZELTMELER
OZEL_DUZELTMELER = {
    "AYTEMİZ": "AYTEMİZ AKARYAKIT DAĞITIM A.Ş.",
    "BALPET": "BALPET PETROL ÜRÜNLERİ TAŞ. SAN. VE TİC. A.Ş.",
    "ECOGAZ": "ECOGAZ LPG DAĞITIM A.Ş.",
    "AYGAZ": "AYGAZ A.Ş.",
    "İPRAGAZ": "İPRAGAZ A.Ş.",
    "LİKİTGAZ": LIKITGAZ_NAME,
    "BP": "BP PETROLLERİ A.Ş.",
    "SHELL": "SHELL & TURCAS PETROL A.Ş.",
    "PETROL OFİSİ": "PETROL OFİSİ A.Ş.",
    "HABAŞ": "HABAŞ PETROL ÜRÜNLERİ SAN. VE TİC. A.Ş.",
    "TP PETROL": "TP PETROL DAĞITIM A.Ş.",
    "GÜZEL ENERJİ": "GÜZEL ENERJİ AKARYAKIT A.Ş.",
    "MİLANGAZ": "MİLANGAZ LPG DAĞITIM TİC. VE SAN. A.Ş.",
    "MİNACILAR": "MİNACILAR LPG DEPOLAMA A.Ş.",
    "KADOOĞLU": "KADOOĞLU PETROLCÜLÜK TAŞ. TİC. SAN. İTH. VE İHR. A.Ş.",
    "TERMOPET": "TERMOPET AKARYAKIT A.Ş.",
    "ERGAZ": "ERGAZ SAN. VE TİC. A.Ş.",
    "BLUEPET": "ERGAZ SAN. VE TİC. A.Ş.",
}

STOP_WORDS = ["A.Ş", "A.S", "A.Ş.", "LTD", "ŞTİ", "STI", "SAN", "VE", "TİC", "TIC", "PETROL", "ÜRÜNLERİ", "URUNLERI", "DAĞITIM", "DAGITIM", "GAZ", "LPG", "AKARYAKIT", "ENERJİ", "ENERJI", "NAKLİYE", "NAKLIYE", "İNŞAAT", "INSAAT", "PAZARLAMA", "DEPOLAMA", "TURİZM", "TURIZM", "SANAYİ", "SANAYI"]

# --- YARDIMCI FONKSİYONLAR ---
def get_total_ram_usage():
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

def format_tarih_tr(date_obj):
    if pd.isna(date_obj): return ""
    return f"{TR_AYLAR.get(date_obj.month, '')} {date_obj.year}"

def format_tarih_grafik(date_obj):
    if pd.isna(date_obj): return ""
    return f"{TR_AYLAR_KISA.get(date_obj.month, '')} {date_obj.year}"

def iter_block_items(parent):
    if isinstance(parent, _Document): parent_elm = parent.element.body
    elif isinstance(parent, _Cell): parent_elm = parent._tc
    else: raise ValueError("Hata")
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P): yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl): yield Table(child, parent)

def dosya_isminden_tarih(filename):
    base = os.path.splitext(filename)[0].lower().replace('ş','s').replace('ı','i').replace('ğ','g').replace('ü','u').replace('ö','o').replace('ç','c')
    match = re.match(r"([a-z]+)(\d{2})", base)
    if match:
        ay, yil = match.groups()
        if ay in DOSYA_AY_MAP: return pd.Timestamp(year=2000+int(yil), month=DOSYA_AY_MAP[ay], day=1)
    return None

def sayi_temizle(text):
    try: return float(text.replace('.', '').replace(',', '.'))
    except: return 0.0

def ismi_temizle_kok(isim):
    isim = isim.upper().replace('İ', 'I').replace('.', ' ')
    kelimeler = isim.split()
    temiz_kelimeler = [k for k in kelimeler if k not in STOP_WORDS and len(k) > 2]
    return " ".join(temiz_kelimeler) if temiz_kelimeler else isim

def sirket_ismi_standartlastir(ham_isim, mevcut_isimler):
    ham_isim = ham_isim.strip()
    ham_upper = ham_isim.upper().replace('İ', 'I')
    for k, v in OZEL_DUZELTMELER.items():
        if k.upper().replace('İ', 'I') in ham_upper: return v
    if mevcut_isimler:
        ham_kok = ismi_temizle_kok(ham_upper)
        en_iyi, skor = None, 0
        for mevcut in mevcut_isimler:
            skor_temp = fuzz.ratio(ham_kok, ismi_temizle_kok(mevcut))
            if skor_temp > skor: en_iyi, skor = mevcut, skor_temp
        if skor >= 95: return en_iyi
    return ham_isim

def sehir_ismi_duzelt(sehir):
    return sehir.replace('İ', 'i').replace('I', 'ı').title() if sehir else ""

@st.cache_data
def dolar_verisi_getir(baslangic_tarihi):
    if not DOLAR_MODULU_VAR: return pd.DataFrame()
    try:
        dolar = yf.download("TRY=X", start=baslangic_tarihi, progress=False)
        if dolar.empty: return pd.DataFrame()
        dolar_aylik = dolar['Close'].resample('MS').mean().reset_index()
        dolar_aylik.columns = ['Tarih', 'Dolar Kuru']
        return dolar_aylik
    except: return pd.DataFrame()

def grafik_bayram_ekle(fig, df_dates):
    if df_dates.empty: return fig
    min_date, max_date = df_dates.min(), df_dates.max()
    for bayram in BAYRAMLAR:
        b_date = pd.to_datetime(bayram["Tarih"])
        if min_date <= b_date <= max_date:
            fig.add_vline(x=b_date, line_width=1, line_dash="dot", line_color="#333", opacity=0.4)
            fig.add_annotation(x=b_date, y=1, yref="paper", text=bayram["Isim"], showarrow=False, textangle=-90, yanchor="top")
    return fig

# --- VERİ OKUMA ---
@st.cache_data
def verileri_oku():
    tum_veri_sirket, tum_veri_iller = [], []
    
    # 3.1 ve 3.2 İçin (Toptan)
    tum_toptan_aylik, tum_toptan_kumulatif = [], []
    
    # 3.5 ve 3.6 İçin (Genel Satış - Türkiye)
    tum_genel_aylik, tum_genel_kumulatif = [], []
    
    # 3.7 İçin (Karşılaştırma)
    tum_karsilastirma = []
    
    sirket_listesi = set()
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx') or f.endswith('.doc')])
    
    for dosya in files:
        tarih = dosya_isminden_tarih(dosya)
        if not tarih: continue
        try: doc = Document(os.path.join(DOSYA_KLASORU, dosya))
        except: continue
        son_baslik, son_sehir_sirket = "", None
        
        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if len(text) > 5:
                    son_baslik = text
                    if text.startswith("Tablo") and ":" in text:
                        parts = text.split(":")
                        if len(parts)>1 and 2<len(parts[1].strip())<40: son_sehir_sirket = parts[1].strip()
                    else: son_sehir_sirket = None
            
            elif isinstance(block, Table):
                # -------------------------------------------------------------
                # 1. TOPTAN SATIŞLAR (Tablo 3.1 ve 3.2)
                # -------------------------------------------------------------
                if "DAĞITICILAR ARASI" in son_baslik.upper():
                    # Başlıkta "OCAK" veya "DÖNEMLERİ" geçiyorsa Kümülatiftir
                    is_cumulative = ("OCAK" in son_baslik.upper() or "DÖNEMLERİ" in son_baslik.upper())
                    target_list = tum_toptan_kumulatif if is_cumulative else tum_toptan_aylik
                    
                    try:
                        for row in block.rows:
                            if len(row.cells) < 9: continue
                            isim = row.cells[0].text.strip()
                            if not isim or "TOPLAM" in isim.upper() or "SATIŞ YAPAN" in isim.upper(): continue
                            
                            std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                            sirket_listesi.add(std_isim)
                            
                            target_list.append({
                                'Tarih': tarih,
                                'Şirket': std_isim,
                                'Tüplü Ton': sayi_temizle(row.cells[1].text),
                                'Tüplü Pay': sayi_temizle(row.cells[2].text),
                                'Dökme Ton': sayi_temizle(row.cells[3].text),
                                'Dökme Pay': sayi_temizle(row.cells[4].text),
                                'Otogaz Ton': sayi_temizle(row.cells[5].text),
                                'Otogaz Pay': sayi_temizle(row.cells[6].text),
                                'Toplam Ton': sayi_temizle(row.cells[7].text),
                                'Toplam Pay': sayi_temizle(row.cells[8].text)
                            })
                    except: pass

                # -------------------------------------------------------------
                # 2. GENEL SATIŞLAR (Tablo 3.5 ve 3.6)
                # -------------------------------------------------------------
                elif "ÜRÜN TÜRÜNE GÖRE DAĞILIMI" in son_baslik.upper():
                    is_cumulative = ("OCAK" in son_baslik.upper() or "DÖNEMLERİ" in son_baslik.upper())
                    target_list = tum_genel_kumulatif if is_cumulative else tum_genel_aylik
                    
                    try:
                        for row in block.rows:
                            if len(row.cells) < 9: continue
                            isim = row.cells[0].text.strip()
                            if not isim or "TOPLAM" in isim.upper() or "LİSANS" in isim.upper(): continue
                            
                            std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                            sirket_listesi.add(std_isim)
                            
                            target_list.append({
                                'Tarih': tarih,
                                'Şirket': std_isim,
                                'Tüplü Ton': sayi_temizle(row.cells[1].text),
                                'Tüplü Pay': sayi_temizle(row.cells[2].text),
                                'Dökme Ton': sayi_temizle(row.cells[3].text),
                                'Dökme Pay': sayi_temizle(row.cells[4].text),
                                'Otogaz Ton': sayi_temizle(row.cells[5].text),
                                'Otogaz Pay': sayi_temizle(row.cells[6].text),
                                'Toplam Ton': sayi_temizle(row.cells[7].text),
                                'Toplam Pay': sayi_temizle(row.cells[8].text)
                            })
                    except: pass

                # -------------------------------------------------------------
                # 3. KARŞILAŞTIRMA (Tablo 3.7) - Şirket Bazlı
                # -------------------------------------------------------------
                elif "3.7" in son_baslik or ("LİSANS" in son_baslik.upper() and "KARŞILAŞTIRMA" in son_baslik.upper()):
                    try:
                        # Bu tablo yapısı biraz karışık (Merged Cells olabilir). 
                        # Genelde: Şirket | Ürün | Tarih1 Ton | Tarih1 Pay | Tarih2 Ton | Tarih2 Pay | Değişim
                        mevcut_sirket_37 = None
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 6: continue
                            
                            # İlk hücrede şirket adı varsa al, yoksa önceki satırdan devam (merged cell mantığı)
                            raw_sirket = cells[0].text.strip()
                            if raw_sirket and "LİSANS" not in raw_sirket.upper():
                                mevcut_sirket_37 = sirket_ismi_standartlastir(raw_sirket, sirket_listesi)
                                sirket_listesi.add(mevcut_sirket_37)
                            
                            if not mevcut_sirket_37: continue
                            
                            urun = cells[1].text.strip().title() # Dökme, Otogaz vs.
                            if urun in ["Dökme", "Otogaz", "Tüplü", "Firma Toplamı"]:
                                # Değerler genellikle sondan başa doğru sabittir
                                # Değişim(%), Cari Yıl Pay(%), Cari Yıl Ton, Geçen Yıl Pay(%), Geçen Yıl Ton
                                # Tablo yapısına göre indexleri ayarlıyoruz (Resim 3'e göre)
                                # Resim: Şirket | Ürün | Ton 2024 | Pay 2024 | Ton 2025 | Pay 2025 | Değişim
                                try:
                                    ton_once = sayi_temizle(cells[2].text)
                                    pay_once = sayi_temizle(cells[3].text)
                                    ton_cari = sayi_temizle(cells[4].text)
                                    pay_cari = sayi_temizle(cells[5].text)
                                    degisim = sayi_temizle(cells[6].text)
                                    
                                    tum_karsilastirma.append({
                                        'Tarih': tarih,
                                        'Şirket': mevcut_sirket_37,
                                        'Ürün': urun,
                                        'Önceki Ton': ton_once,
                                        'Önceki Pay': pay_once,
                                        'Cari Ton': ton_cari,
                                        'Cari Pay': pay_cari,
                                        'Değişim %': degisim
                                    })
                                except: pass
                    except: pass

                # -------------------------------------------------------------
                # 4. İL BAZLI VERİLER (Tablo 4.x)
                # -------------------------------------------------------------
                elif "İLLERE" in son_baslik.upper() and "DAĞILIMI" in son_baslik.upper():
                    for row in block.rows:
                        if len(row.cells) < 6: continue
                        il = row.cells[0].text.strip()
                        if "İL" not in il.upper() and il != "" and "TOPLAM" not in il.upper():
                            t, d, o = sayi_temizle(row.cells[1].text), sayi_temizle(row.cells[3].text), sayi_temizle(row.cells[5].text)
                            if t+d+o > 0: tum_veri_iller.append({'Tarih': tarih, 'Şehir': sehir_ismi_duzelt(il), 'Tüplü Ton': t, 'Dökme Ton': d, 'Otogaz Ton': o})
                
                # -------------------------------------------------------------
                # 5. ŞEHİR DETAYLARI
                # -------------------------------------------------------------
                elif son_sehir_sirket:
                    header = "".join([c.text.lower() for row in block.rows[:2] for c in row.cells])
                    if any(x in header for x in ["tüplü", "dökme", "pay"]):
                        for row in block.rows:
                            if len(row.cells) < 7: continue
                            isim = row.cells[0].text.strip()
                            if not isim or "TOPLAM" in isim.upper(): continue
                            std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                            sirket_listesi.add(std_isim)
                            vals = [sayi_temizle(c.text) for c in row.cells[1:7]]
                            if sum(vals) > 0:
                                tum_veri_sirket.append({
                                    'Tarih': tarih, 'Şehir': sehir_ismi_duzelt(son_sehir_sirket), 'Şirket': std_isim,
                                    'Tüplü Ton': vals[0], 'Tüplü Pay': vals[1], 'Dökme Ton': vals[2], 'Dökme Pay': vals[3], 'Otogaz Ton': vals[4], 'Otogaz Pay': vals[5]
                                })

    gc.collect()
    
    # DATAFRAME OLUŞTURMA
    def create_df(data, group_cols):
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        # Eğer duplicate varsa (örn: aynı şirketin aynı ayda iki satırı) topla
        return df.groupby(group_cols, as_index=False).sum(numeric_only=True)

    # İL VE ŞİRKET DETAYLARI
    df_sirket = create_df(tum_veri_sirket, ['Tarih', 'Şehir', 'Şirket'])
    df_iller = pd.DataFrame(tum_veri_iller) # İller toplanmaz
    
    # TOPTAN (3.1 & 3.2)
    df_toptan_aylik = create_df(tum_toptan_aylik, ['Tarih', 'Şirket'])
    df_toptan_kumulatif = create_df(tum_toptan_kumulatif, ['Tarih', 'Şirket'])
    
    # GENEL (3.5 & 3.6)
    df_genel_aylik = create_df(tum_genel_aylik, ['Tarih', 'Şirket'])
    df_genel_kumulatif = create_df(tum_genel_kumulatif, ['Tarih', 'Şirket'])
    
    # KARŞILAŞTIRMA (3.7) - Toplama yapılmaz, olduğu gibi alınır
    df_karsilastirma = pd.DataFrame(tum_karsilastirma)

    # Tarih formatlama
    for df in [df_sirket, df_iller, df_toptan_aylik, df_toptan_kumulatif, df_genel_aylik, df_genel_kumulatif, df_karsilastirma]:
        if not df.empty:
            df.sort_values('Tarih', inplace=True)
            df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
            df['Tarih_Grafik'] = df['Tarih'].apply(format_tarih_grafik)

    return df_sirket, df_iller, df_toptan_aylik, df_toptan_kumulatif, df_genel_aylik, df_genel_kumulatif, df_karsilastirma

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")

if 'analiz_basladi' not in st.session_state:
    st.session_state['analiz_basladi'] = False
    gc.collect()

# --- GİRİŞ EKRANI ---
if not st.session_state['analiz_basladi']:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("📊 EPDK Stratejik Pazar Analizi")
        st.info("Sistem belleğini (RAM) verimli kullanmak için veriler sadece analiz sırasında yüklenir.")
        if st.button("🚀 ANALİZİ BAŞLAT", type="primary", use_container_width=True):
            st.session_state['analiz_basladi'] = True
            st.rerun()
    st.stop()

# --- ANALİZ EKRANI ---
with st.spinner('Veriler yükleniyor...'):
    df_sirket, df_iller, df_toptan_aylik, df_toptan_kumulatif, df_genel_aylik, df_genel_kumulatif, df_karsilastirma = verileri_oku()

st.title("📊 EPDK Stratejik Pazar Analizi")

if df_sirket.empty and df_genel_aylik.empty:
    st.warning("Veri bulunamadı.")
else:
    # --- SIDEBAR ---
    st.sidebar.header("⚙️ Parametreler")
    
    # 1. ŞEHİR SEÇİMİ
    sehir_listesi = ["TÜRKİYE GENELİ"] + sorted(df_sirket['Şehir'].unique()) if not df_sirket.empty else ["TÜRKİYE GENELİ"]
    secilen_sehir = st.sidebar.selectbox("Bölge / Şehir", sehir_listesi)
    
    # 2. SEGMENT SEÇİMİ (Grafikler için)
    segmentler = ['Otogaz', 'Tüplü', 'Dökme']
    secilen_segment = st.sidebar.selectbox("Segment (Grafik İçin)", segmentler)
    
    # 3. DÖNEM TİPİ
    donem_tipi = st.sidebar.radio("Dönem Tipi:", ["Aylık", "Kümülatif"])

    # --- TABLAR ---
    tab_genel, tab_toptan, tab_karsilastirma, tab_grafik = st.tabs([
        "🇹🇷 Genel Pazar", 
        "🔄 Toptan Satış", 
        "📊 Yıllık Karşılaştırma",
        "📈 Grafikler"
    ])

    # ------------------------------------------
    # TAB 1: GENEL PAZAR (Tablo 3.5 & 3.6 & 4.x)
    # ------------------------------------------
    with tab_genel:
        st.subheader(f"🇹🇷 {secilen_sehir} - Pazar Durumu ({donem_tipi})")
        
        # Veri Kaynağını Belirle
        df_view = pd.DataFrame()
        
        if secilen_sehir == "TÜRKİYE GENELİ":
            # Türkiye geneli için Tablo 3.5 (Aylık) veya 3.6 (Kümülatif)
            df_view = df_genel_kumulatif if donem_tipi == "Kümülatif" else df_genel_aylik
        else:
            # Şehir bazlı ise df_sirket kullanılır
            # Şehir verileri genelde aylıktır. Kümülatif istenirse hesaplanır.
            df_city = df_sirket[df_sirket['Şehir'] == secilen_sehir].copy()
            if donem_tipi == "Kümülatif" and not df_city.empty:
                df_city['Yıl'] = df_city['Tarih'].dt.year
                cols = ['Tüplü Ton', 'Dökme Ton', 'Otogaz Ton']
                df_city[cols] = df_city.groupby(['Yıl', 'Şirket'])[cols].cumsum()
                # Payları yeniden hesapla (Basit yaklaşım: o anki toplama böl)
                # Not: Şehir kümülatif payı için o şehrin toplamına ihtiyaç var.
                # Şimdilik Tonaj odaklı gidelim.
                df_view = df_city
            else:
                df_view = df_city

        if not df_view.empty:
            son_tarih = df_view['Tarih'].max()
            df_son = df_view[df_view['Tarih'] == son_tarih].copy()
            
            # Tablo 3.5 formatı: Toplam Ton'a göre sırala
            if 'Toplam Ton' not in df_son.columns:
                df_son['Toplam Ton'] = df_son['Tüplü Ton'] + df_son['Dökme Ton'] + df_son['Otogaz Ton']
            
            df_son = df_son.sort_values('Toplam Ton', ascending=False).reset_index(drop=True)
            df_son.index += 1
            
            # GÖSTERİLECEK KOLONLAR
            cols_to_show = ['Şirket', 'Tüplü Ton', 'Tüplü Pay', 'Dökme Ton', 'Dökme Pay', 'Otogaz Ton', 'Otogaz Pay', 'Toplam Ton', 'Toplam Pay']
            # Şehir verisinde 'Toplam' olmayabilir, kontrol et
            available_cols = [c for c in cols_to_show if c in df_son.columns]
            
            st.markdown(f"**Dönem:** {format_tarih_tr(son_tarih)}")
            
            # Formatlama
            format_dict = {c: "{:,.2f}" for c in available_cols if "Ton" in c}
            format_dict.update({c: "{:.2f}%" for c in available_cols if "Pay" in c})
            
            st.dataframe(df_son[available_cols].style.format(format_dict), use_container_width=True, height=600)
        else:
            st.warning("Bu kriterlere uygun genel pazar verisi bulunamadı.")

    # ------------------------------------------
    # TAB 2: TOPTAN SATIŞ (Tablo 3.1 & 3.2)
    # ------------------------------------------
    with tab_toptan:
        st.subheader(f"🔄 Dağıtıcılar Arası Toptan LPG Satışları ({donem_tipi})")
        st.caption("Bu veriler Tablo 3.1 (Aylık) ve Tablo 3.2 (Kümülatif) kaynaklıdır.")
        
        # Veri seçimi
        df_top = df_toptan_kumulatif if donem_tipi == "Kümülatif" else df_toptan_aylik
        
        if not df_top.empty:
            son_tarih_toptan = df_top['Tarih'].max()
            df_son_top = df_top[df_top['Tarih'] == son_tarih_toptan].sort_values('Toplam Ton', ascending=False).reset_index(drop=True)
            df_son_top.index += 1
            
            st.markdown(f"**Dönem:** {format_tarih_tr(son_tarih_toptan)}")
            
            # Toptan Tablosu (Resimdeki format)
            cols_top = ['Şirket', 'Tüplü Ton', 'Tüplü Pay', 'Dökme Ton', 'Dökme Pay', 'Otogaz Ton', 'Otogaz Pay', 'Toplam Ton', 'Toplam Pay']
            
            format_dict_top = {c: "{:,.2f}" for c in cols_top if "Ton" in c}
            format_dict_top.update({c: "{:.2f}%" for c in cols_top if "Pay" in c})
            
            st.dataframe(df_son_top[cols_top].style.format(format_dict_top), use_container_width=True, height=600)
            
            # Görselleştirme (Ekstra)
            st.markdown("---")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                fig_top = px.bar(df_son_top.head(10), x='Şirket', y='Toplam Ton', title="Top 10 Toptan Satıcı (Ton)", color='Toplam Ton')
                st.plotly_chart(fig_top, use_container_width=True)
            with col_g2:
                fig_pie = px.pie(df_son_top.head(5), values='Toplam Ton', names='Şirket', title="Pazar Payı Dağılımı (Top 5)")
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning("Toptan satış verisi bulunamadı.")

    # ------------------------------------------
    # TAB 3: KARŞILAŞTIRMA (Tablo 3.7)
    # ------------------------------------------
    with tab_karsilastirma:
        st.subheader("📊 Dönemler Arası Karşılaştırma (Tablo 3.7)")
        
        if not df_karsilastirma.empty:
            # Tarih Seçimi
            tarihler = df_karsilastirma['Dönem'].unique()
            secilen_donem_kar = st.selectbox("Karşılaştırma Dönemi Seç:", tarihler)
            
            df_kar_view = df_karsilastirma[df_karsilastirma['Dönem'] == secilen_donem_kar].copy()
            
            # Şirket Filtresi
            sirketler_kar = ["TÜMÜ"] + sorted(df_kar_view['Şirket'].unique())
            filtre_sirket = st.selectbox("Şirket Filtrele:", sirketler_kar)
            
            if filtre_sirket != "TÜMÜ":
                df_kar_view = df_kar_view[df_kar_view['Şirket'] == filtre_sirket]
            
            # Tablo Gösterimi
            cols_kar = ['Şirket', 'Ürün', 'Önceki Ton', 'Önceki Pay', 'Cari Ton', 'Cari Pay', 'Değişim %']
            
            format_dict_kar = {
                'Önceki Ton': "{:,.2f}", 'Cari Ton': "{:,.2f}",
                'Önceki Pay': "{:.2f}%", 'Cari Pay': "{:.2f}%",
                'Değişim %': "{:.2f}%"
            }
            
            # Renkli Değişim Sütunu
            def color_change(val):
                color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                return f'color: {color}'

            st.dataframe(df_kar_view[cols_kar].style.format(format_dict_kar).applymap(color_change, subset=['Değişim %']), use_container_width=True, height=600)
        else:
            st.warning("Karşılaştırma tablosu (Tablo 3.7) verisi okunamadı.")

    # ------------------------------------------
    # TAB 4: GRAFİKLER (Mevcut yapı)
    # ------------------------------------------
    with tab_grafik:
        col_ton = secilen_segment + " Ton"
        col_pay = secilen_segment + " Pay"
        
        # Veri Hazırlığı
        if secilen_sehir == "TÜRKİYE GENELİ":
            df_chart_base = df_genel_kumulatif if donem_tipi == "Kümülatif" else df_genel_aylik
        else:
            df_chart_base = df_sirket[df_sirket['Şehir'] == secilen_sehir]
            # Kümülatif grafik için basit toplama (Eğer seçilirse)
            if donem_tipi == "Kümülatif" and not df_chart_base.empty:
                df_chart_base = df_chart_base.sort_values('Tarih')
                df_chart_base['Yıl'] = df_chart_base['Tarih'].dt.year
                df_chart_base[col_ton] = df_chart_base.groupby(['Yıl', 'Şirket'])[col_ton].cumsum()

        if not df_chart_base.empty:
            mevcut_sirketler = sorted(df_chart_base['Şirket'].unique())
            st.markdown(f"### {secilen_sehir} - {secilen_segment} Trendi ({donem_tipi})")
            
            secilen_sirketler_gr = st.multiselect("Grafikte Gösterilecek Şirketler:", mevcut_sirketler, default=[LIKITGAZ_NAME] if LIKITGAZ_NAME in mevcut_sirketler else mevcut_sirketler[:3])
            
            if secilen_sirketler_gr:
                df_plot = df_chart_base[df_chart_base['Şirket'].isin(secilen_sirketler_gr)]
                
                # Renk haritası
                color_map = {s: OTHER_COLORS[i%len(OTHER_COLORS)] for i,s in enumerate(secilen_sirketler_gr)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                
                # Grafik Tipi
                y_ekseni = st.radio("Eksen:", ["Satış (Ton)", "Pazar Payı (%)"], horizontal=True)
                y_col = col_ton if "Ton" in y_ekseni else col_pay
                
                fig = px.line(df_plot, x='Tarih', y=y_col, color='Şirket', markers=True, color_discrete_map=color_map)
                fig = grafik_bayram_ekle(fig, df_plot['Tarih'])
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Grafik için veri yok.")
