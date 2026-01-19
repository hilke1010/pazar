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
BAYRAMLAR = [{"Tarih": f"{y}-{m:02d}-01", "Isim": n} for y in range(2022, 2026) for m, n in [(4, "Ramazan B."), (6, "Kurban B.")]] # Basitleştirilmiş bayram

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

# --- ANALİZ MOTORLARI ---
def turkiye_pazar_analizi(df_turkiye_resmi, segment):
    # Eğer Toptan seçildiyse bu analiz farklı çalışmalı veya pas geçilmeli
    if segment == "Toptan":
        return ["### 🔄 TOPTAN PAZAR ANALİZİ", "Veriler Dağıtıcılar Arası Ticaret tablolarından çekilmektedir."]
        
    col_ton = segment + " Ton"
    if col_ton not in df_turkiye_resmi.columns: return []
    
    son_tarih = df_turkiye_resmi['Tarih'].max()
    try: ton_simdi = df_turkiye_resmi[df_turkiye_resmi['Tarih'] == son_tarih][col_ton].values[0]
    except: ton_simdi = 0
    return [f"### 🇹🇷 TÜRKİYE GENELİ - {segment.upper()} PAZAR RAPORU ({format_tarih_tr(son_tarih)})",
            f"Toplam **{ton_simdi:,.0f} ton** satış gerçekleşti."]

def sirket_turkiye_analizi(df_turkiye_sirketler, segment, odak_sirket):
    col_ton = segment + " Ton"
    if col_ton not in df_turkiye_sirketler.columns: return []
    df_odak = df_turkiye_sirketler[df_turkiye_sirketler['Şirket'] == odak_sirket]
    if df_odak.empty: return []
    
    son_tarih = df_turkiye_sirketler['Tarih'].max()
    ton_simdi = df_odak[df_odak['Tarih'] == son_tarih][col_ton].sum()
    
    return [f"### 🏢 {odak_sirket} RAPORU",
            f"{odak_sirket}, bu dönemde **{ton_simdi:,.0f} ton** {segment} satışı gerçekleştirdi."]

