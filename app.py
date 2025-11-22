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
    # Tablo 3.9'dan gelen şehir isimlerini düzelt (ANKARA -> Ankara)
    if not sehir: return ""
    # Türkçe karakter sorunu yaşamamak için basit mapping veya title()
    # Basitçe title() yapalım ama I/İ sorununa dikkat
    return sehir.replace('İ', 'i').replace('I', 'ı').title()

# --- ANALİZ MOTORU ---

def turkiye_pazar_analizi(df_iller, segment):
    """
    Artık df_main (Şirketler) yerine df_iller (Resmi İl Tablosu) kullanılıyor.
    """
    col_ton = segment + " Ton"
    
    son_tarih = df_iller['Tarih'].max()
    onceki_ay = son_tarih - relativedelta(months=1)
    gecen_yil = son_tarih - relativedelta(years=1)
    son_donem_str = format_tarih_tr(son_tarih)
    
    # Türkiye Toplamı (İller tablosundaki o tarihe ait tüm satırların toplamı)
    toplamlar = df_iller.groupby('Tarih')[col_ton].sum()
    
    ton_simdi = toplamlar.get(son_tarih, 0)
    ton_gecen_ay = toplamlar.get(onceki_ay, 0)
    ton_gecen_yil = toplamlar.get(gecen_yil, 0)
    
    rapor = []
    rapor.append(f"### 🇹🇷 TÜRKİYE GENELİ - {segment.upper()} PAZAR RAPORU ({son_donem_str})")
    rapor.append(f"Resmi verilere göre Türkiye genelinde bu ay toplam **{ton_simdi:,.0f} ton** {segment} satışı gerçekleşti.")
    
    analist_yorumu = ""
    
    # Aylık Analiz
    if ton_gecen_ay > 0:
        fark = ton_simdi - ton_gecen_ay
        yuzde = (fark / ton_gecen_ay) * 100
        durum = "büyüyerek" if yuzde > 0 else "küçülerek"
        icon = "📈" if yuzde > 0 else "📉"
        rapor.append(f"- **Aylık:** Geçen aya göre pazar **%{abs(yuzde):.1f}** oranında {durum} **{abs(fark):,.0f} ton** fark oluştu. {icon}")
        if yuzde > 0: analist_yorumu = "Pazar kısa vadede canlılık gösteriyor."
        else: analist_yorumu = "Kısa vadede talep daralması gözleniyor."
        
    # Yıllık Analiz
    if ton_gecen_yil > 0:
        fark_yil = ton_simdi - ton_gecen_yil
        yuzde_yil = (fark_yil / ton_gecen_yil) * 100
        durum_yil = "büyüme" if yuzde_yil > 0 else "daralma"
        icon_yil = "🚀" if yuzde_yil > 0 else "🔻"
        rapor.append(f"- **Yıllık:** Geçen yılın aynı ayına göre **%{abs(yuzde_yil):.1f}** oranında {durum_yil} var. {icon_yil}")
        
        if yuzde > 0 and yuzde_yil > 0: analist_yorumu = "Hem aylık hem yıllık bazda pozitif seyir var. Sektör büyüme trendinde."
        elif yuzde < 0 and yuzde_yil < 0: analist_yorumu = "Hem aylık hem yıllık bazda düşüş var. Sektör genelinde durgunluk hakim."
        elif yuzde > 0 and yuzde_yil < 0: analist_yorumu = "Yıllık bazda düşüş olsa da, son ayda toparlanma sinyalleri (Recovery) var."
        elif yuzde < 0 and yuzde_yil > 0: analist_yorumu = "Yıllık trend pozitif olsa da, son ayda mevsimsel bir gevşeme var."
            
    rapor.append(f"> **💡 Analist Görüşü:** {analist_yorumu}")
    rapor.append("---")
    return rapor

