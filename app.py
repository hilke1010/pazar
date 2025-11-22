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
import locale

# --- AYARLAR ---
DOSYA_KLASORU = 'raporlar'

# Türkçe Ay İsimleri Haritalaması (Grafik ve Tablo Görünümü İçin)
TR_AYLAR = {
    1: 'Ocak', 2: 'Şubat', 3: 'Mart', 4: 'Nisan', 5: 'Mayıs', 6: 'Haziran',
    7: 'Temmuz', 8: 'Ağustos', 9: 'Eylül', 10: 'Ekim', 11: 'Kasım', 12: 'Aralık'
}

# Dosya isminden okumak için (küçük harf)
DOSYA_AY_MAP = {
    'ocak': 1, 'subat': 2, 'mart': 3, 'nisan': 4, 'mayis': 5, 'haziran': 6,
    'temmuz': 7, 'agustos': 8, 'eylul': 9, 'ekim': 10, 'kasim': 11, 'aralik': 12
}


# --- YARDIMCI FONKSİYONLAR ---

def format_tarih_tr(date_obj):
    """Tarih objesini 'Ocak 2024' formatına çevirir."""
    if pd.isna(date_obj): return ""
    ay_isim = TR_AYLAR.get(date_obj.month, "")
    yil_isim = str(date_obj.year)[2:]  # 2024 -> 24
    # İsteğe bağlı: Uzun yıl istenirse str(date_obj.year) yapılabilir.
    return f"{ay_isim} {date_obj.year}"


def iter_block_items(parent):
    """Word dokümanını sırayla okur."""
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
    # Türkçe karakterleri İngilizceye çevirerek dosya ismini normalize et (şubat -> subat gibi)
    base = base.lower().replace('ş', 's').replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u').replace('ö',
                                                                                                        'o').replace(
        'ç', 'c')

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
        # 7.432,81 -> 7432.81
        clean = text.replace('.', '').replace(',', '.')
        return float(clean)
    except:
        return 0.0


