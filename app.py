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
LIKITGAZ_NAME = "LİKİTGAZ DAĞITIM VE ENDÜSTRİ A.Ş."
LIKITGAZ_COLOR = "#DC3912" # Kırmızı
OTHER_COLORS = px.colors.qualitative.Set2

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

# --- MAKİNE ÖĞRENMESİ ANALİZ MOTORU ---
def detayli_analiz_raporu(df_main, sehir, segment):
    # Veri Hazırlığı
    col_pay = segment + " Pay"
    col_ton = segment + " Ton"
    
    # Toplam Pazar Büyüklüğü (Tonaj Toplamı)
    # Her ay için o şehirdeki toplam tonajı hesapla
    pazar_buyuklugu = df_main.groupby('Tarih')[col_ton].sum().sort_index()
    
    son_tarih = df_main['Tarih'].max()
    onceki_ay = son_tarih - relativedelta(months=1)
    
    son_donem_str = format_tarih_tr(son_tarih)
    
    rapor_satirlari = []
    
    # 1. PAZAR BÜYÜKLÜĞÜ ANALİZİ (DARALMA/BÜYÜME)
    son_tonaj = pazar_buyuklugu.get(son_tarih, 0)
    onceki_tonaj = pazar_buyuklugu.get(onceki_ay, 0)
    
    trend_emoji = "➖"
    trend_yorum = "yatay seyretti"
    
    if son_tonaj > 0 and onceki_tonaj > 0:
        degisim_ton = son_tonaj - onceki_tonaj
        degisim_yuzde = (degisim_ton / onceki_tonaj) * 100
        
        if degisim_yuzde > 2:
            trend_emoji = "📈"
            trend_yorum = f"**büyüdü**. Geçen ay **{onceki_tonaj:,.0f}** ton olan pazar hacmi, bu ay **{son_tonaj:,.0f}** tona çıktı"
        elif degisim_yuzde < -2:
            trend_emoji = "📉"
            trend_yorum = f"**küçüldü**. Geçen ay **{onceki_tonaj:,.0f}** ton olan pazar hacmi, bu ay **{son_tonaj:,.0f}** tona geriledi"
        else:
             trend_yorum = f"**dengeli kaldı**. Toplam satış **{son_tonaj:,.0f}** ton seviyesinde gerçekleşti"
            
        rapor_satirlari.append(f"### 🌍 Pazar Durumu ({son_donem_str})")
        rapor_satirlari.append(f"{trend_emoji} {sehir} {segment} pazarı bir önceki aya göre %{abs(degisim_yuzde):.1f} oranında {trend_yorum}.")
    
    rapor_satirlari.append("---")
    
    # 2. LİKİTGAZ ÖZEL ANALİZİ (TÜM GEÇMİŞ)
    rapor_satirlari.append(f"### 🔴 Likitgaz Detaylı Performans Analizi")
    
    df_likit = df_main[df_main['Şirket'] == LIKITGAZ_NAME].sort_values('Tarih')
    
    if not df_likit.empty:
        # Son durum
        son_veri = df_likit[df_likit['Tarih'] == son_tarih]
        if not son_veri.empty:
            curr_pay = son_veri.iloc[0][col_pay]
            curr_ton = son_veri.iloc[0][col_ton]
            rapor_satirlari.append(f"**SON DURUM:** {son_donem_str} itibarıyla Likitgaz, **%{curr_pay:.2f}** pazar payı ve **{curr_ton:,.2f} ton** satış ile ayı kapattı.")
        else:
            rapor_satirlari.append(f"⚠️ Likitgaz'ın {son_donem_str} döneminde satışı bulunmamaktadır.")

        # Tarihsel Süreç (Storytelling)
        rapor_satirlari.append("\n**🗓️ Dönemsel Hareketler:**")
        
        for i in range(len(df_likit)):
            row = df_likit.iloc[i]
            tarih_str = format_tarih_tr(row['Tarih'])
            pay = row[col_pay]
            ton = row[col_ton]
            
            # Bir önceki aya göre kıyas
            yorum = ""
            if i > 0:
                prev = df_likit.iloc[i-1]
                diff_pay = pay - prev[col_pay]
                if diff_pay > 1.5: yorum = "🚀 **(Güçlü Çıkış)**"
                elif diff_pay > 0: yorum = "↗️ (Yükseliş)"
                elif diff_pay < -1.5: yorum = "🔻 **(Sert Düşüş)**"
                elif diff_pay < 0: yorum = "↘️ (Düşüş)"
                else: yorum = "➡️ (Yatay)"
            
            rapor_satirlari.append(f"- **{tarih_str}:** Pazar Payı %{pay:.2f} ({ton:,.0f} ton) {yorum}")
            
    else:
        rapor_satirlari.append("Likitgaz'ın bu şehir ve segmentte tarihsel verisi bulunamadı.")

    return rapor_satirlari

