import streamlit as st
import pandas as pd
import io
from datetime import datetime

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Otomatik Kesafet", layout="wide", page_icon="🧪")

# --- MODERN VE OKUNAKLI TASARIM (YÜKSEK KONTRAST CSS) ---
st.markdown("""
    <style>
    /* Google Font */
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@300;400;600;800&display=swap');

    /* Genel Sayfa */
    .stApp {
        background: radial-gradient(circle at 10% 20%, #020617 0%, #0f172a 90%); /* Çok daha koyu zemin */
        font-family: 'Poppins', sans-serif;
        color: #ffffff;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: #020617;
        border-right: 1px solid rgba(255,255,255,0.1);
    }
    [data-testid="stSidebar"] * {
        color: #e2e8f0 !important; /* Sidebar yazıları beyaz */
    }

    /* Ana Başlık */
    .hero-title {
        font-size: 3.5rem;
        font-weight: 800;
        text-align: center;
        background: -webkit-linear-gradient(left, #FF7E5F, #00C6FF);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 10px;
        text-shadow: 0 0 20px rgba(255, 255, 255, 0.1); /* Hafif beyaz gölge */
    }
    .hero-subtitle {
        text-align: center;
        color: #e2e8f0; /* Açık Gri (Okunaklı) */
        font-size: 1.1rem;
        margin-bottom: 40px;
        font-weight: 300;
    }

    /* KPI Kutuları */
    .kpi-container {
        display: flex;
        justify-content: space-around;
        gap: 20px;
        margin-bottom: 40px;
    }
    .kpi-box {
        background: rgba(30, 41, 59, 0.6); /* Daha koyu transparan */
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.2); /* Çerçeve daha belirgin */
        border-radius: 20px;
        padding: 20px;
        width: 100%;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .kpi-label {
        color: #cbd5e1; /* Çok açık gri */
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 600;
    }
    .kpi-value {
        color: #ffffff; /* Tam Beyaz */
        font-size: 2rem;
        font-weight: 700;
        margin-top: 5px;
        text-shadow: 0 2px 4px rgba(0,0,0,0.5);
    }

    /* Müşteri Kartları */
    .glass-card {
        background: rgba(15, 23, 42, 0.8); /* Arka planı koyulaştırdım */
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 16px;
        padding: 25px;
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
    }
    .glass-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: linear-gradient(to bottom, #FF7E5F, #feb47b);
    }

    /* Kart Başlıkları */
    .card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(255,255,255,0.2);
    }
    .customer-name {
        font-size: 1.4rem;
        font-weight: 600;
        color: #ffffff; /* Tam Beyaz */
        text-shadow: 0 1px 2px rgba(0,0,0,0.8);
    }
    .customer-code {
        background: rgba(255,255,255,0.15);
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.9rem;
        color: #f1f5f9; /* Neredeyse Beyaz */
        font-weight: 500;
    }

    /* İstatistik Grid */
    .stats-row {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 15px;
    }
    .stat-item {
        background: rgba(0, 0, 0, 0.4); /* Siyah yarı saydam */
        padding: 15px;
        border-radius: 12px;
        text-align: center;
        border: 1px solid rgba(255,255,255,0.05);
    }
    .stat-title {
        font-size: 0.8rem;
        color: #cbd5e1; /* Açık Gri - OKUNAKLI OLAN BU */
        margin-bottom: 6px;
        font-weight: 600;
        text-transform: uppercase;
    }
    .stat-num {
        font-size: 1.2rem;
        font-weight: 700;
        color: #ffffff; /* Tam Beyaz */
        letter-spacing: 0.5px;
    }

    /* Renkli Vurgular (Daha Parlak) */
    .highlight-orange { color: #FF9F85 !important; text-shadow: 0 0 10px rgba(255, 126, 95, 0.4); }
    .highlight-blue { color: #38bdf8 !important; text-shadow: 0 0 10px rgba(56, 189, 248, 0.4); }

    </style>
""", unsafe_allow_html=True)

