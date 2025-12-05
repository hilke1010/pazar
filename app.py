import streamlit as st
import pandas as pd
import os
import gc  # Hafıza temizliği için
import psutil # RAM takibi için
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from thefuzz import process
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
# ----------------------

# --- AYARLAR ---
DOSYA_KLASORU = 'raporlar'
LIKITGAZ_NAME = "LİKİTGAZ DAĞITIM VE ENDÜSTRİ A.Ş."
LIKITGAZ_COLOR = "#DC3912" 
OTHER_COLORS = px.colors.qualitative.Set2

TR_AYLAR = {
    1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
    7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
}

TR_AYLAR_KISA = {
    1: 'Oca', 2: 'Şub', 3: 'Mar', 4: 'Nis', 5: 'May', 6: 'Haz',
    7: 'Tem', 8: 'Ağu', 9: 'Eyl', 10: 'Eki', 11: 'Kas', 12: 'Ara'
}

DOSYA_AY_MAP = {
    'ocak': 1, 'subat': 2, 'mart': 3, 'nisan': 4, 'mayis': 5, 'haziran': 6,
    'temmuz': 7, 'agustos': 8, 'eylul': 9, 'ekim': 10, 'kasim': 11, 'aralik': 12
}

BAYRAMLAR = [
    {"Tarih": "2022-05-01", "Isim": "Ramazan B."}, {"Tarih": "2022-07-01", "Isim": "Kurban B."},
    {"Tarih": "2023-04-01", "Isim": "Ramazan B."}, {"Tarih": "2023-06-01", "Isim": "Kurban B."},
    {"Tarih": "2024-04-01", "Isim": "Ramazan B."}, {"Tarih": "2024-06-01", "Isim": "Kurban B."},
    {"Tarih": "2025-03-01", "Isim": "Ramazan B."}, {"Tarih": "2025-06-01", "Isim": "Kurban B."}
]

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
    "TERMOPET": "TERMOPET AKARYAKIT A.Ş."
}

# --- YARDIMCI FONKSİYONLAR ---
def get_total_ram_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss / 1024 / 1024

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

def sirket_ismi_standartlastir(ham_isim, mevcut_isimler):
    ham_isim = ham_isim.strip()
    ham_upper = ham_isim.upper().replace('İ', 'I')
    for k, v in OZEL_DUZELTMELER.items():
        if k.upper().replace('İ', 'I') in ham_upper: return v
    temiz = re.sub(r'\b(A\.?S\.?|LTD|STI|SAN|TIC)\b', '', ham_upper.replace('.','')).strip()
    if mevcut_isimler:
        match, score = process.extractOne(ham_isim, mevcut_isimler)
        if score >= 88: return match
    return ham_isim

def sehir_ismi_duzelt(sehir):
    if not sehir: return ""
    return sehir.replace('İ', 'i').replace('I', 'ı').title()

@st.cache_data(ttl="2h") # Veriler 2 saat sonra otomatik silinir
def dolar_verisi_getir(baslangic_tarihi):
    if not DOLAR_MODULU_VAR: return pd.DataFrame()
    try:
        dolar = yf.download("TRY=X", start=baslangic_tarihi, progress=False)
        if dolar.empty: return pd.DataFrame()
        dolar_aylik = dolar['Close'].resample('MS').mean().reset_index()
        dolar_aylik.columns = ['Tarih', 'Dolar Kuru']
        dolar_aylik['Tarih'] = pd.to_datetime(dolar_aylik['Tarih'])
        return dolar_aylik
    except Exception: return pd.DataFrame()

def grafik_bayram_ekle(fig, df_dates):
    if df_dates.empty: return fig
    min_date = df_dates.min()
    max_date = df_dates.max()
    for bayram in BAYRAMLAR:
        b_date = pd.to_datetime(bayram["Tarih"])
        if min_date <= b_date <= max_date:
            fig.add_vline(x=b_date, line_width=1, line_dash="dot", line_color="#333", opacity=0.4)
            fig.add_annotation(x=b_date, y=1, yref="paper", text=bayram["Isim"], showarrow=False, 
                               font=dict(size=14, color="black", family="Arial Black"),
                               textangle=-90, yanchor="top")
    return fig

