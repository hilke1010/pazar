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

@st.cache_data(ttl="2h") 
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

# --- ANALİZ MOTORLARI ---
def turkiye_pazar_analizi(df_turkiye_resmi, segment):
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
    
    if ton_gecen_ay > 0:
        fark = ton_simdi - ton_gecen_ay
        yuzde = (fark / ton_gecen_ay) * 100
        durum = "büyüyerek" if yuzde > 0 else "küçülerek"
        rapor.append(f"- **Aylık:** Geçen aya göre pazar **%{abs(yuzde):.1f}** oranında {durum} **{abs(fark):,.0f} ton** fark oluşturdu.")
        
    if ton_gecen_yil > 0:
        fark_yil = ton_simdi - ton_gecen_yil
        yuzde_yil = (fark_yil / ton_gecen_yil) * 100
        durum_yil = "büyüme" if yuzde_yil > 0 else "daralma"
        rapor.append(f"- **Yıllık:** Geçen yılın aynı ayına göre **%{abs(yuzde_yil):.1f}** oranında {durum_yil} var. (Geçen Yıl: **{ton_gecen_yil:,.0f} ton**)")
    
    rapor.append(f"> **💡 Analist Notu:** {segment} pazarında yıllık bazda {ton_gecen_yil:,.0f} tondan {ton_simdi:,.0f} tona gelindi.")
    return rapor

def sirket_turkiye_analizi(df_turkiye_sirketler, segment, odak_sirket):
    if df_turkiye_sirketler.empty or 'Şirket' not in df_turkiye_sirketler.columns:
        return [f"⚠️ {odak_sirket} için Türkiye geneli (Tablo 3.7) verisi okunamadı."]
    col_ton = segment + " Ton"
    df_odak = df_turkiye_sirketler[df_turkiye_sirketler['Şirket'] == odak_sirket]
    if df_odak.empty: return [f"{odak_sirket} için Tablo 3.7'de (Ulusal Veri) kayıt bulunamadı."]
    
    toplamlar = df_odak.groupby('Tarih')[col_ton].sum()
    son_tarih = df_turkiye_sirketler['Tarih'].max()
    onceki_ay = son_tarih - relativedelta(months=1)
    gecen_yil = son_tarih - relativedelta(years=1)
    
    ton_simdi = toplamlar.get(son_tarih, 0)
    ton_gecen_ay = toplamlar.get(onceki_ay, 0)
    ton_gecen_yil = toplamlar.get(gecen_yil, 0)
    
    rapor = []
    rapor.append(f"### 🏢 {odak_sirket} TÜRKİYE GENELİ RAPORU")
    rapor.append(f"EPDK Tablo 3.7 (Resmi Veri)'ye göre {odak_sirket}, bu ay Türkiye genelinde **{ton_simdi:,.0f} ton** {segment} satışı gerçekleştirdi.")
    
    if ton_gecen_ay > 0:
        yuzde_ay = ((ton_simdi - ton_gecen_ay) / ton_gecen_ay) * 100
        icon_ay = "📈" if yuzde_ay > 0 else "📉"
        rapor.append(f"- **Aylık Performans:** {icon_ay} Geçen aya göre **%{yuzde_ay:+.1f}** değişim var. (Geçen Ay: {ton_gecen_ay:,.0f} ton)")

    if ton_gecen_yil > 0:
        yuzde_yil = ((ton_simdi - ton_gecen_yil) / ton_gecen_yil) * 100
        icon = "🚀" if yuzde_yil > 0 else "🔻"
        rapor.append(f"- **Yıllık Performans:** {icon} Geçen yılın aynı ayına göre **%{yuzde_yil:+.1f}** değişim var. (Geçen Sene: **{ton_gecen_yil:,.0f} ton**)")
    
    return rapor

