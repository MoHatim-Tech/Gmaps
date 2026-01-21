import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync
import time
import re
import requests
from bs4 import BeautifulSoup
import asyncio
import sys
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
import io
import subprocess

# وظيفة لتثبيت متصفح Playwright تلقائياً على السيرفر
def install_playwright_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Error installing browsers: {e}")

# تنفيذ التثبيت عند بدء التطبيق
if 'playwright_installed' not in st.session_state:
    with st.spinner("جاري تهيئة محرك البحث (قد يستغرق دقيقة في المرة الأولى)..."):
        install_playwright_browsers()
        st.session_state['playwright_installed'] = True

# حل مشكلة NotImplementedError على ويندوز
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def extract_emails_from_url(url):
    try:
        if not url or url == "N/A": return "N/A"
        if not url.startswith('http'): url = 'https://' + url
        targets = [url]
        base_url = "/".join(url.split("/")[:3])
        potential_pages = ['contact', 'contact-us', 'about', 'about-us', 'support']
        for page_name in potential_pages:
            targets.append(f"{base_url}/{page_name}")
        
        targets = list(dict.fromkeys(targets))
        all_emails = set()
        for target in targets:
            try:
                response = requests.get(target, timeout=5, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                if response.status_code == 200:
                    found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', response.text)
                    for email in found:
                        if not any(ext in email.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', 'wix', 'sentry']):
                            all_emails.add(email)
            except: continue
            if all_emails: break
        return ", ".join(list(all_emails)) if all_emails else "N/A"
    except: return "N/A"

def scrape_google_maps(search_query, max_results=10, data_placeholder=None, progress_bar=None):
    with sync_playwright() as p:
        results = []
        try:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 720},
                locale="ar-SA"
            )
            page = context.new_page()
            stealth_sync(page)
            
            st.toast("🌐 جاري الاتصال بخوادم الخرائط...")
            page.goto("https://www.google.com/maps?hl=ar", wait_until="networkidle", timeout=60000)
            
            try:
                page.click('button:has-text("قبول"), button:has-text("وافق"), button:has-text("Accept")', timeout=5000)
                time.sleep(2)
            except: pass

            search_box = page.locator('#searchboxinput')
            search_box.wait_for(state="visible", timeout=20000)
            search_box.click()
            for char in search_query:
                page.keyboard.type(char, delay=150)
            page.keyboard.press("Enter")
            
            st.toast("⏳ جاري تحليل النتائج...")
            time.sleep(10)

            # تشخيص الفشل
            if page.locator('.Nv262d, .hfpxzc, h1.DUwDvf').count() == 0:
                st.session_state['debug_screenshot'] = page.screenshot()
            
            seen_names = set()
            scroll_attempts = 0
            
            while len(results) < max_results and scroll_attempts < 40:
                if page.locator('h1.DUwDvf').is_visible():
                    name = page.locator('h1.DUwDvf').inner_text()
                    if name not in seen_names:
                        address = page.locator('button[data-item-id="address"]').first.inner_text() if page.locator('button[data-item-id="address"]').count() > 0 else "N/A"
                        phone = page.locator('button[data-item-id^="phone:tel:"]').first.inner_text() if page.locator('button[data-item-id^="phone:tel:"]').count() > 0 else "N/A"
                        website = page.locator('a[data-item-id="authority"]').first.get_attribute('href') if page.locator('a[data-item-id="authority"]').count() > 0 else "N/A"
                        results.append({
                            "🏢 اسم المؤسسة": name, "📞 رقم الهاتف": phone, "🌐 الموقع الالكتروني": website,
                            "📧 الايميل": extract_emails_from_url(website) if website != "N/A" else "N/A",
                            "📍 موقع المكتب": address
                        })
                        seen_names.add(name)
                        if data_placeholder: data_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)
                        if max_results == 1: break

                items = page.locator('.hfpxzc, a[href*="/maps/place/"]').all()
                for item in items:
                    if len(results) >= max_results: break
                    try:
                        name = item.get_attribute("aria-label") or item.inner_text().split('\n')[0]
                        if not name or name in seen_names: continue
                        item.scroll_into_view_if_needed()
                        item.click(force=True)
                        time.sleep(3)
                        name_loc = page.locator('h1.DUwDvf')
                        if name_loc.count() > 0:
                            side_name = name_loc.first.inner_text()
                            if side_name in seen_names: continue
                            address = page.locator('button[data-item-id="address"]').first.inner_text() if page.locator('button[data-item-id="address"]').count() > 0 else "N/A"
                            phone = page.locator('button[data-item-id^="phone:tel:"]').first.inner_text() if page.locator('button[data-item-id^="phone:tel:"]').count() > 0 else "N/A"
                            website = page.locator('a[data-item-id="authority"]').first.get_attribute('href') if page.locator('a[data-item-id="authority"]').count() > 0 else "N/A"
                            results.append({
                                "🏢 اسم المؤسسة": side_name, "📞 رقم الهاتف": phone, "🌐 الموقع الالكتروني": website,
                                "📧 الايميل": extract_emails_from_url(website) if website != "N/A" else "N/A",
                                "📍 موقع المكتب": address
                            })
                            seen_names.add(side_name)
                            if progress_bar: progress_bar.progress(len(results) / max_results)
                            if data_placeholder: data_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)
                    except: continue

                page.mouse.wheel(0, 3000)
                time.sleep(2)
                scroll_attempts += 1
                if "نهاية القائمة" in page.content() or "reached the end" in page.content(): break
            browser.close()
            return results
        except Exception as e:
            st.error(f"❌ خطأ فني: {e}")
            if 'browser' in locals(): browser.close()
            return results

