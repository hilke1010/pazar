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

TR_AYLAR = {1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
            7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'}

TR_AYLAR_KISA = {1: 'Oca', 2: 'Şub', 3: 'Mar', 4: 'Nis', 5: 'May', 6: 'Haz',
                 7: 'Tem', 8: 'Ağu', 9: 'Eyl', 10: 'Eki', 11: 'Kas', 12: 'Ara'}

DOSYA_AY_MAP = {'ocak': 1, 'subat': 2, 'mart': 3, 'nisan': 4, 'mayis': 5, 'haziran': 6,
                'temmuz': 7, 'agustos': 8, 'eylul': 9, 'ekim': 10, 'kasim': 11, 'aralik': 12}

STOP_WORDS = ["A.Ş", "A.S", "A.Ş.", "LTD", "ŞTİ", "STI", "SAN", "VE", "TİC", "TIC", 
              "PETROL", "ÜRÜNLERİ", "URUNLERI", "DAĞITIM", "DAGITIM", "GAZ", "LPG", 
              "AKARYAKIT", "ENERJİ", "ENERJI", "NAKLİYE", "NAKLIYE", "İNŞAAT", "INSAAT",
              "PAZARLAMA", "DEPOLAMA", "TURİZM", "TURIZM", "SANAYİ", "SANAYI"]

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
}

# --- YARDIMCI FONKSİYONLAR ---
def get_total_ram_usage():
    process = psutil.Process(os.getpid())
    return process.memory_info().rss / 1024 / 1024

def format_tarih_tr(date_obj):
    if pd.isna(date_obj): return ""
    return f"{TR_AYLAR.get(date_obj.month, '')} {date_obj.year}"

def format_tarih_grafik(date_obj):
    if pd.isna(date_obj): return ""
    return f"{TR_AYLAR_KISA.get(date_obj.month, '')} {date_obj.year}"

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
        en_iyi_eslesme, en_yuksek_skor = None, 0
        for mevcut in mevcut_isimler:
            mevcut_kok = ismi_temizle_kok(mevcut)
            skor = fuzz.ratio(ham_kok, mevcut_kok)
            if skor > en_yuksek_skor: en_yuksek_skor, en_iyi_eslesme = skor, mevcut
        if en_yuksek_skor >= 95: return en_iyi_eslesme
    return ham_isim

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

# --- VERİ OKUMA SİSTEMİ ---
@st.cache_data
def verileri_oku():
    tum_veri_sirket = []
    tum_veri_kumulatif = [] # Tablo 3.6 için
    sirket_listesi = set()
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx')])
    
    for dosya in files:
        tarih = dosya_isminden_tarih(dosya)
        if not tarih: continue
        path = os.path.join(DOSYA_KLASORU, dosya)
        try: doc = Document(path)
        except: continue
        
        iter_elem = iter_block_items(doc)
        son_baslik = ""
        son_sehir = None
        
        for block in iter_elem:
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if len(text) > 5:
                    son_baslik = text
                    if "Tablo" in text and ":" in text:
                        son_sehir = text.split(":")[1].strip()
            
            elif isinstance(block, Table):
                # --- TABLO 3.6: KÜMÜLATİF TÜRKİYE (OCAK - GÜNCEL AY) ---
                if "3.6" in son_baslik or ("OCAK" in son_baslik.upper() and "DÖNEMLERİ ARASI" in son_baslik.upper()):
                    try:
                        for row in block.rows[1:]: # Başlığı atla
                            cells = row.cells
                            if len(cells) < 7: continue
                            isim = cells[0].text.strip()
                            if not isim or any(x in isim.upper() for x in ["TOPLAM", "LİSANS"]): continue
                            std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                            sirket_listesi.add(std_isim)
                            tum_veri_kumulatif.append({
                                'Tarih': tarih, 'Şehir': 'TÜRKİYE GENELİ', 'Şirket': std_isim,
                                'Tüplü Ton': sayi_temizle(cells[1].text), 'Tüplü Pay': sayi_temizle(cells[2].text),
                                'Dökme Ton': sayi_temizle(cells[3].text), 'Dökme Pay': sayi_temizle(cells[4].text),
                                'Otogaz Ton': sayi_temizle(cells[5].text), 'Otogaz Pay': sayi_temizle(cells[6].text)
                            })
                    except: pass

                # --- ŞEHİR BAZLI TABLOLAR ---
                elif son_sehir and any(x in son_baslik for x in ["3.8", "3.9", "3.10", "3.11"]): # Şehir tabloları genelde buralardadır
                    try:
                        header = "".join([c.text.lower() for c in block.rows[0].cells])
                        if "tüplü" in header or "otogaz" in header:
                            for row in block.rows[1:]:
                                cells = row.cells
                                if len(cells) < 7: continue
                                isim = cells[0].text.strip()
                                if not isim or any(x in isim.upper() for x in ["TOPLAM", "LİSANS"]): continue
                                std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                                sirket_listesi.add(std_isim)
                                tum_veri_sirket.append({
                                    'Tarih': tarih, 'Şehir': son_sehir.replace('İ','i').replace('I','ı').title(), 'Şirket': std_isim,
                                    'Tüplü Ton': sayi_temizle(cells[1].text), 'Tüplü Pay': sayi_temizle(cells[2].text),
                                    'Dökme Ton': sayi_temizle(cells[3].text), 'Dökme Pay': sayi_temizle(cells[4].text),
                                    'Otogaz Ton': sayi_temizle(cells[5].text), 'Otogaz Pay': sayi_temizle(cells[6].text)
                                })
                    except: pass
    
    df_aylik = pd.DataFrame(tum_veri_sirket)
    df_kum = pd.DataFrame(tum_veri_kumulatif)
    
    for df in [df_aylik, df_kum]:
        if not df.empty:
            df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
            df['Tarih_Grafik'] = df['Tarih'].apply(format_tarih_grafik)
            
    return df_aylik, df_kum

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Kümülatif Analiz", layout="wide")

