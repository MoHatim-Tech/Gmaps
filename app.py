import streamlit as st
import pandas as pd
from playwright.sync_api import sync_playwright
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

# حل مشكلة NotImplementedError على ويندوز
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

def extract_emails_from_url(url):
    try:
        if not url or url == "N/A": return "N/A"
        if not url.startswith('http'): url = 'https://' + url
        
        targets = [url]
        base_url = "/".join(url.split("/")[:3])
        potential_pages = ['contact', 'contact-us', 'about', 'about-us', 'support', 'terms']
        for page_name in potential_pages:
            targets.append(f"{base_url}/{page_name}")
            targets.append(f"{base_url}/ar/{page_name}")
            targets.append(f"{base_url}/en/{page_name}")
        
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
    except:
        return "N/A"

def scrape_google_maps(search_query, max_results=10, data_placeholder=None, progress_bar=None):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="ar-SA",
            viewport={'width': 1920, 'height': 1080}
        )
        page = context.new_page()
        results = []
        
        try:
            page.goto(f"https://www.google.com/maps/search/{search_query}", wait_until="load", timeout=60000)
            time.sleep(5)
            
            try:
                if "consent" in page.url or page.locator('button[aria-label*="Accept all"]').count() > 0:
                    for selector in ['button[aria-label*="Accept all"]', 'button[aria-label*="وافق"]', 'button[aria-label*="قبول"]', 'button:has-text("Accept all")']:
                        if page.locator(selector).count() > 0:
                            page.locator(selector).first.click()
                            page.wait_for_load_state("networkidle")
                            break
            except:
                pass

            seen_names = set()
            scroll_attempts = 0
            max_scroll_attempts = 30 
            
            while len(results) < max_results and scroll_attempts < max_scroll_attempts:
                item_selectors = ['a[href*="/maps/place/"]', '.hfpxzc', 'div[role="article"] a']
                items = []
                for sel in item_selectors:
                    found = page.locator(sel).all()
                    if len(found) > 0:
                        items = found
                        break
                
                if not items:
                    page.mouse.wheel(0, 2000)
                    time.sleep(3)
                    scroll_attempts += 1
                    continue

                for item in items:
                    if len(results) >= max_results: break
                    try:
                        card_name = item.get_attribute("aria-label") or item.inner_text().split('\n')[0]
                        if not card_name or card_name in seen_names or "N/A" in card_name: continue
                        
                        item.scroll_into_view_if_needed()
                        item.click(force=True)
                        time.sleep(3)
                        
                        name = "N/A"
                        name_selectors = ['h1.DUwDvf', 'h1.lfPIob', 'h1']
                        for selector in name_selectors:
                            if page.locator(selector).count() > 0:
                                name = page.locator(selector).first.inner_text()
                                break
                        
                        if name == "N/A" or name in seen_names: continue
                        seen_names.add(name)
                        
                        page_content = page.content()
                        emails_in_maps = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_content)
                        emails_in_maps = [e for e in emails_in_maps if not any(x in e.lower() for x in ['google', 'sentry', 'wix', 'example', 'domain', 'png', 'jpg'])]

                        address = "N/A"
                        address_loc = page.locator('button[data-item-id="address"]')
                        if address_loc.count() > 0: address = address_loc.first.inner_text()
                        
                        phone = "N/A"
                        phone_loc = page.locator('button[data-item-id^="phone:tel:"]')
                        if phone_loc.count() > 0: phone = phone_loc.first.inner_text()
                        
                        website = "N/A"
                        website_loc = page.locator('a[data-item-id="authority"]')
                        if website_loc.count() > 0: website = website_loc.first.get_attribute('href')
                        
                        email = "N/A"
                        if emails_in_maps: email = emails_in_maps[0]
                        elif website != "N/A": email = extract_emails_from_url(website)

                        new_entry = {
                            "🏢 اسم المؤسسة": name,
                            "📞 رقم الهاتف": phone,
                            "🌐 الموقع الالكتروني": website,
                            "📧 الايميل": email,
                            "📍 موقع المكتب": address
                        }
                        results.append(new_entry)
                        
                        if progress_bar: progress_bar.progress(len(results) / max_results)
                        if data_placeholder: data_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)
                    except: continue
                
                feed_selector = 'div[role="feed"]'
                if page.locator(feed_selector).count() > 0:
                    page.locator(feed_selector).evaluate("el => el.scrollBy(0, 2000)")
                else:
                    page.mouse.wheel(0, 2000)
                time.sleep(3)
                scroll_attempts += 1
                    
            browser.close()
            return results
        except Exception:
            if 'browser' in locals(): browser.close()
            return results

# إعدادات الواجهة
st.set_page_config(page_title="مستخرج بيانات خرائط جوجل", layout="wide", initial_sidebar_state="expanded")

