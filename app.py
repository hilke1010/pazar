import streamlit as st
import pandas as pd
import os
import gc  # RAM temizliği için
import psutil # RAM takibi için
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

# Bayram Tarihleri
BAYRAMLAR = [
    {"Tarih": "2022-05-01", "Isim": "Ramazan B."}, {"Tarih": "2022-07-01", "Isim": "Kurban B."},
    {"Tarih": "2023-04-01", "Isim": "Ramazan B."}, {"Tarih": "2023-06-01", "Isim": "Kurban B."},
    {"Tarih": "2024-04-01", "Isim": "Ramazan B."}, {"Tarih": "2024-06-01", "Isim": "Kurban B."},
    {"Tarih": "2025-03-01", "Isim": "Ramazan B."}, {"Tarih": "2025-06-01", "Isim": "Kurban B."}
]

# ÖZEL DÜZELTMELER LİSTESİ
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

# ORTAK KELİMELERİ TEMİZLEME LİSTESİ (STOP WORDS)
STOP_WORDS = [
    "A.Ş", "A.S", "A.Ş.", "LTD", "ŞTİ", "STI", "SAN", "VE", "TİC", "TIC", 
    "PETROL", "ÜRÜNLERİ", "URUNLERI", "DAĞITIM", "DAGITIM", "GAZ", "LPG", 
    "AKARYAKIT", "ENERJİ", "ENERJI", "NAKLİYE", "NAKLIYE", "İNŞAAT", "INSAAT",
    "PAZARLAMA", "DEPOLAMA", "TURİZM", "TURIZM", "SANAYİ", "SANAYI"
]

# --- RAM TAKİP ---
def get_total_ram_usage():
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return mem_info.rss / 1024 / 1024

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

def ismi_temizle_kok(isim):
    """
    Şirket isminden 'Petrol', 'Gaz', 'A.Ş' gibi gürültü kelimeleri atar.
    """
    isim = isim.upper().replace('İ', 'I').replace('.', ' ')
    kelimeler = isim.split()
    temiz_kelimeler = [k for k in kelimeler if k not in STOP_WORDS and len(k) > 2]
    
    if not temiz_kelimeler: 
        return isim 
    return " ".join(temiz_kelimeler)

def sirket_ismi_standartlastir(ham_isim, mevcut_isimler):
    ham_isim = ham_isim.strip()
    ham_upper = ham_isim.upper().replace('İ', 'I')
    
    # 1. Adım: Kesin Liste Kontrolü
    for k, v in OZEL_DUZELTMELER.items():
        if k.upper().replace('İ', 'I') in ham_upper: 
            return v

    # 2. Adım: Akıllı Eşleştirme (FUZZY MATCHING - GÜVENLİ MOD)
    if mevcut_isimler:
        ham_kok = ismi_temizle_kok(ham_upper)
        en_iyi_eslesme = None
        en_yuksek_skor = 0
        
        for mevcut in mevcut_isimler:
            mevcut_kok = ismi_temizle_kok(mevcut)
            skor = fuzz.ratio(ham_kok, mevcut_kok)
            if skor > en_yuksek_skor:
                en_yuksek_skor = skor
                en_iyi_eslesme = mevcut
        
        # Eşik Değer: 95 (Çok yüksek, sadece yazım hatalarını yakalar)
        if en_yuksek_skor >= 95:
            return en_iyi_eslesme
            
    return ham_isim

def sehir_ismi_duzelt(sehir):
    if not sehir: return ""
    return sehir.replace('İ', 'i').replace('I', 'ı').title()

@st.cache_data
def dolar_verisi_getir(baslangic_tarihi):
    if not DOLAR_MODULU_VAR:
        return pd.DataFrame()
    try:
        dolar = yf.download("TRY=X", start=baslangic_tarihi, progress=False)
        if dolar.empty: return pd.DataFrame()
        dolar_aylik = dolar['Close'].resample('MS').mean().reset_index()
        dolar_aylik.columns = ['Tarih', 'Dolar Kuru']
        dolar_aylik['Tarih'] = pd.to_datetime(dolar_aylik['Tarih'])
        return dolar_aylik
    except Exception as e:
        return pd.DataFrame()

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

# --- ANALİZ MOTORLARI (ESKİLER KORUNDU) ---
def turkiye_pazar_analizi(df_turkiye_resmi, segment):
    # Bu fonksiyon aynen kalacak
    col_ton = segment + " Ton"
    son_tarih = df_turkiye_resmi['Tarih'].max()
    onceki_ay = son_tarih - relativedelta(months=1)
    gecen_yil = son_tarih - relativedelta(years=1)
    son_donem_str = format_tarih_tr(son_tarih)
    
    try: ton_simdi = df_turkiye_resmi[df_turkiye_resmi['Tarih'] == son_tarih][col_ton].values[0]
    except: ton_simdi = 0
    try: ton_gecen_ay = df_turkiye_resmi[df_turkiye_resmi['Tarih'] == onceki_ay][col_ton].values[0]
    except: ton_gecen_ay = 0
    try: ton_gecen_yil = df_turkiye_resmi[df_turkiye_resmi['Tarih'] == gecen_yil][col_ton].values[0]
    except: ton_gecen_yil = 0
    
    rapor = []
    rapor.append(f"### 🇹🇷 TÜRKİYE GENELİ - {segment.upper()} PAZAR RAPORU ({son_donem_str})")
    rapor.append(f"Resmi EPDK verilerine göre Türkiye genelinde bu ay toplam **{ton_simdi:,.0f} ton** {segment} satışı gerçekleşti.")
    return rapor