def stratejik_analiz_raporu(df_sirket, df_iller, sehir, segment, odak_sirket):
    col_pay = segment + " Pay"
    col_ton_il = segment + " Ton"
    col_ton_sirket = segment + " Ton"
    
    # --- ŞEHİR BAZLI SON TARİH BULMA ---
    df_sehir_resmi = df_iller[df_iller['Şehir'].str.upper() == sehir.upper()].sort_values('Tarih')
    
    if df_sehir_resmi.empty or df_sehir_resmi[col_ton_il].sum() == 0:
        son_tarih = df_sirket['Tarih'].max()
    else:
        son_tarih = df_sehir_resmi[df_sehir_resmi[col_ton_il] > 0]['Tarih'].max()
        
    son_donem_str = format_tarih_tr(son_tarih)
    
    pazar_raporu = []
    sirket_raporu = []
    rakip_raporu = []

    # 1. ŞEHİR PAZAR BÜYÜKLÜĞÜ ANALİZİ
    try:
        if not df_sehir_resmi.empty:
            ton_simdi = df_sehir_resmi[df_sehir_resmi['Tarih'] == son_tarih][col_ton_il].sum()
            
            onceki_ay_date = son_tarih - relativedelta(months=1)
            ton_onceki_ay = df_sehir_resmi[df_sehir_resmi['Tarih'] == onceki_ay_date][col_ton_il].sum()
            
            gecen_yil_date = son_tarih - relativedelta(years=1)
            ton_gecen_yil = df_sehir_resmi[df_sehir_resmi['Tarih'] == gecen_yil_date][col_ton_il].sum()
            
            pazar_raporu.append(f"### 🌍 {sehir} - {segment} Pazar Durumu ({son_donem_str})")
            pazar_raporu.append(f"Bu ay toplam **{ton_simdi:,.0f} ton** satış gerçekleşti.")
            
            if ton_onceki_ay > 0:
                pazar_buyume_ay = ((ton_simdi - ton_onceki_ay) / ton_onceki_ay) * 100
                icon_ay = "📈" if pazar_buyume_ay > 0 else "📉"
                pazar_raporu.append(f"- **Aylık:** {icon_ay} Geçen ay **{ton_onceki_ay:,.0f} ton** olan pazar, **%{pazar_buyume_ay:.1f}** değişimle bu seviyeye geldi.")

            if ton_gecen_yil > 0:
                pazar_buyume_yil = ((ton_simdi - ton_gecen_yil) / ton_gecen_yil) * 100
                icon_yil = "🚀" if pazar_buyume_yil > 0 else "🔻"
                pazar_raporu.append(f"- **Yıllık:** {icon_yil} Geçen sene **{ton_gecen_yil:,.0f} ton** olan pazar, bu sene **%{pazar_buyume_yil:.1f}** değişimle **{ton_simdi:,.0f} ton** oldu.")
            
        else:
            pazar_raporu.append("Şehir pazar verisi hesaplanamadı.")
    except:
        pazar_raporu.append("Pazar verisi hatası.")
    pazar_raporu.append("---")

    # 2. DETAYLI ŞİRKET ANALİZİ
    sirket_raporu.append(f"### 📊 {odak_sirket} Performans Detayı")
    
    df_odak = df_sirket[(df_sirket['Şirket'] == odak_sirket) & (df_sirket['Şehir'] == sehir)].sort_values('Tarih')
    
    if not df_odak.empty:
        df_odak = df_odak[df_odak['Tarih'] <= son_tarih]
        for i in range(len(df_odak)):
            if i == 0: continue
            
            curr = df_odak.iloc[i]
            prev = df_odak.iloc[i-1]
            curr_date = curr['Tarih']
            tarih_str = format_tarih_tr(curr_date)
            
            sirket_ton_curr = curr[col_ton_sirket]
            sirket_ton_prev = prev[col_ton_sirket]
            sirket_pay_curr = curr[col_pay]
            
            pazar_buyume_aylik = 0
            try:
                p_curr = df_sehir_resmi[df_sehir_resmi['Tarih'] == curr_date][col_ton_il].sum()
                p_prev = df_sehir_resmi[df_sehir_resmi['Tarih'] == prev['Tarih']][col_ton_il].sum()
                if p_prev > 0: pazar_buyume_aylik = ((p_curr - p_prev) / p_prev) * 100
            except: pass

            sirket_buyume_aylik = 0
            if sirket_ton_prev > 0: 
                sirket_buyume_aylik = ((sirket_ton_curr - sirket_ton_prev) / sirket_ton_prev) * 100
            
            gy_tarih = curr_date - relativedelta(years=1)
            row_gy = df_odak[df_odak['Tarih'] == gy_tarih]
            sirket_buyume_yillik = 0
            gy_ton = 0
            has_gy = False
            
            if not row_gy.empty:
                has_gy = True
                gy_ton = row_gy.iloc[0][col_ton_sirket]
                if gy_ton > 0:
                    sirket_buyume_yillik = ((sirket_ton_curr - gy_ton) / gy_ton) * 100

            yorum = ""
            icon = "➡️"
            aylik_yorum = ""
            if sirket_buyume_aylik > 0 and pazar_buyume_aylik > 0:
                if sirket_buyume_aylik > pazar_buyume_aylik:
                    icon = "🚀"
                    aylik_yorum = f"**Mükemmel.** Pazar aylık %{pazar_buyume_aylik:.1f} büyürken, biz **%{sirket_buyume_aylik:.1f}** büyüdük."
                else:
                    icon = "⚠️"
                    aylik_yorum = f"**Yetersiz.** Satış %{sirket_buyume_aylik:.1f} arttı ama pazar %{pazar_buyume_aylik:.1f} büyüdüğü için geride kaldık."
            elif sirket_buyume_aylik > 0 and pazar_buyume_aylik < 0:
                icon = "⭐"
                aylik_yorum = f"**Ayrışma.** Pazar %{abs(pazar_buyume_aylik):.1f} daralırken, satışları **%{sirket_buyume_aylik:.1f}** artırdık."
            elif sirket_buyume_aylik < 0 and pazar_buyume_aylik < 0:
                icon = "🛡️" if abs(sirket_buyume_aylik) < abs(pazar_buyume_aylik) else "🔻"
                aylik_yorum = f"**Negatif.** Pazarla birlikte küçülme var."
            else:
                aylik_yorum = f"Satışlar aylık %{sirket_buyume_aylik:.1f} değişti."

            yillik_yorum = ""
            if has_gy:
                if sirket_buyume_yillik > 0:
                    yillik_yorum = f" Geçen yılın aynı ayına göre **%{sirket_buyume_yillik:.1f}** büyüme var (Geçen yıl: {gy_ton:,.0f} ton)."
                else:
                    yillik_yorum = f" Geçen yılın aynı ayına göre **%{abs(sirket_buyume_yillik):.1f}** düşüş var."

            sirket_raporu.append(f"{icon} **{tarih_str}:** Pay: %{sirket_pay_curr:.2f} | Satış: {sirket_ton_curr:,.0f} ton | {aylik_yorum}{yillik_yorum}")
    else:
        sirket_raporu.append("Şirket verisi bulunamadı.")

    # 3. DETAYLI RAKİP TREND ANALİZİ
    rakip_raporu.append(f"### 📡 Rakip Trend Dedektörü ({sehir})")
    df_sehir_sirket = df_sirket[df_sirket['Şehir'] == sehir]
    df_sehir_sirket = df_sehir_sirket[df_sehir_sirket['Tarih'] <= son_tarih]
    
    son_df = df_sehir_sirket[df_sehir_sirket['Tarih'] == son_tarih].sort_values(col_pay, ascending=False)
    rakipler = son_df[(son_df['Şirket'] != odak_sirket) & (son_df[col_pay] > 2.0)].head(6)['Şirket'].tolist()
    
    yakalanan_trend = 0
    for rakip in rakipler:
        df_rakip = df_sehir_sirket[df_sehir_sirket['Şirket'] == rakip].sort_values('Tarih').tail(10)
        if len(df_rakip) < 3: continue
        paylar = df_rakip[col_pay].values
        tarihler = df_rakip['Dönem'].values
        
        trend_tipi = "yok"
        seri_uzunlugu = 0
        
        if paylar[-1] < paylar[-2]:
            trend_tipi = "azalis"
            for i in range(len(paylar)-1, 0, -1):
                if paylar[i] < paylar[i-1]: seri_uzunlugu += 1
                else: break
        elif paylar[-1] > paylar[-2]:
            trend_tipi = "artis"
            for i in range(len(paylar)-1, 0, -1):
                if paylar[i] > paylar[i-1]: seri_uzunlugu += 1
                else: break

        if trend_tipi == "azalis" and seri_uzunlugu >= 3:
            baslangic = tarihler[-(seri_uzunlugu+1)]
            toplam_kayip = paylar[-(seri_uzunlugu+1)] - paylar[-1]
            rakip_raporu.append(f"📉 **{rakip}:** Düşüş trendinde. **{seri_uzunlugu} aydır** düşüyor ({baslangic}'dan beri). (Kayıp: -{toplam_kayip:.2f})")
            yakalanan_trend += 1
        elif trend_tipi == "artis" and seri_uzunlugu >= 3:
            baslangic = tarihler[-(seri_uzunlugu+1)]
            toplam_kazanc = paylar[-1] - paylar[-(seri_uzunlugu+1)]
            rakip_raporu.append(f"📈 **{rakip}:** Yükseliş trendinde. **{seri_uzunlugu} aydır** artırıyor ({baslangic}'dan beri). (Kazanç: +{toplam_kazanc:.2f})")
            yakalanan_trend += 1
        else:
            son_fark = paylar[-1] - paylar[-2]
            if son_fark > 1.5:
                 rakip_raporu.append(f"🔥 **{rakip}:** Son ayda agresif bir atak yaptı (+{son_fark:.2f}).")
                 yakalanan_trend += 1
            elif son_fark < -1.5:
                 rakip_raporu.append(f"🔻 **{rakip}:** Son ayda sert bir kayıp yaşadı ({son_fark:.2f}).")
                 yakalanan_trend += 1
    if yakalanan_trend == 0:
        rakip_raporu.append("✅ Rakiplerde şu an belirgin bir uzun vadeli trend veya şok hareket görülmüyor.")

    return pazar_raporu, sirket_raporu, rakip_raporu

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
        # Hugging Face için 16GB limit, normal için 1024
        ram_limit = 16384.0 
        
        st.metric("Şu anki RAM (Boşta)", f"{ram_now:.0f} MB")
        
        if st.button("🚀 ANALİZİ BAŞLAT", type="primary", use_container_width=True):
            st.session_state['analiz_basladi'] = True
            st.rerun()
    st.stop() # Kodun geri kalanını çalıştırma

