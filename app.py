import streamlit as st
import subprocess
import sys
import os
import time
import re
import requests
import asyncio
import io

# وظيفة لتثبيت التبعيات برمجياً عند الحاجة
def ensure_dependencies():
    try:
        import playwright
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
    try:
        import playwright_stealth
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright-stealth"], check=True)
    try:
        import docx
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "python-docx"], check=True)

# تهيئة الصفحة
st.set_page_config(page_title="مستخرج بيانات خرائط جوجل", layout="wide", initial_sidebar_state="expanded")

# تصميم الواجهة
style_code = """<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet"><style>
    body, .stApp { font-family: 'Tajawal', sans-serif !important; direction: RTL !important; text-align: right !important; background-color: #F8FAFC !important; }
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-left: 1px solid #E2E8F0 !important; }
    .stButton button { background-color: #2563EB !important; color: white !important; border-radius: 8px !important; width: 100% !important; font-weight: bold !important; border: none !important; }
    .developer-footer { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #1E3A8A; color: white; text-align: center; padding: 8px 0; font-size: 0.9rem; z-index: 100; }
</style>"""
st.markdown(style_code, unsafe_allow_html=True)
st.markdown("""<div class="developer-footer">👨‍💻 تطوير: <b>عبدالمنعم حاتم</b> | 📞: +966544451878 | 📧: info@mohatim.tech</div>""", unsafe_allow_html=True)

def extract_emails_from_url(url):
    try:
        if not url or url == "N/A": return "N/A"
        if not url.startswith('http'): url = 'https://' + url
        res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', res.text)
        valid = [e for e in emails if not any(x in e.lower() for x in ['png', 'jpg', 'wix', 'sentry'])]
        return ", ".join(list(set(valid))) if valid else "N/A"
    except: return "N/A"

def scrape_google_maps(search_query, max_results=10, data_placeholder=None, progress_bar=None):
    ensure_dependencies()
    from playwright.sync_api import sync_playwright
    from playwright_stealth import stealth_sync
    import pandas as pd
    
    with sync_playwright() as p:
        results = []
        try:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(user_agent="Mozilla/5.0", locale="ar-SA")
            page = context.new_page()
            stealth_sync(page)
            
            page.goto("https://www.google.com/maps?hl=ar", wait_until="networkidle")
            try:
                page.click('button:has-text("قبول"), button:has-text("وافق")', timeout=5000)
            except: pass

            search_box = page.locator('#searchboxinput')
            search_box.wait_for(state="visible")
            for char in search_query:
                page.keyboard.type(char, delay=100)
            page.keyboard.press("Enter")
            
            time.sleep(10)
            
            seen_names = set()
            scroll_attempts = 0
            while len(results) < max_results and scroll_attempts < 30:
                items = page.locator('.hfpxzc, a[href*="/maps/place/"]').all()
                if not items:
                    page.mouse.wheel(0, 1000)
                    time.sleep(2)
                    scroll_attempts += 1
                    continue

                for item in items:
                    if len(results) >= max_results: break
                    try:
                        name = item.get_attribute("aria-label") or item.inner_text().split('\n')[0]
                        if not name or name in seen_names: continue
                        
                        item.click(force=True)
                        time.sleep(3)
                        
                        name_h1 = page.locator('h1.DUwDvf')
                        if name_h1.count() > 0:
                            actual_name = name_h1.first.inner_text()
                            if actual_name in seen_names: continue
                            
                            address = page.locator('button[data-item-id="address"]').first.inner_text() if page.locator('button[data-item-id="address"]').count() > 0 else "N/A"
                            phone = page.locator('button[data-item-id^="phone:tel:"]').first.inner_text() if page.locator('button[data-item-id^="phone:tel:"]').count() > 0 else "N/A"
                            website = page.locator('a[data-item-id="authority"]').first.get_attribute('href') if page.locator('a[data-item-id="authority"]').count() > 0 else "N/A"
                            
                            results.append({
                                "🏢 اسم المؤسسة": actual_name, "📞 رقم الهاتف": phone, "🌐 الموقع الالكتروني": website,
                                "📧 الايميل": extract_emails_from_url(website) if website != "N/A" else "N/A",
                                "📍 موقع المكتب": address
                            })
                            seen_names.add(actual_name)
                            if progress_bar: progress_bar.progress(len(results) / max_results)
                            if data_placeholder: data_placeholder.dataframe(pd.DataFrame(results))
                    except: continue

                page.mouse.wheel(0, 3000)
                time.sleep(2)
                scroll_attempts += 1
            browser.close()
            return results
        except Exception as e:
            st.error(f"خطأ: {e}")
            return results

st.title("🔍 نظام استخراج البيانات الذكي")

with st.sidebar:
    st.markdown("### 🛠️ إعدادات البحث")
    biz = st.text_input("مجال المؤسسة")
    city = st.text_input("المدينة")
    country = st.text_input("الدولة")
    num = st.number_input("النتائج", 1, 100, 10)
    start = st.button("🚀 ابدأ الاستخراج")

if start:
    if biz or city:
        query = f"{biz} في {city} {country}".strip()
        st.info(f"🔎 جاري البحث عن: {query}")
        p_bar = st.progress(0); d_place = st.empty()
        final_data = scrape_google_maps(query, num, d_place, p_bar)
        if final_data:
            import pandas as pd
            from docx import Document
            from docx.shared import Pt
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            
            st.success("✅ اكتمل الاستخراج!")
            df = pd.DataFrame(final_data)
            
            doc = Document()
            for entry in final_data:
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
                p.add_run(f"🏢 المؤسسة: {entry['🏢 اسم المؤسسة']}\n").bold = True
                p.add_run(f"📞 الهاتف: {entry['📞 رقم الهاتف']}\n")
                p.add_run(f"📧 الايميل: {entry['📧 الايميل']}\n")
                doc.add_paragraph("-" * 20)
            
            bio = io.BytesIO(); doc.save(bio)
            c1, c2 = st.columns(2)
            with c1: st.download_button("تحميل Word", bio.getvalue(), "results.docx")
            with c2: st.download_button("تحميل CSV", df.to_csv(index=False).encode('utf-8-sig'), "results.csv")
    else: st.warning("يرجى إدخال بيانات للبحث.")