def sirket_ismi_standartlastir(isim, mevcut_isimler, esik=92):
    """
    Şirket isimlerini birleştirir.
    DİKKAT: Eşik değerini 92'ye çıkardım.
    Böylece 'AKPET GAZ' ile 'AKÇAGAZ' gibi farklı firmalar karışmayacak.
    Sadece 'AYGAZ A.Ş.' ile 'AYGAZ A.S.' birleşecek.
    """
    isim_upper = isim.strip().upper()
    isim_clean = " ".join(isim_upper.split())  # Fazla boşlukları al

    if not mevcut_isimler:
        return isim_clean

    en_iyi_eslesme, skor = process.extractOne(isim_clean, mevcut_isimler)

    if skor >= esik:
        return en_iyi_eslesme
    else:
        return isim_clean


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
        if not tarih:
            continue

        path = os.path.join(DOSYA_KLASORU, dosya)
        try:
            doc = Document(path)
        except:
            continue

        status_text.text(f"İşleniyor ({i + 1}/{len(files)}): {dosya}")

        son_sehir = None
        iterator = iter_block_items(doc)

        for block in iterator:
            if isinstance(block, Paragraph):
                text = block.text.strip()
                # Şehir yakalama: "Tablo 4.7: Ankara" formatı
                if text.startswith("Tablo") and ":" in text:
                    parts = text.split(":")
                    if len(parts) > 1:
                        potansiyel_sehir = parts[1].strip()
                        # Şehir ismi mantıklı uzunlukta mı?
                        if 2 < len(potansiyel_sehir) < 40:
                            son_sehir = potansiyel_sehir

            elif isinstance(block, Table):
                if son_sehir:
                    try:
                        # Tablo başlığını kontrol et (Tüplü / Dökme kelimeleri geçiyor mu?)
                        header_rows_text = ""
                        for r in range(min(2, len(block.rows))):  # İlk 2 satıra bak
                            for c in block.rows[r].cells:
                                header_rows_text += c.text.lower()

                        if "tüplü" in header_rows_text or "dökme" in header_rows_text or "pay" in header_rows_text:

                            # Satırları işle
                            for row in block.rows:
                                cells = row.cells
                                # Hücre sayısı kontrolü (En az 7 sütun olmalı: İsim + 3x(Satış+Pay))
                                if len(cells) < 7:
                                    continue

                                ham_isim = cells[0].text.strip()

                                # Başlık veya Toplam satırlarını atla
                                if "LİSANS" in ham_isim.upper() or "TOPLAM" in ham_isim.upper() or ham_isim == "":
                                    continue
                                if "UNVANI" in ham_isim.upper():
                                    continue

                                # Şirket ismini temizle ve standartlaştır
                                std_isim = sirket_ismi_standartlastir(ham_isim, sirket_listesi)
                                sirket_listesi.add(std_isim)

                                try:
                                    # Sütun İndeksleri (Görsele göre):
                                    # 0: İsim, 2: Tüplü Pay, 4: Dökme Pay, 6: Otogaz Pay
                                    tuplu_pay = sayi_temizle(cells[2].text)
                                    dokme_pay = sayi_temizle(cells[4].text)
                                    otogaz_pay = sayi_temizle(cells[6].text)

                                    # Veriyi ekle (Eğer tüm paylar 0 ise ekleme, kalabalık yapmasın)
                                    if tuplu_pay + dokme_pay + otogaz_pay > 0:
                                        tum_veri.append({
                                            'Tarih': tarih,
                                            'Şehir': son_sehir,
                                            'Şirket': std_isim,
                                            'Tüplü': tuplu_pay,
                                            'Dökme': dokme_pay,
                                            'Otogaz': otogaz_pay
                                        })
                                except Exception as e:
                                    continue

                    except Exception as e:
                        pass  # Tablo okuma hatası

                # Tablo bitti, şehri sıfırla (ki sonraki alakasız tabloları bu şehre yazmasın)
                son_sehir = None

    status_text.empty()
    progress_bar.empty()

    df = pd.DataFrame(tum_veri)
    if not df.empty:
        # Tarihi sıralama için kullanacağız, ama Türkçe gösterim için yeni kolon ekle
        df = df.sort_values('Tarih')
        df['Dönem'] = df['Tarih'].apply(format_tarih_tr)

    return df


# --- ARAYÜZ ---

st.set_page_config(page_title="EPDK Pazar Analizi", layout="wide")
st.title("📈 EPDK Sektör Raporu Analiz Aracı")

if not os.path.exists(DOSYA_KLASORU):
    st.error(f"Lütfen '{DOSYA_KLASORU}' klasörünü oluşturun.")
