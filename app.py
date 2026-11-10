import streamlit as st
import pandas as pd
import os
import gc
import psutil
from difflib import SequenceMatcher
import plotly.express as px
import plotly.graph_objects as go
import re
from dateutil.relativedelta import relativedelta
import datetime
import unicodedata
from pathlib import Path
import numpy as np 

# --- GÜVENLİ IMPORT ---
try:
    import yfinance as yf
    DOLAR_MODULU_VAR = True
except ImportError:
    DOLAR_MODULU_VAR = False
# ----------------------

# --- AYARLAR ---
DOSYA_KLASORU = Path(__file__).resolve().parent / 'raporlar'
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

STOP_WORDS = [
    "A.Ş", "A.S", "A.Ş.", "LTD", "ŞTİ", "STI", "SAN", "VE", "TİC", "TIC", 
    "PETROL", "ÜRÜNLERİ", "URUNLERI", "DAĞITIM", "DAGITIM", "GAZ", "LPG", 
    "AKARYAKIT", "ENERJİ", "ENERJI", "NAKLİYE", "NAKLIYE", "İNŞAAT", "INSAAT",
    "PAZARLAMA", "DEPOLAMA", "TURİZM", "TURIZM", "SANAYİ", "SANAYI"
]

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

def dosya_isminden_tarih(filename):
    base = os.path.splitext(filename)[0].lower().replace('ş','s').replace('ı','i').replace('ğ','g').replace('ü','u').replace('ö','o').replace('ç','c')
    match = re.match(r"([a-z]+)(\d{2})", base)
    if match:
        ay, yil = match.groups()
        if ay in DOSYA_AY_MAP: return pd.Timestamp(year=2000+int(yil), month=DOSYA_AY_MAP[ay], day=1)
    return None

def sayi_temizle(value):
    """Excel numeric cells and Turkish-style number strings to float."""
    if value is None or isinstance(value, bool):
        return 0.0
    if isinstance(value, (int, float, np.number)):
        n = float(value)
        return n if np.isfinite(n) else 0.0
    s = str(value).strip().replace('\u00a0', '').replace(' ', '').replace('%', '')
    if s in ('', '-', '—', '–'):
        return 0.0
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def isim_anahtari(isim):
    """Normalize Turkish legal company suffixes without conflating product/company names."""
    txt = str(isim or '').upper().replace('İ', 'I').replace('ı', 'I')
    txt = ''.join(c for c in unicodedata.normalize('NFKD', txt)
                  if not unicodedata.combining(c))
    txt = re.sub(r'[^A-Z0-9]+', ' ', txt)
    legal = {'ANONIM', 'SIRKETI', 'SIRKET', 'A', 'S', 'AS', 'LTD', 'LIMITED', 'STI'}
    return ' '.join(k for k in txt.split() if k not in legal)

def ismi_temizle_kok(isim):
    return isim_anahtari(isim)


def sirket_ismi_standartlastir(ham_isim, mevcut_isimler):
    raw = str(ham_isim or '').strip()
    if not raw:
        return ''
    key = isim_anahtari(raw)
    # High-confidence aliases from the original application.
    for label, canonical in OZEL_DUZELTMELER.items():
        label_key = isim_anahtari(label)
        if key == label_key or key.startswith(label_key + ' '):
            return canonical
    if mevcut_isimler:
        names = sorted(mevcut_isimler)
        exact = {isim_anahtari(s): s for s in names}
        if key in exact:
            return exact[key]
        scores = sorted(((SequenceMatcher(None, key, isim_anahtari(s)).ratio(), s)
                         for s in names), reverse=True)
        if scores and scores[0][0] >= .94 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= .04):
            return scores[0][1]
    return raw

def sehir_ismi_duzelt(sehir):
    if not sehir: return ""
    return sehir.replace('İ', 'i').replace('I', 'ı').title()

def highlight_val(val):
    if isinstance(val, (int, float)):
        color = 'green' if val > 0 else 'red' if val < 0 else 'black'
        weight = 'bold'
        return f'color: {color}; font-weight: {weight}'
    return ''

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
    
    analist_yorumu = ""
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

# --- EXCEL VERİ OKUMA / DOĞRULAMA ---
# Klasörde: Ocak26.xlsx, Subat26.xlsx, Mart25.xlsx, ...
# EPDK Ocak26 örneğinde il bazlı tablo TABLO 13, toptan satış TABLO 14'tür.

TABLO_RE = re.compile(r'^\s*Tablo\s+(\d{1,2})\s*:', re.IGNORECASE)
TON_KOLONLARI = ['Tüplü Ton', 'Dökme Ton', 'Otogaz Ton']
PAY_KOLONLARI = ['Tüplü Pay', 'Dökme Pay', 'Otogaz Pay']
SIRKET_KOLONLARI = ['Tarih', 'Şehir', 'Şirket', *TON_KOLONLARI, *PAY_KOLONLARI]


def aylik_excel_imzasi():
    """Changed/added XLSX files invalidate Streamlit's data cache automatically."""
    if not DOSYA_KLASORU.exists():
        return (), []
    bulunan, atlanan = {}, []
    for path in DOSYA_KLASORU.iterdir():
        if not path.is_file() or path.suffix.lower() != '.xlsx' or path.name.startswith('~$'):
            continue
        tarih = dosya_isminden_tarih(path.name)
        if tarih is None:
            atlanan.append(f'{path.name}: isim Ocak26.xlsx biçiminde değil')
            continue
        key = (tarih.year, tarih.month)
        if key in bulunan:
            eski = bulunan[key]
            yeni = path if path.stat().st_mtime_ns > eski.stat().st_mtime_ns else eski
            bulunan[key] = yeni
            atlanan.append(f'{tarih:%Y-%m}: aynı aya ait birden fazla dosya var; {yeni.name} kullanıldı')
        else:
            bulunan[key] = path
    imza = tuple((p.name, p.stat().st_mtime_ns, p.stat().st_size)
                 for _, p in sorted(bulunan.items()))
    return imza, atlanan


