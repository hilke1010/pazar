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

# --- MAKİNE ÖĞRENMESİ VE ANOMALİ ANALİZİ ---
def gelismis_analiz_raporu(df_main, sehir, segment):
    col_pay = segment + " Pay"
    col_ton = segment + " Ton"
    
    # Tarihleri Belirle
    son_tarih = df_main['Tarih'].max()
    onceki_ay = son_tarih - relativedelta(months=1)
    gecen_yil = son_tarih - relativedelta(years=1)
    
    son_donem_str = format_tarih_tr(son_tarih)
    
    pazar_analizi = []
    likitgaz_analizi = []
    rakip_analizi = []
    
    # --- 1. PAZAR BÜYÜKLÜĞÜ ANALİZİ (MoM & YoY) ---
    # Her dönem için toplam tonajı hesapla
    toplamlar = df_main.groupby('Tarih')[col_ton].sum()
    
    ton_simdi = toplamlar.get(son_tarih, 0)
    ton_gecen_ay = toplamlar.get(onceki_ay, 0)
    ton_gecen_yil = toplamlar.get(gecen_yil, 0)
    
    pazar_analizi.append(f"### 🌍 Pazar Büyüklüğü Analizi ({son_donem_str})")
    pazar_analizi.append(f"Bu ay **{sehir}** genelinde toplam **{ton_simdi:,.0f} ton** {segment} satışı gerçekleşti.")
    
    # Aylık Değişim (MoM)
    if ton_gecen_ay > 0:
        degisim_ay = ((ton_simdi - ton_gecen_ay) / ton_gecen_ay) * 100
        if degisim_ay > 0:
            pazar_analizi.append(f"- 📊 Geçen aya göre: **%{degisim_ay:.1f} BÜYÜME** 📈 (Önceki: {ton_gecen_ay:,.0f} ton)")
        else:
            pazar_analizi.append(f"- 📊 Geçen aya göre: **%{abs(degisim_ay):.1f} DARALMA** 📉 (Önceki: {ton_gecen_ay:,.0f} ton)")
    
    # Yıllık Değişim (YoY)
    if ton_gecen_yil > 0:
        degisim_yil = ((ton_simdi - ton_gecen_yil) / ton_gecen_yil) * 100
        icon = "📈" if degisim_yil > 0 else "📉"
        durum = "BÜYÜME" if degisim_yil > 0 else "DARALMA"
        pazar_analizi.append(f"- 📅 Geçen yılın aynı ayına göre: **%{abs(degisim_yil):.1f} {durum}** {icon} (Geçen Yıl: {ton_gecen_yil:,.0f} ton)")
    else:
        pazar_analizi.append("- 📅 Geçen yılın verisi bulunamadığı için yıllık karşılaştırma yapılamadı.")
        
    pazar_analizi.append("---")

    # --- 2. LİKİTGAZ DETAYLI ANALİZİ ---
    df_likit = df_main[df_main['Şirket'] == LIKITGAZ_NAME].sort_values('Tarih')
    
    likitgaz_analizi.append(f"### 🔴 Likitgaz Performansı")
    if not df_likit.empty:
        for i in range(len(df_likit)):
            curr = df_likit.iloc[i]
            tarih_str = format_tarih_tr(curr['Tarih'])
            pay = curr[col_pay]
            ton = curr[col_ton]
            
            # İlk veri
            if i == 0:
                likitgaz_analizi.append(f"- **{tarih_str}:** %{pay:.2f} pay ile başlangıç.")
                continue
            
            prev = df_likit.iloc[i-1]
            diff_pay = pay - prev[col_pay]
            diff_ton_yuzde = ((ton - prev[col_ton]) / prev[col_ton] * 100) if prev[col_ton] > 0 else 0
            
            # Yorum Mantığı
            yorum = ""
            icon = "➡️"
            
            if diff_pay > 0:
                icon = "↗️"
                if diff_pay > 1.0: icon = "🚀" # Sert yükseliş
                yorum = f"Pazar payı **{diff_pay:+.2f}** puan arttı."
            elif diff_pay < 0:
                icon = "↘️"
                if diff_pay < -1.0: icon = "🔻" # Sert düşüş
                yorum = f"Pazar payı **{abs(diff_pay):.2f}** puan geriledi."
            
            # Satış hacmi ile karşılaştırma
            if diff_ton_yuzde > 0 and diff_pay < 0:
                yorum += f" (Satış tonajı %{diff_ton_yuzde:.1f} artmasına rağmen pazar payı düştü -> **Pazar bizden hızlı büyüdü**)"
            elif diff_ton_yuzde < 0 and diff_pay > 0:
                yorum += f" (Satış tonajı düşmesine rağmen pazar payı arttı -> **Rakipler daha çok müşteri kaybetti**)"

            likitgaz_analizi.append(f"- {icon} **{tarih_str}:** %{pay:.2f} ({yorum})")
    else:
        likitgaz_analizi.append("Veri bulunamadı.")

    # --- 3. RAKİP RADARI (AFAKİ HAREKETLER) ---
    # Sadece son ayın verisine göre analiz yapalım
    son_df = df_main[df_main['Tarih'] == son_tarih]
    onceki_df = df_main[df_main['Tarih'] == onceki_ay]
    
    rakip_analizi.append(f"### 📡 Rakip İzleme Radarı ({son_donem_str})")
    
    if not son_df.empty and not onceki_df.empty:
        # Pazar payı %1'in üzerinde olan şirketleri incele
        onemli_sirketler = son_df[son_df[col_pay] > 1.0]['Şirket'].tolist()
        
        anomali_var_mi = False
        
        for sirket in onemli_sirketler:
            if sirket == LIKITGAZ_NAME: continue
            
            try:
                curr_pay = son_df[son_df['Şirket'] == sirket][col_pay].values[0]
                prev_pay = onceki_df[onceki_df['Şirket'] == sirket][col_pay].values[0] if sirket in onceki_df['Şirket'].values else 0
                
                fark = curr_pay - prev_pay
                
                # EŞİKLER (Thresholds) - Afaki Hareket Tanımı
                # 1. Pazar Payı 1.0 puandan fazla değiştiyse (Çok büyük olay)
                # 2. Veya kendi hacminde %20'den fazla oynama olduysa (opsiyonel)
                
                if fark <= -1.5: # ÇÖKÜŞ (TP Örneği gibi)
                    rakip_analizi.append(f"🛑 **{sirket}:** KRİTİK DÜŞÜŞ! Pazar payı **{prev_pay:.2f}%** seviyesinden **{curr_pay:.2f}%** seviyesine çakıldı. (Fark: {fark:.2f} puan)")
                    anomali_var_mi = True
                elif fark >= 1.5: # RALLİ
                    rakip_analizi.append(f"🔥 **{sirket}:** AFAKİ YÜKSELİŞ! Pazar payını **{fark:+.2f}** puan artırarak **%{curr_pay:.2f}** seviyesine fırladı.")
                    anomali_var_mi = True
                elif fark <= -0.7: # DİKKAT ÇEKEN DÜŞÜŞ
                    rakip_analizi.append(f"📉 **{sirket}:** Kan kaybetti. Pazar payı {fark:.2f} puan düştü.")
                    anomali_var_mi = True
                elif fark >= 0.7: # DİKKAT ÇEKEN YÜKSELİŞ
                    rakip_analizi.append(f"📈 **{sirket}:** Çıkış yakaladı. Pazar payı {fark:+.2f} puan arttı.")
                    anomali_var_mi = True
                    
            except: continue
            
        if not anomali_var_mi:
            rakip_analizi.append("✅ Rakiplerde bu ay 'afaki' (olağandışı) bir kırılma tespit edilmedi. Pazar stabil.")
    else:
        rakip_analizi.append("Kıyaslama için yeterli veri yok.")

    return pazar_analizi, likitgaz_analizi, rakip_analizi

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
        
        # --- SEKME 1: GRAFİK ---
        with tab1:
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                sirketler = sorted(df_sehir['Şirket'].unique())
                defaults = [LIKITGAZ_NAME] if LIKITGAZ_NAME in sirketler else []
                top_3 = df_sehir.groupby('Şirket')[secilen_segment + " Pay"].mean().nlargest(4).index.tolist()
                defaults += [s for s in top_3 if s != LIKITGAZ_NAME]
                secilen_sirketler = st.multiselect("Grafik İçin Şirketler", sirketler, default=defaults[:5])
                
            with col_filter2:
                veri_tipi = st.radio("Gösterim Tipi:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
                y_column = secilen_segment + " Pay" if veri_tipi == "Pazar Payı (%)" else secilen_segment + " Ton"

            if secilen_sirketler:
                df_chart = df_sehir[df_sehir['Şirket'].isin(secilen_sirketler)]
                color_map = {s: OTHER_COLORS[i % len(OTHER_COLORS)] for i, s in enumerate(secilen_sirketler)}
                if LIKITGAZ_NAME in color_map: color_map[LIKITGAZ_NAME] = LIKITGAZ_COLOR
                
                fig = px.line(df_chart, x='Tarih', y=y_column, color='Şirket', markers=True,
                              color_discrete_map=color_map, title=f"{secilen_sehir} - {secilen_segment} - {veri_tipi}")
                fig.update_xaxes(dtick="M1", tickformat="%b %Y", ticktext=df_chart['Dönem'].unique(), tickvals=df_chart['Tarih'].unique())
                fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
                fig.update_traces(patch={"line": {"width": 4}}, selector={"legendgroup": LIKITGAZ_NAME})
                st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("---")
            st.subheader("📋 Dönemsel Sıralama Tablosu")
            
            mevcut_donemler = df_sehir.sort_values('Tarih', ascending=False)['Dönem'].unique()
            secilen_tablo_donemi = st.selectbox("Görüntülenecek Dönemi Seçin:", mevcut_donemler)
            
            col_ton = secilen_segment + " Ton"
            col_pay = secilen_segment + " Pay"
            
            df_table_filtered = df_sehir[df_sehir['Dönem'] == secilen_tablo_donemi].copy()
            df_table_filtered = df_table_filtered.sort_values(col_pay, ascending=False).reset_index(drop=True)
            df_table_filtered.index += 1
            
            st.dataframe(
                df_table_filtered[['Şirket', col_ton, col_pay]].style.format({col_pay: "{:.2f}%", col_ton: "{:,.2f}"}), 
                use_container_width=True
            )

        # --- SEKME 2: GELİŞMİŞ ANALİZ ---
        with tab2:
            pazar_txt, likitgaz_txt, rakip_txt = gelismis_analiz_raporu(df_sehir, secilen_sehir, secilen_segment)
            
            # 1. PAZAR BÜYÜKLÜĞÜ
            for line in pazar_txt: st.markdown(line)
            
            col_l, col_r = st.columns(2)
            
            # 2. LİKİTGAZ
            with col_l:
                for line in likitgaz_txt: st.markdown(line)
            
            # 3. RAKİPLER (AFAKİ DURUMLAR)
            with col_r:
                for line in rakip_txt: 
                    if "🛑" in line or "🔥" in line:
                        st.error(line) # Kritik durumları kırmızı kutuda göster
                    else:
                        st.info(line)