def sirket_turkiye_analizi(df_turkiye_sirketler, segment, odak_sirket):
    # Bu fonksiyon aynen kalacak
    if df_turkiye_sirketler.empty or 'Şirket' not in df_turkiye_sirketler.columns:
        return [f"⚠️ {odak_sirket} için Türkiye geneli (Tablo 3.7) verisi okunamadı."]
    col_ton = segment + " Ton"
    df_odak = df_turkiye_sirketler[df_turkiye_sirketler['Şirket'] == odak_sirket]
    if df_odak.empty: return [f"{odak_sirket} için Tablo 3.7'de (Ulusal Veri) kayıt bulunamadı."]
    
    toplamlar = df_odak.groupby('Tarih')[col_ton].sum()
    son_tarih = df_turkiye_sirketler['Tarih'].max()
    ton_simdi = toplamlar.get(son_tarih, 0)
    
    rapor = []
    rapor.append(f"### 🏢 {odak_sirket} TÜRKİYE GENELİ RAPORU")
    rapor.append(f"EPDK Tablo 3.7 (Resmi Veri)'ye göre {odak_sirket}, bu ay Türkiye genelinde **{ton_simdi:,.0f} ton** {segment} satışı gerçekleştirdi.")
    return rapor

def stratejik_analiz_raporu(df_sirket, df_iller, sehir, segment, odak_sirket):
    # Mevcut stratejik analiz fonksiyonu (Değiştirilmedi)
    col_pay = segment + " Pay"
    col_ton_il = segment + " Ton"
    col_ton_sirket = segment + " Ton"
    
    df_sehir_resmi = df_iller[df_iller['Şehir'].str.upper() == sehir.upper()].sort_values('Tarih')
    
    if df_sehir_resmi.empty or df_sehir_resmi[col_ton_il].sum() == 0:
        son_tarih = df_sirket['Tarih'].max()
    else:
        son_tarih = df_sehir_resmi[df_sehir_resmi[col_ton_il] > 0]['Tarih'].max()
        
    son_donem_str = format_tarih_tr(son_tarih)
    
    pazar_raporu = []
    sirket_raporu = []
    rakip_raporu = []

    try:
        if not df_sehir_resmi.empty:
            ton_simdi = df_sehir_resmi[df_sehir_resmi['Tarih'] == son_tarih][col_ton_il].sum()
            pazar_raporu.append(f"### 🌍 {sehir} - {segment} Pazar Durumu ({son_donem_str})")
            pazar_raporu.append(f"Bu ay toplam **{ton_simdi:,.0f} ton** satış gerçekleşti.")
        else:
            pazar_raporu.append("Şehir pazar verisi hesaplanamadı.")
    except:
        pazar_raporu.append("Pazar verisi hatası.")
    pazar_raporu.append("---")
    
    sirket_raporu.append(f"### 📊 {odak_sirket} Performans Detayı")
    df_odak = df_sirket[(df_sirket['Şirket'] == odak_sirket) & (df_sirket['Şehir'] == sehir)].sort_values('Tarih')
    if not df_odak.empty:
        df_odak = df_odak[df_odak['Tarih'] <= son_tarih]
        for i in range(len(df_odak)):
            curr = df_odak.iloc[i]
            tarih_str = format_tarih_tr(curr['Tarih'])
            sirket_raporu.append(f"**{tarih_str}:** Pay: %{curr[col_pay]:.2f} | Satış: {curr[col_ton_sirket]:,.0f} ton")
    
    rakip_raporu.append(f"### 📡 Rakip Trend Dedektörü ({sehir})")
    
    return pazar_raporu, sirket_raporu, rakip_raporu

