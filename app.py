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
BAYRAMLAR = [{"Tarih": "2022-05-01", "Isim": "Ramazan B."}, {"Tarih": "2024-06-01", "Isim": "Kurban B."}] # Örnek

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
}

STOP_WORDS = ["A.Ş", "A.S", "A.Ş.", "LTD", "ŞTİ", "STI", "SAN", "VE", "TİC", "TIC", "PETROL", "GAZ", "LPG", "AKARYAKIT"]

# --- YARDIMCI FONKSİYONLAR ---
def get_total_ram_usage():
    return psutil.Process(os.getpid()).memory_info().rss / 1024 / 1024

def format_tarih_tr(date_obj):
    return f"{TR_AYLAR.get(date_obj.month, '')} {date_obj.year}" if not pd.isna(date_obj) else ""

def format_tarih_grafik(date_obj):
    return f"{TR_AYLAR_KISA.get(date_obj.month, '')} {date_obj.year}" if not pd.isna(date_obj) else ""

def sayi_temizle(text):
    try: return float(text.replace('.', '').replace(',', '.'))
    except: return 0.0

def ismi_temizle_kok(isim):
    isim = isim.upper().replace('İ', 'I').replace('.', ' ')
    kelimeler = isim.split()
    temiz = [k for k in kelimeler if k not in STOP_WORDS and len(k) > 2]
    return " ".join(temiz) if temiz else isim

def sirket_ismi_standartlastir(ham_isim, mevcut_isimler):
    ham_isim = ham_isim.strip()
    ham_upper = ham_isim.upper().replace('İ', 'I')
    for k, v in OZEL_DUZELTMELER.items():
        if k.upper().replace('İ', 'I') in ham_upper: return v
    if mevcut_isimler:
        ham_kok = ismi_temizle_kok(ham_upper)
        en_iyi, en_yuksek = None, 0
        for mevcut in mevcut_isimler:
            skor = fuzz.ratio(ham_kok, ismi_temizle_kok(mevcut))
            if skor > en_yuksek: en_yuksek, en_iyi = skor, mevcut
        if en_yuksek >= 95: return en_iyi
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
    return pd.Timestamp(year=2000+int(match.group(2)), month=DOSYA_AY_MAP[match.group(1)], day=1) if match else None

# --- VERİ OKUMA ---
@st.cache_data
def verileri_oku():
    tum_veri_sirket = []
    tum_veri_iller = []
    tum_veri_turkiye = [] 
    tum_tr_aylik = [] # Tablo 3.5
    tum_tr_kumulatif = [] # Tablo 3.6
    sirket_listesi = set()
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx')])
    
    for dosya in files:
        tarih = dosya_isminden_tarih(dosya)
        if not tarih: continue
        try: doc = Document(os.path.join(DOSYA_KLASORU, dosya))
        except: continue
        
        iter_elem = iter_block_items(doc)
        son_baslik = ""
        son_sehir_sirket = None
        
        for block in iter_elem:
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if len(text) > 5:
                    son_baslik = text
                    if "Tablo" in text and ":" in text:
                        son_sehir_sirket = text.split(":")[1].strip()
            
            elif isinstance(block, Table):
                header_text = "".join([c.text.upper() for row in block.rows[:2] for c in row.cells])
                
                # Tablo 3.5 veya 3.6 (Türkiye Geneli Dağıtıcı Bazlı)
                if ("3.5" in son_baslik or "3.6" in son_baslik) and "SATIŞ (TON)" in header_text:
                    hedef_liste = tum_tr_kumulatif if "3.6" in son_baslik or "OCAK-" in son_baslik.upper() else tum_tr_aylik
                    for row in block.rows:
                        cells = row.cells
                        if len(cells) < 7: continue
                        isim = cells[0].text.strip()
                        if any(x in isim.upper() for x in ["UNVANI", "TOPLAM", "LİSANS"]) or not isim: continue
                        std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                        sirket_listesi.add(std_isim)
                        hedef_liste.append({
                            'Tarih': tarih, 'Şirket': std_isim,
                            'Tüplü Ton': sayi_temizle(cells[1].text), 'Tüplü Pay': sayi_temizle(cells[2].text),
                            'Dökme Ton': sayi_temizle(cells[3].text), 'Dökme Pay': sayi_temizle(cells[4].text),
                            'Otogaz Ton': sayi_temizle(cells[5].text), 'Otogaz Pay': sayi_temizle(cells[6].text)
                        })

                # İllere Göre Dağılım (Pazar Toplamları)
                elif "İLLERE" in son_baslik.upper() and "DAĞILIMI" in son_baslik.upper():
                    for row in block.rows:
                        cells = row.cells
                        if len(cells) < 6: continue
                        il_adi = cells[0].text.strip()
                        if "TOPLAM" in il_adi.upper():
                            tum_veri_turkiye.append({'Tarih': tarih, 'Tüplü Ton': sayi_temizle(cells[1].text), 'Dökme Ton': sayi_temizle(cells[3].text), 'Otogaz Ton': sayi_temizle(cells[5].text)})
                        elif il_adi and "İL" not in il_adi.upper():
                            tum_veri_iller.append({'Tarih': tarih, 'Şehir': il_adi.replace('İ','i').replace('I','ı').title(), 'Tüplü Ton': sayi_temizle(cells[1].text), 'Dökme Ton': sayi_temizle(cells[3].text), 'Otogaz Ton': sayi_temizle(cells[5].text)})

                # Şehir ve Şirket Bazlı Detay
                elif son_sehir_sirket and "PAY" in header_text:
                    for row in block.rows:
                        cells = row.cells
                        if len(cells) < 7: continue
                        isim = cells[0].text.strip()
                        if any(x in isim.upper() for x in ["UNVANI", "TOPLAM", "LİSANS"]) or not isim: continue
                        std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                        sirket_listesi.add(std_isim)
                        tum_veri_sirket.append({
                            'Tarih': tarih, 'Şehir': son_sehir_sirket.replace('İ','i').replace('I','ı').title(), 'Şirket': std_isim, 
                            'Tüplü Ton': sayi_temizle(cells[1].text), 'Tüplü Pay': sayi_temizle(cells[2].text),
                            'Dökme Ton': sayi_temizle(cells[3].text), 'Dökme Pay': sayi_temizle(cells[4].text),
                            'Otogaz Ton': sayi_temizle(cells[5].text), 'Otogaz Pay': sayi_temizle(cells[6].text)
                        })

    # DataFrame'e çevir ve temizle
    res = []
    for d in [tum_veri_sirket, tum_veri_iller, tum_veri_turkiye, tum_tr_aylik, tum_tr_kumulatif]:
        df = pd.DataFrame(d)
        if not df.empty:
            if 'Şirket' in df.columns and 'Şehir' in df.columns:
                df = df.groupby(['Tarih','Şehir','Şirket'], as_index=False).sum()
            elif 'Şirket' in df.columns:
                df = df.groupby(['Tarih','Şirket'], as_index=False).sum()
            df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
            df['Tarih_Grafik'] = df['Tarih'].apply(format_tarih_grafik)
        res.append(df)
    return res

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Stratejik Analiz", layout="wide")
if 'analiz_basladi' not in st.session_state: st.session_state['analiz_basladi'] = False