def stratejik_analiz_raporu(df_sirket, df_iller, sehir, segment):
    """
    Pazar Büyüklüğü -> df_iller (Tablo 3.9)
    Şirket/Rakip Analizi -> df_sirket (Tablo 4.7)
    """
    col_pay = segment + " Pay"
    col_ton_sirket = segment + " Ton"  # Şirket verisindeki tonaj
    col_ton_il = segment + " Ton"      # İl verisindeki tonaj
    
    # Tarihleri Ayarla
    son_tarih = df_sirket['Tarih'].max()
    onceki_ay = son_tarih - relativedelta(months=1)
    gecen_yil = son_tarih - relativedelta(years=1)
    son_donem_str = format_tarih_tr(son_tarih)
    
    pazar_raporu = []
    likitgaz_raporu = []
    rakip_raporu = []

    # 1. PAZAR BÜYÜKLÜĞÜ (RESMİ İL TABLOSUNDAN)
    # Seçilen şehre göre filtrele
    df_sehir_resmi = df_iller[df_iller['Şehir'].str.upper() == sehir.upper()]
    
    # Şehir toplamlarını al
    ton_simdi = df_sehir_resmi[df_sehir_resmi['Tarih'] == son_tarih][col_ton_il].sum()
    ton_gecen_ay = df_sehir_resmi[df_sehir_resmi['Tarih'] == onceki_ay][col_ton_il].sum()
    ton_gecen_yil = df_sehir_resmi[df_sehir_resmi['Tarih'] == gecen_yil][col_ton_il].sum()
    
    pazar_raporu.append(f"### 🌍 {sehir} - {segment} Pazar Büyüklüğü ({son_donem_str})")
    pazar_raporu.append(f"Bu ay **{sehir}** genelinde toplam **{ton_simdi:,.0f} ton** satış gerçekleşti (Resmi Veri).")
    
    if ton_gecen_ay > 0:
        degisim_ay = ((ton_simdi - ton_gecen_ay) / ton_gecen_ay) * 100
        fark = ton_simdi - ton_gecen_ay
        icon = "📈" if degisim_ay > 0 else "📉"
        fiil = "büyüyerek" if degisim_ay > 0 else "küçülerek"
        pazar_raporu.append(f"- **Aylık:** {icon} Geçen aya göre pazar **%{abs(degisim_ay):.1f}** oranında {fiil} **{abs(fark):,.0f} ton** fark kaydetti.")
        
    if ton_gecen_yil > 0:
        degisim_yil = ((ton_simdi - ton_gecen_yil) / ton_gecen_yil) * 100
        icon = "🚀" if degisim_yil > 5 else ("🔻" if degisim_yil < -5 else "⚖️")
        durum = "büyüme" if degisim_yil > 0 else "daralma"
        pazar_raporu.append(f"- **Yıllık:** {icon} Geçen yıla göre **%{abs(degisim_yil):.1f}** oranında {durum} var.")
    else:
        pazar_raporu.append("- Yıllık veri yetersiz.")
        
    pazar_raporu.append("---")

    # 2. LİKİTGAZ ANALİZİ (Şirket Tablosundan)
    likitgaz_raporu.append(f"### 🔴 Likitgaz Performans Tarihçesi ({sehir})")
    # Sadece seçilen şehirdeki Likitgaz verisini al
    df_likit = df_sirket[(df_sirket['Şirket'] == LIKITGAZ_NAME) & (df_sirket['Şehir'] == sehir)].sort_values('Tarih')
    
    if not df_likit.empty:
        for i in range(len(df_likit)):
            curr = df_likit.iloc[i]
            tarih_str = format_tarih_tr(curr['Tarih'])
            pay = curr[col_pay]
            
            if i == 0:
                likitgaz_raporu.append(f"- **{tarih_str}:** 🏁 Başlangıç: %{pay:.2f}")
                continue
            
            prev = df_likit.iloc[i-1]
            diff_pay = pay - prev[col_pay]
            
            icon = "➡️"
            yorum = "Yatay."
            if diff_pay > 1.5: icon, yorum = "🚀", "**Güçlü Çıkış!**"
            elif diff_pay > 0.2: icon, yorum = "↗️", "Yükseliş."
            elif diff_pay < -1.5: icon, yorum = "🔻", "**Sert Düşüş!**"
            elif diff_pay < -0.2: icon, yorum = "↘️", "Düşüş."
            
            likitgaz_raporu.append(f"- {icon} **{tarih_str}:** Pay: %{pay:.2f} | {yorum}")
    else:
        likitgaz_raporu.append("Likitgaz verisi bulunamadı.")

    # 3. RAKİP ANALİZİ (Şirket Tablosundan)
    rakip_raporu.append(f"### 📡 Rakip Trend Analizi ({sehir})")
    # Sadece seçilen şehirdeki rakipler
    df_sehir_sirket = df_sirket[df_sirket['Şehir'] == sehir]
    
    son_df = df_sehir_sirket[df_sehir_sirket['Tarih'] == son_tarih].sort_values(col_pay, ascending=False)
    rakipler = son_df[(son_df['Şirket'] != LIKITGAZ_NAME) & (son_df[col_pay] > 2.0)].head(7)['Şirket'].tolist()
    
    yakalanan = 0
    for rakip in rakipler:
        df_rakip = df_sehir_sirket[df_sehir_sirket['Şirket'] == rakip].sort_values('Tarih').tail(6)
        if len(df_rakip) < 2: continue
        
        son_veri = df_rakip.iloc[-1]
        curr_pay = son_veri[col_pay]
        onceki_veri = df_rakip.iloc[-2]
        fark_aylik = curr_pay - onceki_veri[col_pay]
        
        max_pay = df_rakip[col_pay].max()
        zirve_row = df_rakip.loc[df_rakip[col_pay].idxmax()]
        zirve_donemi = zirve_row['Dönem']
        fark_zirve = curr_pay - max_pay
        
        mesaj = ""
        kutu_tipi = "info"
        
        if fark_zirve < -1.0:
            mesaj = f"📉 **DÜŞÜŞ TRENDİ:** **{zirve_donemi}** ayındaki zirvesinden (%{max_pay:.2f}) sonra **{fark_zirve:.2f}** puan kaybetti."
            kutu_tipi = "error"
        elif fark_aylik > 1.5:
             mesaj = f"🔥 **AFAKİ YÜKSELİŞ:** Son ayda **+{fark_aylik:.2f}** puan sıçradı."
             kutu_tipi = "success"
        elif fark_aylik < -1.5 and kutu_tipi != "error":
             mesaj = f"🔻 **SERT DÜŞÜŞ:** Son ayda **{fark_aylik:.2f}** puan kaybetti."
             kutu_tipi = "warning"
             
        if mesaj:
            yakalanan += 1
            if kutu_tipi == "error": rakip_raporu.append(f"🔴 **{rakip}:** {mesaj} (Pay: %{curr_pay:.2f})")
            elif kutu_tipi == "success": rakip_raporu.append(f"🟢 **{rakip}:** {mesaj} (Pay: %{curr_pay:.2f})")
            elif kutu_tipi == "warning": rakip_raporu.append(f"🟠 **{rakip}:** {mesaj} (Pay: %{curr_pay:.2f})")
            else: rakip_raporu.append(f"🔵 **{rakip}:** {mesaj}")
            rakip_raporu.append("---")
            
    if yakalanan == 0: rakip_raporu.append("✅ Rakiplerde olağandışı bir hareket yok.")

    return pazar_raporu, likitgaz_raporu, rakip_raporu

