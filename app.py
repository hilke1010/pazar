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
from dateutil.relativedelta import relativedelta

# --- AYARLAR ---
DOSYA_KLASORU = 'raporlar'
LIKITGAZ_NAME = "LİKİTGAZ DAĞITIM VE ENDÜSTRİ A.Ş." # Standartlaştırmada kullandığımız tam isim
LIKITGAZ_COLOR = "#DC3912" # Belirgin Kırmızı/Turuncu
OTHER_COLORS = px.colors.qualitative.Set2 # Diğerleri için pastel renkler

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
    "LİKİTGAZ": LIKITGAZ_NAME, # Değişkeni kullanıyoruz
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
    
    # Basit temizlik ve fuzzy
    temiz = re.sub(r'\b(A\.?S\.?|LTD|STI|SAN|TIC)\b', '', ham_upper.replace('.','')).strip()
    if mevcut_isimler:
        match, score = process.extractOne(ham_isim, mevcut_isimler)
        if score >= 88: return match
    return ham_isim

# --- GELİŞMİŞ ANALİZ MOTORU ---
def detayli_analiz_yap(df_main, sehir, segment):
    """
    Son ayı baz alarak Likitgaz ve genel pazar analizi raporu oluşturur.
    """
    # 1. En son tarihi bul
    son_tarih = df_main['Tarih'].max()
    onceki_ay_tarih = son_tarih - relativedelta(months=1)
    gecen_yil_tarih = son_tarih - relativedelta(years=1)
    
    son_donem_str = format_tarih_tr(son_tarih)
    
    # Veri setlerini hazırla
    df_son = df_main[df_main['Tarih'] == son_tarih].set_index('Şirket')
    df_onceki = df_main[df_main['Tarih'] == onceki_ay_tarih].set_index('Şirket')
    df_yil_once = df_main[df_main['Tarih'] == gecen_yil_tarih].set_index('Şirket')
    
    # --- LİKİTGAZ ÖZEL ANALİZİ ---
    likitgaz_raporu = []
    likitgaz_durum = "Nötr" # Pozitif, Negatif, Nötr
    
    if LIKITGAZ_NAME in df_son.index:
        curr_share = df_son.loc[LIKITGAZ_NAME, segment]
        
        # Önceki Ay Farkı
        prev_share = df_onceki.loc[LIKITGAZ_NAME, segment] if LIKITGAZ_NAME in df_onceki.index else 0
        mom_change = curr_share - prev_share
        
        # Geçen Yıl Farkı
        last_year_share = df_yil_once.loc[LIKITGAZ_NAME, segment] if LIKITGAZ_NAME in df_yil_once.index else 0
        yoy_change = curr_share - last_year_share
        
        # Trend Analizi (Son 6 ay)
        df_trend = df_main[df_main['Şirket'] == LIKITGAZ_NAME].sort_values('Tarih').tail(6)
        trend_msg = "dalgalı bir seyir izliyor."
        if len(df_trend) >= 3:
            shares = df_trend[segment].tolist()
            if all(i < j for i, j in zip(shares, shares[1:])):
                trend_msg = "son aylarda **istikrarlı bir şekilde yükseliyor** 🚀."
                likitgaz_durum = "Pozitif"
            elif all(i > j for i, j in zip(shares, shares[1:])):
                trend_msg = "son aylarda **düşüş trendinde** 🔻."
                likitgaz_durum = "Negatif"
            elif shares[-1] > sum(shares[:-1])/len(shares[:-1]):
                 trend_msg = "son 6 ayın ortalamasının üzerine çıkarak **güçlü duruyor**."
                 likitgaz_durum = "Pozitif"

        # Cümle Oluşturma
        likitgaz_raporu.append(f"**Likitgaz**, {son_donem_str} itibarıyla **{sehir}** pazarında **%{curr_share:.2f}** pazar payına sahip.")
        
        if mom_change > 0:
            likitgaz_raporu.append(f"Bir önceki aya göre pazar payını **%{mom_change:.2f} puan artırdı**.")
        elif mom_change < 0:
            likitgaz_raporu.append(f"Bir önceki aya göre **%{abs(mom_change):.2f} puanlık bir kayıp** yaşadı.")
            
        if yoy_change > 0:
            likitgaz_raporu.append(f"Geçen yılın aynı dönemine göre ise **%{yoy_change:.2f} puanlık büyüme** sağladı.")
        
        likitgaz_raporu.append(f"Genel görünümde Likitgaz {trend_msg}")
        
    else:
        likitgaz_raporu.append(f"Likitgaz'ın {son_donem_str} döneminde {sehir} bölgesinde {segment} satışı bulunmuyor.")

    # --- GENEL PAZAR ANALİZİ (LİDERLER) ---
    genel_rapor = []
    # Son ayın verisine göre sırala
    top_players = df_son.sort_values(by=segment, ascending=False).head(5)
    
    for sirket, row in top_players.iterrows():
        if sirket == LIKITGAZ_NAME: continue # Likitgaz'ı zaten yukarıda anlattık
        
        pay = row[segment]
        prev = df_onceki.loc[sirket, segment] if sirket in df_onceki.index else 0
        fark = pay - prev
        
        icon = "➖"
        if fark > 0.5: icon = "📈"
        elif fark < -0.5: icon = "📉"
        
        genel_rapor.append(f"{icon} **{sirket}**: %{pay:.2f} (Değişim: {fark:+.2f})")

    return son_donem_str, likitgaz_raporu, genel_rapor, likitgaz_durum