# --- BAŞLIK ALANI ---
st.markdown('<div class="hero-title">Otomatik Kesafet Ayarlama</div>', unsafe_allow_html=True)
st.markdown('<div class="hero-subtitle">Excel verilerinizi yükleyin, mevsimsel yoğunluk farklarını net bir şekilde analiz edin.</div>', unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("📂 Veri Yükleme")
    uploaded_file = st.file_uploader("Dosyayı buraya sürükle", type=["xlsx", "xls"])
    st.markdown("---")
    st.info("💡 **İpucu:** Rapor otomatik olarak koyu moda ve yüksek kontrasta uyumludur.")

# --- HESAPLAMA ---
def tr_format(sayi, ondalik=2):
    format_str = f"{{:,.{ondalik}f}}"
    return format_str.format(sayi).replace(",", "X").replace(".", ",").replace("X", ".")

def get_kesafet(tarih):
    if pd.isnull(tarih): return 0.545
    # Geçmiş dönemler
    if datetime(2021, 10, 15) <= tarih <= datetime(2022, 4, 15): return 0.545
    elif datetime(2022, 4, 15) < tarih <= datetime(2022, 10, 15): return 0.560
    elif datetime(2022, 10, 15) < tarih <= datetime(2023, 4, 15): return 0.545
    elif datetime(2023, 4, 15) < tarih <= datetime(2023, 10, 15): return 0.560
    elif datetime(2023, 10, 15) < tarih <= datetime(2024, 4, 15): return 0.545
    elif datetime(2024, 4, 15) < tarih <= datetime(2024, 10, 15): return 0.560
    elif datetime(2024, 10, 15) < tarih <= datetime(2025, 4, 20): return 0.545
    elif datetime(2025, 4, 21) <= tarih <= datetime(2025, 10, 15): return 0.560
    # YENİ EKLENEN SATIR (15 Ekim 2025 - 15 Nisan 2026 -> 0.545)
    elif datetime(2025, 10, 15) < tarih <= datetime(2026, 4, 15): return 0.545
    # Varsayılan döngü
    else: return 0.560 if 4 <= tarih.month < 10 else 0.545

# --- AKIŞ ---
if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file)
        
        req_cols = ["Sipariş veren", "Müşterinin adı", "Faturalanan miktar", "Faturalama tarihi"]
        if not all(col in df.columns for col in req_cols):
            st.error("⚠️ Excel dosyasında gerekli sütunlar eksik!")
        else:
            # İşlemler
            df['Faturalama tarihi'] = pd.to_datetime(df['Faturalama tarihi'], dayfirst=True, errors='coerce')
            df['Faturalanan miktar'] = pd.to_numeric(df['Faturalanan miktar'], errors='coerce').fillna(0)
            df['Kesafet'] = df['Faturalama tarihi'].apply(get_kesafet)
            df['Hesaplanan Litre'] = df['Faturalanan miktar'] / df['Kesafet']

            # Gruplama
            rapor = df.groupby(['Sipariş veren', 'Müşterinin adı']).agg({
                'Faturalama tarihi': ['min', 'max'],
                'Faturalanan miktar': 'sum',
                'Hesaplanan Litre': 'sum'
            }).reset_index()

            rapor.columns = ['Sipariş Veren', 'Müşteri Adı', 'İlk Tarih', 'Son Tarih', 'Toplam KG', 'Toplam Litre']
            rapor['Toplam Ton'] = rapor['Toplam KG'] / 1000

            # KPI
            total_ton = rapor['Toplam Ton'].sum()
            total_litre = rapor['Toplam Litre'].sum()
            
            st.markdown(f"""
            <div class="kpi-container">
                <div class="kpi-box">
                    <div class="kpi-label">Toplam Müşteri</div>
                    <div class="kpi-value">{len(rapor)}</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-label">Toplam Tonaj</div>
                    <div class="kpi-value" style="color: #FF9F85;">{tr_format(total_ton, 3)}</div>
                </div>
                <div class="kpi-box">
                    <div class="kpi-label">Toplam Litre</div>
                    <div class="kpi-value" style="color: #38bdf8;">{tr_format(total_litre, 0)}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            # LİSTE
            st.markdown("### 📊 Detaylı Analiz Sonuçları")
            
            for index, row in rapor.iterrows():
                m_adi = row['Müşteri Adı']
                m_kodu = row['Sipariş Veren']
                ilk = row['İlk Tarih'].strftime('%d.%m.%Y')
                son = row['Son Tarih'].strftime('%d.%m.%Y')
                ton = tr_format(row['Toplam Ton'], 3)
                litre = tr_format(row['Toplam Litre'], 2)

                st.markdown(f"""
                <div class="glass-card">
                    <div class="card-header">
                        <div class="customer-name">{m_adi}</div>
                        <div class="customer-code">#{m_kodu}</div>
                    </div>
                    <div class="stats-row">
                        <div class="stat-item">
                            <div class="stat-title">🗓️ İlk İşlem</div>
                            <div class="stat-num">{ilk}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-title">🗓️ Son İşlem</div>
                            <div class="stat-num">{son}</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-title">⚖️ Tonaj</div>
                            <div class="stat-num highlight-orange">{ton} TON</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-title">💧 Litre</div>
                            <div class="stat-num highlight-blue">{litre} LT</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            # EXCEL
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                excel_rapor = rapor.copy()
                excel_rapor['İlk Tarih'] = excel_rapor['İlk Tarih'].dt.strftime('%d.%m.%Y')
                excel_rapor['Son Tarih'] = excel_rapor['Son Tarih'].dt.strftime('%d.%m.%Y')
                excel_rapor.to_excel(writer, sheet_name='Kesafet_Analizi', index=False)
                
                # Excel Format
                worksheet = writer.sheets['Kesafet_Analizi']
                header_fmt = writer.book.add_format({'bold': True, 'fg_color': '#0f172a', 'font_color': 'white', 'border': 1})
                for col_num, value in enumerate(excel_rapor.columns.values):
                    worksheet.write(0, col_num, value, header_fmt)
                worksheet.set_column('A:B', 30)
                worksheet.set_column('C:F', 18)

            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                st.download_button(
                    label="📥 Raporu Excel Olarak İndir",
                    data=buffer.getvalue(),
                    file_name=f"Kesafet_Raporu_{datetime.now().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.ms-excel",
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"Bir hata oluştu: {e}")