def normalize_baslik(value):
    """EPDK başlıklarında Türkçe karakter/boşluk/noktalama farklarını giderir."""
    text = str(value or '').strip().casefold().replace('ı', 'i')
    text = ''.join(c for c in unicodedata.normalize('NFKD', text)
                   if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', text).strip().upper()


def sayi_hucresi_mi(value):
    """Excel sayıları, metin biçiminde kaydedilmiş Türkçe sayılar ve sıfırları kabul eder."""
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, (int, float, np.number)):
        return bool(np.isfinite(value))
    s = str(value).replace('\u00a0', '').strip().replace(' ', '').replace('%', '')
    return bool(re.fullmatch(r'[+-]?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?|[+-]?\d+\.\d+', s))


def table_content_type(rows):
    """Tablonun gerçek türünü başlığı + sütun isimlerinden belirle (numaradan bağımsız)."""
    head = ' '.join(normalize_baslik(c) for row in rows[:16]
                    for c in row if isinstance(c, str) and c.strip())
    if ('IL ADI' in head and 'LISANS' in head and 'SATIS' in head) or ('81 IL BAZINDA' in head and 'LPG SATIS' in head):
        return 13
    if ('DAGITICILAR ARASI TOPTAN' in head or
            'SATIS YAPAN LISANS' in head) and ('SATIS' in head or 'OTOGAZ' in head):
        return 14
    if 'URUN TURU' in head and 'DEGISIM' in head and 'LISANS' in head:
        return 12
    if 'DAGITICI VE URUN TURUNE GORE' in head and 'SATIS' in head:
        return 11
    return None


def tablolari_ayir(sayfalar):
    """Sayfa adı değişse de Excel içindeki 1–14 numaralı tabloları bulur.

    Başlık sadece 'Tablo 13' şeklindeyse, A/B sütunu dışındaysa veya çalışma
    sayfasında hiç başlık yoksa sayfa adındaki tablo numarası kullanılır.
    """
    arsiv = {}
    baslik_re = re.compile(r'\btablo\s*[-_.#]*\s*(\d{1,2})\b', re.I)
    for sheet_name, sheet_rows in sayfalar.items():
        if 'ICINDEKILER' in normalize_baslik(sheet_name).replace(' ', ''):
            continue
        current, bolum = None, []
        had_title = False
        # Excel içinde birbirini izleyen birden fazla tablo bulunabilir.
        for row in sheet_rows:
            heading_num = None
            for c in row[:min(len(row), 12)]:
                if not isinstance(c, str):
                    continue
                m = baslik_re.search(normalize_baslik(c))
                if m:
                    heading_num = int(m.group(1))
                    break
            if heading_num is not None and 1 <= heading_num <= 50:
                if bolum and current is not None:
                    arsiv.setdefault(current, []).extend(bolum)
                current, bolum = heading_num, []
                had_title = True
            if current is not None:
                bolum.append(tuple(row))
        if had_title:
            if bolum and current is not None:
                arsiv.setdefault(current, []).extend(bolum)
            continue
        # İndirilen bazı dosyalarda başlık hücresi yok; sekme adına bak.
        matches = [int(n) for n in baslik_re.findall(normalize_baslik(sheet_name))]
        if len(matches) == 1:
            arsiv.setdefault(matches[0], []).extend(tuple(r) for r in sheet_rows)
            continue
        # Sekme adı da yeniden adlandırılmışsa içerik ve kolon imzalarına bak.
        typ = table_content_type(sheet_rows)
        if typ is None and 'TOPTAN' in normalize_baslik(sheet_name):
            typ = 14
        if typ is None and 'IL BAZINDA' in normalize_baslik(sheet_name):
            typ = 13
        if typ is not None:
            arsiv.setdefault(typ, []).extend(tuple(r) for r in sheet_rows)
    return {no: rows for no, rows in arsiv.items() if rows}


def tabloyu_bul(arsiv, kind):
    """Önce içerik imzasını, ardından numara eşleşmesini kullanır."""
    for number, rows in arsiv.items():
        if table_content_type(rows) == kind:
            return rows, number
    return arsiv.get(kind, []), kind


def tablo_teşhis_notu(sayfalar, arsiv, kind):
    pages = ', '.join(str(n) for n in sorted(arsiv)) or 'hiçbiri'
    candidate = []
    for name, rows in sayfalar.items():
        first = ' '.join(normalize_baslik(c) for r in rows[:8]
                         for c in r if isinstance(c, str))
        if ('13' in normalize_baslik(name) or '14' in normalize_baslik(name) or
                'IL BAZINDA' in first or 'TOPTAN' in first):
            candidate.append(f'{name} ({len(rows)} satır)')
    return (f'Bulunan tablo numaraları: {pages}. '
            f'Aday sekmeler: {", ".join(candidate[:7]) or "; ".join(sayfalar.keys())[:280]}. '
            'Kaynak dosyanın tablo yapısı kontrol edilmeli.')