# =========================================================
# ANALİZ EKRANI (Veri Yüklendikten Sonra)
# =========================================================

# SADECE ANALİZ BAŞLADIYSA VERİLERİ OKU
with st.spinner('Veriler taranıyor... (Ortalama 2 dakika sürüyor, lütfen bekleyin)'):
    df_sirket, df_iller, df_turkiye, df_turkiye_sirket = verileri_oku()

# SOL MENÜ RAM
st.sidebar.title("Kontrol Paneli")
ram_now = get_total_ram_usage()
ram_limit = 16384.0 # Hugging Face için 16GB ayarlı

# RAM RENK AYARI
if ram_now < 10000: color = "green"; msg = "✅ Güvenli"
elif ram_now < 14000: color = "orange"; msg = "⚠️ Sınırda"
else: color = "red"; msg = "🛑 KRİTİK"

st.sidebar.markdown(f"### RAM: :{color}[{ram_now:.0f} MB]")
st.sidebar.progress(min(ram_now/ram_limit, 1.0))
st.sidebar.caption(msg)
st.sidebar.markdown("---")

# --- ANA İÇERİK ---
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
        st.error("⚠️ **SİSTEM UYARISI:** Adana ili geçici olarak kapalıdır.")
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
             col_ton = secilen_segment + " Ton"
             son_tarih = df_sehir_sirket['Tarih'].max()
             gecen_yil = son_tarih - relativedelta(years=1)
             st.subheader(f"🥊 Kazananlar ve Kaybedenler ({secilen_sehir} - {secilen_segment})")
             df_now = df_sehir_sirket[df_sehir_sirket['Tarih'] == son_tarih][['Şirket', col_pay]]
             df_old = df_sehir_sirket[df_sehir_sirket['Tarih'] == gecen_yil][['Şirket', col_pay]]
             if not df_now.empty and not df_old.empty:
                 df_diff = pd.merge(df_now, df_old, on='Şirket', how='inner', suffixes=('_now', '_old'))
                 df_diff['Fark'] = df_diff[col_pay + '_now'] - df_diff[col_pay + '_old']
                 df_diff = df_diff[df_diff['Fark'] != 0].sort_values('Fark', ascending=True)
                 df_diff['Renk'] = df_diff['Fark'].apply(lambda x: 'Kazanan' if x > 0 else 'Kaybeden')
                 color_map_w = {'Kazanan': '#2ECC71', 'Kaybeden': '#E74C3C'}
                 fig_diff = px.bar(df_diff, x='Fark', y='Şirket', orientation='h', color='Renk', color_discrete_map=color_map_w)
                 st.plotly_chart(fig_diff, use_container_width=True)
             else: st.warning("Yıllık kıyaslama verisi yok.")

        with tab4: # Mevsimsellik
             col_ton = secilen_segment + " Ton"
             df_sehir_toplam = df_sehir_sirket.groupby('Tarih')[col_ton].sum().reset_index()
             if not df_sehir_toplam.empty:
                 df_mevsim = df_sehir_toplam.copy()
                 df_mevsim['Yıl'] = df_mevsim['Tarih'].dt.year.astype(str)
                 df_mevsim['Ay_No'] = df_mevsim['Tarih'].dt.month
                 df_mevsim['Ay_Isim'] = df_mevsim['Ay_No'].apply(lambda x: TR_AYLAR[x])
                 df_mevsim = df_mevsim.sort_values(['Yıl', 'Ay_No'])
                 fig_cycle = px.line(df_mevsim, x='Ay_Isim', y=col_ton, color='Yıl', markers=True)
                 st.plotly_chart(fig_cycle, use_container_width=True)

        with tab5: # Rapor
             sirketler_listesi = sorted(df_sehir_sirket['Şirket'].unique())
             varsayilan_index = sirketler_listesi.index(LIKITGAZ_NAME) if LIKITGAZ_NAME in sirketler_listesi else 0
             secilen_odak_sirket = st.selectbox("Analiz Edilecek Dağıtıcı:", sirketler_listesi, index=varsayilan_index)
             if not df_iller.empty:
                 p_txt, s_txt, r_txt = stratejik_analiz_raporu(df_sehir_sirket, df_iller, secilen_sehir, secilen_segment, secilen_odak_sirket)
                 for l in p_txt: st.markdown(l)
                 c1, c2 = st.columns(2)
                 with c1: 
                    for l in s_txt: st.markdown(l)
                 with c2: 
                    for l in r_txt: st.info(l)