if not st.session_state['analiz_basladi']:
    with st.container():
        st.title("📊 EPDK Stratejik Pazar Analizi")
        if st.button("🚀 SİSTEMİ BAŞLAT"): st.session_state['analiz_basladi'] = True; st.rerun()
    st.stop()

with st.spinner('Veriler İşleniyor...'):
    df_sirket, df_iller, df_turkiye, df_tr_aylik, df_tr_kumulatif = verileri_oku()

# --- SIDEBAR ---
st.sidebar.header("⚙️ Parametreler")
sehir_listesi = sorted(df_sirket['Şehir'].unique())
secilen_sehir = st.sidebar.selectbox("Şehir Seçiniz:", sehir_listesi, index=sehir_listesi.index("Ankara") if "Ankara" in sehir_listesi else 0)
secilen_segment = st.sidebar.selectbox("Segment:", ["Otogaz", "Tüplü", "Dökme"])
veri_kapsami = st.sidebar.radio("📊 Veri Kapsamı (Grafikler İçin):", ["Aylık (Tablo 3.5)", "Kümülatif (Tablo 3.6 - Ocak'tan Beri)"])

# --- ANA PANEL ---
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["📈 Pazar Grafiği", "💵 Makro", "🥊 Rekabet", "🌡️ Tahmin", "🧠 Stratejik", "🇹🇷 Türkiye Detay (3.5 & 3.6)"])

with tab1:
    st.subheader(f"📈 {secilen_sehir} - {secilen_segment} Trend Analizi")
    df_hedef = df_sirket[df_sirket['Şehir'] == secilen_sehir]
    sirketler = sorted(df_hedef['Şirket'].unique())
    secilen_sirketler = st.multiselect("Şirketleri Seç:", sirketler, default=[s for s in [LIKITGAZ_NAME, "AYGAZ A.Ş."] if s in sirketler])
    
    veri_tipi = st.radio("Veri Tipi:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
    y_col = secilen_segment + (" Pay" if "Pay" in veri_tipi else " Ton")
    
    if secilen_sirketler:
        fig = px.line(df_hedef[df_hedef['Şirket'].isin(secilen_sirketler)], x='Tarih', y=y_col, color='Şirket', markers=True)
        st.plotly_chart(fig, use_container_width=True)

with tab6:
    st.subheader("🇹🇷 Türkiye Geneli Dağıtıcı Performansı (Tablo 3.5 & 3.6)")
    tr_mod = st.radio("Tablo Türü Seçin:", ["Aylık (Tablo 3.5)", "Kümülatif Ocak-Güncel (Tablo 3.6)"], horizontal=True)
    df_tr_aktif = df_tr_kumulatif if "Kümülatif" in tr_mod else df_tr_aylik
    
    if not df_tr_aktif.empty:
        son_tr_tarih = df_tr_aktif['Tarih'].max()
        st.info(f"Son Veri Dönemi: {format_tarih_tr(son_tr_tarih)}")
        
        c1, c2 = st.columns([1, 2])
        with c1:
            seg_pay = secilen_segment + " Pay"
            df_pie = df_tr_aktif[df_tr_aktif['Tarih'] == son_tr_tarih].sort_values(seg_pay, ascending=False).head(8)
            fig_pie = px.pie(df_pie, values=seg_pay, names='Şirket', title=f"Türkiye Geneli {secilen_segment} Payları")
            st.plotly_chart(fig_pie, use_container_width=True)
        
        with c2:
            df_tablo = df_tr_aktif[df_tr_aktif['Tarih'] == son_tr_tarih].sort_values(secilen_segment + " Ton", ascending=False).reset_index(drop=True)
            df_tablo.index += 1
            st.write("**Dağıtıcı Bazlı Detay Sıralaması**")
            st.dataframe(df_tablo[['Şirket', secilen_segment+' Ton', secilen_segment+' Pay']].style.format({secilen_segment+' Ton': '{:,.2f}', secilen_segment+' Pay': '%{:.2f}'}), use_container_width=True)
    else:
        st.warning("Bu tablolar için veri bulunamadı.")

# Diğer tablar mevcut kodundaki mantıkla çalışmaya devam eder...
# (HHI, Stratejik Rapor vb. bölümleri buraya aynen ekleyebilirsin)