def tablo_satirlari(arsiv, no):
    rows = arsiv.get(no, [])
    # Title followed by one or two nested header lines. Data begins after them.
    return rows


def parse_tablo_11(rows, tarih, sirket_listesi):
    national, totals = [], None
    for r in rows:
        if not r: continue
        isim = str(r[0] or '').strip()
        if not isim or isim.upper().startswith('TABLO') or 'LİSANS SAHİB' in isim.upper():
            continue
        if len(r) < 9 or not isinstance(r[1], (int, float, np.number)):
            continue
        v = [sayi_temizle(r[j]) for j in (1, 2, 3, 4, 5, 6)]
        if isim.upper() == 'TOPLAM':
            totals = {'Tarih': tarih, 'Tüplü Ton': v[0],
                      'Dökme Ton': v[2], 'Otogaz Ton': v[4]}
            continue
        std = sirket_ismi_standartlastir(isim, sirket_listesi)
        sirket_listesi.add(std)
        national.append({'Tarih': tarih, 'Şirket': std,
                         'Tüplü Ton': v[0], 'Tüplü Pay': v[1],
                         'Dökme Ton': v[2], 'Dökme Pay': v[3],
                         'Otogaz Ton': v[4], 'Otogaz Pay': v[5]})
    return national, totals


IL_ISIMLERI = {normalize_baslik(n): n for n in ['Adana', 'Adıyaman', 'Afyonkarahisar', 'Ağrı', 'Aksaray', 'Amasya', 'Ankara', 'Antalya', 'Ardahan', 'Artvin', 'Aydın', 'Balıkesir', 'Bartın', 'Batman', 'Bayburt', 'Bilecik', 'Bingöl', 'Bitlis', 'Bolu', 'Burdur', 'Bursa', 'Çanakkale', 'Çankırı', 'Çorum', 'Denizli', 'Diyarbakır', 'Düzce', 'Edirne', 'Elazığ', 'Erzincan', 'Erzurum', 'Eskişehir', 'Gaziantep', 'Giresun', 'Gümüşhane', 'Hakkari', 'Hatay', 'Iğdır', 'Isparta', 'İstanbul', 'İzmir', 'Kahramanmaraş', 'Karabük', 'Karaman', 'Kars', 'Kastamonu', 'Kayseri', 'Kırıkkale', 'Kırklareli', 'Kırşehir', 'Kilis', 'Kocaeli', 'Konya', 'Kütahya', 'Malatya', 'Manisa', 'Mardin', 'Mersin', 'Muğla', 'Muş', 'Nevşehir', 'Niğde', 'Ordu', 'Osmaniye', 'Rize', 'Sakarya', 'Samsun', 'Siirt', 'Sinop', 'Sivas', 'Şanlıurfa', 'Şırnak', 'Tekirdağ', 'Tokat', 'Trabzon', 'Tunceli', 'Uşak', 'Van', 'Yalova', 'Yozgat', 'Zonguldak']}


def parse_tablo_13(rows, tarih, sirket_listesi):
    """İl + firma sütunlarını başlıktan bul; metin/sayı hücrelerini okuyup ili doldur."""
    sales, totals = [], []
    city_col, company_col = 0, 1
    for r in rows[:25]:
        norm = [normalize_baslik(c) for c in r]
        cities = [i for i, v in enumerate(norm) if v in ('IL ADI', 'IL')]
        firms = [i for i, v in enumerate(norm) if 'LISANS SAHIB' in v and 'UNVAN' in v]
        if cities and firms:
            city_col, company_col = cities[0], firms[0]
            break
    first_sales_col = company_col + 1
    current_city = None
    for row in rows:
        if len(row) < first_sales_col + 6:
            continue
        first = str(row[city_col] or '').strip()
        second = str(row[company_col] or '').strip()
        if not second or ('LISANS' in normalize_baslik(second) and 'UNVAN' in normalize_baslik(second)):
            continue
        # Grup başlangıcında il görünür; sonraki şirketlerde il hücresi boştur.
        if first:
            possible_city = sehir_ismi_duzelt(first)
            candidate = normalize_baslik(possible_city)
            if candidate in IL_ISIMLERI:
                current_city = IL_ISIMLERI[candidate]
        if not current_city or not sayi_hucresi_mi(row[first_sales_col]):
            continue
        vals = [sayi_temizle(row[j]) for j in range(first_sales_col, first_sales_col + 6)]
        if normalize_baslik(second) in ('TOPLAM', 'IL TOPLAMI'):
            totals.append({'Tarih': tarih, 'Şehir': current_city,
                           'Tüplü Ton': vals[0], 'Dökme Ton': vals[2],
                           'Otogaz Ton': vals[4]})
            current_city = None  # Grup sonundan sonra bir sonraki il beklenir.
            continue
        if 'TOPLAM' in normalize_baslik(second) or second.startswith('Tablo'):
            continue
        std = sirket_ismi_standartlastir(second, sirket_listesi)
        sirket_listesi.add(std)
        sales.append({'Tarih': tarih, 'Şehir': current_city, 'Şirket': std,
                      'Tüplü Ton': vals[0], 'Tüplü Pay': vals[1],
                      'Dökme Ton': vals[2], 'Dökme Pay': vals[3],
                      'Otogaz Ton': vals[4], 'Otogaz Pay': vals[5]})
    return sales, totals


