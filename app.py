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
from thefuzz import fuzz
import plotly.express as px
import plotly.graph_objects as go
import re
from dateutil.relativedelta import relativedelta

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

# Şehir listesi (Şirket kolonunda şehir isimlerini filtrelemek için)
SEHIRLER_LISTESI = [
    "ADANA", "ADIYAMAN", "AFYONKARAHİSAR", "AĞRI", "AMASYA", "ANKARA", "ANTALYA", "ARTVİN", "AYDIN", "BALIKESİR", "BİLECİK", "BİNGÖL", "BİTLİS", "BOLU", "BURDUR", "BURSA", "ÇANAKKALE", "ÇANKIRI", "ÇORUM", "DENİZLİ", "DİYARBAKIR", "EDİRNE", "ELAZIĞ", "ERZİNCAN", "ERZURUM", "ESKİŞEHİR", "GAZİANTEP", "GİRESUN", "GÜMÜŞHANE", "HAKKARİ", "HATAY", "ISPARTA", "MERSİN", "İSTANBUL", "İZMİR", "KARS", "KASTAMONU", "KAYSERİ", "KIRKLARELİ", "KIRŞEHİR", "KOCAELİ", "KONYA", "KÜTAHYA", "MALATYA", "MANİSA", "KAHRAMANMARAŞ", "MARDİN", "MUĞLA", "MUŞ", "NEVŞEHİR", "NİĞDE", "ORDU", "RIZE", "SAKARYA", "SAMSUN", "SİİRT", "SİNOP", "SİVAS", "TEKİRDAĞ", "TOKAT", "TRABZON", "TUNCELİ", "ŞANLIURFA", "UŞAK", "VAN", "YOZGAT", "ZONGULDAK", "AKSARAY", "BAYBURT", "KARAMAN", "KIRIKKALE", "BATMAN", "ŞIRNAK", "BARTIN", "ARDAHAN", "IĞDIR", "YALOVA", "KARABÜK", "KİLİS", "OSMANİYE", "DÜZCE"
]

OZEL_DUZELTMELER = {
    "AYTEMİZ": "AYTEMİZ AKARYAKIT DAĞITIM A.Ş.",
    "AYGAZ": "AYGAZ A.Ş.",
    "İPRAGAZ": "İPRAGAZ A.Ş.",
    "LİKİTGAZ": LIKITGAZ_NAME,
    "SHELL": "SHELL & TURCAS PETROL A.Ş.",
    "PETROL OFİSİ": "PETROL OFİSİ A.Ş.",
    "TERMOPET": "TERMOPET AKARYAKIT A.Ş.",
}

STOP_WORDS = ["A.Ş", "A.S", "A.Ş.", "LTD", "ŞTİ", "STI", "SAN", "VE", "TİC", "TIC", "PETROL", "ÜRÜNLERİ", "URUNLERI", "DAĞITIM", "DAGITIM", "GAZ", "LPG", "AKARYAKIT", "ENERJİ", "ENERJI", "NAKLİYE", "NAKLIYE"]

# --- YARDIMCI FONKSİYONLAR ---
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
    ham_isim = ham_isim.strip().upper().replace('İ', 'I')
    # Şehir isimlerini filtrele
    if ham_isim in SEHIRLER_LISTESI: return None
    
    for k, v in OZEL_DUZELTMELER.items():
        if k in ham_isim: return v
    
    if mevcut_isimler:
        for mevcut in mevcut_isimler:
            if fuzz.ratio(ham_isim, mevcut.upper()) > 95: return mevcut
    return ham_isim.title()