# --- VERİ OKUMA (ARTIK BUTTONA BASINCA ÇALIŞACAK) ---
@st.cache_data(show_spinner=False)
def verileri_oku():
    tum_veri_sirket = []
    tum_veri_iller = []
    tum_veri_turkiye = [] 
    tum_veri_turkiye_sirket = []
    sirket_listesi = set()
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx') or f.endswith('.doc')])
    
    for dosya in files:
        tarih = dosya_isminden_tarih(dosya)
        if not tarih: continue
        path = os.path.join(DOSYA_KLASORU, dosya)
        try: doc = Document(path)
        except: continue
        iter_elem = iter_block_items(doc)
        son_baslik = ""
        son_sehir_sirket = None
        
        for block in iter_elem:
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if len(text) > 5:
                    son_baslik = text
                    if text.startswith("Tablo") and ":" in text:
                         parts = text.split(":")
                         if len(parts)>1 and 2<len(parts[1].strip())<40:
                             son_sehir_sirket = parts[1].strip()
                    else: son_sehir_sirket = None

            elif isinstance(block, Table):
                if "İLLERE" in son_baslik.upper() and "DAĞILIMI" in son_baslik.upper():
                    try:
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 6: continue
                            il_adi = cells[0].text.strip()
                            if "TOPLAM" in il_adi.upper():
                                try:
                                    tum_veri_turkiye.append({
                                        'Tarih': tarih,
                                        'Tüplü Ton': sayi_temizle(cells[1].text),
                                        'Dökme Ton': sayi_temizle(cells[3].text),
                                        'Otogaz Ton': sayi_temizle(cells[5].text)
                                    })
                                except: pass
                                continue 
                            if il_adi == "" or "İL" in il_adi.upper(): continue
                            try:
                                il_duzgun = sehir_ismi_duzelt(il_adi)
                                t_ton, d_ton, o_ton = sayi_temizle(cells[1].text), sayi_temizle(cells[3].text), sayi_temizle(cells[5].text)
                                if t_ton + d_ton + o_ton > 0:
                                    tum_veri_iller.append({'Tarih': tarih, 'Şehir': il_duzgun, 'Tüplü Ton': t_ton, 'Dökme Ton': d_ton, 'Otogaz Ton': o_ton})
                            except: continue
                    except: pass
                elif ("3.7" in son_baslik or ("LİSANS" in son_baslik.upper() and "KARŞILAŞTIRMA" in son_baslik.upper())):
                    try:
                        mevcut_sirket = None
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 5: continue
                            ham_sirket = cells[0].text.strip()
                            if ham_sirket and "LİSANS" not in ham_sirket.upper(): mevcut_sirket = ham_sirket
                            if not mevcut_sirket: continue 
                            tur = cells[1].text.strip().lower()
                            if any(x in tur for x in ["otogaz","dökme","tüplü"]):
                                std_isim = sirket_ismi_standartlastir(mevcut_sirket, sirket_listesi)
                                sirket_listesi.add(std_isim)
                                satis_ton = sayi_temizle(cells[4].text)
                                t_ton, d_ton, o_ton = 0, 0, 0
                                if "tüplü" in tur: t_ton = satis_ton
                                elif "dökme" in tur: d_ton = satis_ton
                                elif "otogaz" in tur: o_ton = satis_ton
                                if t_ton+d_ton+o_ton > 0:
                                    tum_veri_turkiye_sirket.append({'Tarih': tarih, 'Şirket': std_isim, 'Tüplü Ton': t_ton, 'Dökme Ton': d_ton, 'Otogaz Ton': o_ton})
                    except: pass
                elif son_sehir_sirket:
                    try:
                        header = "".join([c.text.lower() for row in block.rows[:2] for c in row.cells])
                        if any(x in header for x in ["tüplü", "dökme", "pay"]):
                            for row in block.rows:
                                cells = row.cells
                                if len(cells) < 7: continue
                                isim = cells[0].text.strip()
                                if any(x in isim.upper() for x in ["LİSANS", "TOPLAM", "UNVANI"]) or not isim: continue
                                std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                                sirket_listesi.add(std_isim)
                                try:
                                    vals = [sayi_temizle(cells[i].text) for i in range(1,7)]
                                    if sum(vals) > 0:
                                        tum_veri_sirket.append({
                                            'Tarih': tarih, 'Şehir': sehir_ismi_duzelt(son_sehir_sirket), 'Şirket': std_isim, 
                                            'Tüplü Ton': vals[0], 'Tüplü Pay': vals[1],
                                            'Dökme Ton': vals[2], 'Dökme Pay': vals[3],
                                            'Otogaz Ton': vals[4], 'Otogaz Pay': vals[5]
                                        })
                                except: continue
                    except: pass
    
    gc.collect()
    df_sirket = pd.DataFrame(tum_veri_sirket)
    df_iller = pd.DataFrame(tum_veri_iller)
    df_turkiye = pd.DataFrame(tum_veri_turkiye)
    if tum_veri_turkiye_sirket:
        df_ts = pd.DataFrame(tum_veri_turkiye_sirket)
        df_turkiye_sirket = df_ts.groupby(['Tarih', 'Şirket'], as_index=False)[['Tüplü Ton', 'Dökme Ton', 'Otogaz Ton']].sum()
    else: df_turkiye_sirket = pd.DataFrame(columns=['Tarih', 'Şirket', 'Tüplü Ton', 'Dökme Ton', 'Otogaz Ton'])
    
    for df in [df_sirket, df_iller, df_turkiye, df_turkiye_sirket]:
        if not df.empty:
            df.sort_values('Tarih', inplace=True)
            df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
            df['Tarih_Grafik'] = df['Tarih'].apply(format_tarih_grafik)
            
    return df_sirket, df_iller, df_turkiye, df_turkiye_sirket

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")