else:
    df = verileri_oku()

    if df.empty:
        st.warning("Veri bulunamadı. Word dosyalarındaki tablo formatını kontrol edin.")
    else:
        # --- SOL MENÜ (FİLTRELER) ---
        st.sidebar.header("Filtreler")

        # Şehir Seçimi
        sehirler = sorted(df['Şehir'].unique())
        secilen_sehir = st.sidebar.selectbox("Şehir", sehirler,
                                             index=sehirler.index('Ankara') if 'Ankara' in sehirler else 0)

        # Segment Seçimi
        segmentler = ['Otogaz', 'Tüplü', 'Dökme']
        secilen_segment = st.sidebar.selectbox("Segment", segmentler)

        # Şirket Seçimi (Multiselect)
        df_sehir = df[df['Şehir'] == secilen_sehir]
        # Şirketleri alfabetik sırala
        sirketler = sorted(df_sehir['Şirket'].unique())

        st.sidebar.markdown("---")
        st.sidebar.info(f"Toplam {len(sirketler)} dağıtıcı bulundu.")
        secilen_sirketler = st.sidebar.multiselect("Grafikte Gösterilecek Şirketler", sirketler)

        # --- 1. BÖLÜM: GRAFİK ---
        st.subheader(f"{secilen_sehir} - {secilen_segment} Pazar Payı Zaman Grafiği")

        # Grafik için veri hazırlığı
        if secilen_sirketler:
            df_chart = df_sehir[df_sehir['Şirket'].isin(secilen_sirketler)]
        else:
            # Hiçbiri seçilmezse, pazar payı en yüksek 5 şirketi varsayılan göster
            top_companies = df_sehir.groupby('Şirket')[secilen_segment].mean().nlargest(5).index.tolist()
            df_chart = df_sehir[df_sehir['Şirket'].isin(top_companies)]
            st.info(
                f"Herhangi bir şirket seçilmediği için ortalama pazar payı en yüksek 5 şirket gösteriliyor: {', '.join(top_companies)}")

        # Plotly Grafiği
        fig = px.line(
            df_chart,
            x='Tarih',
            y=secilen_segment,
            color='Şirket',
            markers=True,
            labels={secilen_segment: 'Pazar Payı (%)', 'Tarih': 'Dönem', 'Şirket': 'Dağıtıcı'},
            hover_name='Şirket',
            hover_data={'Tarih': False, 'Dönem': True, secilen_segment: ':.2f'}
        )

        # X Ekseni Formatı (Türkçe Ay İsimleri görünmesi için)
        # Tarihleri sıralı tutmak için x ekseni 'Tarih' objesi kalmalı, ancak etiketleri değiştirebiliriz.
        fig.update_xaxes(
            dtick="M1",  # Her ay bir çizgi
            tickformat="%b %Y",  # Normalde Jan 2024 yazar, ama aşağıda manuel array vereceğiz
            ticktext=df_chart['Dönem'].unique(),
            tickvals=df_chart['Tarih'].unique()
        )
        fig.update_layout(hovermode="x unified", legend=dict(orientation="h", y=1.1))
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        # --- 2. BÖLÜM: AYLIK SIRALAMA VE DETAY ---
        st.subheader("🗓️ Aylık Pazar Payı Sıralaması")

        col1, col2 = st.columns([1, 3])

        with col1:
            # Dönem Seçimi Kutusu
            mevcut_donemler = df['Dönem'].unique().tolist()
            # Dönemleri tarihe göre sıralı tutmak lazım, string yapınca karışabilir.
            # Bu yüzden 'Tarih' üzerinden unique alıp formatlayacağız.
            unique_dates = df['Tarih'].unique()
            unique_dates_sorted = sorted(unique_dates, reverse=True)  # En yeni tarih en üstte
            formatted_dates = [format_tarih_tr(pd.Timestamp(ts)) for ts in unique_dates_sorted]

            secilen_donem_str = st.selectbox("Dönem Seçin", formatted_dates)

            # Seçilen stringi tekrar Timestamp'e veya string filtrelemeye çevirmemiz lazım
            # Kolay yol: DataFrame'de string kolon ('Dönem') üzerinden filtrelemek

        with col2:
            # Seçilen Ay ve Şehre göre filtrele
            df_table = df_sehir[df_sehir['Dönem'] == secilen_donem_str].copy()

            # İlgili segment (Otogaz/Tüplü) 0'dan büyük olanları al
            df_table = df_table[df_table[secilen_segment] > 0]

            # Pazar Payına göre BÜYÜKTEN KÜÇÜĞE sırala
            df_table = df_table.sort_values(by=secilen_segment, ascending=False)

            # Tabloyu Düzenle (Sadece gerekli kolonlar)
            df_display = df_table[['Şirket', secilen_segment]].reset_index(drop=True)

            # İndeksi 1'den başlat (Sıralama numarası olsun diye)
            df_display.index = df_display.index + 1

            st.markdown(f"**{secilen_sehir} - {secilen_donem_str} - {secilen_segment} Pazar Payı Sıralaması**")

            if df_display.empty:
                st.warning("Bu dönem ve şehir için veri bulunamadı.")
            else:
                # Streamlit tablosu (Formatlı)
                st.dataframe(
                    df_display.style.format({secilen_segment: "{:.2f}%"}),
                    use_container_width=True,
                    height=400
                )