@st.cache_data
def dolar_verisi_getir(baslangic_tarihi):
    if not DOLAR_MODULU_VAR: return pd.DataFrame()
    try:
        dolar = yf.download("TRY=X", start=baslangic_tarihi, progress=False)
        if dolar.empty: return pd.DataFrame()
        dolar_aylik = dolar['Close'].resample('MS').mean().reset_index()
        dolar_aylik.columns = ['Tarih', 'Dolar Kuru']
        dolar_aylik['Tarih'] = pd.to_datetime(dolar_aylik['Tarih']).dt.tz_localize(None)
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
    tum_veri_sirket, tum_toptan_aylik, tum_genel_aylik, tum_karsilastirma = [], [], [], []
    sirket_listesi = set()
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx')])
    
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
                        if len(parts)>1: son_sehir_sirket = parts[1].strip().upper()
            
            elif isinstance(block, Table):
                # Toptan veya Genel Satış
                if "DAĞITICILAR ARASI" in son_baslik.upper() or "ÜRÜN TÜRÜNE GÖRE DAĞILIMI" in son_baslik.upper():
                    target_list = tum_toptan_aylik if "DAĞITICILAR" in son_baslik.upper() else tum_genel_aylik
                    if "OCAK" in son_baslik.upper(): continue # Kümülatifleri burada okumuyoruz, manuel hesaplayacağız
                    for row in block.rows:
                        if len(row.cells) < 9: continue
                        isim = sirket_ismi_standartlastir(row.cells[0].text.strip(), sirket_listesi)
                        if not isim: continue
                        sirket_listesi.add(isim)
                        target_list.append({
                            'Tarih': tarih, 'Şirket': isim,
                            'Tüplü Ton': sayi_temizle(row.cells[1].text), 'Tüplü Pay': sayi_temizle(row.cells[2].text),
                            'Dökme Ton': sayi_temizle(row.cells[3].text), 'Dökme Pay': sayi_temizle(row.cells[4].text),
                            'Otogaz Ton': sayi_temizle(row.cells[5].text), 'Otogaz Pay': sayi_temizle(row.cells[6].text),
                            'Toplam Ton': sayi_temizle(row.cells[7].text), 'Toplam Pay': sayi_temizle(row.cells[8].text)
                        })
                # Karşılaştırma (Tablo 3.7)
                elif "3.7" in son_baslik or "KARŞILAŞTIRMA" in son_baslik.upper():
                    mevcut_s_37 = None
                    for row in block.rows:
                        if len(row.cells) < 6: continue
                        raw_s = row.cells[0].text.strip()
                        if raw_s and "LİSANS" not in raw_s.upper(): mevcut_s_37 = sirket_ismi_standartlastir(raw_s, sirket_listesi)
                        if not mevcut_s_37: continue
                        urun = row.cells[1].text.strip().title()
                        if urun in ["Dökme", "Otogaz", "Tüplü"]:
                            tum_karsilastirma.append({'Tarih': tarih, 'Şirket': mevcut_s_37, 'Ürün': urun, 'Önceki Ton': sayi_temizle(row.cells[2].text), 'Önceki Pay': sayi_temizle(row.cells[3].text), 'Cari Ton': sayi_temizle(row.cells[4].text), 'Cari Pay': sayi_temizle(row.cells[5].text)})
                # Şehir Detay
                elif son_sehir_sirket and son_sehir_sirket in SEHIRLER_LISTESI:
                    header = "".join([c.text.lower() for row in block.rows[:2] for c in row.cells])
                    if any(x in header for x in ["tüplü", "pay"]):
                        for row in block.rows:
                            if len(row.cells) < 7: continue
                            isim = sirket_ismi_standartlastir(row.cells[0].text.strip(), sirket_listesi)
                            if not isim: continue
                            sirket_listesi.add(isim)
                            v = [sayi_temizle(c.text) for c in row.cells[1:7]]
                            if sum(v) > 0:
                                tum_veri_sirket.append({'Tarih': tarih, 'Şehir': son_sehir_sirket.title(), 'Şirket': isim, 'Tüplü Ton': v[0], 'Tüplü Pay': v[1], 'Dökme Ton': v[2], 'Dökme Pay': v[3], 'Otogaz Ton': v[4], 'Otogaz Pay': v[5]})

    def create_df(data, group_cols):
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data).groupby(group_cols, as_index=False).sum(numeric_only=True)
        df.sort_values('Tarih', inplace=True)
        df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
        return df

    return create_df(tum_veri_sirket, ['Tarih', 'Şehir', 'Şirket']), create_df(tum_toptan_aylik, ['Tarih', 'Şirket']), create_df(tum_genel_aylik, ['Tarih', 'Şirket']), create_df(tum_karsilastirma, ['Tarih', 'Şirket', 'Ürün'])

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")