def parse_tablo_14(rows, tarih, sirket_listesi):
    """Toptan LPG satış tablosunun sütunlarını (kaydırılmışsa da) algılar."""
    company_col = 0
    for r in rows[:25]:
        for i, c in enumerate(r):
            v = normalize_baslik(c)
            if 'SATIS YAPAN' in v and 'LISANS' in v:
                company_col = i
                break
    start = company_col + 1
    result = []
    for row in rows:
        if len(row) < start + 6 or not sayi_hucresi_mi(row[start]):
            continue
        name = str(row[company_col] or '').strip()
        if not name or 'TOPLAM' in normalize_baslik(name) or 'UNVAN' in normalize_baslik(name):
            continue
        nums = [sayi_temizle(row[i]) if i < len(row) else 0 for i in range(start, start + 8)]
        std = sirket_ismi_standartlastir(name, sirket_listesi)
        result.append({'Tarih': tarih, 'Şirket': std,
                       'Tüplü Ton': nums[0], 'Tüplü Pay': nums[1],
                       'Dökme Ton': nums[2], 'Dökme Pay': nums[3],
                       'Otogaz Ton': nums[4], 'Otogaz Pay': nums[5],
                       'Toplam Ton': nums[6] if len(row) >= start + 7 else sum(nums[i] for i in (0, 2, 4)),
                       'Toplam Pay': nums[7]})
    return result


def parse_tablo_12(rows, tarih, sirket_listesi):
    """Year-over-year per-company sales. Source pay (%) = product mix within company."""
    result, current_name = [], ''
    for r in rows:
        if len(r) < 7:
            continue
        name = str(r[0] or '').strip()
        if name and not name.upper().startswith('TABLO') and name.upper() != 'LİSANS SAHİBİ UNVANI':
            current_name = name
        typ = str(r[1] or '').strip()
        if typ not in ('Otogaz', 'Dökme', 'Tüplü', 'Firma Toplamı') or not current_name:
            continue
        if not isinstance(r[2], (int, float, np.number)) or not isinstance(r[4], (int, float, np.number)):
            continue
        std = sirket_ismi_standartlastir(current_name, sirket_listesi)
        curr, prev = sayi_temizle(r[4]), sayi_temizle(r[2])
        difference = ((curr / prev) - 1) * 100 if prev else np.nan
        result.append({'Tarih': tarih, 'Şirket': std, 'Ürün': typ,
                       'Önceki Yıl Ton': prev, 'Güncel Yıl Ton': curr,
                       'Değişim (%)': difference,
                       'Önceki Yıl Ürün Karması (%)': sayi_temizle(r[3]),
                       'Güncel Yıl Ürün Karması (%)': sayi_temizle(r[5])})
    return result


def parse_lpg_sheets(sayfalar, tarih, sirket_listesi):
    arsiv = tablolari_ayir(sayfalar)
    t11, src11 = tabloyu_bul(arsiv, 11)
    t13, src13 = tabloyu_bul(arsiv, 13)
    t14, src14 = tabloyu_bul(arsiv, 14)
    t12, src12 = tabloyu_bul(arsiv, 12)
    national, totals = parse_tablo_11(t11, tarih, sirket_listesi)
    province, cities = parse_tablo_13(t13, tarih, sirket_listesi)
    wholesale = parse_tablo_14(t14, tarih, sirket_listesi)
    yoy = parse_tablo_12(t12, tarih, sirket_listesi)
    warnings = []
    for kind, source, entries in ((11, src11, national), (12, src12, yoy),
                                  (13, src13, province), (14, src14, wholesale)):
        if not entries:
            warnings.append(f'{format_tarih_tr(tarih)}: Tablo {kind} okunamadı. '
                            + tablo_teşhis_notu(sayfalar, arsiv, kind))
        elif kind != source:
            warnings.append(f'{format_tarih_tr(tarih)}: İlgi alanı Tablo {kind} '
                            f'kaynak dosyada Tablo {source} başlığında bulundu; içerik imzasına göre okundu.')
    if cities and len(cities) != 81:
        warnings.append(f'{format_tarih_tr(tarih)}: 81 il beklenirken {len(cities)} il toplamı bulundu')
    if national and totals:
        for col in TON_KOLONLARI:
            diff = abs(sum(x[col] for x in national) - totals[col])
            if diff > 0.1:
                warnings.append(f'{format_tarih_tr(tarih)} Tablo 11 {col}: firma toplamı ile resmi toplam farkı {diff:.3f} ton')
    if province and cities:
        for col in TON_KOLONLARI:
            diff = abs(sum(x[col] for x in province) - sum(x[col] for x in cities))
            if diff > 0.1:
                warnings.append(f'{format_tarih_tr(tarih)} Tablo 13 {col}: il toplamları ile şirket satışları farkı {diff:.3f} ton')
    if province and national:
        for col in TON_KOLONLARI:
            diff = abs(sum(x[col] for x in province) - sum(x[col] for x in national))
            if diff > 0.1:
                warnings.append(f'{format_tarih_tr(tarih)} {col}: Tablo 11 ve 13 arasında {diff:.3f} ton fark')
    return national, totals, province, cities, wholesale, yoy, arsiv, warnings


