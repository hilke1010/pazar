
            st.subheader("Dağıtıcı Bazlı Kümülatif Satışlar ve Pazar Payları")
            use_months = ortak if ortak else sorted(ay_curr)
            current_dist = df_turkiye_sirket[
                (df_turkiye_sirket['Tarih'].dt.year == yil) &
                df_turkiye_sirket['Tarih'].dt.month.isin(use_months)
            ].groupby('Şirket', as_index=False)[TON_KOLONLARI].sum()
            previous_dist = df_turkiye_sirket[
                (df_turkiye_sirket['Tarih'].dt.year == yil - 1) &
                df_turkiye_sirket['Tarih'].dt.month.isin(ortak)
            ].groupby('Şirket', as_index=False)[TON_KOLONLARI].sum() if ortak else pd.DataFrame()

            if not current_dist.empty:
                current_dist['Toplam Ton'] = current_dist[TON_KOLONLARI].sum(axis=1)
                if segment == 'Tüm Ürünler':
                    for col in TON_KOLONLARI + ['Toplam Ton']:
                        total = current_dist[col].sum()
                        current_dist[col.replace(' Ton', ' Pay (%)')] = current_dist[col] / total * 100 if total else 0
                    view = current_dist.sort_values('Toplam Ton', ascending=False).reset_index(drop=True)
                    st.dataframe(view.style.format({c: '{:,.2f}' for c in view.columns if 'Ton' in c})
                                 .format({c: '{:.2f}%' for c in view.columns if 'Pay (%)' in c}),
                                 use_container_width=True)
                else:
                    ton = segment + ' Ton'
                    curr = current_dist[['Şirket', ton]].copy()
                    curr.rename(columns={ton: f'{yil} Ton'}, inplace=True)
                    if ortak and not previous_dist.empty:
                        prev = previous_dist[['Şirket', ton]].rename(columns={ton: f'{yil-1} Ton'})
                        result = curr.merge(prev, on='Şirket', how='outer').fillna(0)
                        curr_total, prev_total = result[f'{yil} Ton'].sum(), result[f'{yil-1} Ton'].sum()
                        result[f'{yil} Pazar Payı (%)'] = (100 * result[f'{yil} Ton'] / curr_total) if curr_total else 0
                        result[f'{yil-1} Pazar Payı (%)'] = (100 * result[f'{yil-1} Ton'] / prev_total) if prev_total else 0
                        result['Fark Ton'] = result[f'{yil} Ton'] - result[f'{yil-1} Ton']
                        result['Fark Pay (puan)'] = result[f'{yil} Pazar Payı (%)'] - result[f'{yil-1} Pazar Payı (%)']
                        result = result.sort_values(f'{yil} Ton', ascending=False)
                        st.dataframe(result.style.format({c: '{:,.2f}' for c in result.columns if 'Ton' in c})
                                     .format({c: '{:.2f}' for c in result.columns if 'Pazar Payı' in c})
                                     .format({'Fark Pay (puan)': '{:+.2f}'})
                                     .map(highlight_val, subset=['Fark Ton', 'Fark Pay (puan)']),
                                     use_container_width=True)
                    else:
                        total = curr[f'{yil} Ton'].sum()
                        curr['Pazar Payı (%)'] = curr[f'{yil} Ton'] / total * 100 if total else 0
                        st.dataframe(curr.sort_values(f'{yil} Ton', ascending=False), use_container_width=True)
            else:
                st.warning('Seçilen dönem için Tablo 11 dağıtıcı verisi bulunamadı.')

        # =================================================================================================
        # 3. TABLO 14: WHOLESALE (NOT CITY-LEVEL)
        # =================================================================================================
        elif sayfa_secimi == "Toptan LPG (Tablo 14)":
            st.header("🚚 Dağıtıcılar Arası Toptan LPG Satışları — Tablo 14")
            if df_toptan.empty:
                st.warning("Tablo 14 verisi bulunamadı.")
            else:
                dates = sorted(df_toptan['Tarih'].unique(), reverse=True)
                date = st.selectbox('Dönem', dates, format_func=tarih_secim_etiketi)
                month = df_toptan[df_toptan['Tarih'] == date]
                fields = ['Şirket', 'Tüplü Ton', 'Tüplü Pay', 'Dökme Ton', 'Dökme Pay',
                          'Otogaz Ton', 'Otogaz Pay', 'Toplam Ton', 'Toplam Pay']
                st.dataframe(month[fields].sort_values('Toplam Ton', ascending=False)
                             .style.format({c: '{:,.2f}' for c in fields if c != 'Şirket'}),
                             use_container_width=True)
                st.caption('Bu tablo toptan dağıtıcılar arası satışlardır; perakende il pazarının toplamına eklenmez.')
                st.subheader('Toptan Satış Eğilimleri')
                ss = sorted(df_toptan['Şirket'].unique())
                chosen = st.multiselect('Şirketler', ss, default=[LIKITGAZ_NAME] if LIKITGAZ_NAME in ss else ss[:1])
                if chosen:
                    fig = px.line(df_toptan[df_toptan['Şirket'].isin(chosen)],
                                  x='Tarih', y='Toplam Ton', color='Şirket', markers=True)
                    st.plotly_chart(fig, use_container_width=True)

        # =================================================================================================
        # 4. TABLO 12: YOY COMPANY REPORT
        # =================================================================================================
        elif sayfa_secimi == "Yıllık Kıyas (Tablo 12)":
            st.header("📆 Şirketlerin Önceki Yıla Göre Satışları — Tablo 12")
            st.caption('Kaynakta Pay (%) sütunları şirket içi ürün karmasını ifade eder; il/ulusal pazar payı değildir.')
            if df_yillik.empty:
                st.warning('Tablo 12 verisi bulunamadı.')
            else:
                dates = sorted(df_yillik['Tarih'].unique(), reverse=True)
                chosen_date = st.selectbox('Dönem', dates, format_func=tarih_secim_etiketi)
                product = st.selectbox('Ürün türü', ['Firma Toplamı', 'Otogaz', 'Tüplü', 'Dökme'])
                table = df_yillik[(df_yillik['Tarih'] == chosen_date) & (df_yillik['Ürün'] == product)]
                cols = ['Şirket', 'Önceki Yıl Ton', 'Güncel Yıl Ton', 'Değişim (%)']
                st.dataframe(table[cols].sort_values('Güncel Yıl Ton', ascending=False)
                             .style.format({'Önceki Yıl Ton': '{:,.2f}', 'Güncel Yıl Ton': '{:,.2f}',
                                            'Değişim (%)': '{:+.2f}'})
                             .map(highlight_val, subset=['Değişim (%)']), use_container_width=True)

        # =================================================================================================
        # 5. EVERY TABLE 1-14 IN THE SOURCE FILES (UNMODIFIED CELL VALUES)
        # =================================================================================================
        elif sayfa_secimi == "Tüm Tablolar (1–14)":
            st.header('📚 Tüm EPDK Excel Tabloları')
            available_dates = sorted(tablo_arsivi.keys(), reverse=True)
            chosen_period = st.selectbox('Dönem', available_dates,
                                         format_func=lambda key: f'{TR_AYLAR[key[1]]} {key[0]}')
            all_tables = tablo_arsivi[chosen_period]
            table_numbers = sorted(all_tables.keys())
            selected_table = st.selectbox('Tablo numarası', table_numbers,
                                          format_func=lambda k: f'Tablo {k}' + (' — İl bazlı satışlar' if k == 13 else
                                          ' — Dağıtıcılar arası toptan satış' if k == 14 else ''))
            st.caption('Excel hücrelerindeki değerler olduğu gibi gösterilir; birleşik başlık satırları korunur.')
            raw = tablo_dataframe(all_tables[selected_table])
            st.dataframe(raw, use_container_width=True, hide_index=True, height=540)
            st.download_button('📥 Bu tabloyu CSV indir',
                               data=raw.to_csv(index=False, header=False, sep=';', decimal=',').encode('utf-8-sig'),
                               file_name=f'Tablo{selected_table}_{TR_AYLAR[chosen_period[1]]}{chosen_period[0]}.csv',
                               mime='text/csv')
