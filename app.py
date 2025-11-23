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

    # --- 2. DETAYLI ŞİRKET ANALİZİ (Sizin istediğiniz mantık) ---
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
                    # İSTEDİĞİNİZ SENARYO BURASI:
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

            # Çıktı Satırı
            sirket_raporu.append(f"{icon} **{tarih_str}:** Pay: %{sirket_pay_curr:.2f} | Satış: {sirket_ton_curr:,.0f} ton | {yorum}{gy_text}")
            
    else:
        sirket_raporu.append("Şirket verisi bulunamadı.")

    # --- 3. DETAYLI RAKİP TREND ANALİZİ ---
    rakip_raporu.append(f"### 📡 Rakip Trend Dedektörü ({sehir})")
    
    # Mevcut aydaki en büyük rakipleri bul (Biz hariç)
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
