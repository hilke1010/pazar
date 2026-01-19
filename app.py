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

# --- ANALİZ MOTORLARI (Basitleştirilmiş, sadece metin döndürüyor) ---
def get_pazar_analizi_metni(secilen_sehir, secilen_segment, donem_tipi):
    return f"ℹ️ Bu bölümde, **{secilen_sehir}** için **{secilen_segment}** segmentindeki şirketlerin **{donem_tipi.lower()}** satış trendlerini ve pazar paylarını inceleyebilirsiniz."

def get_toptan_satis_metni(donem_tipi):
    return f"ℹ️ Bu bölümde, dağıtıcılar arası **{donem_tipi.lower()}** toptan LPG satış verilerini (Tablo 3.1/3.2) görebilirsiniz."

def get_yillik_karsilastirma_metni():
    return "ℹ️ Bu bölümde, seçilen dönem için geçen yılın aynı dönemiyle (Tablo 3.7) şirketlerin LPG satışlarındaki yıllık değişimleri inceleyebilirsiniz."

def get_makro_analiz_metni(secilen_sehir, secilen_segment):
    return f"ℹ️ Bu bölümde, **{secilen_sehir}** için **{secilen_segment}** pazar hacmi ile Dolar kuru arasındaki ilişkiyi inceleyebilirsiniz."

def get_rekabet_analizi_metni(secilen_sehir, secilen_segment):
    return f"ℹ️ Bu bölümde, **{secilen_sehir}** için **{secilen_segment}** pazarındaki rekabet yoğunluğunu (HHI) ve pazar payı değişimlerini inceleyebilirsiniz."


# --- VERİ OKUMA ---
@st.cache_data
def verileri_oku():
    tum_veri_sirket, tum_veri_iller = [], []
    tum_toptan_aylik, tum_toptan_kumulatif = [], []
    tum_genel_aylik, tum_genel_kumulatif = [], []
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
                # TOPTAN (3.1 & 3.2)
                if "DAĞITICILAR ARASI" in son_baslik.upper():
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
                                'Tarih': tarih, 'Şirket': std_isim,
                                'Tüplü Ton': sayi_temizle(row.cells[1].text), 'Tüplü Pay': sayi_temizle(row.cells[2].text),
                                'Dökme Ton': sayi_temizle(row.cells[3].text), 'Dökme Pay': sayi_temizle(row.cells[4].text),
                                'Otogaz Ton': sayi_temizle(row.cells[5].text), 'Otogaz Pay': sayi_temizle(row.cells[6].text),
                                'Toplam Ton': sayi_temizle(row.cells[7].text), 'Toplam Pay': sayi_temizle(row.cells[8].text)
                            })
                    except: pass
                # GENEL SATIŞ (3.5 & 3.6)
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
                                'Tarih': tarih, 'Şirket': std_isim,
                                'Tüplü Ton': sayi_temizle(row.cells[1].text), 'Tüplü Pay': sayi_temizle(row.cells[2].text),
                                'Dökme Ton': sayi_temizle(row.cells[3].text), 'Dökme Pay': sayi_temizle(row.cells[4].text),
                                'Otogaz Ton': sayi_temizle(row.cells[5].text), 'Otogaz Pay': sayi_temizle(row.cells[6].text),
                                'Toplam Ton': sayi_temizle(row.cells[7].text), 'Toplam Pay': sayi_temizle(row.cells[8].text)
                            })
                    except: pass
                # KARŞILAŞTIRMA (3.7)
                elif "3.7" in son_baslik or ("LİSANS" in son_baslik.upper() and "KARŞILAŞTIRMA" in son_baslik.upper()):
                    try:
                        mevcut_sirket_37 = None
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 6: continue
                            raw_sirket = cells[0].text.strip()
                            if raw_sirket and "LİSANS" not in raw_sirket.upper():
                                mevcut_sirket_37 = sirket_ismi_standartlastir(raw_sirket, sirket_listesi)
                                sirket_listesi.add(mevcut_sirket_37)
                            if not mevcut_sirket_37: continue
                            urun = cells[1].text.strip().title()
                            if urun in ["Dökme", "Otogaz", "Tüplü", "Firma Toplamı"]:
                                try:
                                    tum_karsilastirma.append({
                                        'Tarih': tarih, 'Şirket': mevcut_sirket_37, 'Ürün': urun,
                                        'Önceki Ton': sayi_temizle(cells[2].text), 'Önceki Pay': sayi_temizle(cells[3].text),
                                        'Cari Ton': sayi_temizle(cells[4].text), 'Cari Pay': sayi_temizle(cells[5].text),
                                        'Değişim %': sayi_temizle(cells[6].text)
                                    })
                                except: pass
                    except: pass
                # İLLER
                elif "İLLERE" in son_baslik.upper() and "DAĞILIMI" in son_baslik.upper():
                    for row in block.rows:
                        if len(row.cells) < 6: continue
                        il = row.cells[0].text.strip()
                        if "İL" not in il.upper() and il != "" and "TOPLAM" not in il.upper():
                            t, d, o = sayi_temizle(row.cells[1].text), sayi_temizle(row.cells[3].text), sayi_temizle(row.cells[5].text)
                            if t+d+o > 0: tum_veri_iller.append({'Tarih': tarih, 'Şehir': sehir_ismi_duzelt(il), 'Tüplü Ton': t, 'Dökme Ton': d, 'Otogaz Ton': o})
                # ŞEHİR DETAY
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
    
    def create_df(data, group_cols):
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        return df.groupby(group_cols, as_index=False).sum(numeric_only=True)

    df_sirket = create_df(tum_veri_sirket, ['Tarih', 'Şehir', 'Şirket'])
    df_iller = pd.DataFrame(tum_veri_iller) 
    df_toptan_aylik = create_df(tum_toptan_aylik, ['Tarih', 'Şirket'])
    df_toptan_kumulatif = create_df(tum_toptan_kumulatif, ['Tarih', 'Şirket'])
    df_genel_aylik = create_df(tum_genel_aylik, ['Tarih', 'Şirket'])
    df_genel_kumulatif = create_df(tum_genel_kumulatif, ['Tarih', 'Şirket'])
    df_karsilastirma = pd.DataFrame(tum_karsilastirma)

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

