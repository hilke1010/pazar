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

# --- MAKİNE ÖĞRENMESİ ANALİZ MOTORU (GELİŞMİŞ) ---
def akilli_analiz_raporu(df_main, sehir, segment):
    col_pay = segment + " Pay"
    col_ton = segment + " Ton"
    
    son_tarih = df_main['Tarih'].max()
    son_donem_str = format_tarih_tr(son_tarih)
    
    analiz_text = []
    rakip_notlari = []
    
    # 1. LİKİTGAZ ANALİZİ
    df_likit = df_main[df_main['Şirket'] == LIKITGAZ_NAME].sort_values('Tarih')
    
    if not df_likit.empty:
        analiz_text.append(f"### 🔴 Likitgaz Performans Hikayesi")
        
        for i in range(len(df_likit)):
            curr = df_likit.iloc[i]
            tarih_str = format_tarih_tr(curr['Tarih'])
            pay = curr[col_pay]
            ton = curr[col_ton]
            
            if i == 0:
                # İlk veri
                analiz_text.append(f"- **{tarih_str}:** Başlangıç verisi. Pazar payı: %{pay:.2f} ({ton:,.0f} ton).")
                continue
            
            prev = df_likit.iloc[i-1]
            prev_ton = prev[col_ton] if prev[col_ton] > 0 else 1 # Sıfıra bölünme hatası olmasın
            
            diff_pay = pay - prev[col_pay]
            diff_ton_yuzde = ((ton - prev_ton) / prev_ton) * 100
            
            # Karmaşık Mantık (Pay vs Tonaj)
            yorum = ""
            durum_icon = "➡️"
            
            # Senaryo 1: Pay Düştü, Tonaj Arttı (Pazar Büyüyor, Biz Yavaşız)
            if diff_pay < 0 and diff_ton_yuzde > 0:
                yorum = f"📉 Pazar payı %{abs(diff_pay):.2f} puan geriledi, ANCAK satış tonajı %{diff_ton_yuzde:.1f} arttı. **Analiz:** Pazar genelinde talep artışı var, Likitgaz satışlarını artırsa da rakipler daha agresif büyüdüğü için pay kaybı oluştu."
                durum_icon = "⚠️"
            
            # Senaryo 2: Pay Arttı, Tonaj Düştü (Pazar Küçülüyor, Biz İyiyiz)
            elif diff_pay > 0 and diff_ton_yuzde < 0:
                yorum = f"📈 Pazar payı %{diff_pay:.2f} puan arttı, buna rağmen satış tonajı %{abs(diff_ton_yuzde):.1f} düştü. **Analiz:** Pazar genelinde daralma var (talep düşüklüğü), ancak Likitgaz bu ortamda rakiplerinden müşteri çalarak payını artırmayı başardı."
                durum_icon = "🛡️"

            # Senaryo 3: İkisi de Arttı (Mükemmel)
            elif diff_pay > 0 and diff_ton_yuzde > 0:
                yorum = f"🚀 **Çifte Başarı:** Hem pazar payı (%{diff_pay:.2f}+) hem de satış tonajı (%{diff_ton_yuzde:.1f}+) arttı. Şirket büyüme trendinde."
                durum_icon = "✅"

            # Senaryo 4: İkisi de Düştü (Kötü)
            elif diff_pay < 0 and diff_ton_yuzde < 0:
                yorum = f"🔻 **Kritik:** Hem pazar payı hem de satış hacmi küçüldü. Pazar kaybı yaşanıyor."
                durum_icon = "🛑"
                
            # Toparlanma (Recovery) Kontrolü
            if i > 1:
                prev2 = df_likit.iloc[i-2]
                # Eğer önceki ay düşmüş, bu ay artmışsa
                if (prev[col_pay] < prev2[col_pay]) and (pay > prev[col_pay]):
                    yorum += " **Not:** Bir önceki aydaki düşüş trendi kırılarak tekrar toparlanma sürecine girildi."

            analiz_text.append(f"- {durum_icon} **{tarih_str}:** {yorum} (Pay: %{pay:.2f}, Satış: {ton:,.0f} Ton)")
            
    else:
        analiz_text.append("Likitgaz verisi bulunamadı.")

    # 2. RAKİP RADARI (ANOMALİ TESPİTİ)
    # Son aydaki en büyük 5 rakibi bul
    son_df = df_main[df_main['Tarih'] == son_tarih].sort_values(col_pay, ascending=False)
    rakipler = son_df[son_df['Şirket'] != LIKITGAZ_NAME].head(5)['Şirket'].tolist()
    
    for rakip in rakipler:
        df_rakip = df_main[df_main['Şirket'] == rakip].sort_values('Tarih').tail(2)
        if len(df_rakip) < 2: continue
        
        son = df_rakip.iloc[-1]
        onceki = df_rakip.iloc[-2]
        
        fark_pay = son[col_pay] - onceki[col_pay]
        
        # Dikkat çeken hareketler
        if fark_pay > 2.0:
            rakip_notlari.append(f"📈 **{rakip}**: Son ayda %{fark_pay:.2f} puanlık **sert bir yükseliş** yaptı.")
        elif fark_pay < -2.0:
            rakip_notlari.append(f"📉 **{rakip}**: Son ayda %{abs(fark_pay):.2f} puanlık **ciddi kayıp** yaşadı.")
        elif fark_pay < -0.5:
             rakip_notlari.append(f"🔻 **{rakip}**: Hafif düşüş eğiliminde (-%{abs(fark_pay):.2f}).")
        
        # Son durum notu
        rakip_notlari.append(f"ℹ️ *{rakip}* güncel pay: %{son[col_pay]:.2f}")
        rakip_notlari.append("---")

    return analiz_text, rakip_notlari

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
                                t_ton = sayi_temizle(cells[1].text)
                                t_pay = sayi_temizle(cells[2].text)
                                d_ton = sayi_temizle(cells[3].text)
                                d_pay = sayi_temizle(cells[4].text)
                                o_ton = sayi_temizle(cells[5].text)
                                o_pay = sayi_temizle(cells[6].text)
                                if t_ton+t_pay+d_ton+d_pay+o_ton+o_pay > 0:
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
        st.sidebar.header("⚙️ Parametreler")
        sehirler = sorted(df['Şehir'].unique())
        secilen_sehir = st.sidebar.selectbox("Şehir", sehirler, index=sehirler.index('Ankara') if 'Ankara' in sehirler else 0)
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("Segment", segmentler)
        
        df_sehir = df[df['Şehir'] == secilen_sehir]
        
        tab1, tab2 = st.tabs(["📈 Görsel & Tablo", "🧠 Makine Öğrenmesi Analizi"])
        
        # --- SEKME 1 ---
        with tab1:
            # Grafik Kısmı (Aynı kalıyor)
            sirketler = sorted(df_sehir['Şirket'].unique())
            defaults = [LIKITGAZ_NAME] if LIKITGAZ_NAME in sirketler else []
            top_3 = df_sehir.groupby('Şirket')[secilen_segment + " Pay"].mean().nlargest(4).index.tolist()
            defaults += [s for s in top_3 if s != LIKITGAZ_NAME]
            secilen_sirketler = st.multiselect("Grafik İçin Şirketler", sirketler, default=defaults[:5])
            
            col_ton = secilen_segment + " Ton"
            col_pay = secilen_segment + " Pay"
            
            if secilen_sirketler:
                df_chart = df_sehir[df_sehir['Şirket'].isin(secilen_sirketler)]
                color_map = {s: OTHER_COLORS[i % len(OTHER_COLORS)] for i, s in enumerate(secilen_sirketler)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                
                fig = px.line(df_chart, x='Tarih', y=col_pay, color='Şirket', markers=True,
                              color_discrete_map=color_map, title=f"{secilen_sehir} - {secilen_segment} Pazar Payı Trendi")
                fig.update_xaxes(dtick="M1", tickformat="%b %Y", ticktext=df_chart['Dönem'].unique(), tickvals=df_chart['Tarih'].unique())
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
                fig.update_traces(patch={"line": {"width": 4}}, selector={"legendgroup": LIKITGAZ_NAME})
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            # FİLTRELİ TABLO KISMI (YENİ)
            st.subheader("📋 Dönemsel Sıralama Tablosu")
            
            # Dönem Filtresi
            mevcut_donemler = df_sehir.sort_values('Tarih', ascending=False)['Dönem'].unique()
            secilen_tablo_donemi = st.selectbox("Görüntülenecek Dönemi Seçin:", mevcut_donemler)
            
            # Tabloyu Oluştur
            df_table_filtered = df_sehir[df_sehir['Dönem'] == secilen_tablo_donemi].copy()
            # Pazar payına göre sırala
            df_table_filtered = df_table_filtered.sort_values(col_pay, ascending=False).reset_index(drop=True)
            df_table_filtered.index += 1 # Sıralama 1'den başlasın
            
            # Gösterilecek kolonlar
            display_cols = ['Şirket', col_ton, col_pay]
            
            # Tabloyu Göster
            st.dataframe(
                df_table_filtered[display_cols].style.format({col_pay: "{:.2f}%", col_ton: "{:,.2f}"}), 
                use_container_width=True
            )

        # --- SEKME 2: GELİŞMİŞ ANALİZ ---
        with tab2:
            col_main, col_side = st.columns([2, 1])
            
            likitgaz_analizi, rakip_notlari = akilli_analiz_raporu(df_sehir, secilen_sehir, secilen_segment)
            
            with col_main:
                for line in likitgaz_analizi:
                    st.markdown(line)
            
            with col_side:
                st.success("📡 Rakip İzleme Radarı")
                if not rakip_notlari:
                    st.write("Rakiplerde olağandışı bir hareket tespit edilmedi.")
                for not_item in rakip_notlari:
                    st.markdown(not_item)