# إعدادات الواجهة
st.set_page_config(page_title="مستخرج بيانات خرائط جوجل", layout="wide", initial_sidebar_state="expanded")
style_code = """<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet"><style>
    body, .stApp { font-family: 'Tajawal', sans-serif !important; direction: RTL !important; text-align: right !important; background-color: #F8FAFC !important; }
    h1, h2, h3, p, span, label { font-family: 'Tajawal', sans-serif !important; text-align: right !important; color: #1E3A8A !important; }
    [data-testid="stSidebar"] { background-color: #FFFFFF !important; border-left: 1px solid #E2E8F0 !important; }
    .stTextInput div[data-baseweb="input"], .stNumberInput div[data-baseweb="input"] { border: 1px solid #CBD5E1 !important; border-radius: 8px !important; }
    [data-testid="stDataFrame"], [data-testid="stTable"] { direction: LTR !important; text-align: left !important; background-color: white !important; border-radius: 12px !important; }
    .stButton button { background-color: #2563EB !important; color: white !important; border-radius: 8px !important; width: 100% !important; font-weight: bold !important; border: none !important; }
    .stButton button p { color: white !important; }
    .developer-footer { position: fixed; bottom: 0; left: 0; width: 100%; background-color: #1E3A8A; color: white; text-align: center; padding: 8px 0; font-family: 'Tajawal', sans-serif; z-index: 100; font-size: 0.9rem; }
</style>"""
st.markdown(style_code, unsafe_allow_html=True)

st.markdown("""<div class="developer-footer">👨‍💻 تطوير: <b>عبدالمنعم حاتم</b> | 📞: +966544451878 | 📧: info@mohatim.tech</div>""", unsafe_allow_html=True)

st.title("🔍 نظام استخراج البيانات الذكي")

with st.sidebar:
    st.markdown("### 🛠️ إعدادات البحث")
    business_type = st.text_input("مجال المؤسسة", placeholder="مطاعم، فنادق...")
    city = st.text_input("المدينة", placeholder="الرياض، دبي...")
    country = st.text_input("الدولة", placeholder="السعودية...")
    max_res = st.number_input("عدد النتائج المطلوبة", min_value=1, max_value=500, value=10, step=1)
    st.markdown("---")
    search_clicked = st.button("🚀 ابدأ عملية الاستخراج")
    st.markdown("### 📖 تعليمات")
    st.info("أدخل التفاصيل واضغط بدء. إذا فشل الاستخراج، سيظهر قسم تشخيصي يوضح السبب.")

def create_word_doc(data):
    doc = Document()
    style = doc.styles['Normal']; font = style.font; font.name = 'Arial'; font.size = Pt(12)
    doc.add_heading('نتائج استخراج بيانات خرائط جوجل', 0).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for entry in data:
        p = doc.add_paragraph(); p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.add_run(f"🏢 اسم المؤسسة: {entry['🏢 اسم المؤسسة']}\n").bold = True
        p.add_run(f"📞 رقم الهاتف: {entry['📞 رقم الهاتف']}\n")
        p.add_run(f"🌐 الموقع الالكتروني: {entry['🌐 الموقع الالكتروني']}\n")
        p.add_run(f"📧 الايميل: {entry['📧 الايميل']}\n")
        p.add_run(f"📍 موقع المكتب: {entry['📍 موقع المكتب']}\n")
        doc.add_paragraph("-" * 30).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    bio = io.BytesIO(); doc.save(bio); return bio.getvalue()

if search_clicked:
    if business_type or city or country:
        query = f"{business_type} في {city} {country}".strip()
        st.info(f"🔎 جاري البحث عن: {query}")
        progress_bar = st.progress(0); data_placeholder = st.empty()
        
        final_data = scrape_google_maps(query, max_res, data_placeholder, progress_bar)
        
        if not final_data and 'debug_screenshot' in st.session_state:
            with st.expander("🛠️ تفاصيل تشخيصية (لماذا لم تظهر نتائج؟)"):
                st.image(st.session_state['debug_screenshot'])
                st.warning("إذا رأيت صور كابتشا، فهذا يعني أن جوجل حظر السيرفر. حاول مرة أخرى لاحقاً أو غير كلمات البحث.")
        
        if final_data:
            st.success("✅ اكتمل الاستخراج!")
            df = pd.DataFrame(final_data)
            c1, c2 = st.columns(2)
            with c1: st.download_button("تحميل Word", create_word_doc(final_data), "results.docx", use_container_width=True)
            with c2: st.download_button("تحميل CSV", df.to_csv(index=False).encode('utf-8-sig'), "results.csv", use_container_width=True)
    else: st.warning("يرجى إدخال معلومة بحث واحدة على الأقل.")
