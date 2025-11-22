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
import re

# --- AYARLAR ---
DOSYA_KLASORU = 'raporlar'

# Türkçe Ay İsimleri
TR_AYLAR = {
    1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
    7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
}

DOSYA_AY_MAP = {
    'ocak': 1, 'subat': 2, 'mart': 3, 'nisan': 4, 'mayis': 5, 'haziran': 6,
    'temmuz': 7, 'agustos': 8, 'eylul': 9, 'ekim': 10, 'kasim': 11, 'aralik': 12
}

# --- ÖZEL DÜZELTME LİSTESİ ---
OZEL_DUZELTMELER = {
    "AYTEMİZ": "AYTEMİZ AKARYAKIT DAĞITIM A.Ş.",
    "BALPET": "BALPET PETROL ÜRÜNLERİ TAŞ. SAN. VE TİC. A.Ş.",
    "ECOGAZ": "ECOGAZ LPG DAĞITIM A.Ş.",
    "AYGAZ": "AYGAZ A.Ş.",
    "İPRAGAZ": "İPRAGAZ A.Ş.",
    "LİKİTGAZ": "LİKİTGAZ DAĞITIM VE ENDÜSTRİ A.Ş.",
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
    ay_isim = TR_AYLAR.get(date_obj.month, "")
    return f"{ay_isim} {date_obj.year}"

def iter_block_items(parent):
    if isinstance(parent, _Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("Doküman yapısı hatalı")
    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)

def dosya_isminden_tarih(filename):
    base = os.path.splitext(filename)[0]
    base = base.lower().replace('ş', 's').replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ö', 'o').replace('ç', 'c')
    match = re.match(r"([a-z]+)(\d{2})", base)
    if match:
        ay_str, yil_str = match.groups()
        if ay_str in DOSYA_AY_MAP:
            yil = 2000 + int(yil_str)
            ay = DOSYA_AY_MAP[ay_str]
            return pd.Timestamp(year=yil, month=ay, day=1)
    return None

def sayi_temizle(text):
    if not text: return 0.0
    try:
        clean = text.replace('.', '').replace(',', '.')
        return float(clean)
    except:
        return 0.0

def metin_temizle_kok(text):
    text = text.upper().replace('İ', 'I').replace('Ş', 'S').replace('Ğ', 'G').replace('Ü', 'U').replace('Ö', 'O').replace('Ç', 'C')
    text = re.sub(r'\b(A\.?\s?S\.?|LTD\.?|STI\.?|SAN\.?|TIC\.?|VE|AS|ANONIM|SIRKETI)\b', '', text)
    text = re.sub(r'[^\w\s]', '', text)
    text = text.replace("DAG ", "DAGITIM ")
    return " ".join(text.split())

def sirket_ismi_standartlastir(ham_isim, mevcut_isimler, esik=88):
    ham_isim = ham_isim.strip()
    ham_isim_upper = ham_isim.upper().replace('İ', 'I')
    
    for anahtar, standart_isim in OZEL_DUZELTMELER.items():
        if anahtar.upper().replace('İ', 'I') in ham_isim_upper:
            return standart_isim

    temiz_isim = metin_temizle_kok(ham_isim)
    if not mevcut_isimler: return ham_isim
    
    en_iyi_eslesme, skor = process.extractOne(ham_isim, mevcut_isimler)
    mevcut_temiz = {metin_temizle_kok(isim): isim for isim in mevcut_isimler}
    en_iyi_temiz, skor_temiz = process.extractOne(temiz_isim, list(mevcut_temiz.keys()))
    
    if skor_temiz >= esik: return mevcut_temiz[en_iyi_temiz]
    elif skor >= esik: return en_iyi_eslesme
    else: return ham_isim

# --- AKILLI ANALİZ MOTORU (YENİ) ---
def anormallik_tespiti(df_filtered, segment, threshold_std=1.5):
    """
    Basit Anormallik Tespiti: Ortalama + (1.5 * Standart Sapma)
    """
    analiz_sonuclari = []
    sirketler = df_filtered['Şirket'].unique()
    
    for sirket in sirketler:
        df_sirket = df_filtered[df_filtered['Şirket'] == sirket].sort_values('Tarih')
        if len(df_sirket) < 3: continue # En az 3 ay veri lazım analiz için
        
        veriler = df_sirket[segment]
        ortalama = veriler.mean()
        std_sapma = veriler.std()
        
        if std_sapma == 0: continue
        
        # Her ay için kontrol et
        for index, row in df_sirket.iterrows():
            deger = row[segment]
            fark = deger - ortalama
            
            # Pazar payı çok küçükse (örn %0.1) analiz etme, gürültü yapar
            if ortalama < 1.0: continue 

            # POZİTİF PİK (ANİ YÜKSELİŞ)
            if fark > (threshold_std * std_sapma):
                analiz_sonuclari.append({
                    "Tip": "Yükseliş",
                    "Şirket": sirket,
                    "Dönem": row['Dönem'],
                    "Mesaj": f"🚀 **{sirket}**, {row['Dönem']} döneminde **PİK YAPTI**! Ortalaması %{ortalama:.2f} iken, bu ay **%{deger:.2f}** seviyesine çıktı."
                })
            
            # NEGATİF KIRILMA (ANİ DÜŞÜŞ)
            elif fark < -(threshold_std * std_sapma):
                 analiz_sonuclari.append({
                    "Tip": "Düşüş",
                    "Şirket": sirket,
                    "Dönem": row['Dönem'],
                    "Mesaj": f"🔻 **{sirket}**, {row['Dönem']} döneminde **SERT DÜŞTÜ**. Ortalaması %{ortalama:.2f} iken, bu ay **%{deger:.2f}** seviyesine geriledi."
                })
    
    return analiz_sonuclari

# --- VERİ OKUMA ---

@st.cache_data
def verileri_oku():
    tum_veri = []
    sirket_listesi = set()
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx') or f.endswith('.doc')])
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, dosya in enumerate(files):
        tarih = dosya_isminden_tarih(dosya)
        if not tarih: continue
        path = os.path.join(DOSYA_KLASORU, dosya)
        try: doc = Document(path)
        except: continue
        status_text.text(f"İşleniyor: {dosya}")
        son_sehir = None
        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if text.startswith("Tablo") and ":" in text:
                    parts = text.split(":")
                    if len(parts) > 1:
                        pot_sehir = parts[1].strip()
                        if 2 < len(pot_sehir) < 40: son_sehir = pot_sehir
            elif isinstance(block, Table):
                if son_sehir:
                    try:
                        header_text = "".join([c.text.lower() for c in block.rows[0].cells] + ([c.text.lower() for c in block.rows[1].cells] if len(block.rows)>1 else []))
                        if "tüplü" in header_text or "dökme" in header_text or "pay" in header_text:
                            for row in block.rows:
                                cells = row.cells
                                if len(cells) < 7: continue
                                ham_isim = cells[0].text.strip()
                                if any(x in ham_isim.upper() for x in ["LİSANS", "TOPLAM", "UNVANI"]) or ham_isim == "": continue
                                std_isim = sirket_ismi_standartlastir(ham_isim, sirket_listesi)
                                sirket_listesi.add(std_isim)
                                try:
                                    tuplu_pay = sayi_temizle(cells[2].text)
                                    dokme_pay = sayi_temizle(cells[4].text)
                                    otogaz_pay = sayi_temizle(cells[6].text)
                                    if tuplu_pay + dokme_pay + otogaz_pay > 0:
                                        tum_veri.append({'Tarih': tarih, 'Şehir': son_sehir, 'Şirket': std_isim, 'Tüplü': tuplu_pay, 'Dökme': dokme_pay, 'Otogaz': otogaz_pay})
                                except: continue
                    except: pass
                son_sehir = None
    status_text.empty()
    progress_bar.empty()
    df = pd.DataFrame(tum_veri)
    if not df.empty:
        df = df.sort_values('Tarih')
        df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
    return df

# --- ARAYÜZ ---

st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")
st.title("📈 EPDK Sektör Raporu & Yapay Zeka Analizi")

if not os.path.exists(DOSYA_KLASORU):
    st.error(f"Lütfen '{DOSYA_KLASORU}' klasörünü oluşturun.")
else:
    df = verileri_oku()
    
    if df.empty:
        st.warning("Veri bulunamadı.")
    else:
        # --- YAN MENÜ ---
        st.sidebar.header("Filtreler")
        sehirler = sorted(df['Şehir'].unique())
        secilen_sehir = st.sidebar.selectbox("Şehir", sehirler, index=sehirler.index('Ankara') if 'Ankara' in sehirler else 0)
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("Segment", segmentler)
        
        # Veri Filtreleme
        df_sehir = df[df['Şehir'] == secilen_sehir]
        
        # --- SEKMELER (TABS) ---
        tab1, tab2 = st.tabs(["📊 Grafik ve Tablo", "🤖 Makine Analizi (Anormallik Tespiti)"])
        
        # ---------------- SEKME 1: GRAFİK ----------------
        with tab1:
            sirketler = sorted(df_sehir['Şirket'].unique())
            secilen_sirketler = st.multiselect(f"Grafikte Gösterilecek Şirketler", sirketler)
            
            if secilen_sirketler:
                df_chart = df_sehir[df_sehir['Şirket'].isin(secilen_sirketler)]
            else:
                top_companies = df_sehir.groupby('Şirket')[secilen_segment].mean().nlargest(5).index.tolist()
                df_chart = df_sehir[df_sehir['Şirket'].isin(top_companies)]
                st.info(f"Varsayılan: En büyük 5 şirket gösteriliyor.")

            fig = px.line(df_chart, x='Tarih', y=secilen_segment, color='Şirket', markers=True,
                          labels={secilen_segment: 'Pazar Payı (%)', 'Tarih': 'Dönem'}, hover_name='Şirket')
            fig.update_xaxes(dtick="M1", tickformat="%b %Y", ticktext=df_chart['Dönem'].unique(), tickvals=df_chart['Tarih'].unique())
            fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, use_container_width=True)
            
            # Aylık Sıralama
            st.markdown("---")
            st.subheader(f"🗓️ {secilen_sehir} - Aylık Pazar Liderleri")
            col1, col2 = st.columns([1, 3])
            with col1:
                dates = sorted(df['Tarih'].unique(), reverse=True)
                date_opts = [format_tarih_tr(d) for d in dates]
                secilen_donem_str = st.selectbox("Dönem Seçin", date_opts)
            with col2:
                df_table = df_sehir[df_sehir['Dönem'] == secilen_donem_str].copy()
                df_table = df_table[df_table[secilen_segment] > 0].sort_values(by=secilen_segment, ascending=False).reset_index(drop=True)
                df_table.index += 1
                st.dataframe(df_table[['Şirket', secilen_segment]].style.format({secilen_segment: "{:.2f}%"}), use_container_width=True)

        # ---------------- SEKME 2: MAKİNE ANALİZİ ----------------
        with tab2:
            st.subheader(f"🤖 {secilen_sehir} - {secilen_segment} İçin Anormallik Tespiti")
            st.markdown("Bu modül, şirketlerin geçmiş performanslarını inceler ve **olağandışı yükseliş (Pik)** veya **düşüşleri** otomatik tespit eder.")
            
            # Analizi Çalıştır
            anomaliler = anormallik_tespiti(df_sehir, secilen_segment)
            
            if not anomaliler:
                st.success("✅ Bu şehir ve segmentte olağandışı bir hareket (anormallik) tespit edilmedi. Pazar stabil görünüyor.")
            else:
                # Sonuçları Tarihe Göre (En yeniden en eskiye) Sırala
                # Önce 'Dönem' string olduğu için sıralama zor, listeyi ters çevirelim (son eklenenler altta kalırsa)
                # Ama en iyisi dataframe yapıp göstermek.
                
                st.write(f"⚠️ Toplam **{len(anomaliler)}** adet dikkat çekici hareket tespit edildi:")
                
                for olay in reversed(anomaliler): # En son olay en üstte
                    if olay["Tip"] == "Yükseliş":
                        st.success(olay["Mesaj"]) # Yeşil Kutu
                    else:
                        st.error(olay["Mesaj"])   # Kırmızı Kutu