# --- GÜNCELLENMİŞ VERİ OKUMA (İKİ TABLO TÜRÜNÜ DE OKUR) ---
@st.cache_data
def verileri_oku():
    tum_veri_sirket = []
    tum_veri_iller = []
    sirket_listesi = set()
    
    files = sorted([f for f in os.listdir(DOSYA_KLASORU) if f.endswith('.docx') or f.endswith('.doc')])
    
    for dosya in files:
        tarih = dosya_isminden_tarih(dosya)
        if not tarih: continue
        path = os.path.join(DOSYA_KLASORU, dosya)
        try: doc = Document(path)
        except: continue
        
        # 1. PARAGRAFLARI TARAYARAK TABLOLARI BULMA
        # Word'deki sırayı takip ediyoruz.
        # Eğer paragrafta "İllere" ve "Dağılımı" varsa sonraki tablo İl tablosudur.
        # Eğer paragrafta "Tablo" ve ":" varsa sonraki tablo Şirket tablosudur.
        
        iter_elem = iter_block_items(doc)
        son_baslik = ""
        son_sehir_sirket = None # Şirket tablosu için şehir
        
        for block in iter_elem:
            if isinstance(block, Paragraph):
                text = block.text.strip()
                if len(text) > 5:
                    son_baslik = text
                    # Şirket tablosu başlığı yakalama (Tablo 4.7: Ankara)
                    if text.startswith("Tablo") and ":" in text:
                         parts = text.split(":")
                         if len(parts)>1 and 2<len(parts[1].strip())<40:
                             son_sehir_sirket = parts[1].strip()
                    else:
                        son_sehir_sirket = None # Başka bir başlık geldiyse sıfırla

            elif isinstance(block, Table):
                # A) İL ÖZET TABLOSU KONTROLÜ (Tablo 3.9 benzeri)
                if "İLLERE" in son_baslik.upper() and "DAĞILIMI" in son_baslik.upper():
                    try:
                        # İlk satır başlıklar mı?
                        # Resimdeki yapı: 
                        # Row 0: İl | Tüplü | Dökme | Otogaz | Toplam (Merged)
                        # Row 1: ... | Satış | Pay | Satış | Pay ...
                        # Biz direkt indeksle alalım çünkü format standarttır.
                        # Col 0: İl Adı
                        # Col 1: Tüplü Ton, Col 3: Dökme Ton, Col 5: Otogaz Ton
                        
                        for row in block.rows:
                            cells = row.cells
                            if len(cells) < 6: continue
                            il_adi = cells[0].text.strip()
                            
                            # Başlık satırlarını atla
                            if il_adi == "" or "İL" in il_adi.upper() or "TOPLAM" in il_adi.upper():
                                continue
                            
                            try:
                                il_duzgun = sehir_ismi_duzelt(il_adi)
                                t_ton = sayi_temizle(cells[1].text)
                                d_ton = sayi_temizle(cells[3].text)
                                o_ton = sayi_temizle(cells[5].text)
                                
                                if t_ton + d_ton + o_ton > 0:
                                    tum_veri_iller.append({
                                        'Tarih': tarih,
                                        'Şehir': il_duzgun,
                                        'Tüplü Ton': t_ton,
                                        'Dökme Ton': d_ton,
                                        'Otogaz Ton': o_ton
                                    })
                            except: continue
                    except: pass

                # B) ŞİRKET DAĞILIM TABLOSU KONTROLÜ (Tablo 4.7 vb)
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
                                    t_ton = sayi_temizle(cells[1].text)
                                    t_pay = sayi_temizle(cells[2].text)
                                    d_ton = sayi_temizle(cells[3].text)
                                    d_pay = sayi_temizle(cells[4].text)
                                    o_ton = sayi_temizle(cells[5].text)
                                    o_pay = sayi_temizle(cells[6].text)
                                    if t_ton+t_pay+d_ton+d_pay+o_ton+o_pay > 0:
                                        tum_veri_sirket.append({
                                            'Tarih': tarih, 'Şehir': sehir_ismi_duzelt(son_sehir_sirket), 'Şirket': std_isim, 
                                            'Tüplü Pay': t_pay, 'Tüplü Ton': t_ton,
                                            'Dökme Pay': d_pay, 'Dökme Ton': d_ton,
                                            'Otogaz Pay': o_pay, 'Otogaz Ton': o_ton
                                        })
                                except: continue
                    except: pass
                    
    df_sirket = pd.DataFrame(tum_veri_sirket)
    df_iller = pd.DataFrame(tum_veri_iller)
    
    if not df_sirket.empty:
        df_sirket = df_sirket.sort_values('Tarih')
        df_sirket['Dönem'] = df_sirket['Tarih'].apply(format_tarih_tr)
        
    if not df_iller.empty:
        df_iller = df_iller.sort_values('Tarih')
        df_iller['Dönem'] = df_iller['Tarih'].apply(format_tarih_tr)
        
    return df_sirket, df_iller