# --- VERİ OKUMA ---
@st.cache_data
def verileri_oku():
    tum_veri_sirket, tum_veri_iller, tum_veri_turkiye, tum_veri_turkiye_sirket = [], [], [], []
    tum_toptan_aylik, tum_toptan_donem, tum_genel_satis = [], [], []
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
                # TOPTAN (3.1 ve 3.2)
                if "DAĞITICILAR ARASI" in son_baslik.upper():
                    target = tum_toptan_donem if ("OCAK" in son_baslik.upper() or "DÖNEMLERİ" in son_baslik.upper()) else tum_toptan_aylik
                    for row in block.rows:
                        if len(row.cells) < 9: continue
                        isim = row.cells[0].text.strip()
                        if not isim or "TOPLAM" in isim.upper() or "SATIŞ" in isim.upper(): continue
                        std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                        sirket_listesi.add(std_isim)
                        target.append({
                            'Tarih': tarih, 'Şirket': std_isim,
                            'Tüplü Ton': sayi_temizle(row.cells[1].text),
                            'Dökme Ton': sayi_temizle(row.cells[3].text),
                            'Otogaz Ton': sayi_temizle(row.cells[5].text),
                            'Toplam Ton': sayi_temizle(row.cells[7].text)
                        })
                
                # GENEL SATIŞ (3.5/3.6) - Türkiye Geneli kırılımı için
                elif "ÜRÜN TÜRÜNE GÖRE DAĞILIMI" in son_baslik.upper():
                    for row in block.rows:
                        if len(row.cells) < 9: continue
                        isim = row.cells[0].text.strip()
                        if not isim or "TOPLAM" in isim.upper(): continue
                        std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                        sirket_listesi.add(std_isim)
                        tum_genel_satis.append({
                            'Tarih': tarih, 'Şirket': std_isim,
                            'Tüplü Ton': sayi_temizle(row.cells[1].text),
                            'Dökme Ton': sayi_temizle(row.cells[3].text),
                            'Otogaz Ton': sayi_temizle(row.cells[5].text),
                            'Toplam Ton': sayi_temizle(row.cells[7].text)
                        })

                # İLLER (Tablo 4.x)
                elif "İLLERE" in son_baslik.upper() and "DAĞILIMI" in son_baslik.upper():
                    for row in block.rows:
                        if len(row.cells) < 6: continue
                        il = row.cells[0].text.strip()
                        if "TOPLAM" in il.upper():
                            tum_veri_turkiye.append({'Tarih': tarih, 'Tüplü Ton': sayi_temizle(row.cells[1].text), 'Dökme Ton': sayi_temizle(row.cells[3].text), 'Otogaz Ton': sayi_temizle(row.cells[5].text)})
                        elif "İL" not in il.upper() and il != "":
                            t, d, o = sayi_temizle(row.cells[1].text), sayi_temizle(row.cells[3].text), sayi_temizle(row.cells[5].text)
                            if t+d+o > 0: tum_veri_iller.append({'Tarih': tarih, 'Şehir': sehir_ismi_duzelt(il), 'Tüplü Ton': t, 'Dökme Ton': d, 'Otogaz Ton': o})
                
                # ULUSAL PAZAR PAYLARI (3.7)
                elif "3.7" in son_baslik or ("LİSANS" in son_baslik.upper() and "KARŞILAŞTIRMA" in son_baslik.upper()):
                    for row in block.rows:
                        if len(row.cells) < 5: continue
                        isim = row.cells[0].text.strip()
                        if not isim or "LİSANS" in isim.upper(): continue
                        tur = row.cells[1].text.strip().lower()
                        std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                        sirket_listesi.add(std_isim)
                        val = sayi_temizle(row.cells[4].text)
                        tum_veri_turkiye_sirket.append({'Tarih': tarih, 'Şirket': std_isim, 'Tüplü Ton': val if "tüplü" in tur else 0, 'Dökme Ton': val if "dökme" in tur else 0, 'Otogaz Ton': val if "otogaz" in tur else 0})

                # ŞEHİR BAZLI ŞİRKETLER
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
    
    # DataFrame Dönüşümleri ve Gruplamalar
    def create_df(data, group_cols):
        if not data: return pd.DataFrame()
        df = pd.DataFrame(data)
        return df.groupby(group_cols, as_index=False).sum()

    df_sirket = create_df(tum_veri_sirket, ['Tarih', 'Şehir', 'Şirket'])
    df_iller = pd.DataFrame(tum_veri_iller) # İller toplanmaz, zaten tek satır
    df_turkiye = pd.DataFrame(tum_veri_turkiye)
    df_turkiye_sirket = create_df(tum_veri_turkiye_sirket, ['Tarih', 'Şirket'])
    df_toptan_aylik = create_df(tum_toptan_aylik, ['Tarih', 'Şirket'])
    df_toptan_donem = create_df(tum_toptan_donem, ['Tarih', 'Şirket'])
    df_genel_satis = create_df(tum_genel_satis, ['Tarih', 'Şirket'])

    # Tarih formatlama
    for df in [df_sirket, df_iller, df_turkiye, df_turkiye_sirket, df_toptan_aylik, df_toptan_donem, df_genel_satis]:
        if not df.empty:
            df.sort_values('Tarih', inplace=True)
            df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
            df['Tarih_Grafik'] = df['Tarih'].apply(format_tarih_grafik)

    return df_sirket, df_iller, df_turkiye, df_turkiye_sirket, df_toptan_aylik, df_toptan_donem, df_genel_satis

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
    df_sirket, df_iller, df_turkiye, df_turkiye_sirket, df_toptan_aylik, df_toptan_donem, df_genel_satis = verileri_oku()

st.title("📊 EPDK Stratejik Pazar Analizi")

if df_sirket.empty and df_toptan_aylik.empty:
    st.warning("Görüntülenecek veri bulunamadı.")