# --- VERİ OKUMA (GÜNCELLENDİ) ---
@st.cache_data
def verileri_oku():
    tum_veri_sirket = []
    tum_veri_iller = []
    tum_veri_turkiye = [] 
    tum_veri_turkiye_sirket = []
    
    # Yeni Tablolar için Listeler
    tum_toptan_aylik = [] # Tablo 3.1
    tum_toptan_donem = [] # Tablo 3.2
    tum_genel_satis = [] # Tablo 3.5/3.6
    tum_karsilastirma = [] # Tablo 3.4
    
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
                # 1. TABLO 3.4: Yıllık Karşılaştırma
                if "KARŞILAŞTIRMA" in son_baslik.upper() and "ÜRÜN TÜRÜNE" in son_baslik.upper():
                    try:
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 6: continue
                            tur = cells[0].text.strip().upper()
                            if tur in ["TÜPLÜ", "DÖKME", "OTOGAZ", "GENEL TOPLAM", "DÖKME*"]:
                                if "DÖKME*" in tur: tur = "DÖKME"
                                tum_karsilastirma.append({
                                    'Tarih': tarih,
                                    'Ürün Türü': tur,
                                    'Onceki_Yil_Ton': sayi_temizle(cells[1].text),
                                    'Cari_Yil_Ton': sayi_temizle(cells[3].text),
                                    'Degisim_Yuzde': sayi_temizle(cells[5].text)
                                })
                    except: pass
                
                # 2. TABLO 3.1 & 3.2: Dağıtıcılar Arası Toptan
                elif "DAĞITICILAR ARASI" in son_baslik.upper():
                    is_donemlik = "OCAK" in son_baslik.upper() or "DÖNEMLERİ" in son_baslik.upper()
                    target_list = tum_toptan_donem if is_donemlik else tum_toptan_aylik
                    
                    try:
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 9: continue
                            isim = cells[0].text.strip()
                            if not isim or "SATIŞ YAPAN" in isim.upper() or "TOPLAM" in isim.upper(): continue
                            
                            std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                            sirket_listesi.add(std_isim)
                            
                            target_list.append({
                                'Tarih': tarih,
                                'Şirket': std_isim,
                                'Tüplü Ton': sayi_temizle(cells[1].text),
                                'Dökme Ton': sayi_temizle(cells[3].text),
                                'Otogaz Ton': sayi_temizle(cells[5].text),
                                'Toplam Ton': sayi_temizle(cells[7].text)
                            })
                    except: pass

                # 3. TABLO 3.5/3.6: Genel Satış Dağılımı
                elif "DAĞITICILARA VE ÜRÜN TÜRÜNE GÖRE" in son_baslik.upper():
                    try:
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 9: continue
                            isim = cells[0].text.strip()
                            if not isim or "LİSANS SAHİBİ" in isim.upper() or "TOPLAM" in isim.upper(): continue
                            
                            std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                            sirket_listesi.add(std_isim)
                            
                            tum_genel_satis.append({
                                'Tarih': tarih,
                                'Şirket': std_isim,
                                'Tüplü Ton': sayi_temizle(cells[1].text),
                                'Dökme Ton': sayi_temizle(cells[3].text),
                                'Otogaz Ton': sayi_temizle(cells[5].text),
                                'Toplam Ton': sayi_temizle(cells[7].text)
                            })
                    except: pass

                # MEVCUT MANTIK (İL BAZLI & TÜRKİYE TOPLAMI)
                elif "İLLERE" in son_baslik.upper() and "DAĞILIMI" in son_baslik.upper():
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
    
    gc.collect() # Çöp toplayıcı
    
    # DATAFRAME OLUŞTURMA
    df_sirket = pd.DataFrame(tum_veri_sirket)
    if not df_sirket.empty:
        df_sirket = df_sirket.groupby(['Tarih', 'Şehir', 'Şirket'], as_index=False)[
            ['Tüplü Ton', 'Tüplü Pay', 'Dökme Ton', 'Dökme Pay', 'Otogaz Ton', 'Otogaz Pay']
        ].sum()
    
    df_iller = pd.DataFrame(tum_veri_iller)
    df_turkiye = pd.DataFrame(tum_veri_turkiye)
    
    if tum_veri_turkiye_sirket:
        df_ts = pd.DataFrame(tum_veri_turkiye_sirket)
        df_turkiye_sirket = df_ts.groupby(['Tarih', 'Şirket'], as_index=False)[['Tüplü Ton', 'Dökme Ton', 'Otogaz Ton']].sum()
    else: df_turkiye_sirket = pd.DataFrame()
    
    # Yeni DF'ler
    df_toptan_aylik = pd.DataFrame(tum_toptan_aylik)
    if not df_toptan_aylik.empty: df_toptan_aylik = df_toptan_aylik.groupby(['Tarih', 'Şirket'], as_index=False).sum()

    df_toptan_donem = pd.DataFrame(tum_toptan_donem)
    if not df_toptan_donem.empty: df_toptan_donem = df_toptan_donem.groupby(['Tarih', 'Şirket'], as_index=False).sum()

    df_genel_satis = pd.DataFrame(tum_genel_satis)
    if not df_genel_satis.empty: df_genel_satis = df_genel_satis.groupby(['Tarih', 'Şirket'], as_index=False).sum()

    df_karsilastirma = pd.DataFrame(tum_karsilastirma)
    
    for df in [df_sirket, df_iller, df_turkiye, df_turkiye_sirket, df_toptan_aylik, df_toptan_donem, df_genel_satis, df_karsilastirma]:
        if not df.empty:
            df.sort_values('Tarih', inplace=True)
            df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
            df['Tarih_Grafik'] = df['Tarih'].apply(format_tarih_grafik)
            
    return df_sirket, df_iller, df_turkiye, df_turkiye_sirket, df_toptan_aylik, df_toptan_donem, df_genel_satis, df_karsilastirma

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
        
        ram_mb = get_total_ram_usage()
        st.metric("Sistem Boşta (RAM)", f"{ram_mb:.0f} MB")
        
        if st.button("🚀 ANALİZİ BAŞLAT", type="primary", use_container_width=True):
            st.session_state['analiz_basladi'] = True
            st.rerun()
    st.stop()