if not st.session_state.get('analiz_basladi', False):
    st.title("📊 EPDK Stratejik Pazar Analizi")
    if st.button("🚀 ANALİZİ BAŞLAT", type="primary"):
        st.session_state['analiz_basladi'] = True
        st.rerun()
    st.stop()

df_sirket, df_toptan, df_genel, df_kar = verileri_oku()

# --- SIDEBAR ---
st.sidebar.header("⚙️ Parametreler")
sehir_listesi = ["TÜRKİYE GENELİ"] + sorted(df_sirket['Şehir'].unique()) if not df_sirket.empty else ["TÜRKİYE GENELİ"]
secilen_sehir = st.sidebar.selectbox("Bölge / Şehir", sehir_listesi)
secilen_segment = st.sidebar.selectbox("Segment", ['Otogaz', 'Tüplü', 'Dökme'])
donem_tipi = st.sidebar.radio("Dönem Tipi:", ["Aylık", "Ocak - Güncel Ay (Kümülatif)"])

# --- TABLAR ---
t1, t2, t3, t4, t5 = st.tabs(["📈 Trend ve Sıralama", "🚀 Pazar Payını Artıranlar", "🔄 Toptan Satış", "📊 Yıllık Karşılaştırma", "💵 Makro Analiz"])

# --- TAB 1: Trend ve Sıralama ---
with t1:
    df_ana = df_genel if secilen_sehir == "TÜRKİYE GENELİ" else df_sirket[df_sirket['Şehir'] == secilen_sehir].copy()
    col_ton, col_pay = f"{secilen_segment} Ton", f"{secilen_segment} Pay"
    
    if donem_tipi != "Aylık" and not df_ana.empty:
        df_ana = df_ana.sort_values('Tarih')
        df_ana[col_ton] = df_ana.groupby([df_ana['Tarih'].dt.year, 'Şirket'])[col_ton].cumsum()
        df_ana[col_pay] = (df_ana[col_ton] / df_ana.groupby('Tarih')[col_ton].transform('sum')) * 100

    if not df_ana.empty:
        st.subheader("📋 Dönemsel Sıralama ve Yıllık Değişim")
        donemler = df_ana.sort_values('Tarih', ascending=False)['Dönem'].unique()
        secilen_donem = st.selectbox("Dönem Seç:", donemler)
        
        curr_t = df_ana[df_ana['Dönem'] == secilen_donem]['Tarih'].iloc[0]
        prev_t = curr_t - relativedelta(years=1)
        
        df_curr = df_ana[df_ana['Tarih'] == curr_t][['Şirket', col_ton, col_pay]]
        df_prev = df_ana[df_ana['Tarih'] == prev_t][['Şirket', col_ton, col_pay]]
        
        df_f = pd.merge(df_curr, df_prev, on='Şirket', how='left', suffixes=('', '_prev')).fillna(0)
        df_f['Fark (Ton)'] = df_f[col_ton] - df_f[f'{col_ton}_prev']
        df_f['Fark (Pay%)'] = df_f[col_pay] - df_f[f'{col_pay}_prev']
        
        df_f = df_f.sort_values(col_pay, ascending=False).reset_index(drop=True)
        df_f.index += 1
        
        st.dataframe(df_f.style.format({col_ton: "{:,.2f}", col_pay: "{:.2f}%", f"{col_ton}_prev": "{:,.2f}", f"{col_pay}_prev": "{:.2f}%", 'Fark (Ton)': "{:+,.2f}", 'Fark (Pay%)': "{:+.2f}%"}), use_container_width=True)