if not st.session_state['analiz_basladi']:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        st.title("📊 EPDK Stratejik Pazar Analizi")
        st.info("Sistem belleğini (RAM) verimli kullanmak için veriler sadece analiz sırasında yüklenir.")
        if st.button("🚀 ANALİZİ BAŞLAT", type="primary", use_container_width=True):
            st.session_state['analiz_basladi'] = True
            st.rerun()
    st.stop()

with st.spinner('Veriler yükleniyor...'):
    df_sirket, df_iller, df_toptan_aylik, df_toptan_kumulatif, df_genel_aylik, df_genel_kumulatif, df_karsilastirma = verileri_oku()

st.title("📊 EPDK Stratejik Pazar Analizi")

if df_sirket.empty and df_genel_aylik.empty:
    st.warning("Veri bulunamadı.")
else:
    # --- SIDEBAR ---
    st.sidebar.header("⚙️ Parametreler")
    
    sehir_listesi = ["TÜRKİYE GENELİ"] + sorted(df_sirket['Şehir'].unique()) if not df_sirket.empty else ["TÜRKİYE GENELİ"]
    secilen_sehir = st.sidebar.selectbox("Bölge / Şehir", sehir_listesi)
    
    segmentler = ['Otogaz', 'Tüplü', 'Dökme']
    secilen_segment = st.sidebar.selectbox("Segment", segmentler)
    
    donem_tipi = st.sidebar.radio("Dönem Tipi:", ["Aylık", "Kümülatif"])

    # --- TABLAR ---
    tab_grafik, tab_toptan, tab_karsilastirma, tab_makro, tab_rekabet = st.tabs([
        "📈 Grafikler ve Analiz", 
        "🔄 Toptan Satış", 
        "📊 Yıllık Karşılaştırma",
        "💵 Makro Analiz",
        "🥊 Rekabet Analizi"
    ])

    # ------------------------------------------
    # TAB 1: GRAFİKLER VE ANALİZ
    # ------------------------------------------
    with tab_grafik:
        st.info(get_pazar_analizi_metni(secilen_sehir, secilen_segment, donem_tipi))

        # Veri Kaynağını Belirle
        df_ana = pd.DataFrame()
        col_ton = secilen_segment + " Ton"
        col_pay = secilen_segment + " Pay"
        
        if secilen_sehir == "TÜRKİYE GENELİ":
            df_ana = df_genel_kumulatif if donem_tipi == "Kümülatif" else df_genel_aylik
        else:
            df_ana = df_sirket[df_sirket['Şehir'] == secilen_sehir].copy()
            if donem_tipi == "Kümülatif" and not df_ana.empty:
                df_ana = df_ana.sort_values('Tarih')
                df_ana['Yıl'] = df_ana['Tarih'].dt.year
                df_ana[col_ton] = df_ana.groupby(['Yıl', 'Şirket'])[col_ton].cumsum()
                toplamlar = df_ana.groupby('Tarih')[col_ton].transform('sum')
                df_ana[col_pay] = (df_ana[col_ton] / toplamlar) * 100

        if not df_ana.empty:
            
            # --- 1. GRAFİK ---
            mevcut_sirketler = sorted(df_ana['Şirket'].unique())
            c1, c2 = st.columns(2)
            with c1:
                session_key_grafik_sirket = f"grafik_sirket_secim_{secilen_sehir}_{secilen_segment}_{donem_tipi}"
                if session_key_grafik_sirket not in st.session_state:
                    default_sirketler = [LIKITGAZ_NAME] if LIKITGAZ_NAME in mevcut_sirketler else (mevcut_sirketler[:3] if len(mevcut_sirketler) > 3 else mevcut_sirketler)
                    st.session_state[session_key_grafik_sirket] = default_sirketler
                secilen_sirketler_gr = st.multiselect("Grafikte Gösterilecek Şirketler:", mevcut_sirketler, default=st.session_state[session_key_grafik_sirket], key=session_key_grafik_sirket)
            with c2:
                y_ekseni = st.radio("Grafik Ekseni:", ["Satış (Ton)", "Pazar Payı (%)"], horizontal=True)
            
            y_col = col_ton if "Ton" in y_ekseni else col_pay
            if secilen_sirketler_gr:
                df_plot = df_ana[df_ana['Şirket'].isin(secilen_sirketler_gr)]
                color_map = {s: OTHER_COLORS[i%len(OTHER_COLORS)] for i,s in enumerate(secilen_sirketler_gr)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                fig = px.line(df_plot, x='Tarih', y=y_col, color='Şirket', markers=True, color_discrete_map=color_map, title=f"{secilen_sehir} - {secilen_segment} Trendi ({donem_tipi})")
                fig = grafik_bayram_ekle(fig, df_plot['Tarih'])
                st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            
            # --- 2. DÖNEM SEÇİMİ VE KARŞILAŞTIRMA TABLOSU ---
            st.subheader("📋 Dönemsel Sıralama ve Yıllık Değişim")
            donemler = df_ana.sort_values('Tarih', ascending=False)['Dönem'].unique()
            secilen_donem = st.selectbox("Dönem Seçiniz:", donemler, key="donem_secici_grafik")
            
            curr_date = df_ana[df_ana['Dönem'] == secilen_donem]['Tarih'].iloc[0]
            prev_date = curr_date - relativedelta(years=1)
            prev_donem = format_tarih_tr(prev_date)
            
            df_curr = df_ana[df_ana['Tarih'] == curr_date][['Şirket', col_ton, col_pay]]
            df_prev = df_ana[df_ana['Tarih'] == prev_date][['Şirket', col_ton, col_pay]]
            
            df_final = pd.merge(df_curr, df_prev, on='Şirket', how='left', suffixes=('', '_prev'))
            
            col_ton_curr_name = f"Ton ({secilen_donem})"
            col_pay_curr_name = f"Pay ({secilen_donem})"
            col_ton_prev_name = f"Ton ({prev_donem})"
            col_pay_prev_name = f"Pay ({prev_donem})"
            
            df_final.rename(columns={
                col_ton: col_ton_curr_name, 
                col_pay: col_pay_curr_name, 
                col_ton + '_prev': col_ton_prev_name, 
                col_pay + '_prev': col_pay_prev_name
            }, inplace=True)
            df_final.fillna(0, inplace=True)
            
            # YENİ SÜTUNLAR: FARK (Ton) ve FARK (Pay%)
            df_final['Fark (Ton)'] = df_final[col_ton_curr_name] - df_final[col_ton_prev_name]
            df_final['Fark (Pay%)'] = df_final[col_pay_curr_name] - df_final[col_pay_prev_name]
            
            df_final = df_final.sort_values(col_pay_curr_name, ascending=False).reset_index(drop=True)
            df_final.index += 1
            
            cols_final = ['Şirket', col_ton_curr_name, col_pay_curr_name, col_ton_prev_name, col_pay_prev_name, 'Fark (Ton)', 'Fark (Pay%)']
            
            format_dict = {
                col_ton_curr_name: "{:,.2f}", col_pay_curr_name: "{:.2f}%", 
                col_ton_prev_name: "{:,.2f}", col_pay_prev_name: "{:.2f}%", 
                'Fark (Ton)': "{:+,.2f}", 'Fark (Pay%)': "{:+.2f}%"
            }
            
            def color_val(val):
                color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                return f'color: {color}'

            st.dataframe(df_final[cols_final].style.format(format_dict).applymap(color_val, subset=['Fark (Ton)', 'Fark (Pay%)']), use_container_width=True)
        else:
            st.warning("Bu kriterlere uygun pazar verisi bulunamadı.")

    # ------------------------------------------
    # TAB 2: TOPTAN SATIŞ
    # ------------------------------------------
    with tab_toptan:
        st.info(get_toptan_satis_metni(donem_tipi))
        
        df_top = df_toptan_kumulatif if donem_tipi == "Kümülatif" else df_toptan_aylik
        
        if not df_top.empty:
            donemler_toptan = df_top.sort_values('Tarih', ascending=False)['Dönem'].unique()
            secilen_donem_top = st.selectbox("Toptan Dönemi Seç:", donemler_toptan, key="donem_secici_toptan")
            
            df_son_top = df_top[df_top['Dönem'] == secilen_donem_top].copy()
            df_son_top = df_son_top.sort_values('Toplam Ton', ascending=False).reset_index(drop=True)
            df_son_top.index += 1
            
            st.markdown("### 🏆 İlk 10 Şirket - Toptan Satış Performansı")
            cols_top = ['Şirket', 'Tüplü Ton', 'Tüplü Pay', 'Dökme Ton', 'Dökme Pay', 'Otogaz Ton', 'Otogaz Pay', 'Toplam Ton', 'Toplam Pay']
            format_dict_top = {c: "{:,.2f}" for c in cols_top if "Ton" in c}
            format_dict_top.update({c: "{:.2f}%" for c in cols_top if "Pay" in c})
            
            st.dataframe(df_son_top.head(10)[cols_top].style.format(format_dict_top), use_container_width=True)
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                fig_top = px.bar(df_son_top.head(10), x='Şirket', y='Toplam Ton', title="Top 10 Toptan Hacim (Ton)", color='Toplam Ton')
                st.plotly_chart(fig_top, use_container_width=True)
            with col_g2:
                df_melt = df_son_top.head(5).melt(id_vars='Şirket', value_vars=['Tüplü Ton', 'Dökme Ton', 'Otogaz Ton'], var_name='Ürün', value_name='Ton')
                fig_break = px.bar(df_melt, x='Şirket', y='Ton', color='Ürün', title="Top 5 - Ürün Kırılımı", color_discrete_map={'Tüplü Ton': '#FF9900', 'Dökme Ton': '#3366CC', 'Otogaz Ton': '#109618'})
                st.plotly_chart(fig_break, use_container_width=True)
        else:
            st.warning("Toptan satış verisi bulunamadı.")

    # ------------------------------------------
    # TAB 3: YILLIK KARŞILAŞTIRMA (Tablo 3.7)
    # ------------------------------------------
    with tab_karsilastirma:
        st.info(get_yillik_karsilastirma_metni())
        
        if not df_karsilastirma.empty:
            tarihler = df_karsilastirma['Dönem'].unique()
            secilen_donem_kar = st.selectbox("Karşılaştırma Dönemi:", tarihler, key="donem_secici_karsilastirma")
            df_kar_view = df_karsilastirma[df_karsilastirma['Dönem'] == secilen_donem_kar].copy()
            
            sirketler_kar = ["TÜMÜ"] + sorted(df_kar_view['Şirket'].unique())
            filtre_sirket_kar = st.selectbox("Şirket Filtrele:", sirketler_kar, key="filtre_sirket_karsilastirma")
            
            if filtre_sirket_kar != "TÜMÜ":
                df_kar_view = df_kar_view[df_kar_view['Şirket'] == filtre_sirket_kar]
            
            cols_kar = ['Şirket', 'Ürün', 'Önceki Ton', 'Önceki Pay', 'Cari Ton', 'Cari Pay', 'Değişim %']
            format_dict_kar = {
                'Önceki Ton': "{:,.2f}", 'Cari Ton': "{:,.2f}",
                'Önceki Pay': "{:.2f}%", 'Cari Pay': "{:.2f}%",
                'Değişim %': "{:+.2f}%" # Yüzde değişimde +/- göster
            }
            
            def color_change(val):
                color = 'green' if val > 0 else 'red' if val < 0 else 'black'
                return f'color: {color}'

            st.dataframe(df_kar_view[cols_kar].style.format(format_dict_kar).applymap(color_change, subset=['Değişim %']), use_container_width=True, height=600)
        else:
            st.warning("Karşılaştırma verisi okunamadı.")

    # ------------------------------------------
    # TAB 4: MAKRO ANALİZ
    # ------------------------------------------
    with tab_makro:
        st.info(get_makro_analiz_metni(secilen_sehir, secilen_segment))
        
        # Makro analiz için daima aylık verinin toplam tonajı ve dolar kuru kullanılır.
        df_makro_base = df_genel_aylik if secilen_sehir == "TÜRKİYE GENELİ" else df_sirket[df_sirket['Şehir'] == secilen_sehir]
        
        if not df_makro_base.empty:
            col_ton_makro = secilen_segment + " Ton"
            df_toplam = df_makro_base.groupby('Tarih')[col_ton_makro].sum().reset_index()
            
            if not df_toplam.empty:
                df_dolar = dolar_verisi_getir(df_toplam['Tarih'].min())
                if not df_dolar.empty:
                    df_makro = pd.merge(df_toplam, df_dolar, on='Tarih', how='inner')
                    
                    fig = go.Figure()
                    fig.add_trace(go.Bar(x=df_makro['Tarih'], y=df_makro[col_ton_makro], name='Pazar (Ton)', marker_color='#3366CC', opacity=0.6))
                    fig.add_trace(go.Scatter(x=df_makro['Tarih'], y=df_makro['Dolar Kuru'], name='Dolar (TL)', yaxis='y2', line=dict(color='#DC3912', width=3)))
                    
                    fig.update_layout(
                        title=f"{secilen_sehir} {secilen_segment} Pazar Hacmi vs Dolar Kuru",
                        yaxis=dict(title=f"Satış ({secilen_segment} Ton)"),
                        yaxis2=dict(title='USD/TL', overlaying='y', side='right'),
                        hovermode='x unified', 
                        legend=dict(orientation="h", y=1.1)
                    )
                    fig = grafik_bayram_ekle(fig, df_makro['Tarih'])
                    st.plotly_chart(fig, use_container_width=True)
                else: st.warning("Dolar kuru verisi alınamadı.")
            else: st.warning("Makro analiz için yeterli satış verisi bulunamadı.")
        else:
            st.warning("Makro analiz için veri yok.")

    # ------------------------------------------
    # TAB 5: REKABET ANALİZİ
    # ------------------------------------------
    with tab_rekabet:
        st.info(get_rekabet_analizi_metni(secilen_sehir, secilen_segment))
        
        # df_ana zaten seçilen şehir, segment ve dönem tipine göre filtrelenmiş durumda
        # HHI için daima son dönemin pazar payları kullanılır.
        col_pay_rekabet = secilen_segment + " Pay"

        if not df_ana.empty:
            son_tarih = df_ana['Tarih'].max()
            df_son_rekabet = df_ana[df_ana['Tarih'] == son_tarih].copy()
            
            if col_pay_rekabet in df_son_rekabet.columns and not df_son_rekabet.empty:
                # HHI Endeksi Hesaplama
                hhi_score = (df_son_rekabet[col_pay_rekabet] ** 2).sum()
                
                st.markdown("### 🧮 Pazar Rekabet Yoğunluğu (HHI) Endeksi")
                c_hhi1, c_hhi2 = st.columns([1, 2])
                with c_hhi1:
                    fig_hhi = go.Figure(go.Indicator(mode = "gauge+number", value = hhi_score, domain = {'x': [0, 1], 'y': [0, 1]}, title = {'text': "HHI Skoru"}, gauge = {'axis': {'range': [0, 10000]}, 'bar': {'color': "black"}, 'steps': [{'range': [0, 1500], 'color': '#2ECC71'}, {'range': [1500, 2500], 'color': '#F1C40F'}, {'range': [2500, 10000], 'color': '#E74C3C'}]}))
                    st.plotly_chart(fig_hhi, use_container_width=True)
                with c_hhi2:
                    st.markdown("""
                    #### 🧠 HHI (Herfindahl-Hirschman) Endeksi Nedir?
                    Bu metrik, bir pazarın ne kadar **rekabetçi** veya ne kadar **tekelleşmiş** olduğunu ölçen uluslararası bir standarttır.
                    
                    *   🟢 **< 1.500 (Düşük Yoğunluk):** **Rekabetçi Pazar.** Pazarda çok sayıda oyuncu var, hiçbir firma tek başına hakim değil. Pazara giriş kolaydır.
                    *   🟡 **1.500 - 2.500 (Orta Yoğunluk):** **Oligopol Eğilimi.** Pazar, birkaç büyük şirketin kontrolüne girmeye başlamış. Rekabet zorlaşıyor.
                    *   🔴 **> 2.500 (Yüksek Yoğunluk):** **Tekelleşmiş Pazar.** Pazarın hakimi 1 veya 2 şirkettir. Yeni oyuncuların barınması veya pazar payı çalması çok zordur.
                    
                    > **Stratejik Yorum:** HHI puanı arttıkça, o şehirdeki rekabet azalır ve büyük oyuncuların pazar gücü artar.
                    """)
                
                st.markdown("---")
                st.markdown(f"### 🚀 Pazar Payını Artıranlar ({format_tarih_tr(son_tarih)})")

                # Pazar Payı Değişimini Hesapla (Geçen Yıla Göre)
                prev_year_date_rekabet = son_tarih - relativedelta(years=1)
                
                df_curr_rekabet = df_son_rekabet[['Şirket', col_pay_rekabet]]
                df_prev_rekabet = df_ana[df_ana['Tarih'] == prev_year_date_rekabet][['Şirket', col_pay_rekabet]]
                
                df_pay_degisim = pd.merge(df_curr_rekabet, df_prev_rekabet, on='Şirket', how='left', suffixes=('_curr', '_prev'))
                df_pay_degisim.fillna(0, inplace=True)
                
                df_pay_degisim['Pay Farkı'] = df_pay_degisim[f'{col_pay_rekabet}_curr'] - df_pay_degisim[f'{col_pay_rekabet}_prev']
                
                df_artanlar = df_pay_degisim[df_pay_degisim['Pay Farkı'] > 0].sort_values('Pay Farkı', ascending=False).head(10)
                
                if not df_artanlar.empty:
                    st.dataframe(
                        df_artanlar[['Şirket', f'{col_pay_rekabet}_curr', f'{col_pay_rekabet}_prev', 'Pay Farkı']]
                        .rename(columns={
                            f'{col_pay_rekabet}_curr': f'Güncel Pay ({format_tarih_tr(son_tarih)})',
                            f'{col_pay_rekabet}_prev': f'Önceki Yıl Pay ({format_tarih_tr(prev_year_date_rekabet)})'
                        })
                        .style.format({
                            f'Güncel Pay ({format_tarih_tr(son_tarih)})': '{:.2f}%',
                            f'Önceki Yıl Pay ({format_tarih_tr(prev_year_date_rekabet)})': '{:.2f}%',
                            'Pay Farkı': '{:+.2f}%'
                        })
                        .applymap(color_val, subset=['Pay Farkı']),
                        use_container_width=True
                    )
                else:
                    st.info("Bu dönemde pazar payını artıran şirket bulunamadı.")

            else:
                st.warning("Rekabet analizi için yeterli pazar payı verisi bulunamadı.")
        else:
            st.warning("Rekabet analizi için veri yok.")