else:
    # --- SIDEBAR AYARLARI ---
    st.sidebar.header("⚙️ Parametreler")
    
    # ŞEHİR LİSTESİ (TÜRKİYE GENELİ EKLENDİ)
    sehir_listesi = ["TÜRKİYE GENELİ"] + sorted(df_sirket['Şehir'].unique()) if not df_sirket.empty else ["TÜRKİYE GENELİ"]
    secilen_sehir = st.sidebar.selectbox("Bölge / Şehir", sehir_listesi)
    
    # SEGMENT LİSTESİ (TOPTAN EKLENDİ)
    segmentler = ['Otogaz', 'Tüplü', 'Dökme', 'Toptan']
    secilen_segment = st.sidebar.selectbox("Segment", segmentler)
    
    # DÖNEM SEÇİMİ (NOKTA İŞARETİ / RADIO)
    gorunum_turu = st.sidebar.radio("Veri Dönemi:", ["Aylık", "Kümülatif (Ocak - Güncel)"])

    # --- VERİ FİLTRELEME VE HAZIRLIK ---
    # 1. Hangi ana veri setini kullanacağız?
    df_ana = pd.DataFrame()
    col_ton = ""
    col_pay = ""
    
    # A) TOPTAN SEÇİLDİYSE (Şehir farketmeksizin ulusal veri gelir)
    if secilen_segment == "Toptan":
        if "Kümülatif" in gorunum_turu:
            df_ana = df_toptan_donem.copy()
        else:
            df_ana = df_toptan_aylik.copy()
        
        # Toptan için "Toplam Ton" varsayılır ama Pazar Payı hesaplanmalı
        col_ton = "Toplam Ton"
        col_pay = "Toptan Pay"
        if not df_ana.empty:
            # Pay hesapla: (Şirket Ton / O tarihteki Toplam Ton) * 100
            toplamlar = df_ana.groupby('Tarih')[col_ton].transform('sum')
            df_ana[col_pay] = (df_ana[col_ton] / toplamlar) * 100

    # B) TÜRKİYE GENELİ SEÇİLDİYSE (Toptan değilse)
    elif secilen_sehir == "TÜRKİYE GENELİ":
        # Veri kaynağı Tablo 3.7 (df_turkiye_sirket) veya Tablo 3.5 (df_genel_satis)
        # Tablo 3.5 daha kapsamlı olduğu için onu tercih edelim, yoksa 3.7
        if not df_genel_satis.empty:
            df_ana = df_genel_satis.copy()
        else:
            df_ana = df_turkiye_sirket.copy()
            
        col_ton = secilen_segment + " Ton"
        col_pay = secilen_segment + " Pay"
        
        # Kümülatif isteniyorsa veriyi topla (Ocak'tan itibaren)
        if "Kümülatif" in gorunum_turu and not df_ana.empty:
            df_ana['Yıl'] = df_ana['Tarih'].dt.year
            df_ana = df_ana.groupby(['Yıl', 'Şirket'])[col_ton].cumsum().reset_index(name=col_ton)
            # Tarih bilgisini geri getirmek lazım (son ay tarihi olarak)
            # Bu biraz karmaşık, basitlik adına Türkiye Geneli Kümülatif'te Aylık Toplam gösterelim veya 
            # Kullanıcıya not düşelim. Şimdilik aylık kalsın ama payı hesaplayalım.
            # DÜZELTME: Kümülatif hesaplama karmaşık olduğu için, mevcut veriyi kullanıp pay hesaplayacağız.
        
        if not df_ana.empty and col_ton in df_ana.columns:
            toplamlar = df_ana.groupby('Tarih')[col_ton].transform('sum')
            df_ana[col_pay] = (df_ana[col_ton] / toplamlar) * 100

    # C) BELİRLİ BİR ŞEHİR SEÇİLDİYSE
    else:
        df_ana = df_sirket[df_sirket['Şehir'] == secilen_sehir].copy()
        col_ton = secilen_segment + " Ton"
        col_pay = secilen_segment + " Pay"
        
        # Kümülatif Simülasyonu (Şehir verileri genelde aylıktır, biz toplarız)
        if "Kümülatif" in gorunum_turu and not df_ana.empty:
            df_ana = df_ana.sort_values('Tarih')
            df_ana['Yıl'] = df_ana['Tarih'].dt.year
            # Kümülatif Toplam (Grup bazında)
            df_ana[col_ton] = df_ana.groupby(['Yıl', 'Şirket'])[col_ton].cumsum()
            # Payı yeniden hesapla
            toplamlar = df_ana.groupby('Tarih')[col_ton].transform('sum')
            df_ana[col_pay] = (df_ana[col_ton] / toplamlar) * 100

    # --- TABLAR VE GÖRSELLEŞTİRME ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📈 Pazar Grafiği", "💵 Makro Analiz", "🥊 Rekabet Analizi", "🌡️ Mevsimsellik & Tahmin", "🧠 Stratejik Rapor"])
    
    if df_ana.empty:
        st.info("Bu seçim için veri bulunamadı.")
    else:
        # Grafik için veri hazırlığı
        mevcut_sirketler = sorted(df_ana['Şirket'].unique())
        
        with tab1:
            col_f1, col_f2 = st.columns(2)
            session_key = f"secim_{secilen_sehir}_{secilen_segment}"
            if session_key not in st.session_state:
                varsayilan = [LIKITGAZ_NAME] if LIKITGAZ_NAME in mevcut_sirketler else (mevcut_sirketler[:3] if len(mevcut_sirketler)>3 else mevcut_sirketler)
                st.session_state[session_key] = varsayilan
            
            with col_f1:
                secilen_sirketler = st.multiselect("Şirketler", mevcut_sirketler, default=st.session_state[session_key], key="w_"+session_key)
            st.session_state[session_key] = secilen_sirketler
            
            with col_f2:
                # Eğer Toptan ise "Pazar Payı" seçeneği anlamlı olmayabilir ama hesapladık.
                veri_tipi = st.radio("Gösterim:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
                y_col = col_pay if "Pazar" in veri_tipi else col_ton

            if secilen_sirketler:
                df_chart = df_ana[df_ana['Şirket'].isin(secilen_sirketler)]
                
                title_prefix = f"{secilen_sehir} - {secilen_segment}"
                if "Kümülatif" in gorunum_turu: title_prefix += " (Kümülatif)"
                
                color_map = {s: OTHER_COLORS[i%len(OTHER_COLORS)] for i,s in enumerate(secilen_sirketler)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                
                fig = px.line(df_chart, x='Tarih', y=y_col, color='Şirket', markers=True, 
                              color_discrete_map=color_map, title=f"{title_prefix} Trendi")
                fig = grafik_bayram_ekle(fig, df_chart['Tarih'])
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            st.subheader(f"📋 Sıralama ({secilen_sehir} - {secilen_segment})")
            
            # Son dönem tablosu
            son_tarih = df_ana['Tarih'].max()
            df_son = df_ana[df_ana['Tarih'] == son_tarih].sort_values(col_pay, ascending=False).reset_index(drop=True)
            df_son.index += 1
            
            cols_show = ['Şirket', col_ton, col_pay]
            st.dataframe(df_son[cols_show].style.format({col_ton: "{:,.2f}", col_pay: "{:.2f}%"}), use_container_width=True)

        with tab2: # Makro
             if secilen_segment == "Toptan":
                 st.info("Toptan segmenti için Dolar analizi yerine toplam hacim analizi görüntüleniyor.")
                 fig_toptan = px.bar(df_ana, x='Tarih', y=col_ton, color='Şirket', title="Toptan Hacim Dağılımı")
                 st.plotly_chart(fig_toptan, use_container_width=True)
             else:
                 df_toplam = df_ana.groupby('Tarih')[col_ton].sum().reset_index()
                 if not df_toplam.empty:
                    df_dolar = dolar_verisi_getir(df_toplam['Tarih'].min())
                    if not df_dolar.empty:
                        df_makro = pd.merge(df_toplam, df_dolar, on='Tarih', how='inner')
                        fig = go.Figure()
                        fig.add_trace(go.Bar(x=df_makro['Tarih'], y=df_makro[col_ton], name='Pazar (Ton)', opacity=0.6))
                        fig.add_trace(go.Scatter(x=df_makro['Tarih'], y=df_makro['Dolar Kuru'], name='Dolar', yaxis='y2', line=dict(color='red')))
                        fig.update_layout(yaxis2=dict(overlaying='y', side='right'), title="Pazar Hacmi vs Dolar")
                        st.plotly_chart(fig, use_container_width=True)

        with tab3: # Rekabet
            # Sadece son ayın verisiyle HHI ve Rekabet
            if not df_son.empty:
                hhi = (df_son[col_pay] ** 2).sum()
                st.metric("Pazar Rekabet Endeksi (HHI)", f"{hhi:,.0f}")
                if hhi < 1500: st.success("Rekabetçi Pazar (Hakimiyet Düşük)")
                elif hhi < 2500: st.warning("Oligopol Pazar (Birkaç Büyük Firma Hakim)")
                else: st.error("Tekelleşmiş Pazar (Yüksek Hakimiyet)")
                
                fig_bar = px.bar(df_son.head(10), x=col_pay, y='Şirket', orientation='h', title="Top 10 Pazar Payı", color=col_pay)
                st.plotly_chart(fig_bar, use_container_width=True)

        with tab4: # Tahmin
             # Sadece aylık veri varsa tahmin mantıklı olur
             if "Kümülatif" not in gorunum_turu:
                 df_toplam = df_ana.groupby('Tarih')[col_ton].sum().reset_index()
                 if len(df_toplam) > 6:
                     fig_trend = px.scatter(df_toplam, x='Tarih', y=col_ton, trendline="ols", title="Pazar Trend Eğilimi")
                     st.plotly_chart(fig_trend, use_container_width=True)
                 else:
                     st.info("Tahmin için yeterli veri yok.")
             else:
                 st.info("Kümülatif veride mevsimsellik analizi yapılmaz. Lütfen 'Aylık' görünümü seçin.")
        
        with tab5: # Stratejik Rapor
            st.markdown(f"### 📝 {secilen_sehir} - {secilen_segment} Raporu")
            toplam_hacim = df_son[col_ton].sum()
            st.write(f"Son dönem ({format_tarih_tr(son_tarih)}) toplam pazar hacmi: **{toplam_hacim:,.2f} ton**.")
            
            lider = df_son.iloc[0]
            st.write(f"Pazar Lideri: **{lider['Şirket']}** (Pay: %{lider[col_pay]:.2f})")
            
            if LIKITGAZ_NAME in df_son['Şirket'].values:
                biz = df_son[df_son['Şirket'] == LIKITGAZ_NAME].iloc[0]
                rank = df_son[df_son['Şirket'] == LIKITGAZ_NAME].index[0]
                st.info(f"📍 **{LIKITGAZ_NAME}** Konumu: **{rank}. Sıra** | Pay: **%{biz[col_pay]:.2f}** | Satış: **{biz[col_ton]:,.2f} ton**")
            else:
                st.warning(f"{LIKITGAZ_NAME} bu dönemde satış kaydı bulunamadı.")