# --- VERİ OKUMA (TONAJ DAHİL) ---
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
                                # SÜTUNLAR (Tahmini): 
                                # 1: Tüplü Ton, 2: Tüplü Pay
                                # 3: Dökme Ton, 4: Dökme Pay
                                # 5: Otogaz Ton, 6: Otogaz Pay
                                t_ton = sayi_temizle(cells[1].text)
                                t_pay = sayi_temizle(cells[2].text)
                                d_ton = sayi_temizle(cells[3].text)
                                d_pay = sayi_temizle(cells[4].text)
                                o_ton = sayi_temizle(cells[5].text)
                                o_pay = sayi_temizle(cells[6].text)
                                
                                if t_pay+d_pay+o_pay > 0 or t_ton+d_ton+o_ton > 0:
                                    tum_veri.append({
                                        'Tarih': tarih, 'Şehir': son_sehir, 'Şirket': std_isim, 
                                        'Tüplü Pay': t_pay, 'Tüplü Ton': t_ton,
                                        'Dökme Pay': d_pay, 'Dökme Ton': d_ton,
                                        'Otogaz Pay': o_pay, 'Otogaz Ton': o_ton
                                    })
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
        st.sidebar.header("⚙️ Parametreler")
        sehirler = sorted(df['Şehir'].unique())
        secilen_sehir = st.sidebar.selectbox("Şehir", sehirler, index=sehirler.index('Ankara') if 'Ankara' in sehirler else 0)
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("Segment", segmentler)
        
        df_sehir = df[df['Şehir'] == secilen_sehir]
        
        tab1, tab2 = st.tabs(["📈 Görsel Analiz", "🧠 Makine Öğrenmesi Analizi"])
        
        # --- SEKME 1: GRAFİK ---
        with tab1:
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                # Şirket Seçimi
                sirketler = sorted(df_sehir['Şirket'].unique())
                defaults = [LIKITGAZ_NAME] if LIKITGAZ_NAME in sirketler else []
                # En büyük 3 rakip (Pay'a göre)
                top_3 = df_sehir.groupby('Şirket')[secilen_segment + " Pay"].mean().nlargest(4).index.tolist()
                defaults += [s for s in top_3 if s != LIKITGAZ_NAME]
                secilen_sirketler = st.multiselect("Şirketler", sirketler, default=defaults[:5])
                
            with col_filter2:
                # Veri Tipi (Ton mu Pay mı?)
                veri_tipi = st.radio("Gösterim Tipi:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
                y_column = secilen_segment + " Pay" if veri_tipi == "Pazar Payı (%)" else secilen_segment + " Ton"

            if secilen_sirketler:
                df_chart = df_sehir[df_sehir['Şirket'].isin(secilen_sirketler)]
                
                # Renkler
                color_map = {s: OTHER_COLORS[i % len(OTHER_COLORS)] for i, s in enumerate(secilen_sirketler)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                
                fig = px.line(df_chart, x='Tarih', y=y_column, color='Şirket', markers=True,
                              color_discrete_map=color_map,
                              title=f"{secilen_sehir} - {secilen_segment} - {veri_tipi}")
                
                fig.update_xaxes(dtick="M1", tickformat="%b %Y", ticktext=df_chart['Dönem'].unique(), tickvals=df_chart['Tarih'].unique())
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
                fig.update_traces(patch={"line": {"width": 4}}, selector={"legendgroup": LIKITGAZ_NAME})
                
                st.plotly_chart(fig, use_container_width=True)
                
            # Alt Tablo
            st.markdown("---")
            st.write(" **Dönemsel Veri Tablosu (Satış ve Pay)**")
            # Pivot tablo ile daha temiz görüntü
            col_ton = secilen_segment + " Ton"
            col_pay = secilen_segment + " Pay"
            
            # Seçilen şirketlerin verisini göster
            if secilen_sirketler:
                df_table = df_chart[['Dönem', 'Şirket', col_ton, col_pay]].sort_values(['Dönem', col_pay], ascending=[False, False])
                st.dataframe(df_table, use_container_width=True)

        # --- SEKME 2: ANALİZ ---
        with tab2:
            rapor = detayli_analiz_raporu(df_sehir, secilen_sehir, secilen_segment)
            
            for satir in rapor:
                st.markdown(satir)