# تصميم عصري متطور
style_code = """
<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700&display=swap" rel="stylesheet">
<style>
    /* الإعدادات العامة */
    * { font-family: 'Tajawal', sans-serif !important; }
    
    .stApp {
        background: linear-gradient(135deg, #f1f5f9 0%, #e2e8f0 100%) !important;
        direction: RTL !important;
        text-align: right !important;
    }

    /* إخفاء الزوائد */
    #MainMenu, footer, header { visibility: hidden !important; }
    
    /* السايدبار الأنيق */
    [data-testid="stSidebar"] {
        background-color: rgba(255, 255, 255, 0.95) !important;
        backdrop-filter: blur(10px) !important;
        border-left: 1px solid rgba(30, 58, 138, 0.1) !important;
        box-shadow: -4px 0 15px rgba(0,0,0,0.05) !important;
    }

    /* مدخلات البيانات */
    .stTextInput input, .stNumberInput input {
        border-radius: 10px !important;
        border: 1px solid #cbd5e1 !important;
        padding: 12px !important;
        transition: all 0.3s ease !important;
    }

    .stTextInput input:focus {
        border-color: #2563eb !important;
        box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.1) !important;
    }

    /* أزرار مذهلة */
    .stButton button {
        background: linear-gradient(90deg, #1e3a8a 0%, #2563eb 100%) !important;
        color: white !important;
        border: none !important;
        border-radius: 12px !important;
        padding: 20px !important;
        font-weight: 700 !important;
        font-size: 1.1rem !important;
        letter-spacing: 0.5px !important;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        box-shadow: 0 4px 15px rgba(37, 99, 235, 0.2) !important;
    }

    .stButton button:hover {
        transform: scale(1.02) !important;
        box-shadow: 0 8px 25px rgba(37, 99, 235, 0.3) !important;
        background: linear-gradient(90deg, #2563eb 0%, #1e3a8a 100%) !important;
    }

    /* كروت المحتوى */
    .main-container {
        background: white !important;
        border-radius: 20px !important;
        padding: 30px !important;
        box-shadow: 0 10px 30px rgba(0,0,0,0.04) !important;
        border: 1px solid rgba(255,255,255,0.8) !important;
    }

    /* تخصيص جدول البيانات */
    [data-testid="stDataFrame"] {
        border: 1px solid #e2e8f0 !important;
        border-radius: 15px !important;
        overflow: hidden !important;
    }

    /* تذييل المطور */
    .dev-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: rgba(30, 58, 138, 0.9);
        color: white;
        padding: 12px;
        text-align: center;
        backdrop-filter: blur(5px);
        font-weight: 500;
        z-index: 1000;
        font-size: 0.9rem;
    }

    /* العناوين */
    h1 {
        background: linear-gradient(90deg, #1e3a8a, #3b82f6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        margin-bottom: 30px !important;
    }

    /* شريط التقدم */
    .stProgress > div > div > div > div {
        background-color: #2563eb !important;
    }
</style>
"""
st.markdown(style_code, unsafe_allow_html=True)

# تذييل المطور
st.markdown("""
    <div class="dev-footer">
        👨‍💻 تطوير: <b>عبدالمنعم حاتم</b> | 📞: 0544451878 | 📧: info@mohatim.tech
    </div>
    """, unsafe_allow_html=True)

# محتوى السايدبار (الإعدادات)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/854/854878.png", width=80)
    st.title("إعدادات البحث")
    st.markdown("---")
    business_type = st.text_input("🏢 مجال المؤسسة", placeholder="مثال: مطاعم، شركات تقنية")
    city = st.text_input("📍 المدينة", placeholder="الرياض، جدة")
    country = st.text_input("🌍 الدولة", placeholder="السعودية، مصر")
    max_res = st.number_input("🔢 عدد النتائج", min_value=1, max_value=500, value=10)
    st.markdown("<br>", unsafe_allow_html=True)
    search_clicked = st.button("🚀 بدء الاستخراج")

# المحتوى الرئيسي
st.title("🔍 نظام استخراج البيانات الذكي")
st.info("قم بتعبئة بيانات البحث في القائمة الجانبية ثم اضغط على زر البدء.")

def create_word_doc(data):
    doc = Document()
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(12)
    doc.add_heading('نتائج استخراج بيانات خرائط جوجل', 0).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    for entry in data:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for key, val in entry.items():
            p.add_run(f"{key}: ").bold = True
            p.add_run(f"{val}\n")
        doc.add_paragraph("-" * 30).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph("\n")
    dev_info = doc.add_paragraph()
    dev_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = dev_info.add_run("تم الاستخراج بواسطة نظام استخراج البيانات الذكي")
    run.font.size = Pt(10)
    run.italic = True
    dev_contact = doc.add_paragraph()
    dev_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = dev_contact.add_run("تطوير: عبدالمنعم حاتم | جوال: 0544451878 | ايميل: info@mohatim.tech")
    run2.font.size = Pt(10)
    run2.bold = True
    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

if search_clicked:
    if business_type or city or country:
        query_parts = []
        if business_type: query_parts.append(business_type)
        location_parts = []
        if city: location_parts.append(city)
        if country: location_parts.append(country)
        if location_parts:
            query_parts.append("في")
            query_parts.append(", ".join(location_parts))
        query = " ".join(query_parts)
        
        st.write(f"### 📊 النتائج المباشرة لـ: {query}")
        progress_bar = st.progress(0)
        data_placeholder = st.empty()
        
        final_data = scrape_google_maps(query, max_res, data_placeholder, progress_bar)
        
        if final_data:
            st.success(f"✅ اكتمل بنجاح! تم العثور على {len(final_data)} مؤسسة.")
            df = pd.DataFrame(final_data)
            
            col_word, col_csv = st.columns(2)
            with col_word:
                word_data = create_word_doc(final_data)
                st.download_button("📥 تحميل Word (.docx)", data=word_data, file_name="results.docx", use_container_width=True)
            with col_csv:
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button("📥 تحميل CSV (.csv)", data=csv, file_name="results.csv", use_container_width=True)
        else:
            st.error("❌ لم يتم العثور على نتائج. حاول تغيير معايير البحث.")
    else:
        st.warning("⚠️ يرجى إدخال معلومة واحدة على الأقل للبحث.")
