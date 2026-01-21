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
import subprocess

# وظيفة لتثبيت متصفح Playwright تلقائياً على السيرفر
def install_playwright_browsers():
    try:
        subprocess.run(["playwright", "install", "chromium"], check=True)
    except Exception as e:
        st.error(f"Error installing browsers: {e}")

# تنفيذ التثبيت عند بدء التطبيق (للمنصات السحابية مثل Streamlit Cloud)
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
        
        # محاولة البحث في عدة صفحات شائعة
        targets = [url]
        base_url = "/".join(url.split("/")[:3])
        # قائمة الصفحات المحتملة للاتصال
        potential_pages = ['contact', 'contact-us', 'about', 'about-us', 'support', 'terms']
        for page_name in potential_pages:
            targets.append(f"{base_url}/{page_name}")
            targets.append(f"{base_url}/ar/{page_name}") # دعم المواقع العربية
            targets.append(f"{base_url}/en/{page_name}") # دعم المواقع الإنجليزية
        
        # إزالة التكرار مع الحفاظ على الترتيب
        targets = list(dict.fromkeys(targets))
        
        all_emails = set()
        for target in targets:
            try:
                response = requests.get(target, timeout=5, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
                if response.status_code == 200:
                    # استخراج الإيميلات مع استبعاد الصور والملفات الشائعة
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
    # التأكد من تثبيت المتصفح قبل البدء (حل أخير للسيرفرات السحابية)
    try:
        subprocess.run(["python", "-m", "playwright", "install", "chromium"], check=True)
    except:
        pass

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                locale="ar-SA",
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()
            results = []
            
            # استخدام wait_until="load" بدلاً من networkidle لتجنب التعليق
            page.goto(f"https://www.google.com/maps/search/{search_query}", wait_until="load", timeout=60000)
            time.sleep(5)
            
            # معالجة متقدمة لصفحة الموافقة
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
            # زيادة محاولات التمرير لضمان الوصول للعدد المطلوب
            max_scroll_attempts = 30 
            
            while len(results) < max_results and scroll_attempts < max_scroll_attempts:
                # محاولة البحث عن العناصر بعدة طرق (Selectors متنوعة)
                item_selectors = [
                    'a[href*="/maps/place/"]',
                    '.hfpxzc',
                    'div[role="article"] a'
                ]
                
                items = []
                for sel in item_selectors:
                    found = page.locator(sel).all()
                    if len(found) > 0:
                        items = found
                        break
                
                if not items:
                    # إذا لم نجد عناصر، نحاول التمرير لأسفل ربما لم تتحمل بعد
                    page.mouse.wheel(0, 2000)
                    time.sleep(3)
                    scroll_attempts += 1
                    continue

                for item in items:
                    if len(results) >= max_results:
                        break
                        
                    try:
                        # استخراج الاسم من الـ aria-label أو النص
                        card_name = item.get_attribute("aria-label") or item.inner_text().split('\n')[0]
                        if not card_name or card_name in seen_names or "N/A" in card_name:
                            continue
                        
                        # النقر على العنصر مع محاولة التمرير إليه أولاً
                        item.scroll_into_view_if_needed()
                        item.click(force=True)
                        time.sleep(3) # زيادة وقت الانتظار للتحميل
                        
                        # استخراج البيانات من اللوحة الجانبية
                        name = "N/A"
                        # محددات أسماء المؤسسات الأكثر شيوعاً حالياً
                        name_selectors = ['h1.DUwDvf', 'h1.lfPIob', 'h1']
                        for selector in name_selectors:
                            if page.locator(selector).count() > 0:
                                name = page.locator(selector).first.inner_text()
                                break
                        
                        if name == "N/A" or name in seen_names:
                            continue
                            
                        seen_names.add(name)
                        
                        # استخراج باقي التفاصيل
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
                        if emails_in_maps:
                            email = emails_in_maps[0]
                        elif website != "N/A":
                            email = extract_emails_from_url(website)

                        new_entry = {
                            "🏢 اسم المؤسسة": name,
                            "📞 رقم الهاتف": phone,
                            "🌐 الموقع الالكتروني": website,
                            "📧 الايميل": email,
                            "📍 موقع المكتب": address
                        }
                        results.append(new_entry)
                        
                        if progress_bar:
                            progress_bar.progress(len(results) / max_results)
                        if data_placeholder:
                            data_placeholder.dataframe(pd.DataFrame(results), use_container_width=True)
                            
                    except Exception:
                        continue
                
                # التمرير لتحميل المزيد
                feed_selector = 'div[role="feed"]'
                if page.locator(feed_selector).count() > 0:
                    page.locator(feed_selector).evaluate("el => el.scrollBy(0, 2000)")
                else:
                    page.mouse.wheel(0, 2000)
                
                time.sleep(3)
                scroll_attempts += 1
                    
            browser.close()
            return results
        except Exception as e:
            if 'browser' in locals(): browser.close()
            return results

# إعدادات الواجهة
st.set_page_config(page_title="مستخرج بيانات خرائط جوجل", layout="wide")

# تصميم عصري وأنيق مع تجاوز تنسيقات Streamlit
style_code = """<link href="https://fonts.googleapis.com/css2?family=Tajawal:wght@400;500;700&display=swap" rel="stylesheet"><style>
    body, .stApp { font-family: 'Tajawal', sans-serif !important; direction: RTL !important; text-align: right !important; background-color: #F0F2F6 !important; }
    h1, h2, h3, p, span, label { font-family: 'Tajawal', sans-serif !important; text-align: right !important; color: #1E3A8A !important; }
    
    /* تنسيق مربعات الإدخال */
    .stTextInput div[data-baseweb="input"], .stNumberInput div[data-baseweb="input"] {
        border: 2px solid #2563EB !important;
        border-radius: 12px !important;
        background-color: white !important;
    }
    
    /* تنسيق جدول النتائج - LTR */
    [data-testid="stDataFrame"], [data-testid="stTable"] {
        direction: LTR !important;
        text-align: left !important;
        background-color: white !important;
        border-radius: 10px !important;
        padding: 10px !important;
    }
    
    /* إخفاء الرسائل المزعجة */
    [data-testid="stInputHelperText"], .st-emotion-cache-1pxm8v5, .st-emotion-cache-10trblm { display: none !important; }
    
    /* تنسيق الزر */
    .stButton button {
        background-color: #2563EB !important;
        color: white !important;
        border-radius: 12px !important;
        padding: 0.5rem 1rem !important;
        width: 100% !important;
        font-weight: bold !important;
        font-family: 'Tajawal', sans-serif !important;
        font-size: 1.1rem !important;
        border: none !important;
        transition: all 0.3s ease !important;
        height: 45px !important;
    }

    .stButton button p {
        color: white !important;
    }
    
    .stButton button:hover, .stButton button:active, .stButton button:focus {
        background-color: #1E40AF !important;
        color: white !important;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06) !important;
        transform: translateY(-1px) !important;
    }

    .stButton button:hover p {
        color: white !important;
    }
    
    # MainMenu, footer, header { visibility: hidden !important; }
    
    .developer-footer {
        position: fixed;
        bottom: 0;
        left: 0;
        width: 100%;
        background-color: #1E3A8A;
        color: white;
        text-align: center;
        padding: 10px 0;
        font-family: 'Tajawal', sans-serif;
        z-index: 100;
        border-top: 3px solid #2563EB;
    }
    </style>"""
st.markdown(style_code, unsafe_allow_html=True)

# إضافة حقوق المطور في الأسفل
st.markdown("""
    <div class="developer-footer">
        👨‍💻 تطوير: <b>عبدالمنعم حاتم</b> | 📞: +966544451878 | 📧: info@mohatim.tech
    </div>
    """, unsafe_allow_html=True)

st.title("🔍 نظام استخراج البيانات الذكي")

# تنظيم المدخلات بشكل أنيق
with st.container():
    st.markdown("### 🛠️ إعدادات البحث")
    col1, col2, col3 = st.columns(3)
    with col1:
        business_type = st.text_input("مجال المؤسسة", placeholder="مطاعم، فنادق...")
    with col2:
        city = st.text_input("المدينة", placeholder="الرياض، دبي...")
    with col3:
        country = st.text_input("الدولة", placeholder="السعودية...")

    col_res, col_btn = st.columns([1, 2])
    with col_res:
        max_res = st.number_input("عدد النتائج المطلوبة", min_value=1, max_value=500, value=10, step=1)
    with col_btn:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True) # موازنة المسافة مع العنوان
        search_clicked = st.button("🚀 ابدأ عملية الاستخراج الآن")

