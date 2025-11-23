import streamlit as st
import pandas as pd
import os
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

# --- GÜVENLİ IMPORT (Hata almamak için) ---
try:
    import yfinance as yf
    DOLAR_MODULU_VAR = True
except ImportError:
    DOLAR_MODULU_VAR = False
# ------------------------------------------

# --- AYARLAR ---
DOSYA_KLASORU = 'raporlar'
LIKITGAZ_NAME = "LİKİTGAZ DAĞITIM VE ENDÜSTRİ A.Ş."
LIKITGAZ_COLOR = "#DC3912" 
OTHER_COLORS = px.colors.qualitative.Set2

TR_AYLAR = {
    1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
    7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
}

DOSYA_AY_MAP = {
    'ocak': 1, 'subat': 2, 'mart': 3, 'nisan': 4, 'mayis': 5, 'haziran': 6,
    'temmuz': 7, 'agustos': 8, 'eylul': 9, 'ekim': 10, 'kasim': 11, 'aralik': 12
}

# Bayram Tarihleri (Yaklaşık aylar - Analiz işaretlemesi için)
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
def format_tarih_tr(date_obj):
    if pd.isna(date_obj): return ""
    return f"{TR_AYLAR.get(date_obj.month, '')} {date_obj.year}"

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
        print(f"Dolar hatası: {e}")
        return pd.DataFrame()

def grafik_bayram_ekle(fig, df_dates):
    """Grafiğe bayram çizgilerini ekler"""
    if df_dates.empty: return fig
    min_date = df_dates.min()
    max_date = df_dates.max()
    
    for bayram in BAYRAMLAR:
        b_date = pd.to_datetime(bayram["Tarih"])
        if min_date <= b_date <= max_date:
            fig.add_vline(x=b_date, line_width=1, line_dash="dot", line_color="gray", opacity=0.5)
            fig.add_annotation(x=b_date, y=1, yref="paper", text=bayram["Isim"], showarrow=False, 
                               font=dict(size=8, color="gray"), textangle=-90, yanchor="top")
    return fig

# --- ANALİZ MOTORLARI (GÜNCELLENMİŞ DETAYLI VERSİYON) ---
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
        if yuzde > 0: analist_yorumu = "Pazar kısa vadede canlılık gösteriyor."
        else: analist_yorumu = "Kısa vadede talep daralması gözleniyor."
        
    if ton_gecen_yil > 0:
        fark_yil = ton_simdi - ton_gecen_yil
        yuzde_yil = (fark_yil / ton_gecen_yil) * 100
        durum_yil = "büyüme" if yuzde_yil > 0 else "daralma"
        rapor.append(f"- **Yıllık:** Geçen yılın aynı ayına göre **%{abs(yuzde_yil):.1f}** oranında {durum_yil} var.")
    
    rapor.append(f"> **💡 Analist Görüşü:** {analist_yorumu}")
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
        yuzde = ((ton_simdi - ton_gecen_ay) / ton_gecen_ay) * 100
        icon = "📈" if yuzde > 0 else "📉"
        rapor.append(f"- **Aylık Performans:** {icon} Geçen aya göre satışlar **%{yuzde:+.1f}** değişti.")
    if ton_gecen_yil > 0:
        yuzde_yil = ((ton_simdi - ton_gecen_yil) / ton_gecen_yil) * 100
        icon = "🚀" if yuzde_yil > 0 else "🔻"
        rapor.append(f"- **Yıllık Performans:** {icon} Geçen yılın aynı ayına göre **%{yuzde_yil:+.1f}** değişim var.")
    return rapor