with st.spinner('Veriler Hazırlanıyor...'):
    df_aylik, df_kum = verileri_oku()

st.sidebar.title("⚙️ Analiz Ayarları")
veri_kapsami = st.sidebar.radio("📊 Veri Kapsamı:", ["Aylık (Tablo 3.5 / 3.7+)", "Kümülatif (Yıl Başından Beri - Tablo 3.6)"])

# Veri setini seç
if "Kümülatif" in veri_kapsami:
    df_aktif = df_kum
    baslik_ek = "(Yıl Başından Beri Toplam)"
else:
    df_aktif = df_aylik
    baslik_ek = "(Aylık)"

if df_aktif.empty:
    st.error("Seçilen kapsamda veri bulunamadı.")
    st.stop()

# Şehirleri listele (Kümülatifse sadece Türkiye Geneli gelir, Aylıksa iller gelir)
sehir_listesi = sorted(df_aktif['Şehir'].unique())
if "Kümülatif" in veri_kapsami and "TÜRKİYE GENELİ" not in sehir_listesi:
    sehir_listesi = ["TÜRKİYE GENELİ"] + sehir_listesi

secilen_sehir = st.sidebar.selectbox("📍 Bölge/Şehir:", sehir_listesi)
secilen_segment = st.sidebar.selectbox("⛽ Segment:", ["Otogaz", "Tüplü", "Dökme"])

st.title(f"📊 EPDK Stratejik Analiz {baslik_ek}")

tab1, tab2 = st.tabs(["📈 Pazar Trendi", "🏆 Sıralama Tablosu"])

with tab1:
    col_pay = secilen_segment + " Pay"
    col_ton = secilen_segment + " Ton"
    
    df_plot = df_aktif[df_aktif['Şehir'] == secilen_sehir]
    
    sirketler = sorted(df_plot['Şirket'].unique())
    secilen_sirketler = st.multiselect("Şirket Seçimi:", sirketler, default=[s for s in [LIKITGAZ_NAME, "AYGAZ A.Ş.", "İPRAGAZ A.Ş."] if s in sirketler])
    
    veri_tipi = st.radio("Gösterim:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
    y_ekseni = col_pay if "Pay" in veri_tipi else col_ton

    if secilen_sirketler:
        df_chart = df_plot[df_plot['Şirket'].isin(secilen_sirketler)]
        fig = px.line(df_chart, x='Tarih', y=y_ekseni, color='Şirket', markers=True, 
                      title=f"{secilen_sehir} - {secilen_segment} {veri_tipi} Değişimi")
        
        # Likitgaz'ı belirgin yap
        if LIKITGAZ_NAME in secilen_sirketler:
            fig.update_traces(patch={"line": {"width": 5, "dash": 'solid'}}, selector={"legendgroup": LIKITGAZ_NAME})
            
        fig.update_layout(hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.subheader(f"📋 {secilen_sehir} - Dönemsel Detaylar")
    musait_donemler = sorted(df_plot['Tarih'].unique(), reverse=True)
    donem_obj = st.selectbox("Dönem Seç:", musait_donemler, format_func=lambda x: format_tarih_tr(x))
    
    df_tablo = df_plot[df_plot['Tarih'] == donem_obj].sort_values(col_pay, ascending=False).reset_index(drop=True)
    df_tablo.index += 1
    
    st.dataframe(df_tablo[['Şirket', col_ton, col_pay]].style.format({col_ton: "{:,.2f} Ton", col_pay: "%{:.2f}"}), use_container_width=True)

# RAM Temizliği
gc.collect()