def create_word_doc(data):
    doc = Document()
    
    # إعداد النمط الافتراضي لدعم العربية
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Arial'
    font.size = Pt(12)
    
    doc.add_heading('نتائج استخراج بيانات خرائط جوجل', 0).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    for entry in data:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        p.add_run(f"🏢 اسم المؤسسة: ").bold = True
        p.add_run(f"{entry['🏢 اسم المؤسسة']}\n")
        
        p.add_run(f"📞 رقم الهاتف: ").bold = True
        p.add_run(f"{entry['📞 رقم الهاتف']}\n")
        
        p.add_run(f"🌐 الموقع الالكتروني: ").bold = True
        p.add_run(f"{entry['🌐 الموقع الالكتروني']}\n")
        
        p.add_run(f"📧 الايميل: ").bold = True
        p.add_run(f"{entry['📧 الايميل']}\n")
        
        p.add_run(f"📍 موقع المكتب: ").bold = True
        p.add_run(f"{entry['📍 موقع المكتب']}\n")
        
        doc.add_paragraph("-" * 30).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    
    # إضافة حقوق المطور في نهاية الملف
    doc.add_paragraph("\n")
    dev_info = doc.add_paragraph()
    dev_info.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = dev_info.add_run("تم الاستخراج بواسطة نظام استخراج البيانات الذكي")
    run.font.size = Pt(10)
    run.italic = True
    
    dev_contact = doc.add_paragraph()
    dev_contact.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run2 = dev_contact.add_run("تطوير: عبدالمنعم حاتم | جوال: +966544451878 | ايميل: info@mohatim.tech")
    run2.font.size = Pt(10)
    run2.bold = True

    bio = io.BytesIO()
    doc.save(bio)
    return bio.getvalue()