# Oturum Durumu Kontrolü
if 'analiz_basladi' not in st.session_state:
    st.session_state['analiz_basladi'] = False

# =========================================================
# GİRİŞ EKRANI (Veri Yüklenmeden Önce)
# =========================================================
if not st.session_state['analiz_basladi']:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("📊 EPDK Stratejik Pazar Analizi")
        st.info("RAM kullanımını optimize etmek için veriler sadece analiz sırasında yüklenir.")
        
        # RAM Durumu
        ram_now = get_total_ram_usage()
        st.metric("Şu anki RAM (Boşta)", f"{ram_now:.0f} MB")
        
        if st.button("🚀 ANALİZİ BAŞLAT", type="primary", use_container_width=True):
            st.session_state['analiz_basladi'] = True
            st.rerun()
    st.stop() # Kodun geri kalanını çalıştırma

# =========================================================
# ANALİZ EKRANI (Veri Yüklendikten Sonra)
# =========================================================

# SADECE ANALİZ BAŞLADIYSA VERİLERİ OKU
with st.spinner('Veriler yükleniyor...'):
    df_sirket, df_iller, df_turkiye, df_turkiye_sirket = verileri_oku()

# SOL MENÜ RAM ve ÇIKIŞ
st.sidebar.title("Kontrol Paneli")
ram_now = get_total_ram_usage()
# Hugging Face için 16GB, Streamlit Cloud için 1024MB.
ram_limit = 16384.0 if "hf.space" in str(os.environ.get("SPACE_HOST", "")) else 1024.0
if ram_now < 0.5 * ram_limit: color = "green"; msg = "✅ Güvenli"
elif ram_now < 0.8 * ram_limit: color = "orange"; msg = "⚠️ Sınırda"
else: color = "red"; msg = "🛑 KRİTİK"

st.sidebar.markdown(f"### RAM: :{color}[{ram_now:.0f} MB]")
st.sidebar.progress(min(ram_now/ram_limit, 1.0))
st.sidebar.caption(msg)

# ÇIKIŞ BUTONU
if st.sidebar.button("❌ Analizi Bitir ve Temizle", type="primary"):
    st.session_state['analiz_basladi'] = False
    st.cache_data.clear()
    gc.collect()
    st.rerun()