# --- ARAYÜZ ---
st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")
st.title("📊 EPDK Stratejik Pazar Analizi")

if not os.path.exists(DOSYA_KLASORU):
    st.error(f"'{DOSYA_KLASORU}' klasörü bulunamadı.")
else:
    df_sirket, df_iller = verileri_oku()
    
    if df_sirket.empty:
        st.warning("Veri yok.")
    else:
        st.sidebar.header("⚙️ Parametreler")
        # Şehir listesini Şirket tablosundan al (Analiz yapabileceğimiz şehirler)
        sehirler = sorted(df_sirket['Şehir'].unique())
        # Ankara yoksa ilkini seç
        default_idx = sehirler.index('Ankara') if 'Ankara' in sehirler else 0
        secilen_sehir = st.sidebar.selectbox("Şehir", sehirler, index=default_idx)
        
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("Segment", segmentler)
        
        # Filtreleme
        df_sehir_sirket = df_sirket[df_sirket['Şehir'] == secilen_sehir]
        
        tab1, tab2 = st.tabs(["📈 Görsel & Tablo", "🧠 Makine Öğrenmesi Analizi"])
        
        # --- SEKME 1: GRAFİK ---
        with tab1:
            col_filter1, col_filter2 = st.columns(2)
            with col_filter1:
                sirketler = sorted(df_sehir_sirket['Şirket'].unique())
                defaults = [LIKITGAZ_NAME] if LIKITGAZ_NAME in sirketler else []
                top_3 = df_sehir_sirket.groupby('Şirket')[secilen_segment + " Pay"].mean().nlargest(4).index.tolist()
                defaults += [s for s in top_3 if s != LIKITGAZ_NAME]
                secilen_sirketler = st.multiselect("Grafik İçin Şirketler", sirketler, default=defaults[:5])
                
            with col_filter2:
                veri_tipi = st.radio("Gösterim Tipi:", ["Pazar Payı (%)", "Satış Miktarı (Ton)"], horizontal=True)
                y_column = secilen_segment + " Pay" if veri_tipi == "Pazar Payı (%)" else secilen_segment + " Ton"

            if secilen_sirketler:
                df_chart = df_sehir_sirket[df_sehir_sirket['Şirket'].isin(secilen_sirketler)]
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
            mevcut_donemler = df_sehir_sirket.sort_values('Tarih', ascending=False)['Dönem'].unique()
            secilen_tablo_donemi = st.selectbox("Görüntülenecek Dönemi Seçin:", mevcut_donemler)
            col_ton = secilen_segment + " Ton"
            col_pay = secilen_segment + " Pay"
            df_table_filtered = df_sehir_sirket[df_sehir_sirket['Dönem'] == secilen_tablo_donemi].copy()
            df_table_filtered = df_table_filtered.sort_values(col_pay, ascending=False).reset_index(drop=True)
            df_table_filtered.index += 1
            st.dataframe(df_table_filtered[['Şirket', col_ton, col_pay]].style.format({col_pay: "{:.2f}%", col_ton: "{:,.2f}"}), use_container_width=True)

        # --- SEKME 2: ANALİZ ---
        with tab2:
            # 1. TÜRKİYE GENELİ (df_iller'den)
            if not df_iller.empty:
                turkiye_raporu = turkiye_pazar_analizi(df_iller, secilen_segment)
                st.info("🇹🇷 Türkiye Geneli Özet Bilgi")
                for line in turkiye_raporu: st.markdown(line)
            else:
                st.warning("İl özeti tablosu okunamadığı için Türkiye geneli analizi yapılamıyor.")
                
            st.markdown("---")
            
            # 2. ŞEHİR VE ŞİRKET ANALİZİ
            # Pazar büyüklüğü için df_iller, şirket detayları için df_sehir_sirket gönderiyoruz
            if not df_iller.empty:
                pazar_txt, likitgaz_txt, rakip_txt = stratejik_analiz_raporu(df_sehir_sirket, df_iller, secilen_sehir, secilen_segment)
                
                for line in pazar_txt: st.markdown(line)
                col_l, col_r = st.columns([1, 1])
                with col_l:
                    for line in likitgaz_txt: st.markdown(line)
                with col_r:
                    for line in rakip_txt: 
                        if "🛑" in line or "🔴" in line: st.error(line)
                        elif "🔥" in line or "🟢" in line: st.success(line)
                        elif "📉" in line or "🟠" in line: st.warning(line)
                        else: st.info(line)
            else:
                 st.error("İl verisi eksik.")