# --- ANALİZ EKRANI ---

with st.spinner('Veriler yükleniyor...'):
    # Veri okuma fonksiyonu artık daha fazla veri dönüyor
    df_sirket, df_iller, df_turkiye, df_turkiye_sirket, df_toptan_aylik, df_toptan_donem, df_genel_satis, df_karsilastirma = verileri_oku()

st.title("📊 EPDK Stratejik Pazar Analizi")

ram_now = get_total_ram_usage()
ram_limit = 16384.0
bar_color = "green" if ram_now < 10000 else "red"
st.sidebar.markdown(f"### RAM Durumu")
st.sidebar.progress(min(ram_now/ram_limit, 1.0))
st.sidebar.caption(f"Kullanılan: {ram_now:.0f} MB / {ram_limit:.0f} MB")
st.sidebar.markdown("---")

if not os.path.exists(DOSYA_KLASORU):
    st.error(f"'{DOSYA_KLASORU}' klasörü bulunamadı.")
else:
    if df_sirket.empty:
        st.warning("Veri yok.")
    else:
        st.sidebar.header("⚙️ Parametreler")
        sehirler = sorted(df_sirket['Şehir'].unique())
        idx_ank = sehirler.index('Ankara') if 'Ankara' in sehirler else 0
        secilen_sehir = st.sidebar.selectbox("Şehir", sehirler, index=idx_ank)
        
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("Segment", segmentler)

        st.sidebar.markdown("---")
        st.sidebar.header("🔗 Diğer Raporlar")
        st.sidebar.markdown("⛽ [Akaryakıt Lisans Raporu](https://akartakip.streamlit.app/)")
        st.sidebar.markdown("🔥 [LPG Lisans Raporu](https://lpgtakip.streamlit.app/)")
        
        st.sidebar.markdown("---")
        st.sidebar.header("📧 İletişim")
        st.sidebar.info("kerim.aksu@milangaz.com.tr")
        
        df_sehir_sirket = df_sirket[df_sirket['Şehir'] == secilen_sehir]
        col_pay = secilen_segment + " Pay"
        
        if secilen_sehir in ["Adana", "Bingöl"]:
            st.error("⚠️ **SİSTEM UYARISI:** Adana ili için kaynak veri dosyalarında yapısal bozukluklar tespit edilmiştir (EPDK kaynaklı). Yanlış analiz oluşmaması adına Adana ili tüm sekmelerde geçici olarak erişime kapatılmıştır.")
        else:
            # YENİ TAB EKLENDİ: "🇹🇷 Genel Görünüm & Toptan"
            tab_genel, tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "🇹🇷 Genel Görünüm & Toptan",
                "📈 Pazar Grafiği", 
                "💵 Makro Analiz", 
                "🥊 Rekabet Analizi", 
                "🌡️ Mevsimsellik & Tahmin", 
                "🧠 Stratejik Rapor"
            ])
            
            # --- YENİ EKLENEN SEKME KODLARI ---
            with tab_genel:
                st.subheader("🇹🇷 Türkiye Geneli LPG Sektör Görünümü")
                
                # 1. BÖLÜM: YILLIK KARŞILAŞTIRMA (Tablo 3.4)
                if not df_karsilastirma.empty:
                    son_tarih = df_karsilastirma['Tarih'].max()
                    df_son_kar = df_karsilastirma[df_karsilastirma['Tarih'] == son_tarih]
                    donem_adi = df_son_kar.iloc[0]['Dönem'] if not df_son_kar.empty else ""
                    
                    st.markdown(f"#### 📅 {donem_adi} - Yıllık Karşılaştırma (Tablo 3.4)")
                    col_k1, col_k2 = st.columns([2, 1])
                    
                    with col_k1:
                        fig_kar = px.bar(df_son_kar, x='Ürün Türü', y=['Onceki_Yil_Ton', 'Cari_Yil_Ton'], 
                                         barmode='group', title="Geçen Yıl vs Bu Yıl (Ton)",
                                         labels={'value': 'Ton', 'variable': 'Dönem'})
                        st.plotly_chart(fig_kar, use_container_width=True)
                    
                    with col_k2:
                        st.dataframe(df_son_kar[['Ürün Türü', 'Degisim_Yuzde']].style.format({'Degisim_Yuzde': '{:,.2f}%'}), use_container_width=True)
                else:
                    st.info("Tablo 3.4 verisi bulunamadı.")
                
                st.markdown("---")

                # 2. BÖLÜM: DAĞITICILAR ARASI TOPTAN TİCARET (Tablo 3.1 & 3.2)
                st.markdown("#### 🔄 Dağıtıcılar Arası Toptan LPG Ticareti")
                toptan_mod = st.radio("Görünüm Seç:", ["Kümülatif (Tablo 3.2)", "Aylık (Tablo 3.1)"], horizontal=True)
                
                df_target = df_toptan_donem if "Kümülatif" in toptan_mod else df_toptan_aylik
                
                if not df_target.empty:
                    son_tarih_toptan = df_target['Tarih'].max()
                    df_viz = df_target[df_target['Tarih'] == son_tarih_toptan].sort_values('Toplam Ton', ascending=False).head(15)
                    
                    # Genel Toplam Grafik
                    fig_toptan = px.bar(df_viz, x='Şirket', y='Toplam Ton', text='Toplam Ton', title=f"Toptan Satış Liderleri ({toptan_mod})", color='Toplam Ton', color_continuous_scale='Viridis')
                    fig_toptan.update_traces(texttemplate='%{text:.0s}', textposition='outside')
                    st.plotly_chart(fig_toptan, use_container_width=True)
                    
                    # Segment Bazlı Toptan
                    st.markdown("##### 📦 Ürün Bazlı Toptan Satış Detayı")
                    col_t1, col_t2, col_t3 = st.columns(3)
                    
                    with col_t1:
                        top_tuplu = df_viz.sort_values('Tüplü Ton', ascending=False).head(5)
                        st.plotly_chart(px.bar(top_tuplu, x='Şirket', y='Tüplü Ton', title="Toptan Tüplü Liderleri", color_discrete_sequence=['#FF9900']), use_container_width=True)
                    
                    with col_t2:
                        top_dokme = df_viz.sort_values('Dökme Ton', ascending=False).head(5)
                        st.plotly_chart(px.bar(top_dokme, x='Şirket', y='Dökme Ton', title="Toptan Dökme Liderleri", color_discrete_sequence=['#3366CC']), use_container_width=True)
                        
                    with col_t3:
                        top_oto = df_viz.sort_values('Otogaz Ton', ascending=False).head(5)
                        st.plotly_chart(px.bar(top_oto, x='Şirket', y='Otogaz Ton', title="Toptan Otogaz Liderleri", color_discrete_sequence=['#109618']), use_container_width=True)

                else:
                    st.warning("Toptan ticaret verisi bulunamadı.")
                
                st.markdown("---")

                # 3. BÖLÜM: GENEL SATIŞ DAĞILIMI (Tablo 3.5/3.6)
                st.markdown("#### 🏢 Dağıtıcı Bazlı Toplam Satışlar (Tablo 3.5/3.6)")
                if not df_genel_satis.empty:
                    son_t = df_genel_satis['Tarih'].max()
                    df_gs = df_genel_satis[df_genel_satis['Tarih'] == son_t].sort_values('Toplam Ton', ascending=False).head(20)
                    
                    fig_gs = px.bar(df_gs, x='Şirket', y=['Otogaz Ton', 'Tüplü Ton', 'Dökme Ton'], 
                                    title="Şirketlerin Toplam Satış Dağılımı",
                                    labels={'value': 'Ton', 'variable': 'Ürün'})
                    st.plotly_chart(fig_gs, use_container_width=True)
                else:
                    st.info("Genel satış dağılım tablosu bulunamadı.")
            
            # --- MEVCUT SEKMELER (DEĞİŞTİRİLMEDİ) ---
            with tab1:
                st.info(f"ℹ️ **Bilgi:** Sol menüdeki **Şehir ({secilen_sehir})** ve **Segment ({secilen_segment})** alanlarını değiştirerek bu sayfadaki analizleri güncelleyebilirsiniz.")
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
                    
                    fig = px.line(df_chart, x='Tarih', y=y_col, color='Şirket', markers=True,
                                  color_discrete_map=color_map, title=f"{secilen_sehir} - {secilen_segment} Trendi",
                                  hover_data={'Tarih': False, 'Tarih_Grafik': True})
                    unique_dates = sorted(df_chart['Tarih'].unique())
                    tick_texts = [format_tarih_grafik(pd.to_datetime(d)) for d in unique_dates]
                    fig.update_xaxes(tickvals=unique_dates, ticktext=tick_texts)
                    fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
                    fig.update_traces(patch={"line": {"width": 4}}, selector={"legendgroup": LIKITGAZ_NAME})
                    fig = grafik_bayram_ekle(fig, df_chart['Tarih'])
                    st.plotly_chart(fig, use_container_width=True)
                    
                st.markdown("---")
                st.subheader(f"📋 Dönemsel Sıralama ve Yıllık Karşılaştırma ({secilen_sehir} - {secilen_segment})")
                donemler = df_sehir_sirket.sort_values('Tarih', ascending=False)['Dönem'].unique()
                secilen_donem = st.selectbox("Dönem Seç:", donemler)
                row_ref = df_sehir_sirket[df_sehir_sirket['Dönem'] == secilen_donem].iloc[0]
                curr_date = row_ref['Tarih']
                prev_date = curr_date - relativedelta(years=1)
                prev_donem = format_tarih_tr(prev_date)
                col_ton = secilen_segment + " Ton"
                df_curr = df_sehir_sirket[df_sehir_sirket['Tarih'] == curr_date][['Şirket', col_ton, col_pay]]
                df_prev = df_sehir_sirket[df_sehir_sirket['Tarih'] == prev_date][['Şirket', col_ton, col_pay]]
                df_final = pd.merge(df_curr, df_prev, on='Şirket', how='left', suffixes=('', '_prev'))
                col_ton_prev_name = f"Ton ({prev_donem})"
                col_pay_prev_name = f"Pay ({prev_donem})"
                df_final.rename(columns={col_ton: f"Ton ({secilen_donem})", col_pay: f"Pay ({secilen_donem})", col_ton + '_prev': col_ton_prev_name, col_pay + '_prev': col_pay_prev_name}, inplace=True)
                df_final.fillna(0, inplace=True)
                df_final = df_final.sort_values(f"Pay ({secilen_donem})", ascending=False).reset_index(drop=True)
                df_final.index += 1
                st.dataframe(df_final.style.format({f"Ton ({secilen_donem})": "{:,.2f}", f"Pay ({secilen_donem})": "{:.2f}%", col_ton_prev_name: "{:,.2f}", col_pay_prev_name: "{:.2f}%"}), use_container_width=True)

            with tab2:
                st.subheader(f"💵 Dolar Kuru ve Pazar Hacmi İlişkisi ({secilen_sehir} - {secilen_segment})")
                st.caption(f"Sol menüden parametreleri değiştirerek ({secilen_sehir} - {secilen_segment}) analizi yapabilirsiniz.")
                if not DOLAR_MODULU_VAR:
                    st.warning("⚠️ 'yfinance' yüklü değil.")
                else:
                    col_ton = secilen_segment + " Ton"
                    df_sehir_toplam = df_sehir_sirket.groupby('Tarih')[col_ton].sum().reset_index()
                    df_sehir_toplam = df_sehir_toplam[df_sehir_toplam[col_ton] > 0.1]
                    
                    if not df_sehir_toplam.empty:
                        last_sales_date = df_sehir_toplam['Tarih'].max()
                        min_date = df_sehir_toplam['Tarih'].min()
                        df_dolar = dolar_verisi_getir(min_date)
                        
                        if not df_dolar.empty:
                            df_dolar = df_dolar[df_dolar['Tarih'] <= last_sales_date]
                            df_makro = pd.merge(df_sehir_toplam, df_dolar, on='Tarih', how='inner')
                            
                            fig_makro = go.Figure()
                            fig_makro.add_trace(go.Bar(x=df_makro['Tarih'], y=df_makro[col_ton], name='Pazar (Ton)', marker_color='#3366CC', opacity=0.6))
                            fig_makro.add_trace(go.Scatter(x=df_makro['Tarih'], y=df_makro['Dolar Kuru'], name='Dolar (TL)', yaxis='y2', line=dict(color='#DC3912', width=3)))
                            unique_dates_m = sorted(df_makro['Tarih'].unique())
                            tick_texts_m = [format_tarih_grafik(pd.to_datetime(d)) for d in unique_dates_m]
                            fig_makro.update_layout(title=f"{secilen_sehir} Hacim vs Dolar", yaxis=dict(title='Satış (Ton)'), yaxis2=dict(title='USD/TL', overlaying='y', side='right'), hovermode='x unified', legend=dict(orientation="h", y=1.1), xaxis=dict(tickvals=unique_dates_m, ticktext=tick_texts_m))
                            fig_makro = grafik_bayram_ekle(fig_makro, df_makro['Tarih'])
                            st.plotly_chart(fig_makro, use_container_width=True)
                        else: st.warning("Dolar verisi alınamadı.")
                    else: st.warning("Yeterli veri yok.")

            with tab3:
                col_ton = secilen_segment + " Ton"
                son_tarih = df_sehir_sirket['Tarih'].max()
                gecen_yil = son_tarih - relativedelta(years=1)
                
                st.subheader(f"🥊 Kazananlar ve Kaybedenler ({secilen_sehir} - {secilen_segment})")
                st.caption(f"{format_tarih_tr(gecen_yil)} ile {format_tarih_tr(son_tarih)} arasındaki Pazar Payı değişimi.")
                
                df_now = df_sehir_sirket[df_sehir_sirket['Tarih'] == son_tarih][['Şirket', col_pay]]
                df_old = df_sehir_sirket[df_sehir_sirket['Tarih'] == gecen_yil][['Şirket', col_pay]]
                
                if not df_now.empty and not df_old.empty:
                    df_diff = pd.merge(df_now, df_old, on='Şirket', how='inner', suffixes=('_now', '_old'))
                    df_diff['Fark'] = df_diff[col_pay + '_now'] - df_diff[col_pay + '_old']
                    df_diff = df_diff[df_diff['Fark'] != 0].sort_values('Fark', ascending=True)
                    df_diff['Renk'] = df_diff['Fark'].apply(lambda x: 'Kazanan' if x > 0 else 'Kaybeden')
                    color_map_w = {'Kazanan': '#2ECC71', 'Kaybeden': '#E74C3C'}
                    fig_diff = px.bar(df_diff, x='Fark', y='Şirket', orientation='h', color='Renk', color_discrete_map=color_map_w, title="Pazar Payı Değişimi (Puan)")
                    st.plotly_chart(fig_diff, use_container_width=True)
                else: st.warning("Yıllık kıyaslama için veri eksik.")
                
                st.markdown("---")
                st.subheader(f"🧮 Pazar Rekabet Yoğunluğu (HHI) - {secilen_sehir}")
                if not df_now.empty:
                    hhi_score = (df_now[col_pay] ** 2).sum()
                    fig_hhi = go.Figure(go.Indicator(mode = "gauge+number", value = hhi_score, domain = {'x': [0, 1], 'y': [0, 1]}, title = {'text': "HHI Skoru"}, gauge = {'axis': {'range': [0, 10000]}, 'bar': {'color': "black"}, 'steps': [{'range': [0, 1500], 'color': '#2ECC71'}, {'range': [1500, 2500], 'color': '#F1C40F'}, {'range': [2500, 10000], 'color': '#E74C3C'}]}))
                    c_hhi1, c_hhi2 = st.columns([1, 2])
                    with c_hhi1: st.plotly_chart(fig_hhi, use_container_width=True)
                    with c_hhi2:
                        st.markdown("""
                        #### 🧠 HHI (Herfindahl-Hirschman) Endeksi Nedir?
                        Bu metrik, bir pazarın ne kadar **rekabetçi** veya ne kadar **tekelleşmiş** olduğunu ölçen uluslararası bir standarttır.
                        
                        *   🟢 **< 1.500 (Düşük Yoğunluk):** **Rekabetçi Pazar.** Pazarda çok sayıda oyuncu var, hiçbir firma tek başına hakim değil. Pazara giriş kolaydır.
                        *   🟡 **1.500 - 2.500 (Orta Yoğunluk):** **Oligopol Eğilimi.** Pazar, birkaç büyük şirketin kontrolüne girmeye başlamış. Rekabet zorlaşıyor.
                        *   🔴 **> 2.500 (Yüksek Yoğunluk):** **Tekelleşmiş Pazar.** Pazarın hakimi 1 veya 2 şirkettir. Yeni oyuncuların barınması veya pazar payı çalması çok zordur.
                        
                        > **Stratejik Yorum:** HHI puanı arttıkça, o şehirdeki rekabet azalır ve büyük oyuncuların pazar gücü artar.
                        """)

            with tab4:
                col_ton = secilen_segment + " Ton"
                df_sehir_toplam = df_sehir_sirket.groupby('Tarih')[col_ton].sum().reset_index()
                
                df_likitgaz = df_sehir_sirket[df_sehir_sirket['Şirket'] == LIKITGAZ_NAME].sort_values('Tarih')
                
                col_m1, col_m2 = st.columns(2)
                with col_m1:
                    st.subheader(f"📅 Yıllara Göre Mevsimsel Döngü ({secilen_sehir})")
                    if not df_sehir_toplam.empty:
                        df_mevsim = df_sehir_toplam.copy()
                        df_mevsim['Yıl'] = df_mevsim['Tarih'].dt.year.astype(str)
                        df_mevsim['Ay_No'] = df_mevsim['Tarih'].dt.month
                        df_mevsim['Ay_Isim'] = df_mevsim['Ay_No'].apply(lambda x: TR_AYLAR[x])
                        df_mevsim = df_mevsim.sort_values(['Yıl', 'Ay_No'])
                        fig_cycle = px.line(df_mevsim, x='Ay_Isim', y=col_ton, color='Yıl', markers=True, title=f"{secilen_sehir} Satış Döngüsü")
                        st.plotly_chart(fig_cycle, use_container_width=True)
                        
                with col_m2:
                    st.subheader(f"🔮 {secilen_sehir} - {secilen_segment} 1 Yıllık Tahmin")
                    if len(df_sehir_toplam) > 12:
                        last_date = df_sehir_toplam['Tarih'].max()
                        forecast_data = []
                        
                        for i in range(1, 13):
                            next_date = last_date + relativedelta(months=i)
                            prev_year_date = next_date - relativedelta(years=1)
                            
                            mask = (df_sehir_toplam['Tarih'].dt.year == prev_year_date.year) & (df_sehir_toplam['Tarih'].dt.month == prev_year_date.month)
                            past_val_row = df_sehir_toplam[mask]
                            if not past_val_row.empty: val_prev_year = past_val_row[col_ton].values[0]
                            else:
                                mask_all_years = (df_sehir_toplam['Tarih'].dt.month == next_date.month)
                                val_prev_year = df_sehir_toplam.loc[mask_all_years, col_ton].mean()
                            
                            trend_val = df_sehir_toplam.tail(3)[col_ton].mean()
                            if val_prev_year > 0: forecast_val = (val_prev_year * 0.6) + (trend_val * 0.4)
                            else: forecast_val = trend_val
                            
                            likit_forecast = 0
                            if not df_likitgaz.empty:
                                mask_likit = (df_likitgaz['Tarih'].dt.year == prev_year_date.year) & (df_likitgaz['Tarih'].dt.month == prev_year_date.month)
                                past_row_likit = df_likitgaz[mask_likit]
                                if not past_row_likit.empty: val_prev_likit = past_row_likit[col_ton].values[0]
                                else: 
                                    mask_all_likit = (df_likitgaz['Tarih'].dt.month == next_date.month)
                                    val_prev_likit = df_likitgaz.loc[mask_all_likit, col_ton].mean()
                                    if pd.isna(val_prev_likit): val_prev_likit = 0
                                
                                if len(df_likitgaz) >= 3:
                                    trend_likit = df_likitgaz.tail(3)[col_ton].mean()
                                else:
                                    trend_likit = df_likitgaz[col_ton].mean()
                                
                                if val_prev_likit > 0: likit_forecast = (val_prev_likit * 0.6) + (trend_likit * 0.4)
                                else: likit_forecast = trend_likit

                            forecast_data.append({
                                'Tarih': format_tarih_tr(next_date),
                                'Pazar Tahmin (Ton)': forecast_val,
                                'Likitgaz Tahmin (Ton)': likit_forecast
                            })
                            
                        st.table(pd.DataFrame(forecast_data).style.format({'Pazar Tahmin (Ton)': '{:,.0f}', 'Likitgaz Tahmin (Ton)': '{:,.0f}'}))
                        st.markdown("""
                        > **ℹ️ Nasıl Hesaplandı?**
                        > Bu tahminler, geçmiş verilerin istatistiksel analizine dayanır.
                        > **Formül:** %60 Mevsimsellik (Geçen yılın aynı ayı) + %40 Trend (Son 3 ayın ortalaması).
                        > *Bu sayede hem kış/yaz döngüsü hem de şirketin son dönemdeki büyüme/küçülme ivmesi hesaba katılır.*
                        """)
                    else: st.warning("Yetersiz veri.")

            with tab5:
                st.info("ℹ️ **Bilgilendirme:** Bu sayfadaki tüm analizler, sol menüde seçtiğiniz **Şehir** ve **Segment** kriterlerine göre otomatik oluşturulur.")
                sirketler_listesi = sorted(df_sehir_sirket['Şirket'].unique())
                varsayilan_index = sirketler_listesi.index(LIKITGAZ_NAME) if LIKITGAZ_NAME in sirketler_listesi else 0
                secilen_odak_sirket = st.selectbox("🔎 Analiz Edilecek Dağıtıcı Seçiniz:", sirketler_listesi, index=varsayilan_index)
                st.markdown("---")
                if not df_turkiye.empty:
                    tr_rapor = turkiye_pazar_analizi(df_turkiye, secilen_segment)
                    st.info("🇹🇷 Türkiye Geneli Özet Bilgi (Resmi Veri)")
                    for l in tr_rapor: st.markdown(l)
                    st.markdown("---")
                    if not df_turkiye_sirket.empty:
                        odak_tr_rapor = sirket_turkiye_analizi(df_turkiye_sirket, secilen_segment, secilen_odak_sirket)
                        if len(odak_tr_rapor) > 1:
                             for l in odak_tr_rapor: st.markdown(l)
                st.markdown("---")
                if not df_iller.empty:
                    p_txt, s_txt, r_txt = stratejik_analiz_raporu(df_sehir_sirket, df_iller, secilen_sehir, secilen_segment, secilen_odak_sirket)
                    for l in p_txt: st.markdown(l)
                    c1, c2 = st.columns(2)
                    with c1:
                        for l in s_txt: st.markdown(l)
                    with c2:
                        for l in r_txt:
                            if "🛑" in l or "🔴" in l: st.error(l)
                            elif "🔥" in l or "🟢" in l: st.success(l)
                            elif "📉" in l or "🟠" in l: st.warning(l)
                            else: st.info(l)
                else: st.error("İl verileri eksik.")