st.sidebar.markdown("---")

# --- ANA İÇERİK (Eski Kodunuzun Aynısı) ---
st.title("📊 EPDK Stratejik Pazar Analizi")

if df_sirket.empty:
    st.warning("Veri bulunamadı.")
else:
    st.sidebar.header("⚙️ Parametreler")
    sehirler = sorted(df_sirket['Şehir'].unique())
    idx_ank = sehirler.index('Ankara') if 'Ankara' in sehirler else 0
    secilen_sehir = st.sidebar.selectbox("Şehir", sehirler, index=idx_ank)
    
    segmentler = ['Otogaz', 'Tüplü', 'Dökme']
    secilen_segment = st.sidebar.selectbox("Segment", segmentler)
    
    df_sehir_sirket = df_sirket[df_sirket['Şehir'] == secilen_sehir]
    col_pay = secilen_segment + " Pay"
    
    if secilen_sehir == "Adana":
        st.error("Adana ili geçici olarak kapalıdır.")
    else:
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Trend", "💵 Makro", "🥊 Rekabet", "🌡️ Mevsimsellik", "🧠 Rapor"])
        
        with tab1:
            col_f1, col_f2 = st.columns(2)
            mevcut_sirketler_sehirde = sorted(df_sehir_sirket['Şirket'].unique())
            session_key = f"secim_{secilen_sehir}"
            if session_key not in st.session_state:
                varsayilan = [LIKITGAZ_NAME] if LIKITGAZ_NAME in mevcut_sirketler_sehirde else []
                st.session_state[session_key] = varsayilan
            
            with col_f1:
                secilen_sirketler = st.multiselect("Şirketler", mevcut_sirketler_sehirde, default=st.session_state[session_key], key="widget_" + session_key)
            st.session_state[session_key] = secilen_sirketler

            with col_f2:
                veri_tipi = st.radio("Veri Tipi:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
                y_col = col_pay if veri_tipi == "Pazar Payı (%)" else secilen_segment + " Ton"
            
            if secilen_sirketler:
                df_chart = df_sehir_sirket[df_sehir_sirket['Şirket'].isin(secilen_sirketler)]
                color_map = {s: OTHER_COLORS[i%len(OTHER_COLORS)] for i,s in enumerate(secilen_sirketler)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                
                fig = px.line(df_chart, x='Tarih', y=y_col, color='Şirket', markers=True, color_discrete_map=color_map, title=f"{secilen_sehir} - {secilen_segment}")
                fig = grafik_bayram_ekle(fig, df_chart['Tarih'])
                st.plotly_chart(fig, use_container_width=True)

        with tab2: # Makro
            col_ton = secilen_segment + " Ton"
            df_sehir_toplam = df_sehir_sirket.groupby('Tarih')[col_ton].sum().reset_index()
            df_sehir_toplam = df_sehir_toplam[df_sehir_toplam[col_ton] > 0.1]
            if not df_sehir_toplam.empty and DOLAR_MODULU_VAR:
                df_dolar = dolar_verisi_getir(df_sehir_toplam['Tarih'].min())
                if not df_dolar.empty:
                    df_makro = pd.merge(df_sehir_toplam, df_dolar, on='Tarih', how='inner')
                    fig_makro = go.Figure()
                    fig_makro.add_trace(go.Bar(x=df_makro['Tarih'], y=df_makro[col_ton], name='Pazar (Ton)', marker_color='#3366CC', opacity=0.6))
                    fig_makro.add_trace(go.Scatter(x=df_makro['Tarih'], y=df_makro['Dolar Kuru'], name='Dolar', yaxis='y2', line=dict(color='#DC3912')))
                    fig_makro.update_layout(yaxis2=dict(overlaying='y', side='right'))
                    st.plotly_chart(fig_makro, use_container_width=True)
            else: st.info("Makro veri yok.")

        with tab3: # Rekabet
             st.info("Rekabet Analizi Grafikleri Burada")

        with tab4: # Mevsimsellik
             st.info("Mevsimsellik Grafikleri Burada")

        with tab5: # Rapor
             st.info("Detaylı Rapor Burada")