# --- TAB 2: Pazar Payını Artıranlar ---
with t2:
    if not df_ana.empty:
        son_t = df_ana['Tarih'].max()
        gecen_y = son_t - relativedelta(years=1)
        st.subheader(f"🚀 Pazar Payını Artıranlar ({format_tarih_tr(son_t)})")
        
        df_son = df_ana[df_ana['Tarih'] == son_t][['Şirket', col_pay]]
        df_gecen = df_ana[df_ana['Tarih'] == gecen_y][['Şirket', col_pay]]
        df_diff = pd.merge(df_son, df_gecen, on='Şirket', how='left', suffixes=('_yeni', '_eski')).fillna(0)
        df_diff['Pay Farkı'] = df_diff[f'{col_pay}_yeni'] - df_diff[f'{col_pay}_eski']
        
        df_artanlar = df_diff[df_diff['Pay Farkı'] > 0].sort_values('Pay Farkı', ascending=False).reset_index(drop=True)
        df_artanlar.index += 1
        st.dataframe(df_artanlar.style.format({f'{col_pay}_yeni': '{:.2f}%', f'{col_pay}_eski': '{:.2f}%', 'Pay Farkı': '+{:.2f}%'}), use_container_width=True)

# --- TAB 3: Toptan Satış ---
with t3:
    if not df_toptan.empty:
        st.subheader("🔄 Dağıtıcılar Arası Toptan Satış Performansı")
        t_donem = st.selectbox("Toptan Dönemi:", df_toptan.sort_values('Tarih', ascending=False)['Dönem'].unique())
        curr_t = df_toptan[df_toptan['Dönem'] == t_donem]['Tarih'].iloc[0]
        prev_t = curr_t - relativedelta(years=1)
        
        df_t_c = df_toptan[df_toptan['Tarih'] == curr_t]
        df_t_p = df_toptan[df_toptan['Tarih'] == prev_t]
        
        df_t_f = pd.merge(df_t_c, df_t_p[['Şirket', 'Toplam Ton', 'Toplam Pay']], on='Şirket', how='left', suffixes=('', '_gecen_yil')).fillna(0)
        df_t_f = df_t_f.sort_values('Toplam Pay', ascending=False).reset_index(drop=True)
        df_t_f.index += 1
        st.dataframe(df_t_f.style.format({'Toplam Ton': '{:,.2f}', 'Toplam Pay': '{:.2f}%', 'Toplam Ton_gecen_yil': '{:,.2f}', 'Toplam Pay_gecen_yil': '{:.2f}%'}), use_container_width=True)

# --- TAB 4: Yıllık Karşılaştırma ---
with t4:
    if not df_kar.empty:
        k_donem = st.selectbox("Karsılastırma Dönemi:", df_kar.sort_values('Tarih', ascending=False)['Dönem'].unique())
        st.dataframe(df_kar[(df_kar['Dönem'] == k_donem) & (df_kar['Ürün'] == secilen_segment)].sort_values('Cari Pay', ascending=False).reset_index(drop=True), use_container_width=True)

# --- TAB 5: Makro Analiz (Geri Getirilen Kısım) ---
with t5:
    st.subheader("💵 Makro Analiz: Satış Hacmi vs Dolar Kuru")
    if not df_ana.empty:
        df_hacim = df_ana.groupby('Tarih')[col_ton].sum().reset_index()
        df_dolar = dolar_verisi_getir(df_hacim['Tarih'].min())
        if not df_dolar.empty:
            df_makro = pd.merge(df_hacim, df_dolar, on='Tarih', how='inner')
            fig = go.Figure()
            fig.add_trace(go.Bar(x=df_makro['Tarih'], y=df_makro[col_ton], name='Satış (Ton)', marker_color='#3366CC', opacity=0.6))
            fig.add_trace(go.Scatter(x=df_makro['Tarih'], y=df_makro['Dolar Kuru'], name='USD/TRY', yaxis='y2', line=dict(color='#DC3912', width=3)))
            fig.update_layout(yaxis=dict(title='Tonaj'), yaxis2=dict(title='Dolar', overlaying='y', side='right'), hovermode='x unified')
            st.plotly_chart(fig, use_container_width=True)