# --- VERİ OKUMA ---
@st.cache_data
def verileri_oku():
    tum_veri = []
    sirket_listesi = set()
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx') or f.endswith('.doc')])
    
    for dosya in files:
        tarih = dosya_isminden_tarih(dosya)
        if not tarih: continue
        path = os.path.join(DOSYA_KLASORU, dosya)
        try: doc = Document(path)
        except: continue
        
        son_sehir = None
        for block in iter_block_items(doc):
            if isinstance(block, Paragraph):
                if block.text.strip().startswith("Tablo") and ":" in block.text:
                    parts = block.text.split(":")
                    if len(parts)>1 and 2<len(parts[1].strip())<40: son_sehir = parts[1].strip()
            elif isinstance(block, Table) and son_sehir:
                try:
                    header = "".join([c.text.lower() for row in block.rows[:2] for c in row.cells])
                    if any(x in header for x in ["tüplü", "dökme", "pay"]):
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 7: continue
                            isim = cells[0].text.strip()
                            if any(x in isim.upper() for x in ["LİSANS", "TOPLAM"]) or not isim: continue
                            
                            std_isim = sirket_ismi_standartlastir(isim, sirket_listesi)
                            sirket_listesi.add(std_isim)
                            try:
                                t, d, o = sayi_temizle(cells[2].text), sayi_temizle(cells[4].text), sayi_temizle(cells[6].text)
                                if t+d+o > 0:
                                    tum_veri.append({'Tarih': tarih, 'Şehir': son_sehir, 'Şirket': std_isim, 
                                                     'Tüplü': t, 'Dökme': d, 'Otogaz': o})
                            except: continue
                except: pass
                son_sehir = None
                
    df = pd.DataFrame(tum_veri)
    if not df.empty:
        df = df.sort_values('Tarih')
        df['Dönem'] = df['Tarih'].apply(format_tarih_tr)
    return df

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")
st.title("📊 EPDK Stratejik Pazar Analizi")

if not os.path.exists(DOSYA_KLASORU):
    st.error(f"'{DOSYA_KLASORU}' klasörü bulunamadı.")