st.markdown("<br>", unsafe_allow_html=True)
if search_clicked:
    # التحقق من وجود قيمة واحدة على الأقل للبحث
    if business_type or city or country:
        # بناء نص البحث بشكل أكثر دقة لضمان تصفية المدينة والدولة
        query_parts = []
        if business_type:
            query_parts.append(business_type)
        
        location_parts = []
        if city:
            location_parts.append(city)
        if country:
            location_parts.append(country)
            
        if location_parts:
            query_parts.append("في")
            query_parts.append(", ".join(location_parts))
        
        query = " ".join(query_parts)
        st.info(f"جاري البحث عن: {query}...")
        
        progress_bar = st.progress(0)
        data_placeholder = st.empty()
        
        final_data = scrape_google_maps(query, max_res, data_placeholder, progress_bar)
        
        if final_data:
            st.success("اكتملت عملية الاستخراج!")
            
            df = pd.DataFrame(final_data)
            
            # عرض أزرار التحميل في أعمدة
            col_word, col_csv = st.columns(2)
            
            with col_word:
                # إنشاء ملف Word
                word_data = create_word_doc(final_data)
                st.download_button(
                    label="تحميل النتائج كـ Word (.docx)",
                    data=word_data,
                    file_name="google_maps_results.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            
            with col_csv:
                # إنشاء ملف CSV
                csv = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="تحميل النتائج كـ CSV (.csv)",
                    data=csv,
                    file_name="google_maps_results.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        else:
            st.error("لم يتم العثور على نتائج.")
    else:
        st.warning("يرجى إدخال معلومة واحدة على الأقل للبحث (المجال أو المدينة أو الدولة).")