def stratejik_analiz_raporu(df_sirket, df_iller, sehir, segment, odak_sirket):
    col_pay = segment + " Pay"
    col_ton_il = segment + " Ton"
    col_ton_sirket = segment + " Ton"
    
    son_tarih = df_sirket['Tarih'].max()
    son_donem_str = format_tarih_tr(son_tarih)
    
    # Şehir Toplam Pazar Verisi (Kıyaslama için şart)
    df_sehir_resmi = df_iller[df_iller['Şehir'].str.upper() == sehir.upper()].sort_values('Tarih')
    
    pazar_raporu = []
    sirket_raporu = []
    rakip_raporu = []

    # --- 1. ŞEHİR PAZAR BÜYÜKLÜĞÜ ANALİZİ ---
    try:
        if not df_sehir_resmi.empty:
            ton_simdi = df_sehir_resmi[df_sehir_resmi['Tarih'] == son_tarih][col_ton_il].sum()
            onceki_ay_date = son_tarih - relativedelta(months=1)
            ton_onceki = df_sehir_resmi[df_sehir_resmi['Tarih'] == onceki_ay_date][col_ton_il].sum()
            
            pazar_raporu.append(f"### 🌍 {sehir} - {segment} Pazar Durumu ({son_donem_str})")
            pazar_raporu.append(f"Toplam Pazar: **{ton_simdi:,.0f} ton**")
            
            if ton_onceki > 0:
                pazar_buyume = ((ton_simdi - ton_onceki) / ton_onceki) * 100
                if pazar_buyume > 0:
                    pazar_raporu.append(f"📈 Pazar geçen aya göre **%{pazar_buyume:.1f} büyüdü.**")
                else:
                    pazar_raporu.append(f"📉 Pazar geçen aya göre **%{abs(pazar_buyume):.1f} daraldı.**")
        else:
            pazar_raporu.append("Şehir pazar verisi hesaplanamadı.")
    except:
        pazar_raporu.append("Pazar verisi hatası.")
    pazar_raporu.append("---")

    # --- 2. DETAYLI ŞİRKET ANALİZİ ---
    sirket_raporu.append(f"### 📊 {odak_sirket} Performans Detayı")
    
    df_odak = df_sirket[(df_sirket['Şirket'] == odak_sirket) & (df_sirket['Şehir'] == sehir)].sort_values('Tarih')
    
    if not df_odak.empty:
        # Son 12 ayı analiz edelim
        for i in range(len(df_odak)):
            # İlk veri atla
            if i == 0: continue
            
            curr = df_odak.iloc[i]
            prev = df_odak.iloc[i-1]
            
            curr_date = curr['Tarih']
            tarih_str = format_tarih_tr(curr_date)
            
            # Şirket Verileri
            sirket_ton_curr = curr[col_ton_sirket]
            sirket_ton_prev = prev[col_ton_sirket]
            sirket_pay_curr = curr[col_pay]
            sirket_pay_diff = sirket_pay_curr - prev[col_pay]
            
            # Pazar Verileri (O aya ait toplam pazar)
            try:
                pazar_ton_curr = df_sehir_resmi[df_sehir_resmi['Tarih'] == curr_date][col_ton_il].sum()
                pazar_ton_prev = df_sehir_resmi[df_sehir_resmi['Tarih'] == prev['Tarih']][col_ton_il].sum()
            except:
                pazar_ton_curr, pazar_ton_prev = 0, 0

            # Büyüme Oranları Hesapla
            sirket_buyume = 0
            pazar_buyume = 0
            
            if sirket_ton_prev > 0:
                sirket_buyume = ((sirket_ton_curr - sirket_ton_prev) / sirket_ton_prev) * 100
            
            if pazar_ton_prev > 0:
                pazar_buyume = ((pazar_ton_curr - pazar_ton_prev) / pazar_ton_prev) * 100
            
            # --- DETAYLI YORUM MANTIĞI ---
            yorum = ""
            icon = "➡️"
            
            # Durum 1: Pazar Payı ARTTI
            if sirket_pay_diff > 0.05:
                if sirket_buyume > 0 and pazar_buyume > 0:
                    icon = "🚀"
                    yorum = f"**Mükemmel.** Pazar %{pazar_buyume:.1f} büyürken, biz **%{sirket_buyume:.1f}** büyüdük. Rakiplerden pay çaldık."
                elif sirket_buyume > 0 and pazar_buyume < 0:
                    icon = "⭐"
                    yorum = f"**Ayrışma.** Pazar daralırken (%{pazar_buyume:.1f}), biz satışlarımızı artırdık (%{sirket_buyume:.1f})."
                elif sirket_buyume < 0 and pazar_buyume < 0:
                    if abs(sirket_buyume) < abs(pazar_buyume):
                        icon = "🛡️"
                        yorum = f"**Dirençli.** Pazar sert düştü (%{pazar_buyume:.1f}), biz daha az etkilendik. Payımız arttı."
            
            # Durum 2: Pazar Payı DÜŞTÜ
            elif sirket_pay_diff < -0.05:
                if sirket_buyume > 0 and pazar_buyume > 0:
                    # İSTEDİĞİNİZ SENARYO: Satış arttı ama pazar daha çok büyüdü
                    if sirket_buyume < pazar_buyume:
                        icon = "⚠️"
                        yorum = f"**Yetersiz Büyüme.** Satışımız arttı (%{sirket_buyume:.1f}) ANCAK pazar çok daha hızlı büyüdü (%{pazar_buyume:.1f}). Yetişemedik."
                elif sirket_buyume < 0 and pazar_buyume > 0:
                    icon = "🚨"
                    yorum = f"**Kritik.** Pazar büyürken (%{pazar_buyume:.1f}) biz küçüldük (%{sirket_buyume:.1f}). Müşteri kaçışı var."
                elif sirket_buyume < 0 and pazar_buyume < 0:
                    icon = "🔻"
                    yorum = f"**Negatif.** Pazar daralıyor ama biz pazardan daha hızlı küçülüyoruz."

            # Durum 3: Yatay
            else:
                yorum = f"Pazarla paralel hareket ({pazar_buyume:.1f}% değişim)."

            # Geçen Yıl Bilgisi
            gy_text = ""
            gy_tarih = curr_date - relativedelta(years=1)
            row_gy = df_odak[df_odak['Tarih'] == gy_tarih]
            if not row_gy.empty:
                gy_pay = row_gy.iloc[0][col_pay]
                gy_text = f" (Geçen Yıl: %{gy_pay:.2f})"

            sirket_raporu.append(f"{icon} **{tarih_str}:** Pay: %{sirket_pay_curr:.2f} | Satış: {sirket_ton_curr:,.0f} ton | {yorum}{gy_text}")
            
    else:
        sirket_raporu.append("Şirket verisi bulunamadı.")

    # --- 3. DETAYLI RAKİP TREND ANALİZİ ---
    rakip_raporu.append(f"### 📡 Rakip Trend Dedektörü ({sehir})")
    
    df_sehir_sirket = df_sirket[df_sirket['Şehir'] == sehir]
    son_df = df_sehir_sirket[df_sehir_sirket['Tarih'] == son_tarih].sort_values(col_pay, ascending=False)
    rakipler = son_df[(son_df['Şirket'] != odak_sirket) & (son_df[col_pay] > 2.0)].head(6)['Şirket'].tolist()
    
    yakalanan_trend = 0
    
    for rakip in rakipler:
        # Rakibin son 4 aylık verisini çek
        df_rakip = df_sehir_sirket[df_sehir_sirket['Şirket'] == rakip].sort_values('Tarih').tail(4)
        if len(df_rakip) < 3: continue
        
        paylar = df_rakip[col_pay].values
        tarihler = df_rakip['Dönem'].values
        
        # Trend 1: SERİ DÜŞÜŞ (Son 3 aydır sürekli düşüyorsa)
        if paylar[-1] < paylar[-2] < paylar[-3]:
            baslangic = tarihler[-3]
            toplam_kayip = paylar[-3] - paylar[-1]
            rakip_raporu.append(f"📉 **{rakip}:** Düşüş trendine girdi. **{baslangic}** ayından beri sürekli düşüyor. (Toplam Kayıp: -{toplam_kayip:.2f} puan)")
            yakalanan_trend += 1
            
        # Trend 2: SERİ YÜKSELİŞ (Son 3 aydır sürekli artıyorsa)
        elif paylar[-1] > paylar[-2] > paylar[-3]:
            baslangic = tarihler[-3]
            toplam_kazanc = paylar[-1] - paylar[-3]
            rakip_raporu.append(f"📈 **{rakip}:** Yükseliş trendinde. **{baslangic}** ayından beri pazar payını artırıyor. (Toplam Kazanç: +{toplam_kazanc:.2f} puan)")
            yakalanan_trend += 1

        # Trend 3: ANİ ŞOK (Son ayda sert hareket)
        else:
            son_fark = paylar[-1] - paylar[-2]
            if son_fark > 1.5:
                 rakip_raporu.append(f"🔥 **{rakip}:** Son ayda agresif bir atak yaptı (+{son_fark:.2f} puan).")
                 yakalanan_trend += 1
            elif son_fark < -1.5:
                 rakip_raporu.append(f"🔻 **{rakip}:** Son ayda sert bir kayıp yaşadı ({son_fark:.2f} puan).")
                 yakalanan_trend += 1
                 
    if yakalanan_trend == 0:
        rakip_raporu.append("✅ Rakiplerde şu an belirgin bir seri trend (ardışık artış/azalış) veya şok hareket görülmüyor. Piyasa stabil.")

    return pazar_raporu, sirket_raporu, rakip_raporu