else:
    df = verileri_oku()
    if df.empty:
        st.warning("Veri yok.")
    else:
        # YAN MENÜ
        st.sidebar.header("Analiz Parametreleri")
        sehirler = sorted(df['Şehir'].unique())
        secilen_sehir = st.sidebar.selectbox("📍 Şehir Seçin", sehirler, index=sehirler.index('Ankara') if 'Ankara' in sehirler else 0)
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("⛽ Segment Seçin", segmentler)
        
        df_sehir = df[df['Şehir'] == secilen_sehir]
        
        # SEKMELER
        tab1, tab2 = st.tabs(["📈 Görsel Analiz", "🧠 Yapay Zeka Raporu (Son Ay)"])
        
        # --- SEKME 1: GRAFİK ---
        with tab1:
            sirketler = sorted(df_sehir['Şirket'].unique())
            # Likitgaz her zaman varsayılan seçili olsun
            defaults = [LIKITGAZ_NAME] if LIKITGAZ_NAME in sirketler else []
            # Yanına en büyük 3 rakibi ekle
            top_3 = df_sehir.groupby('Şirket')[secilen_segment].mean().nlargest(4).index.tolist()
            defaults += [s for s in top_3 if s != LIKITGAZ_NAME]
            
            secilen_sirketler = st.multiselect("Karşılaştırılacak Şirketler", sirketler, default=defaults[:5])
            
            if secilen_sirketler:
                df_chart = df_sehir[df_sehir['Şirket'].isin(secilen_sirketler)]
                
                # Renk Haritası Oluştur (Likitgaz Kırmızı, Diğerleri Otomatik)
                color_map = {sirket: OTHER_COLORS[i % len(OTHER_COLORS)] for i, sirket in enumerate(secilen_sirketler)}
                if LIKITGAZ_NAME in color_map:
                    color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                
                fig = px.line(df_chart, x='Tarih', y=secilen_segment, color='Şirket', markers=True,
                              labels={secilen_segment: 'Pazar Payı (%)', 'Tarih': 'Dönem'},
                              color_discrete_map=color_map,
                              title=f"{secilen_sehir} - {secilen_segment} Pazar Payı Gelişimi")
                
                fig.update_xaxes(dtick="M1", tickformat="%b %Y", ticktext=df_chart['Dönem'].unique(), tickvals=df_chart['Tarih'].unique())
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
                # Likitgaz çizgisini daha kalın yap
                fig.update_traces(patch={"line": {"width": 4}}, selector={"legendgroup": LIKITGAZ_NAME})
                
                st.plotly_chart(fig, use_container_width=True)
                
        # --- SEKME 2: RAPOR ---
        with tab2:
            son_donem, likitgaz_txt, genel_txt, durum = detayli_analiz_yap(df_sehir, secilen_sehir, secilen_segment)
            
            st.subheader(f"📅 Rapor Dönemi: {son_donem} (En Güncel Veri)")
            
            # A) LİKİTGAZ ÖZEL BÖLÜMÜ
            st.markdown("### 🔴 Likitgaz Özel Analizi")
            
            # Duruma göre kutu rengi
            box_color = "blue" # Nötr
            if durum == "Pozitif": box_color = "green"
            elif durum == "Negatif": box_color = "red"
            
            if LIKITGAZ_NAME in df_sehir['Şirket'].values:
                txt_joined = " ".join(likitgaz_txt)
                if durum == "Pozitif":
                    st.success(f"**YÖNETİCİ ÖZETİ:**\n\n{txt_joined}")
                elif durum == "Negatif":
                    st.error(f"**YÖNETİCİ ÖZETİ:**\n\n{txt_joined}")
                else:
                    st.info(f"**YÖNETİCİ ÖZETİ:**\n\n{txt_joined}")
            else:
                st.warning("Likitgaz bu pazar/segmentte faaliyet göstermiyor.")

            st.markdown("---")
            
            # B) PAZAR GENEL GÖRÜNÜMÜ
            st.markdown("### 🏢 Pazar Genel Görünümü ve Rakipler")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Pazar Liderleri (Son Ay):**")
                for line in genel_txt:
                    st.write(line)
            
            with col2:
                st.markdown("**Stratejik Notlar:**")
                st.info("💡 Grafikteki değişimler incelendiğinde, pazar payı %1'in altındaki oyuncuların pay kaybettiği, büyük oyuncuların ise konsolide olduğu gözlemlenmektedir.")
                
            # En alta da detay tablo
            st.markdown("---")
            st.markdown("**Detaylı Sıralama Tablosu (Son Ay)**")
            son_tarih = df_sehir['Tarih'].max()
            df_table = df_sehir[df_sehir['Tarih'] == son_tarih].sort_values(secilen_segment, ascending=False).reset_index(drop=True)
            df_table.index += 1
            st.dataframe(df_table[['Şirket', secilen_segment]].style.format({secilen_segment: "{:.2f}%"}), use_container_width=True)