@st.cache_data(show_spinner=False)
def verileri_oku(imza):
    from openpyxl import load_workbook

    tum_sehir_sirket, tum_iller, tum_turkiye, tum_ulusal = [], [], [], []
    tum_toptan, tum_yillik, tum_arsiv, warnings = [], [], {}, []
    sirket_listesi = set()

    for filename, _, _ in imza:
        tarih = dosya_isminden_tarih(filename)
        path = DOSYA_KLASORU / filename
        try:
            wb = load_workbook(path, read_only=True, data_only=True)
            try:
                sayfalar = {ws.title: list(ws.iter_rows(values_only=True)) for ws in wb.worksheets}
            finally:
                wb.close()
        except Exception as ex:
            warnings.append(f'{filename}: Excel okunamadı ({ex})')
            continue
        ulusal, toplam, illerin_satisi, il_toplamlari, toptan, yillik, arsiv, notlar = parse_lpg_sheets(sayfalar, tarih, sirket_listesi)
        tum_ulusal.extend(ulusal)
        tum_sehir_sirket.extend(illerin_satisi)
        tum_iller.extend(il_toplamlari)
        tum_toptan.extend(toptan)
        tum_yillik.extend(yillik)
        tum_arsiv[(tarih.year, tarih.month)] = arsiv
        warnings.extend(notlar)
        if toplam:
            tum_turkiye.append(toplam)

    df_sirket = pd.DataFrame(tum_sehir_sirket, columns=SIRKET_KOLONLARI)
    df_iller = pd.DataFrame(tum_iller, columns=['Tarih', 'Şehir', *TON_KOLONLARI])
    df_turkiye = pd.DataFrame(tum_turkiye, columns=['Tarih', *TON_KOLONLARI])
    df_ulusal = pd.DataFrame(tum_ulusal, columns=['Tarih', 'Şirket', *TON_KOLONLARI, *PAY_KOLONLARI])
    df_toptan = pd.DataFrame(tum_toptan)
    df_yillik = pd.DataFrame(tum_yillik)

    # The input sheets contain each company only once per city and month.
    # Group duplicate names introduced by company-name canonicalization;
    # recompute weighted market shares using the original city/national totals.
    for df, grp in ((df_sirket, ['Tarih', 'Şehir', 'Şirket']),
                    (df_ulusal, ['Tarih', 'Şirket'])):
        if not df.empty:
            df2 = df.groupby(grp, as_index=False)[TON_KOLONLARI].sum()
            group_keys = ['Tarih', 'Şehir'] if 'Şehir' in grp else ['Tarih']
            total = df2.groupby(group_keys)[TON_KOLONLARI].transform('sum')
            for col, pay in zip(TON_KOLONLARI, PAY_KOLONLARI):
                df2[pay] = 100 * df2[col] / total[col].replace(0, np.nan)
                df2[pay] = df2[pay].fillna(0)
            if 'Şehir' in grp:
                df_sirket = df2
            else:
                df_ulusal = df2

    # National rows use Tablo 11 (not duplicated city-derived company volumes).
    if not df_ulusal.empty:
        national = df_ulusal.copy()
        national['Şehir'] = 'TÜRKİYE GENELİ'
        df_sirket = pd.concat([df_sirket, national[df_sirket.columns]], ignore_index=True)
    if not df_turkiye.empty:
        total_rows = df_turkiye.copy()
        total_rows['Şehir'] = 'TÜRKİYE GENELİ'
        df_iller = pd.concat([df_iller, total_rows[df_iller.columns]], ignore_index=True)

    for df in [df_sirket, df_iller, df_turkiye, df_ulusal, df_toptan, df_yillik]:
        if not df.empty:
            df.sort_values('Tarih', inplace=True)
            df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
            df['Tarih_Grafik'] = df['Tarih'].apply(format_tarih_grafik)
    return df_sirket, df_iller, df_turkiye, df_ulusal, df_toptan, df_yillik, tum_arsiv, warnings


def tablo_dataframe(rows):
    if not rows:
        return pd.DataFrame()
    width = max(len(x) for x in rows)
    data = [list(x) + [None] * (width - len(x)) for x in rows]
    df = pd.DataFrame(data)
    df = df.dropna(axis=1, how='all')
    df.columns = [f'Sütun {i+1}' for i in range(len(df.columns))]
    return df


def tarih_secim_etiketi(ts):
    return format_tarih_tr(pd.Timestamp(ts))

def excel_yukle(key):
    files = st.file_uploader("Aylık raporları seç: Ocak26.xlsx, Subat26.xlsx...",
                             type=['xlsx'], accept_multiple_files=True, key=key)
    st.caption("Yüklenen dosyalar bu sunucunun raporlar/ klasörüne kaydedilir. Streamlit Cloud üzerinde kalıcı değildir; GitHub'a da ekleyin.")
    if st.button("Excel dosyalarını ekle / güncelle", key=f'{key}_button', disabled=not files):
        DOSYA_KLASORU.mkdir(parents=True, exist_ok=True)
        saved, skipped = [], []
        for f in files:
            name = Path(f.name).name
            if dosya_isminden_tarih(name) is None:
                skipped.append(name)
                continue
            (DOSYA_KLASORU / name).write_bytes(f.getvalue())
            saved.append(name)
        if skipped:
            st.warning("Atlanan dosyalar (isim formatı hatalı): " + ', '.join(skipped))
        if saved:
            st.cache_data.clear()
            st.rerun()

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
    with st.expander("📥 Yeni aylık Excel ekle (.xlsx)"):
        excel_yukle('excel_ekle')
    st.stop()

# --- ANALİZ EKRANI ---

imza, dosya_uyarilari = aylik_excel_imzasi()
with st.spinner('Aylık Excel verileri yükleniyor...'):
    df_sirket, df_iller, df_turkiye, df_turkiye_sirket, df_toptan, df_yillik, tablo_arsivi, veri_uyarilari = verileri_oku(imza)