# --- VERİ OKUMA (YÜKLEME EKRANLI) ---
@st.cache_data
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
                # A) İL ÖZET TABLOSU
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

                # B) TABLO 3.7
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

                # C) ŞİRKET TABLOLARI
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
    return df_sirket, df_iller, df_turkiye, df_turkiye_sirket

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")
st.title("📊 EPDK Stratejik Pazar Analizi")

if not os.path.exists(DOSYA_KLASORU):
    st.error(f"'{DOSYA_KLASORU}' klasörü bulunamadı.")
else:
    # SPINNER EKLENDİ (YÜKLENİYOR EKRANI)
    with st.spinner('Raporlar taranıyor ve analiz ediliyor... Lütfen bekleyin.'):
        df_sirket, df_iller, df_turkiye, df_turkiye_sirket = verileri_oku()
    
    if df_sirket.empty:
        st.warning("Veri yok.")
    else:
        st.sidebar.header("⚙️ Parametreler")
        sehirler = sorted(df_sirket['Şehir'].unique())
        idx_ank = sehirler.index('Ankara') if 'Ankara' in sehirler else 0
        secilen_sehir = st.sidebar.selectbox("Şehir", sehirler, index=idx_ank)
        
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("Segment", segmentler)
        
        df_sehir_sirket = df_sirket[df_sirket['Şehir'] == secilen_sehir]
        col_pay = secilen_segment + " Pay"
        
        # --- TAB YAPISI ---
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Pazar Grafiği", 
            "💵 Makro Analiz", 
            "🥊 Rekabet Analizi",
            "🌡️ Mevsimsellik & Tahmin", 
            "🧠 Stratejik Rapor"
        ])
        
        # --- TAB 1: KLASİK GÖRÜNÜM ---
        with tab1:
            st.info(f"ℹ️ **Bilgi:** Sol menüdeki **Şehir ({secilen_sehir})** ve **Segment ({secilen_segment})** alanlarını değiştirerek bu sayfadaki analizleri güncelleyebilirsiniz.")
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                sirketler = sorted(df_sehir_sirket['Şirket'].unique())
                defaults = [LIKITGAZ_NAME] if LIKITGAZ_NAME in sirketler else []
                top_3 = df_sehir_sirket.groupby('Şirket')[col_pay].mean().nlargest(4).index.tolist()
                defaults += [s for s in top_3 if s != LIKITGAZ_NAME]
                secilen_sirketler = st.multiselect("Şirketler", sirketler, default=defaults[:5])
            with col_f2:
                veri_tipi = st.radio("Veri Tipi:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
                y_col = col_pay if veri_tipi == "Pazar Payı (%)" else secilen_segment + " Ton"
            
            if secilen_sirketler:
                df_chart = df_sehir_sirket[df_sehir_sirket['Şirket'].isin(secilen_sirketler)]
                color_map = {s: OTHER_COLORS[i%len(OTHER_COLORS)] for i,s in enumerate(secilen_sirketler)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                fig = px.line(df_chart, x='Tarih', y=y_col, color='Şirket', markers=True,
                              color_discrete_map=color_map, title=f"{secilen_sehir} - {secilen_segment} Trendi")
                fig.update_xaxes(dtick="M1", tickformat="%b %Y", ticktext=df_chart['Dönem'].unique(), tickvals=df_chart['Tarih'].unique())
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
                fig.update_traces(patch={"line": {"width": 4}}, selector={"legendgroup": LIKITGAZ_NAME})
                # Bayramları ekle
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

        # --- TAB 2: MAKROEKONOMİK ANALİZ ---
        with tab2:
            st.subheader(f"💵 Dolar Kuru ve Pazar Hacmi İlişkisi ({secilen_sehir} - {secilen_segment})")
            st.caption(f"Sol menüden parametreleri değiştirerek ({secilen_sehir} - {secilen_segment}) analizi yapabilirsiniz.")
            if not DOLAR_MODULU_VAR:
                st.warning("⚠️ 'yfinance' yüklü değil.")
            else:
                col_ton = secilen_segment + " Ton"
                df_sehir_toplam = df_sehir_sirket.groupby('Tarih')[col_ton].sum().reset_index()
                
                # ADANA DÜZELTMESİ: SIFIR OLAN SATIŞLARI FİLTRELE
                df_sehir_toplam = df_sehir_toplam[df_sehir_toplam[col_ton] > 0.1]
                
                if not df_sehir_toplam.empty:
                    min_date = df_sehir_toplam['Tarih'].min()
                    df_dolar = dolar_verisi_getir(min_date)
                    
                    if not df_dolar.empty:
                        df_makro = pd.merge(df_sehir_toplam, df_dolar, on='Tarih', how='inner')
                        fig_makro = go.Figure()
                        fig_makro.add_trace(go.Bar(x=df_makro['Tarih'], y=df_makro[col_ton], name='Pazar (Ton)', marker_color='#3366CC', opacity=0.6))
                        fig_makro.add_trace(go.Scatter(x=df_makro['Tarih'], y=df_makro['Dolar Kuru'], name='Dolar (TL)', yaxis='y2', line=dict(color='#DC3912', width=3)))
                        fig_makro.update_layout(title=f"{secilen_sehir} Hacim vs Dolar", yaxis=dict(title='Satış (Ton)'), yaxis2=dict(title='USD/TL', overlaying='y', side='right'), hovermode='x unified', legend=dict(orientation="h", y=1.1))
                        
                        # Bayramları makro grafiğe de ekle
                        fig_makro = grafik_bayram_ekle(fig_makro, df_makro['Tarih'])
                        st.plotly_chart(fig_makro, use_container_width=True)
                    else: st.warning("Dolar verisi alınamadı.")
                else: st.warning("Yeterli veri yok.")

        # --- TAB 3: REKABET ANALİZİ (YENİ) ---
        with tab3:
            col_ton = secilen_segment + " Ton"
            son_tarih = df_sehir_sirket['Tarih'].max()
            gecen_yil = son_tarih - relativedelta(years=1)
            
            # 1. KAZANANLAR & KAYBEDENLER
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
                
                fig_diff = px.bar(df_diff, x='Fark', y='Şirket', orientation='h', color='Renk',
                                  color_discrete_map=color_map_w, title="Pazar Payı Değişimi (Puan)")
                st.plotly_chart(fig_diff, use_container_width=True)
            else:
                st.warning("Yıllık kıyaslama için veri eksik.")
            
            st.markdown("---")
            
            # 2. PAZAR KONSANTRASYONU (HHI)
            st.subheader(f"🧮 Pazar Rekabet Yoğunluğu (HHI) - {secilen_sehir}")
            
            # HHI Hesapla: Payların karesinin toplamı
            if not df_now.empty:
                hhi_score = (df_now[col_pay] ** 2).sum()
                fig_hhi = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = hhi_score,
                    domain = {'x': [0, 1], 'y': [0, 1]},
                    title = {'text': "HHI Skoru"},
                    gauge = {
                        'axis': {'range': [0, 10000], 'tickwidth': 1, 'tickcolor': "darkblue"},
                        'bar': {'color': "black"},
                        'bgcolor': "white",
                        'borderwidth': 2,
                        'bordercolor': "gray",
                        'steps': [
                            {'range': [0, 1500], 'color': '#2ECC71'}, # Rekabetçi
                            {'range': [1500, 2500], 'color': '#F1C40F'}, # Orta
                            {'range': [2500, 10000], 'color': '#E74C3C'}], # Tekel
                        'threshold': {
                            'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': hhi_score}}))
                
                c_hhi1, c_hhi2 = st.columns([1, 2])
                with c_hhi1:
                    st.plotly_chart(fig_hhi, use_container_width=True)
                with c_hhi2:
                    st.info("""
                    **HHI (Herfindahl-Hirschman) Nedir?**
                    Pazarın tekelleşme oranını gösterir.
                    - **< 1500 (Yeşil):** Rekabetçi Pazar. Pazara girmek kolaydır.
                    - **1500 - 2500 (Sarı):** Orta Yoğunluk. Birkaç büyük oyuncu var.
                    - **> 2500 (Kırmızı):** Yüksek Konsantrasyon. Pazar 1-2 şirketin hakimiyetinde.
                    """)
            
        # --- TAB 4: MEVSİMSELLİK & TAHMİN ---
        with tab4:
            st.caption(f"Sol menüden parametreleri değiştirerek ({secilen_sehir} - {secilen_segment}) tahminini güncelleyebilirsiniz.")
            col_ton = secilen_segment + " Ton"
            df_sehir_toplam = df_sehir_sirket.groupby('Tarih')[col_ton].sum().reset_index()
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
                    ay_sirasi = [TR_AYLAR[i] for i in range(1, 13)]
                    fig_cycle.update_xaxes(categoryorder='array', categoryarray=ay_sirasi, title="Aylar")
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
                        forecast_val = (val_prev_year * 0.6) + (trend_val * 0.4) if val_prev_year > 0 else trend_val
                        forecast_data.append({'Tarih': format_tarih_tr(next_date), 'Tahmin (Ton)': forecast_val})
                    st.table(pd.DataFrame(forecast_data).style.format({'Tahmin (Ton)': '{:,.0f}'}))
                    st.caption("*Tahminler geçmiş yıl verisi ve son trendlerin ağırlıklı ortalamasına dayanır.")
                else: st.warning("Yetersiz veri.")

        # --- TAB 5: STRATEJİK RAPOR ---
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
