import streamlit as st
import sqlite3
import os
from datetime import date
from PIL import Image
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- ŞİFRE KORUMASI ---
def sifre_kontrol():
    if "authed" not in st.session_state:
        st.session_state["authed"] = False

    if not st.session_state["authed"]:
        st.title("🔒 Saha Takip Paneli - Giriş")
        girilen_sifre = st.text_input("Lütfen Giriş Şifrenizi Girin", type="password")
        if st.button("Giriş Yap", type="primary"):
            # Varsayılan şifre: 1234 (İstediğiniz şifre ile değiştirebilirsiniz)
            if girilen_sifre == "1234":
                st.session_state["authed"] = True
                st.rerun()
            else:
                st.error("Hatalı şifre! Lütfen tekrar deneyin.")
        return False
    return True

if sifre_kontrol():
    # --- VERİTABANI VE UYGULAMA MANTIĞI ---
    conn = sqlite3.connect('saha_takip.db', check_same_thread=False)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS is_kayitlari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tarih TEXT,
            proje_adi TEXT,
            is_konusu TEXT,
            aciklama TEXT,
            fotograf_yollari TEXT
        )
    ''')
    conn.commit()

    os.makedirs("yuklenen_fotograflar", exist_ok=True)

    def pdf_rapor_olustur(baslangic_tarihi, bitis_tarihi, dosya_adi="saha_raporu.pdf"):
        doc = SimpleDocTemplate(dosya_adi, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle('TitleStyle', parent=styles['Heading1'], fontSize=18, textColor=colors.HexColor('#1A365D'), spaceAfter=12)
        meta_style = ParagraphStyle('MetaStyle', parent=styles['Normal'], fontSize=10, textColor=colors.gray, spaceAfter=8)
        text_style = ParagraphStyle('TextStyle', parent=styles['Normal'], fontSize=11, spaceAfter=10)

        story.append(Paragraph("SAHA İŞ VE FOTOĞRAF RAPORU", title_style))
        story.append(Paragraph(f"Tarih Aralığı: {baslangic_tarihi} / {bitis_tarihi}", meta_style))
        story.append(Spacer(1, 15))

        c.execute("SELECT tarih, proje_adi, is_konusu, aciklama, fotograf_yollari FROM is_kayitlari WHERE tarih BETWEEN ? AND ? ORDER BY tarih DESC", 
                  (str(baslangic_tarihi), str(bitis_tarihi)))
        kayitlar = c.fetchall()

        if not kayitlar:
            story.append(Paragraph("Seçilen tarih aralığında kayıt bulunamadı.", text_style))
        else:
            for kayit in kayitlar:
                tarih, proje, konu, aciklama, foto_str = kayit
                story.append(Paragraph(f"<b>Tarih:</b> {tarih} | <b>Proje:</b> {proje}", text_style))
                story.append(Paragraph(f"<b>İş Konusu:</b> {konu}", text_style))
                if aciklama:
                    story.append(Paragraph(f"<b>Açıklama:</b> {aciklama}", text_style))
                
                if foto_str:
                    foto_listesi = foto_str.split(";")
                    for foto_yolu in foto_listesi:
                        if os.path.exists(foto_yolu):
                            try:
                                img = RLImage(foto_yolu, width=400, height=250)
                                story.append(img)
                                story.append(Spacer(1, 8))
                            except Exception:
                                pass
                story.append(Spacer(1, 15))

        doc.build(story)
        return dosya_adi

    st.set_page_config(page_title="Saha Takip & Raporlama", layout="centered")
    st.title("📋 Saha İş & Fotoğraf Takip Paneli")

    tab1, tab2 = st.tabs(["➕ Yeni İş Kaydı", "📊 Rapor Al (Günlük/Haftalık/Aylık)"])

    with tab1:
        st.subheader("Saha Veri Girişi")
        tarih = st.date_input("İş Tarihi", date.today())
        proje_adi = st.text_input("Proje / Saha Adı", placeholder="Örn: Park Düzenleme Projesi")
        is_konusu = st.text_input("İş Konusu", placeholder="Örn: Tesisat ve Çim Serimi")
        aciklama = st.text_area("Detaylı Açıklama (İsteğe Bağlı)")
        yuklenen_dosyalar = st.file_uploader("Fotoğrafları Seçin", type=["jpg", "jpeg", "png"], accept_multiple_files=True)

        if st.button("Kaydet ve Depola", type="primary"):
            if not proje_adi or not is_konusu:
                st.error("Lütfen Proje Adı ve İş Konusunu doldurun.")
            else:
                kaydedilen_fotolar = []
                if yuklenen_dosyalar:
                    for dosya in yuklenen_dosyalar:
                        dosya_yolu = os.path.join("yuklenen_fotograflar", f"{tarih}_{dosya.name}")
                        with open(dosya_yolu, "wb") as f:
                            f.write(dosya.getbuffer())
                        kaydedilen_fotolar.append(dosya_yolu)

                foto_str = ";".join(kaydedilen_fotolar)
                c.execute("INSERT INTO is_kayitlari (tarih, proje_adi, is_konusu, aciklama, fotograf_yollari) VALUES (?, ?, ?, ?, ?)",
                          (str(tarih), proje_adi, is_konusu, aciklama, foto_str))
                conn.commit()
                st.success("Kayıt başarıyla depolandı!")

    with tab2:
        st.subheader("PDF Rapor Oluştur")
        rapor_tipi = st.radio("Rapor Aralığı Seçin", ["Günlük", "Haftalık / Aylık Özel Aralık"])
        
        if rapor_tipi == "Günlük":
            secilen_tarih = st.date_input("Rapor Tarihi", date.today())
            bas_tarih = secilen_tarih
            bit_tarih = secilen_tarih
        else:
            col1, col2 = st.columns(2)
            with col1:
                bas_tarih = st.date_input("Başlangıç Tarihi", date.today())
            with col2:
                bit_tarih = st.date_input("Bitiş Tarihi", date.today())

        if st.button("PDF Raporu Hazırla"):
            pdf_dosya = pdf_rapor_olustur(bas_tarih, bit_tarih)
            with open(pdf_dosya, "rb") as f:
                st.download_button(
                    label="📄 PDF Raporunu İndir",
                    data=f,
                    file_name=f"Saha_Raporu_{bas_tarih}_{bit_tarih}.pdf",
                    mime="application/pdf"
                )