st.title("📊 EPDK Stratejik Pazar Analizi")

ram_now = get_total_ram_usage()
ram_limit = 16384.0
bar_color = "green" if ram_now < 10000 else "red"
st.sidebar.markdown(f"### RAM Durumu")
st.sidebar.progress(min(ram_now/ram_limit, 1.0))
st.sidebar.caption(f"Kullanılan: {ram_now:.0f} MB / {ram_limit:.0f} MB")
st.sidebar.markdown("---")
with st.sidebar.expander("📥 Yeni Excel ekle"):
    excel_yukle('excel_sidebar')

if not DOSYA_KLASORU.exists():
    st.error(f"'{DOSYA_KLASORU}' klasörü bulunamadı.")
else:
    if df_sirket.empty:
        st.warning("Okunabilir il verisi bulunamadı. Aylık .xlsx dosyalarını raporlar/ klasörüne ekleyin.")
    else:
        st.sidebar.caption(f"📂 {len(imza)} aylık Excel · {df_iller[df_iller['Şehir'] != 'TÜRKİYE GENELİ']['Şehir'].nunique()} il")
        if veri_uyarilari or dosya_uyarilari:
            with st.expander(f"⚠️ Veri kontrolü: {len(veri_uyarilari) + len(dosya_uyarilari)} uyarı"):
                for mesaj in dosya_uyarilari + veri_uyarilari:
                    st.warning(mesaj)
        # --- ANA MENÜ SEÇİMİ ---
        st.sidebar.title("📌 Menü")
        sayfa_secimi = st.sidebar.radio("Rapor Türü Seçiniz:", [
            "Aylık Analiz (Şehir Bazlı)", "Kümülatif Rapor (Ocak-Güncel)",
            "Toptan LPG (Tablo 14)", "Yıllık Kıyas (Tablo 12)", "Tüm Tablolar (1–14)"])
        st.sidebar.markdown("---")
        
        # =================================================================================================
        # 1. SENARYO: AYLIK ANALİZ (ESKİ KODLARIN AYNISI)
        # =================================================================================================
        if sayfa_secimi == "Aylık Analiz (Şehir Bazlı)":
            st.sidebar.header("⚙️ Parametreler")
            
            sehirler = sorted(df_sirket['Şehir'].unique())
            if "TÜRKİYE GENELİ" in sehirler:
                sehirler.remove("TÜRKİYE GENELİ")
                sehirler.insert(0, "TÜRKİYE GENELİ")
                
            secilen_sehir = st.sidebar.selectbox("Şehir / Bölge", sehirler, index=0)
            
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
            
            tab1, tab2, tab3, tab4, tab5 = st.tabs([
                "📈 Pazar Grafiği", 
                "💵 Makro Analiz", 
                "🥊 Rekabet Analizi", 
                "🌡️ Mevsimsellik & Tahmin", 
                "🧠 Stratejik Rapor"
            ])
            
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
                if len(donemler) > 0:
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
                    
                    df_final[f"Fark Ton"] = df_final[f"Ton ({secilen_donem})"] - df_final[col_ton_prev_name]
                    df_final[f"Fark Pay"] = df_final[f"Pay ({secilen_donem})"] - df_final[col_pay_prev_name]

                    df_final = df_final.sort_values(f"Pay ({secilen_donem})", ascending=False).reset_index(drop=True)
                    df_final.index += 1
                    
                    st.dataframe(df_final.style.format({
                        f"Ton ({secilen_donem})": "{:,.2f}", 
                        f"Pay ({secilen_donem})": "{:.2f}%", 
                        col_ton_prev_name: "{:,.2f}", 
                        col_pay_prev_name: "{:.2f}%",
                        "Fark Ton": "{:+,.2f}",
                        "Fark Pay": "{:+.2f}"
                    }).map(highlight_val, subset=['Fark Ton', 'Fark Pay']), use_container_width=True)
                else:
                    st.warning("Bu seçim için veri bulunamadı.")

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
                if not df_sehir_sirket.empty:
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
                        fig_diff.update_layout(
                            yaxis=dict(automargin=True),
                            height=max(500, len(df_diff)*35),
                            margin=dict(l=20)
                        )
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
                            """)
                else: st.warning("Veri yok.")

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

        # =================================================================================================
        # 2. KÜMÜLATİF RAPOR: MONTHLY XLSX FILES ONLY (NO HARDCODED DOCX)
        # =================================================================================================
        elif sayfa_secimi == "Kümülatif Rapor (Ocak-Güncel)":
            st.header("📈 Kümülatif Pazar Analizi")
            yillar = sorted(df_turkiye['Tarih'].dt.year.unique().tolist(), reverse=True)
            yil = st.sidebar.selectbox("Yıl", yillar)
            aylar_var = sorted(df_turkiye[df_turkiye['Tarih'].dt.year == yil]['Tarih'].dt.month.unique())
            son_ay = st.sidebar.selectbox("Bitiş ayı", list(range(1, max(aylar_var) + 1)),
                                         index=max(aylar_var) - 1,
                                         format_func=lambda x: TR_AYLAR[x])
            segment = st.sidebar.selectbox("Segment", ["Tüm Ürünler", "Otogaz", "Tüplü", "Dökme"])
            aylar_hedef = set(range(1, son_ay + 1))
            curr_dates = df_turkiye[(df_turkiye['Tarih'].dt.year == yil) &
                                    (df_turkiye['Tarih'].dt.month <= son_ay)]
            prev_dates = df_turkiye[(df_turkiye['Tarih'].dt.year == yil - 1) &
                                    (df_turkiye['Tarih'].dt.month <= son_ay)]
            ay_curr = set(curr_dates['Tarih'].dt.month.tolist())
            ay_prev = set(prev_dates['Tarih'].dt.month.tolist())
            eksik = sorted(aylar_hedef - ay_curr)
            if eksik:
                st.warning("Bu yıla ait eksik aylar: " + ', '.join(TR_AYLAR[m] for m in eksik))
            ortak = sorted(ay_curr & ay_prev)
            st.caption(f"Ocak–{TR_AYLAR[son_ay]} {yil}. Kaynak: yüklediğiniz aylık Excel dosyaları, Tablo 11.")

            def donem_toplam(df, year, months):
                d = df[(df['Tarih'].dt.year == year) & df['Tarih'].dt.month.isin(months)]
                return d[TON_KOLONLARI].sum()

            cols = st.columns(3)
            current_total = donem_toplam(df_turkiye, yil, sorted(ay_curr))
            for box, s in zip(cols, ['Otogaz', 'Tüplü', 'Dökme']):
                box.metric(s + ' (ton)', f"{current_total[s + ' Ton']:,.2f}")

            if ortak:
                st.info("Yıllık kıyaslamada yalnızca iki yılda da yüklenmiş aynı aylar kullanılır: " +
                        ', '.join(TR_AYLAR[m] for m in ortak))
                old_tot = donem_toplam(df_turkiye, yil - 1, ortak)
                new_tot = donem_toplam(df_turkiye, yil, ortak)
                rows = []
                for s in ['Tüplü', 'Dökme', 'Otogaz']:
                    a, b = new_tot[s + ' Ton'], old_tot[s + ' Ton']
                    rows.append({'Ürün': s, f'{yil - 1} Ton': b, f'{yil} Ton': a,
                                 'Fark Ton': a - b, 'Değişim (%)': (a / b - 1) * 100 if b else np.nan})
                st.subheader("Ürün Türüne Göre Yıllık Kıyaslama")
                st.dataframe(pd.DataFrame(rows).style.format({
                    f'{yil - 1} Ton': '{:,.2f}', f'{yil} Ton': '{:,.2f}',
                    'Fark Ton': '{:+,.2f}', 'Değişim (%)': '{:+.2f}'
                }).map(highlight_val, subset=['Fark Ton', 'Değişim (%)']), use_container_width=True)
            else:
                st.warning(f"{yil-1} ve {yil} arasında karşılaştırılabilir ortak ay yok. Önceki yılın XLSX dosyalarını da ekleyebilirsiniz.")

            st.subheader("Dağıtıcı Bazlı Kümülatif Satışlar ve Pazar Payları")
            use_months = ortak if ortak else sorted(ay_curr)
            current_dist = df_turkiye_sirket[
                (df_turkiye_sirket['Tarih'].dt.year == yil) &
                df_turkiye_sirket['Tarih'].dt.month.isin(use_months)
            ].groupby('Şirket', as_index=False)[TON_KOLONLARI].sum()
            previous_dist = df_turkiye_sirket[
                (df_turkiye_sirket['Tarih'].dt.year == yil - 1) &
                df_turkiye_sirket['Tarih'].dt.month.isin(ortak)
            ].groupby('Şirket', as_index=False)[TON_KOLONLARI].sum() if ortak else pd.DataFrame()

            if not current_dist.empty:
                current_dist['Toplam Ton'] = current_dist[TON_KOLONLARI].sum(axis=1)
                if segment == 'Tüm Ürünler':
                    for col in TON_KOLONLARI + ['Toplam Ton']:
                        total = current_dist[col].sum()
                        current_dist[col.replace(' Ton', ' Pay (%)')] = current_dist[col] / total * 100 if total else 0
                    view = current_dist.sort_values('Toplam Ton', ascending=False).reset_index(drop=True)
                    st.dataframe(view.style.format({c: '{:,.2f}' for c in view.columns if 'Ton' in c})
                                 .format({c: '{:.2f}%' for c in view.columns if 'Pay (%)' in c}),
                                 use_container_width=True)
                else:
                    ton = segment + ' Ton'
                    curr = current_dist[['Şirket', ton]].copy()
                    curr.rename(columns={ton: f'{yil} Ton'}, inplace=True)
                    if ortak and not previous_dist.empty:
                        prev = previous_dist[['Şirket', ton]].rename(columns={ton: f'{yil-1} Ton'})
                        result = curr.merge(prev, on='Şirket', how='outer').fillna(0)
                        curr_total, prev_total = result[f'{yil} Ton'].sum(), result[f'{yil-1} Ton'].sum()
                        result[f'{yil} Pazar Payı (%)'] = (100 * result[f'{yil} Ton'] / curr_total) if curr_total else 0
                        result[f'{yil-1} Pazar Payı (%)'] = (100 * result[f'{yil-1} Ton'] / prev_total) if prev_total else 0
                        result['Fark Ton'] = result[f'{yil} Ton'] - result[f'{yil-1} Ton']
                        result['Fark Pay (puan)'] = result[f'{yil} Pazar Payı (%)'] - result[f'{yil-1} Pazar Payı (%)']
                        result = result.sort_values(f'{yil} Ton', ascending=False)
                        st.dataframe(result.style.format({c: '{:,.2f}' for c in result.columns if 'Ton' in c})
                                     .format({c: '{:.2f}' for c in result.columns if 'Pazar Payı' in c})
                                     .format({'Fark Pay (puan)': '{:+.2f}'})
                                     .map(highlight_val, subset=['Fark Ton', 'Fark Pay (puan)']),
                                     use_container_width=True)
                    else:
                        total = curr[f'{yil} Ton'].sum()
                        curr['Pazar Payı (%)'] = curr[f'{yil} Ton'] / total * 100 if total else 0
                        st.dataframe(curr.sort_values(f'{yil} Ton', ascending=False), use_container_width=True)
            else:
                st.warning('Seçilen dönem için Tablo 11 dağıtıcı verisi bulunamadı.')

        # =================================================================================================
        # 3. TABLO 14: WHOLESALE (NOT CITY-LEVEL)
        # =================================================================================================
        elif sayfa_secimi == "Toptan LPG (Tablo 14)":
            st.header("🚚 Dağıtıcılar Arası Toptan LPG Satışları — Tablo 14")
            if df_toptan.empty:
                st.warning("Tablo 14 verisi bulunamadı.")
            else:
                dates = sorted(df_toptan['Tarih'].unique(), reverse=True)
                date = st.selectbox('Dönem', dates, format_func=tarih_secim_etiketi)
                month = df_toptan[df_toptan['Tarih'] == date]
                fields = ['Şirket', 'Tüplü Ton', 'Tüplü Pay', 'Dökme Ton', 'Dökme Pay',
                          'Otogaz Ton', 'Otogaz Pay', 'Toplam Ton', 'Toplam Pay']
                st.dataframe(month[fields].sort_values('Toplam Ton', ascending=False)
                             .style.format({c: '{:,.2f}' for c in fields if c != 'Şirket'}),
                             use_container_width=True)
                st.caption('Bu tablo toptan dağıtıcılar arası satışlardır; perakende il pazarının toplamına eklenmez.')
                st.subheader('Toptan Satış Eğilimleri')
                ss = sorted(df_toptan['Şirket'].unique())
                chosen = st.multiselect('Şirketler', ss, default=[LIKITGAZ_NAME] if LIKITGAZ_NAME in ss else ss[:1])
                if chosen:
                    fig = px.line(df_toptan[df_toptan['Şirket'].isin(chosen)],
                                  x='Tarih', y='Toplam Ton', color='Şirket', markers=True)
                    st.plotly_chart(fig, use_container_width=True)

        # =================================================================================================
        # 4. TABLO 12: YOY COMPANY REPORT
        # =================================================================================================
        elif sayfa_secimi == "Yıllık Kıyas (Tablo 12)":
            st.header("📆 Şirketlerin Önceki Yıla Göre Satışları — Tablo 12")
            st.caption('Kaynakta Pay (%) sütunları şirket içi ürün karmasını ifade eder; il/ulusal pazar payı değildir.')
            if df_yillik.empty:
                st.warning('Tablo 12 verisi bulunamadı.')
            else:
                dates = sorted(df_yillik['Tarih'].unique(), reverse=True)
                chosen_date = st.selectbox('Dönem', dates, format_func=tarih_secim_etiketi)
                product = st.selectbox('Ürün türü', ['Firma Toplamı', 'Otogaz', 'Tüplü', 'Dökme'])
                table = df_yillik[(df_yillik['Tarih'] == chosen_date) & (df_yillik['Ürün'] == product)]
                cols = ['Şirket', 'Önceki Yıl Ton', 'Güncel Yıl Ton', 'Değişim (%)']
                st.dataframe(table[cols].sort_values('Güncel Yıl Ton', ascending=False)
                             .style.format({'Önceki Yıl Ton': '{:,.2f}', 'Güncel Yıl Ton': '{:,.2f}',
                                            'Değişim (%)': '{:+.2f}'})
                             .map(highlight_val, subset=['Değişim (%)']), use_container_width=True)

        # =================================================================================================
        # 5. EVERY TABLE 1-14 IN THE SOURCE FILES (UNMODIFIED CELL VALUES)
        # =================================================================================================
        elif sayfa_secimi == "Tüm Tablolar (1–14)":
            st.header('📚 Tüm EPDK Excel Tabloları')
            available_dates = sorted(tablo_arsivi.keys(), reverse=True)
            chosen_period = st.selectbox('Dönem', available_dates,
                                         format_func=lambda key: f'{TR_AYLAR[key[1]]} {key[0]}')
            all_tables = tablo_arsivi[chosen_period]
            table_numbers = sorted(all_tables.keys())
            selected_table = st.selectbox('Tablo numarası', table_numbers,
                                          format_func=lambda k: f'Tablo {k}' + (' — İl bazlı satışlar' if k == 13 else
                                          ' — Dağıtıcılar arası toptan satış' if k == 14 else ''))
            st.caption('Excel hücrelerindeki değerler olduğu gibi gösterilir; birleşik başlık satırları korunur.')
            raw = tablo_dataframe(all_tables[selected_table])
            st.dataframe(raw, use_container_width=True, hide_index=True, height=540)
            st.download_button('📥 Bu tabloyu CSV indir',
                               data=raw.to_csv(index=False, header=False, sep=';', decimal=',').encode('utf-8-sig'),
                               file_name=f'Tablo{selected_table}_{TR_AYLAR[chosen_period[1]]}{chosen_period[0]}.csv',
                               mime='text/csv')
