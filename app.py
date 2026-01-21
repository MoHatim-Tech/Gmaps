import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None 
import time
import re
import requests
import io
import os
import subprocess
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH

# دالة لتثبيت متصفح Playwright إذا لم يكن موجوداً
def ensure_playwright_installed():
    try:
        # محاولة تشغيل أمر التثبيت (سيتم تجاهله إذا كان موجوداً بالفعل في بعض البيئات)
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"فشل تثبيت Playwright: {e}")

# إعداد الصفحة
st.set_page_config(page_title="مستخرج بيانات خرائط جوجل", layout="wide")

# تنفيذ التثبيت عند بدء التطبيق
if 'playwright_installed' not in st.session_state:
    with st.spinner("جاري تهيئة المتصفح... قد يستغرق هذا دقيقة في المرة الأولى"):
        ensure_playwright_installed()
        st.session_state.playwright_installed = True

# تصميم الواجهة
st.markdown("""<style>
    body, .stApp { direction: RTL; text-align: right; font-family: 'Tajawal', sans-serif; }
    [data-testid="stSidebar"] { direction: RTL; text-align: right; }
    .developer-footer { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #1E3A8A; color: white; text-align: center; padding: 5px; font-size: 0.8rem; z-index: 100; }
</style>""", unsafe_allow_html=True)

st.markdown("""<div class="developer-footer">👨‍💻 تطوير: عبدالمنعم حاتم | 📞: +966544451878</div>""", unsafe_allow_html=True)

def extract_emails(url):
    try:
        if not url or url == "N/A": return "N/A"
        res = requests.get(url, timeout=5, headers={'User-Agent': 'Mozilla/5.0'})
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', res.text)
        return ", ".join(list(set(emails))) if emails else "N/A"
    except: return "N/A"

def scrape_maps(query, limit, data_placeholder, progress_bar):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = browser.new_context(user_agent="Mozilla/5.0", locale="ar-SA")
        page = context.new_page()
        if stealth_sync: stealth_sync(page)
        
        results = []
        try:
            page.goto(f"https://www.google.com/maps/search/{query}", wait_until="networkidle", timeout=60000)
            time.sleep(5)
            
            items = page.locator('.hfpxzc').all()[:limit]
            for i, item in enumerate(items):
                try:
                    item.click(force=True)
                    time.sleep(2)
                    
                    name = page.locator('h1.DUwDvf').inner_text() if page.locator('h1.DUwDvf').count() > 0 else "N/A"
                    phone = page.locator('button[data-item-id^="phone:tel:"]').inner_text() if page.locator('button[data-item-id^="phone:tel:"]').count() > 0 else "N/A"
                    web = page.locator('a[data-item-id="authority"]').get_attribute('href') if page.locator('a[data-item-id="authority"]').count() > 0 else "N/A"
                    address = page.locator('button[data-item-id="address"]').inner_text() if page.locator('button[data-item-id="address"]').count() > 0 else "N/A"
                    
                    results.append({
                        "الاسم": name, "الهاتف": phone, "الموقع": web, "الايميل": extract_emails(web), "العنوان": address
                    })
                    data_placeholder.dataframe(pd.DataFrame(results))
                    progress_bar.progress((i + 1) / len(items))
                except: continue
        except Exception as e:
            st.error(f"حدث خطأ: {e}")
        finally:
            browser.close()
        return results

st.title("🔍 مستخرج بيانات خرائط جوجل")

with st.sidebar:
    st.header("إعدادات البحث")
    search_query = st.text_input("مجال البحث (مثال: فنادق في دبي)")
    max_results = st.number_input("عدد النتائج", 1, 50, 10)
    start_btn = st.button("🚀 بدء الاستخراج")

if start_btn and search_query:
    placeholder = st.empty()
    bar = st.progress(0)
    data = scrape_maps(search_query, max_results, placeholder, bar)
    
    if data:
        st.success("✅ اكتمل بنجاح!")
        csv = pd.DataFrame(data).to_csv(index=False).encode('utf-8-sig')
        st.download_button("تحميل CSV", csv, "results.csv", "text/csv")
