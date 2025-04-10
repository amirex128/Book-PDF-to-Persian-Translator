import os
import glob
import re
import shutil
import time
from tqdm import tqdm
import PyPDF2
import google.generativeai as genai
import fitz  # PyMuPDF
import requests
import json
from bs4 import BeautifulSoup
import argparse  # Re-add argparse for command line arguments
import base64

# Try to import pdfkit
try:
    import pdfkit
    PDFKIT_AVAILABLE = True
except ImportError:
    PDFKIT_AVAILABLE = False
    print("For PDF conversion, please install: pip install pdfkit")
    print("And install wkhtmltopdf from: https://wkhtmltopdf.org/downloads.html")

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def extract_images_from_pdf_page(pdf_path, page_num, output_dir):
    """Extract images from PDF page using PyMuPDF"""
    image_list = []
    
    try:
        # Open PDF file
        doc = fitz.open(pdf_path)
        
        # Get the specified page
        page = doc[page_num]
        
        # Create image folder for this page
        page_images_dir = os.path.join(output_dir, f"page_{page_num + 1:04d}_images")
        if not os.path.exists(page_images_dir):
            os.makedirs(page_images_dir)
        
        # Extract images
        image_count = 0
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            
            # Save image
            image_filename = f"image_{img_index:03d}.{image_ext}"
            image_path = os.path.join(page_images_dir, image_filename)
            
            with open(image_path, "wb") as img_file:
                img_file.write(image_bytes)
            
            # Save image path and information
            image_info = {
                "path": image_path,
                "filename": image_filename,
                "relative_path": f"page_{page_num + 1:04d}_images/{image_filename}",
                "bbox": page.get_image_bbox(img)  # Image position on page
            }
            image_list.append(image_info)
            image_count += 1
        
        # Close PDF file
        doc.close()
        
        print(f"  {image_count} images extracted from page {page_num + 1}")
        return image_list
    
    except Exception as e:
        print(f"  Error extracting images from page {page_num + 1}: {str(e)}")
        return []

def translate_text_to_persian(text, api_key, conversation_history=None):
    """Translate text to Persian using Gemini API with conversation history"""
    if not text.strip():
        return "", "Empty text"
    
    # Maximum number of retries for rate limit errors
    max_retries = 3
    current_retry = 0
    wait_time = 60  # Wait time in seconds before retrying
    
    # Analyze the original text structure
    paragraphs = text.split('\n\n')
    has_headings = False
    has_bullet_points = False
    has_numbered_list = False
    has_code_blocks = False
    
    # Check for structural elements
    for para in paragraphs:
        if para.strip():
            # Check for headings (e.g., lines with fewer than 50 chars followed by a blank line)
            if len(para.strip()) < 50 and para.strip().endswith(':'):
                has_headings = True
            # Check for bullet points
            if re.search(r'^\s*[•\-\*]\s', para):
                has_bullet_points = True
            # Check for numbered lists
            if re.search(r'^\s*\d+\.\s', para):
                has_numbered_list = True
            # Check for possible code blocks (indentation, special characters)
            if re.search(r'^\s{4,}', para) or re.search(r'[{};()\[\]]', para):
                has_code_blocks = True
    
    # Prepare additional instructions based on structure
    structure_instructions = ""
    if has_headings:
        structure_instructions += "این متن دارای عنوان‌ها و سرفصل‌هایی است. لطفاً عنوان‌ها را با تگ <h3> و زیرعنوان‌ها را با تگ <h4> مشخص کنید. "
    if has_bullet_points:
        structure_instructions += "متن دارای لیست‌های نقطه‌ای است. لطفاً آنها را با تگ‌های <ul> و <li> مشخص کنید. "
    if has_numbered_list:
        structure_instructions += "متن دارای لیست‌های شماره‌دار است. لطفاً آنها را با تگ‌های <ol> و <li> مشخص کنید. "
    if has_code_blocks:
        structure_instructions += "متن ممکن است حاوی بلوک‌های کد باشد. لطفاً کدها را بدون ترجمه در <pre><code class=\"language-relevant_language\"> قرار دهید. "
    
    while current_retry <= max_retries:
        try:
            # Configure the Gemini API
            genai.configure(api_key=api_key)
            
            # Set up the model - using gemini-1.5-flash-8b as specified
            model = genai.GenerativeModel("models/gemini-1.5-flash-8b")
            
            # Create or continue a conversation
            if conversation_history is None:
                # Initialize a new conversation with detailed instructions
                conversation = model.start_chat(history=[])
                
                # Send initial instructions prompt
                initial_prompt = """
                من قصد دارم متن‌های انگلیسی فنی را به شما بدهم تا به فارسی ترجمه کنید. این متن‌ها از یک کتاب فنی هستند.
                لطفاً به دستورالعمل‌های زیر دقت کنید و همیشه آن‌ها را در ترجمه‌های خود رعایت کنید:
                
                قوانین بسیار مهم برای ترجمه (این قوانین از هر چیزی مهم‌تر هستند):
                
                1. اصطلاحات تخصصی و فنی را به انگلیسی نگه دارید و ترجمه نکنید. هیچ اصطلاح تخصصی را ترجمه نکنید.
                
                2. اولویت اصلی: حفظ اصطلاحات فنی به زبان اصلی (انگلیسی) است، نه ترجمه روان. اگر شک دارید، همیشه به انگلیسی نگه دارید.
                
                3. موارد زیر را هرگز ترجمه نکنید و عیناً به انگلیسی نگه دارید:
                
                   الف) اصطلاحات فنی مهندسی نرم‌افزار:
                   - مفاهیم معماری: API, HTTP, REST, SOAP, MVC, MVVM, Microservices, Monolith, Service, Controller, Middleware, Backend, Frontend
                   - فرمت‌های داده: JSON, XML, YAML, CSV, Protobuf, Schema
                   - پروتکل‌ها: TCP/IP, HTTP, WebSocket, gRPC, SSL, HTTPS
                   - تکنولوژی‌های وب: HTML, CSS, DOM, AJAX, WebAssembly, SPA
                   - مفاهیم امنیت: JWT, OAuth, CORS, XSS, Authentication, Authorization
                   - ابزارها و محیط‌ها: IDE, Repository, VCS, CI/CD, Pipeline
                   
                   ب) نام‌های کلاس‌ها، متدها و سرویس‌ها:
                   - نام‌های کلاس: UserService, InvoiceController, PaymentProcessor, DataContext, Repository
                   - نام‌های متد: getBalance(), processPayment(), validateUser(), findById(), execute()
                   - نام‌های سرویس‌ها: AuthService, Invoicing, PaymentGateway, EventBus, MessageQueue
                   
                   ج) اسامی متغیرها، پارامترها و فیلدها:
                   - متغیرها: userId, accountBalance, isActive, counter, index, temp
                   - پارامترها: customerId, amount, transactionDate, options, config
                   - فیلدها: firstName, lastName, email, createdAt, updatedAt
                   - ثابت‌ها: MAX_RETRY_COUNT, DEFAULT_TIMEOUT, API_VERSION
                   
                   د) الگوهای طراحی و معماری:
                   - الگوهای طراحی: Singleton, Factory, Observer, Strategy, Adapter, Facade
                   - الگوهای معماری: Saga, CQRS, Event Sourcing, Domain-Driven Design, Microservices
                   - اصول: SOLID, DRY, KISS, Separation of Concerns, Dependency Injection
                   - معماری‌های لایه‌ای: n-tier, Clean Architecture, Hexagonal Architecture
                   
                   ه) زبان‌های برنامه‌نویسی، فریم‌ورک‌ها و کتابخانه‌ها:
                   - زبان‌ها: Java, Python, C#, JavaScript, TypeScript, Go, Rust, Swift
                   - فریم‌ورک‌ها: Spring, .NET, React, Angular, Django, Express, Flask
                   - کتابخانه‌ها: JUnit, NumPy, Redux, Axios, Hibernate, Entity Framework
                   - پلتفرم‌ها: Node.js, JVM, .NET Core, WebAssembly
                   
                   و) اسامی خاص محصولات، ابزارها و شرکت‌ها:
                   - محصولات: Docker, Kubernetes, AWS, Azure, Kafka, RabbitMQ, Redis
                   - ابزارها: Git, Jenkins, Travis CI, GitHub Actions, Terraform, Ansible
                   - شرکت‌ها: Microsoft, Google, IBM, Oracle, Amazon, Atlassian
                   - سرویس‌های ابری: S3, EC2, Lambda, Azure Functions, Firestore
                   
                   ز) نام افراد، کتاب‌ها و مراجع:
                   - نویسندگان: Martin Fowler, Robert Martin, Eric Evans, Kent Beck
                   - مراجع: Gang of Four, Reactive Manifesto, Agile Manifesto
                   - کتاب‌ها: "Clean Code", "Domain-Driven Design", "Refactoring"
                
                4. قانون‌های کلیدی برای تشخیص اصطلاحات فنی:
                   - هر کلمه‌ای که حتی یک حرف بزرگ انگلیسی دارد، یک اصطلاح فنی است و نباید ترجمه شود.
                   - هر کلمه‌ای که با حروف بزرگ نوشته شده یا اختصار است، نباید ترجمه شود.
                   - هر عبارتی که با حروف مخفف (acronym) نوشته شده مانند API، REST، SOAP، نباید ترجمه شود.
                   - هر عبارتی که با خط تیره یا زیرخط جدا شده (مانند client-side یا snake_case)، احتمالاً اصطلاح فنی است.
                   - اصطلاحات شناخته شده مهندسی نرم‌افزار مانند endpoint، service، handler، را ترجمه نکنید.
                
                5. مثال‌های بیشتر از آنچه ترجمه نشود (به تفاوت‌ها توجه کنید):
                   - "Invoicing displays the view models to its actors" -> "Invoicing، view models را به actors خود نمایش می‌دهد"
                   - "Customers can get a JSON representation of invoices" -> "مشتریان می‌توانند یک representation از نوع JSON برای invoices دریافت کنند"
                   - "The code uses the Factory pattern to create Order objects" -> "کد از pattern به نام Factory برای ایجاد objects از نوع Order استفاده می‌کند"
                   - "InvoiceController calls PaymentService to process transactions" -> "InvoiceController، PaymentService را برای پردازش transactions فراخوانی می‌کند"
                   - "The app implements CQRS with event sourcing" -> "این app، CQRS را همراه با event sourcing پیاده‌سازی می‌کند"
                   - "REST APIs should use proper HTTP status codes" -> "REST APIs باید از HTTP status codes مناسب استفاده کنند"
                   - "The system has a PostgreSQL database with indexes on frequently queried fields" -> "این system دارای یک database از نوع PostgreSQL با indexes روی fields که مرتباً query می‌شوند، است"
                   - "The authentication middleware validates JWT tokens" -> "middleware مربوط به authentication، JWT tokens را اعتبارسنجی می‌کند"
                   - "React components should be stateless when possible" -> "components در React باید تا حد ممکن stateless باشند"
                   - "Dependency Injection helps with unit testing the service layer" -> "Dependency Injection به unit testing لایه service کمک می‌کند"
                   - "Apache Kafka is used for event streaming between microservices" -> "از Apache Kafka برای event streaming بین microservices استفاده می‌شود"
                   - "Redis provides in-memory caching for frequently accessed data" -> "Redis قابلیت caching درون حافظه را برای data‌هایی که مکرراً به آنها دسترسی می‌شود، فراهم می‌کند"
                   - "The backend exposes endpoints to process client requests" -> "backend، endpoints را برای پردازش client requests در معرض دید قرار می‌دهد"
                   - "Cloud-native applications often use container orchestration" -> "applications از نوع cloud-native اغلب از container orchestration استفاده می‌کنند"
                
                6. مطلقاً هیچ کلمه‌ای را که فکر می‌کنید ممکن است یک اصطلاح فنی باشد ترجمه نکنید. اگر در مورد ترجمه یک کلمه یا عبارت شک دارید، آن را به انگلیسی نگه دارید.
                
                7. اگر بخش‌هایی از متن حاوی کد برنامه‌نویسی است، آن را داخل تگ‌های <pre><code class="language-زبان_برنامه_نویسی"> و </code></pre> قرار دهید.
                   برای مثال، کد جاوا را به این صورت قرار دهید: <pre><code class="language-java">کد جاوا</code></pre>
                
                8. بسیار مهم: ساختار متن اصلی را حفظ کنید. پاراگراف‌بندی، سرفصل‌ها، لیست‌ها و بخش‌های کد را با تگ‌های HTML مناسب حفظ کنید:
                   - تیترها و عنوان‌ها: از <h3> برای عنوان اصلی و <h4> برای زیرعنوان استفاده کنید
                   - پاراگراف‌ها: هر پاراگراف را با <p> محصور کنید
                   - لیست‌های نقطه‌ای: از <ul><li>آیتم اول</li><li>آیتم دوم</li></ul> استفاده کنید
                   - لیست‌های شماره‌دار: از <ol><li>آیتم اول</li><li>آیتم دوم</li></ol> استفاده کنید
                   - کدها: از <pre><code class="language-xxx">کد</code></pre> استفاده کنید
                   - تأکید: از <strong> برای متن پررنگ و <em> برای متن ایتالیک استفاده کنید
                   - جداول: ساختار <table>, <tr>, <td> را حفظ کنید

                9.عنوان ها یا سرفصل ها سر تیتر ها یا هر مورد دیگری که به ظرت باید bold باشد با تگ html بهش این قابلیت رو بده.
                10.از تگ ها html زیاد استفاده کن برای زیبا سازی متن ترجمه شده و خوانا کردن ان ها و حتی بهتر متن های انگلیسی که وسط متن های فارسی ترجمه نشده ان رو داخل یک تگ span بزاری و دایرکتشن ltr بهش بدی تا تراز بندی بهتری داشته باشه
                11.متن های ترجمه شده باید به زبان فارسی روان و قابل فهم و گرامر درست نوشته شود و اگر امکانش هست ترجمه را کمی تغییر هم بده تا متن ترجمه شده به فارسی روان تر و خوانا تر و واضح تر باشد
                12.در صورتی که متن انگلیسی در قسمتی از متن فارسی ترجمه نشده باشد، آن را داخل یک تگ span بزاری و دایرکتشن ltr بهش بدی تا تراز بندی بهتری داشته باشه
                
                """
                
                # Send initial instructions
                initial_response = conversation.send_message(initial_prompt)
                
                # Check if model acknowledges the instructions
                # Now send the actual text to translate with a simpler prompt
                translate_prompt = f"""
                لطفاً متن زیر را با توجه به دستورالعمل‌های قبلی ترجمه کنید و ساختار متن اصلی را با استفاده از تگ‌های HTML حفظ کنید.
                
                {structure_instructions}
                
                متن برای ترجمه:
                {text}
                """
                response = conversation.send_message(translate_prompt)
                translated_text = response.text
            else:
                # Continue existing conversation - only send the text to translate
                conversation = conversation_history
                response = conversation.send_message(f"""لطفا متن زیر را ترجمه کنید و ساختار آن را با تگ‌های HTML حفظ کنید.
                
                {structure_instructions}
                
                متن برای ترجمه:
                {text}
                """)
                translated_text = response.text
            
            # Clean Markdown code block markers from the translated text
            translated_text = clean_markdown_blocks(translated_text)
            
            # Return the translated text and the conversation for future use
            return translated_text, conversation
        
        except Exception as e:
            error_message = str(e)
            print(f"Translation error: {error_message}")
            
            # Check if the error is related to rate limits
            if "429" in error_message or "rate" in error_message.lower() or "quota" in error_message.lower() or "limit" in error_message.lower():
                current_retry += 1
                if current_retry <= max_retries:
                    retry_wait = wait_time * current_retry  # Increase wait time with each retry
                    print(f"Rate limit detected. Retry {current_retry}/{max_retries} - Waiting for {retry_wait} seconds before retrying...")
                    time.sleep(retry_wait)
                else:
                    print(f"Maximum retries ({max_retries}) reached. Giving up on this translation.")
                    return "", error_message
            else:
                # For other types of errors, don't retry
                return "", error_message
    
    # This should not be reached, but just in case
    return "", "Maximum retries exceeded. Unable to translate."

def clean_markdown_blocks(text):
    """Remove Markdown code block markers and other AI formatting artifacts from text"""
    # Remove code block markers with language specifiers
    text = re.sub(r'```(?:html|css|javascript|js|python|java|csharp|c\+\+|cpp|c|bash|shell|sql|php|go|ruby|rust|swift|kotlin|typescript|tsx|jsx|xml|json|yaml|yml|markdown|md)?\s*\n', '', text)
    text = re.sub(r'\n\s*```', '', text)
    
    # Remove potential inline code markers
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove potential AI response prefixes
    text = re.sub(r'^(assistant:|AI:|ChatGPT:|Claude:|Gemini:)\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    
    # Remove potential HTML comments that might be inserted by the AI
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Clean up any duplicate newlines that might result from the above operations
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

def copy_font_assets(output_dir):
    """Copy font files to output directory"""
    assets_dir = os.path.join(os.getcwd(), "assets")
    if not os.path.exists(assets_dir):
        print("Assets folder not found.")
        return False
    
    # Create necessary folders in output directory
    fonts_dir = os.path.join(output_dir, "fonts")
    if not os.path.exists(fonts_dir):
        os.makedirs(fonts_dir)
    
    woff_dir = os.path.join(fonts_dir, "woff")
    woff2_dir = os.path.join(fonts_dir, "woff2")
    if not os.path.exists(woff_dir):
        os.makedirs(woff_dir)
    if not os.path.exists(woff2_dir):
        os.makedirs(woff2_dir)
    
    # Copy CSS file
    source_css = os.path.join(assets_dir, "Webfonts", "fontiran.css")
    target_css = os.path.join(output_dir, "fontiran.css")
    if os.path.exists(source_css):
        shutil.copy2(source_css, target_css)
    
    # Copy woff font files
    source_woff = os.path.join(assets_dir, "Webfonts", "fonts", "woff")
    if os.path.exists(source_woff):
        for font_file in glob.glob(os.path.join(source_woff, "*.woff")):
            shutil.copy2(font_file, woff_dir)
    
    # Copy woff2 font files
    source_woff2 = os.path.join(assets_dir, "Webfonts", "fonts", "woff2")
    if os.path.exists(source_woff2):
        for font_file in glob.glob(os.path.join(source_woff2, "*.woff2")):
            shutil.copy2(font_file, woff2_dir)
    
    return True

def create_html_content(persian_html, file_name, include_font_path, images=None):
    """Create HTML content with Persian translation and images"""
    # We no longer need to clean HTML tags as we're now actively preserving them
    persian_text = persian_html
    
    # Check if the translated text already contains HTML tags
    # If it doesn't have basic HTML structure, wrap it in Persian translation div
    if not re.search(r'<(p|h[1-6]|ul|ol|pre|table)\b', persian_text, re.IGNORECASE):
        persian_text = f"<p>{persian_text}</p>"
    
    # Wrap everything in a Persian translation div
    persian_html = f"<div dir='rtl' class='persian-translation'>{persian_text}</div>"
    
    # Extract page number from filename
    page_number = ""
    if re.search(r'page_(\d+)', file_name):
        page_number = re.search(r'page_(\d+)', file_name).group(1)
        # Remove leading zeros from page number
        page_number = str(int(page_number))
    
    # Add CSS font link
    font_link = ''
    if include_font_path:
        font_link = '<link rel="stylesheet" href="fontiran.css">'
    
    # Check if there are images to add
    has_images = images and len(images) > 0
    
    # Prepare image HTML - Include images inline with text when possible
    images_html = ""
    if has_images:
        images_html = "<div class='page-images'>\n"
        for img in images:
            images_html += f"    <img src='{img['relative_path']}' class='page-image' alt='Page {page_number} image' />\n"
        images_html += "</div>\n"
    
    # Create HTML content with text and images together
    html_content = f"""<!DOCTYPE html>
<html lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_name}</title>
    {font_link}
    <!-- Add Prism CSS for syntax highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css">
    <style>
        @page {{
            size: A4;
            margin: 1.5cm;
        }}
        html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'IRANSansX', 'Tahoma', 'Arial', sans-serif;
            line-height: 1.5;
            background-color: #f8f9fa;
            /* A4 size enforcement */
            width: 21cm;
            height: 29.7cm;
        }}
        .container {{
            width: 18cm; /* A4 width minus margins */
            min-height: 26.7cm; /* A4 height minus margins */
            background-color: white;
            padding: 1cm;
            box-sizing: border-box;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
        }}
        .persian-translation {{
            text-align: right;
            direction: rtl;
            font-size: 1em;
            font-family: 'IRANSansX', 'Tahoma', 'Arial', sans-serif;
            margin-bottom: 20px;
            /* Don't hide any overflow text, let it flow naturally */
            overflow: visible;
        }}
        /* Style for code blocks */
        pre[class*="language-"] {{
            direction: ltr;
            text-align: left;
            border-radius: 5px;
            margin: 1em 0;
            font-size: 0.9em;
            overflow-x: auto;
            white-space: pre-wrap;
        }}
        code {{
            direction: ltr;
            font-family: 'Courier New', Courier, monospace;
            background-color: #f5f5f5;
            border-radius: 3px;
            padding: 2px 4px;
        }}
        .page-images {{
            margin: 1cm 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1cm;
        }}
        .page-image {{
            max-width: 100%;
            height: auto;
            object-fit: contain;
        }}
        .page-number {{
            text-align: center;
            font-size: 1em;
            color: #444;
            font-weight: bold;
            padding: 5px 0;
            border-top: 1px solid #ddd;
            margin-top: 1.5em;
            margin-bottom: 2em;
        }}
        @media print {{
            body {{
                background: none;
                width: 21cm;
                height: 29.7cm;
            }}
            .container {{
                box-shadow: none;
                padding: 1cm;
                height: auto;
                min-height: auto;
            }}
            /* Page break utility */
            .page-break {{
                page-break-before: always;
            }}
            /* Ensure code blocks print with background colors */
            pre[class*="language-"] {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        {persian_html}
        
        {images_html}
        
        <div class="page-number">
            صفحه -{page_number}-
        </div>
    </div>
    
    <!-- Add Prism JS for syntax highlighting -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
    <script>
        // Initialize Prism highlighting
        document.addEventListener('DOMContentLoaded', (event) => {{
            /* Add line-numbers class to all pre elements if not already there */
            document.querySelectorAll('pre').forEach(block => {{
                if (!block.classList.contains('line-numbers')) {{
                    block.classList.add('line-numbers');
                }}
                
                /* If language class is not specified, add 'language-clike' as default */
                let hasLanguageClass = false;
                block.classList.forEach(className => {{
                    if (className.startsWith('language-')) {{
                        hasLanguageClass = true;
                    }}
                }});
                
                if (!hasLanguageClass) {{
                    block.classList.add('language-clike');
                }}
                
                /* Ensure code elements inside pre also have the correct language class */
                const codeElement = block.querySelector('code');
                if (codeElement) {{
                    if (!hasLanguageClass) {{
                        codeElement.classList.add('language-clike');
                    }} else {{
                        /* Copy the language class from pre to code if code doesn't have it */
                        block.classList.forEach(className => {{
                            if (className.startsWith('language-') && !codeElement.classList.contains(className)) {{
                                codeElement.classList.add(className);
                            }}
                        }});
                    }}
                }}
            }});
            
            /* Re-highlight all code blocks */
            if (window.Prism) {{
                Prism.highlightAll();
            }}
            
            /* Smart image scaling based on page content */
            const container = document.querySelector('.container');
            const textElement = document.querySelector('.persian-translation');
            const imageContainer = document.querySelector('.page-images');
            
            if (imageContainer && textElement) {{
                const images = imageContainer.querySelectorAll('.page-image');
                if (images.length > 0) {{
                    /* Calculate available space */
                    const containerHeight = container.clientHeight;
                    const textHeight = textElement.clientHeight;
                    const pageNumberHeight = document.querySelector('.page-number').clientHeight;
                    const availableHeight = containerHeight - textHeight - pageNumberHeight - 40; /* Extra margins */
                    
                    /* Estimate total height of images */
                    let totalImageHeight = 0;
                    images.forEach(img => {{
                        /* Wait for image to load to get accurate height */
                        img.onload = function() {{
                            /* Get natural aspect ratio */
                            const ratio = img.naturalWidth / img.naturalHeight;
                            /* Calculate height based on max width */
                            const estimatedHeight = (img.clientWidth / ratio);
                            totalImageHeight += estimatedHeight + 40; /* Add gap */
                            
                            /* Check if images don't fit */
                            if (totalImageHeight > availableHeight) {{
                                /* Try to scale down by up to 30% */
                                const scaleFactor = Math.max(0.7, availableHeight / totalImageHeight);
                                
                                /* If even with 30% reduction it doesn't fit, set page-break */
                                if (scaleFactor < 0.7) {{
                                    imageContainer.classList.add('page-break');
                                }} else {{
                                    /* Scale images to fit */
                                    images.forEach(i => {{
                                        i.style.maxWidth = (scaleFactor * 100) + '%';
                                    }});
                                }}
                            }}
                        }};
                        
                        /* Force layout calculation in case image is already loaded */
                        if (img.complete) {{
                            img.onload();
                        }}
                    }});
                }}
            }}
        }});
    </script>
</body>
</html>"""

    # Create an empty string for the overflow HTML (in case images don't fit and need a new page)
    overflow_html = ""
    
    # If we decide images need to be on a separate page, create that HTML separately
    # This will be handled by the JavaScript logic above based on content height
    
    return html_content, overflow_html

def detect_heading(text, page_num):
    """Detect if text contains a heading based on formatting and content"""
    # Initialize result
    headings = []
    
    # Simple heuristics to detect headings
    lines = text.split('\n')
    previous_line_empty = True  # Assume start of text is like an empty line
    
    for i, line in enumerate(lines):
        original_line = line
        line = line.strip()
        
        # Skip empty lines but track them
        if not line:
            previous_line_empty = True
            continue
        
        # Get next line if available
        next_line = lines[i+1].strip() if i+1 < len(lines) else ""
        
        # Potential heading characteristics
        is_heading = False
        heading_level = 0
        
        # 1. Check for English heading patterns
        if len(line) < 100:  # Headings are usually short
            # Chapter or section indicators (English)
            if re.match(r'^(chapter|section|part|appendix)\s+\d+', line.lower()):
                is_heading = True
                heading_level = 1
            
            # Numbered headings like "1.", "1.1", "1.1.1" (common in technical docs)
            elif re.match(r'^\d+\.(\d+\.)*\s+\w+', line):
                is_heading = True
                heading_level = line.count('.') + 1  # Level based on dots in numbering
            
            # Simple numbered headings "1 Introduction"
            elif re.match(r'^\d+\s+[A-Z]', line):
                is_heading = True
                heading_level = 1
            
            # All caps headings (common in academic papers and books)
            elif line.isupper() and len(line.split()) <= 10:
                is_heading = True
                heading_level = 2
            
            # Title case headings (proper nouns capitalized)
            elif line.istitle() and len(line.split()) <= 7:
                is_heading = True
                heading_level = 2
            
            # Headings often have different formatting - check if isolated
            elif previous_line_empty and (not next_line or next_line == ""):
                if len(line.split()) <= 10:  # Reasonably short isolated line
                    is_heading = True
                    heading_level = 3
        
        # 2. Check for Persian heading patterns
        if not is_heading and len(line) < 100:
            # Persian chapter indicators فصل، بخش، etc.
            if re.match(r'^(فصل|بخش|قسمت|پیوست)\s+\d+', line):
                is_heading = True
                heading_level = 1
            
            # Persian numbered headings
            elif re.match(r'^\d+[\-\.]\s+\S+', line):  # Number followed by period/dash and text
                is_heading = True
                heading_level = 1
            
            # Check for lines with special formatting that might indicate headings
            # If line is isolated (empty lines before and after) and short
            elif previous_line_empty and (not next_line or next_line == "") and len(line.split()) <= 8:
                is_heading = True
                heading_level = 3
            
            # Check for semantic indicators that might suggest a heading (Persian)
            # Common heading starters in Persian
            elif re.match(r'^(مقدمه|نتیجه‌گیری|روش|مروری بر|بررسی)', line):
                is_heading = True
                heading_level = 2
        
        # 3. Check for heading with underline pattern (text followed by a line of --- or ===)
        if not is_heading and next_line and re.match(r'^[=\-_]{3,}$', next_line):
            is_heading = True
            heading_level = 1 if '=' in next_line else 2  # === is usually level 1, --- is level 2
        
        # If this looks like a heading, add it to the results
        if is_heading:
            # Clean up the heading (remove extra whitespace, etc.)
            clean_heading = ' '.join(line.split())
            
            # Remove common prefix numbers for cleaner display
            display_heading = re.sub(r'^\d+[\.\s]+', '', clean_heading)
            
            # Add to our headings list
            headings.append({
                'text': display_heading,
                'level': heading_level,
                'page': page_num + 1  # Page numbers are 1-based
            })
        
        # Update previous line status
        previous_line_empty = False
    
    # Remove duplicate headings on the same page (keep the one with higher level/priority)
    filtered_headings = []
    seen_texts = set()
    
    # Sort by level (lower level number = higher priority)
    sorted_headings = sorted(headings, key=lambda x: x['level'])
    
    for heading in sorted_headings:
        text = heading['text'].lower()
        if text not in seen_texts:
            filtered_headings.append(heading)
            seen_texts.add(text)
    
    return filtered_headings

def create_html_book(html_files, output_html, output_dir, file_base_name, toc_headings=None):
    """Create a single HTML book file from multiple HTML files"""
    try:
        print(f"\nCreating HTML book: {output_html}")
        print(f"  Combining {len(html_files)} HTML pages into a single book...")
        
        # Filter out non-existent files
        existing_files = [f for f in html_files if os.path.exists(f)]
        if not existing_files:
            print("No HTML files found for combining.")
            return False
        
        # Sort files by page number
        existing_files.sort(key=lambda x: int(re.search(r'page_(\d+)_fa', x).group(1)))
        
        # Analyze text content to better detect chapter/section headings if not provided
        if not toc_headings or len(toc_headings) == 0:
            print("  No headings found. Analyzing PDF content to detect chapter titles...")
            toc_headings = []
            current_chapter = None
            
            # Try to load headings from JSON if it exists
            headings_file = os.path.join(os.path.dirname(existing_files[0]), "..", "headings.json")
            if os.path.exists(headings_file):
                try:
                    with open(headings_file, 'r', encoding='utf-8') as f:
                        toc_headings = json.load(f)
                    print(f"  Loaded {len(toc_headings)} headings from headings.json")
                except Exception as e:
                    print(f"  Error loading headings from JSON: {str(e)}")
            
            # If still no headings, analyze content
            if not toc_headings or len(toc_headings) == 0:
                for html_file in existing_files:
                    with open(html_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Get page number
                    page_match = re.search(r'page_(\d+)_fa', html_file)
                    if page_match:
                        page_num = int(page_match.group(1))
                        
                        # Find any potential headings in this page
                        # Look for bold text, larger text, or text that appears to be a heading
                        # This is a simple approach - adjust as needed for your specific PDFs
                        soup = BeautifulSoup(content, 'html.parser')
                        translation_div = soup.find('div', class_='persian-translation')
                        
                        if translation_div:
                            text_content = translation_div.get_text()
                            lines = text_content.split('\n')
                            
                            for line in lines:
                                line = line.strip()
                                if not line:
                                    continue
                                    
                                # Look for potential chapter/section indicators
                                if (re.search(r'^(فصل|بخش|قسمت)\s+\d+', line) or 
                                    re.search(r'^(chapter|section|part)\s+\d+', line, re.IGNORECASE) or
                                    (line.isupper() and len(line) < 80) or
                                    re.match(r'^\d+[\.\-]\s+[A-Z]', line) or
                                    (len(line) < 60 and line.strip().endswith(':'))):
                                    
                                    level = 1
                                    toc_headings.append({
                                        'text': line.strip(),
                                        'level': level,
                                        'page': page_num
                                    })
                                    current_chapter = line.strip()
                                    
                                # Look for potential subsections
                                elif current_chapter and (
                                    re.match(r'^\d+\.\d+\s+[A-Z]', line) or 
                                    (len(line) < 60 and line[0].isupper() and line.endswith(':'))):
                                    
                                    toc_headings.append({
                                        'text': line.strip(),
                                        'level': 2,
                                        'page': page_num
                                    })
        
        # Create book structure
        book_html = """<!DOCTYPE html>
<html lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>""" + file_base_name + """</title>
    <style>
        @page {
            size: A4;
            margin: 1.5cm;
        }
        body {
            font-family: 'IRANSansX', 'Tahoma', 'Arial', sans-serif;
            line-height: 1.5;
            background-color: #f8f9fa;
            margin: 0;
            padding: 0;
        }
        .book {
            max-width: 1000px;
            margin: 0 auto;
            background-color: white;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            padding: 2cm;
        }
        .chapter {
            margin-bottom: 2em;
            page-break-after: always;
        }
        .chapter:last-child {
            page-break-after: auto;
        }
        .chapter-content {
            width: 100%;
        }
        .persian-translation {
            text-align: right;
            direction: rtl;
            font-size: 1em;
        }
        .page-number {
            position: absolute;
            bottom: 0.5cm;
            width: 100%;
            text-align: center;
            font-size: 1em;
            color: #444;
            font-weight: bold;
            padding: 5px 0;
            border-top: 1px solid #ddd;
        }
        .page-images {
            margin: 1cm 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1cm;
        }
        .page-image {
            max-width: 90%;
            height: auto;
            object-fit: contain;
        }
        /* Style for code blocks */
        pre[class*="language-"] {
            direction: ltr;
            text-align: left;
            border-radius: 5px;
            margin: 1em 0;
            font-size: 0.9em;
            overflow-x: auto;
            white-space: pre-wrap;
            background-color: #f5f5f5;
            padding: 1em;
        }
        code {
            direction: ltr;
            font-family: 'Courier New', Courier, monospace;
            background-color: #f5f5f5;
            border-radius: 3px;
            padding: 2px 4px;
        }
        .cover-page {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100%;
            text-align: center;
        }
        .book-title {
            font-size: 2em;
            margin-bottom: 1cm;
        }
        .book-subtitle {
            font-size: 1.5em;
            margin-bottom: 2cm;
            color: #555;
        }
        .toc {
            text-align: right;
            direction: rtl;
        }
        .toc-title {
            font-size: 1.5em;
            margin-bottom: 1cm;
        }
        .toc-entry {
            margin-bottom: 0.5em;
        }
        .toc-entry a {
            text-decoration: none;
            color: #333;
        }
        .toc-entry a:hover {
            text-decoration: underline;
        }
        .toc-page {
            float: left;
        }
        @media print {
            body {
                background: none;
            }
            .book {
                box-shadow: none;
                margin: 0;
                padding: 1.5cm;
            }
            .page {
                page-break-after: always;
            }
            pre[class*="language-"] {
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }
        }
        .toc-level1 {
            font-weight: bold;
            margin-top: 0.8em;
        }
        .toc-level2 {
            margin-left: 1.5em;
        }
        .toc-level3 {
            margin-left: 3em;
            font-size: 0.9em;
        }
    </style>
    <!-- Add Prism CSS for syntax highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css">
</head>
<body>
    <div class="book">
        <!-- Cover Page -->
        <div class="dual-page-container">
            <div class="cover-page">
                <h1 class="book-title">""" + file_base_name + """</h1>
                <h2 class="book-subtitle">نسخه ترجمه شده</h2>
                <p>تاریخ ایجاد: """ + time.strftime("%Y/%m/%d") + """</p>
            </div>
        </div>
        
        <!-- Table of Contents -->
        <div class="page">
            <div class="toc">
                <h2 class="toc-title">فهرست مطالب</h2>
"""
        
        # Generate table of contents entries
        page_number = 3  # Start after cover and TOC
        
        # Use extracted headings if available, otherwise create basic TOC from page numbers
        if toc_headings and len(toc_headings) > 0:
            # Sort headings by page number
            toc_headings.sort(key=lambda x: (x['page'], x['level']))
            
            # Group headings by level for hierarchical display
            current_level1 = None
            current_level2 = None
            
            for heading in toc_headings:
                level = heading['level']
                heading_text = heading['text']
                heading_page = heading['page']
                
                # Calculate the book page number (offset by 2 for cover and TOC)
                book_page = heading_page + 2
                
                # First level headings
                if level == 1:
                    current_level1 = heading_text
                    current_level2 = None
                    book_html += f'                <div class="toc-entry toc-level1"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                # Second level headings
                elif level == 2:
                    current_level2 = heading_text
                    if current_level1:
                        book_html += f'                <div class="toc-entry toc-level2"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                    else:
                        book_html += f'                <div class="toc-entry toc-level1"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                # Third level headings
                elif level >= 3:
                    if current_level2:
                        book_html += f'                <div class="toc-entry toc-level3"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                    elif current_level1:
                        book_html += f'                <div class="toc-entry toc-level2"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                    else:
                        book_html += f'                <div class="toc-entry toc-level1"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
        else:
            # Default to page-based TOC if no headings detected
            for i, html_file in enumerate(existing_files):
                page_match = re.search(r'page_(\d+)_fa', html_file)
                if page_match:
                    original_page = int(page_match.group(1))
                    book_html += f'                <div class="toc-entry"><a href="#page-{i+3}">صفحه {original_page}<span class="toc-page">{page_number}</span></a></div>\n'
                    page_number += 1
        
        # Close TOC section
        book_html += """            </div>
        </div>
"""
        
        # Process and integrate each HTML file content
        for i, html_file in enumerate(existing_files):
            print(f"  Processing page {i+3}/{len(existing_files)}: {os.path.basename(html_file)}")
            
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Get original page number
                page_match = re.search(r'page_(\d+)_fa', html_file)
                original_page = page_match.group(1) if page_match else str(i+1)
                
                # Extract content from the individual HTML
                # Find the persian-translation div content
                translation_match = re.search(r'<div\s+dir=[\'"]rtl[\'"]\s+class=[\'"]persian-translation[\'"]>(.*?)</div>', content, re.DOTALL)
                text_content = ""
                if translation_match:
                    text_content = translation_match.group(1).strip()
                
                # Find image tags
                image_match = re.search(r'<div\s+class=[\'"]page-images[\'"]>(.*?)</div>', content, re.DOTALL)
                images_content = ""
                if image_match:
                    # Update image paths to be relative to the output directory
                    images_content = image_match.group(0)
                    
                    # Copy any images referenced into the output directory
                    img_tags = re.findall(r'<img\s+src=[\'"]([^\'"]+)[\'"]', images_content)
                    for img_src in img_tags:
                        source_path = os.path.join(os.path.dirname(html_file), img_src)
                        target_dir = os.path.join(output_dir, os.path.dirname(img_src))
                        target_path = os.path.join(output_dir, img_src)
                        
                        # Create directories if they don't exist
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir)
                        
                        # Copy image file
                        if os.path.exists(source_path):
                            shutil.copy2(source_path, target_path)
                
                # Add page to book
                book_html += f'        <!-- Page {i+3} -->\n'
                book_html += f'        <div class="chapter" id="page-{i+3}">\n'
                book_html += f'            <div class="chapter-content">\n'
                book_html += f'                <div dir="rtl" class="persian-translation">{text_content}</div>\n'
                book_html += f'                {images_content}\n'
                book_html += f'                <div class="page-number">صفحه -{i+3}-</div>\n'
                book_html += f'            </div>\n'
                book_html += f'        </div>\n'
                
            except Exception as e:
                print(f"  Error processing {html_file}: {str(e)}")
        
        # Close HTML structure
        book_html += """    </div>
    
    <!-- Add Prism JS for syntax highlighting -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
    <script>
        // Initialize Prism highlighting
        document.addEventListener('DOMContentLoaded', (event) => {
            // Add line-numbers class to all pre elements if not already there
            document.querySelectorAll('pre').forEach(block => {
                if (!block.classList.contains('line-numbers')) {
                    block.classList.add('line-numbers');
                }
                
                // If language class is not specified, add 'language-clike' as default
                let hasLanguageClass = false;
                block.classList.forEach(className => {
                    if (className.startsWith('language-')) {
                        hasLanguageClass = true;
                    }
                });
                
                if (!hasLanguageClass) {
                    block.classList.add('language-clike');
                }
                
                // Ensure code elements inside pre also have the correct language class
                const codeElement = block.querySelector('code');
                if (codeElement) {
                    if (!hasLanguageClass) {
                        codeElement.classList.add('language-clike');
                    } else {
                        // Copy the language class from pre to code if code doesn't have it
                        block.classList.forEach(className => {
                            if (className.startsWith('language-') && !codeElement.classList.contains(className)) {
                                codeElement.classList.add(className);
                            }
                        });
                    }
                }
            });
            
            // Re-highlight all code blocks
            if (window.Prism) {
                Prism.highlightAll();
            }
        });
    </script>
</body>
</html>"""
        
        # Save the combined book HTML
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(book_html)
        
        print(f"  HTML book created successfully: {output_html}")
        return True
    
    except Exception as e:
        print(f"Error during HTML book creation: {str(e)}")
        return False

def extract_pdf_page_as_image(pdf_path, page_num, output_dir, dpi=300):
    """Extract a single page from PDF as an image"""
    try:
        # Open the PDF
        doc = fitz.open(pdf_path)
        
        # Get the page
        page = doc[page_num]
        
        # Create a directory for the page images if it doesn't exist
        page_images_dir = os.path.join(output_dir, f"page_{page_num + 1:04d}_original")
        if not os.path.exists(page_images_dir):
            os.makedirs(page_images_dir)
        
        # Set the zoom factors (higher values mean higher resolution)
        zoom = dpi / 72  # Default DPI in PDF is 72
        mat = fitz.Matrix(zoom, zoom)
        
        # Render page to a pixmap (image)
        pix = page.get_pixmap(matrix=mat)
        
        # Save the image
        image_path = os.path.join(page_images_dir, f"original_page.png")
        pix.save(image_path)
        
        # Return the path to the saved image
        return image_path
    
    except Exception as e:
        print(f"Error extracting page {page_num + 1} as image: {str(e)}")
        return None

def create_dual_page_html(persian_html, original_pdf_path, page_num, file_name, include_font_path, images=None):
    """Create HTML content with original PDF page and Persian translation side by side"""
    # We no longer need to clean HTML tags as we're now actively preserving them
    persian_text = persian_html
    
    # Check if the translated text already contains HTML tags
    # If it doesn't have basic HTML structure, wrap it in Persian translation div
    if not re.search(r'<(p|h[1-6]|ul|ol|pre|table)\b', persian_text, re.IGNORECASE):
        persian_text = f"<p>{persian_text}</p>"
    
    # Wrap everything in a Persian translation div
    persian_html = f"<div dir='rtl' class='persian-translation'>{persian_text}</div>"
    
    # Extract page number from filename
    page_number = ""
    if re.search(r'page_(\d+)', file_name):
        page_number = re.search(r'page_(\d+)', file_name).group(1)
        # Remove leading zeros from page number
        page_number = str(int(page_number))
    
    # Extract the original PDF page as an image
    temp_dir = os.path.dirname(file_name)
    pdf_dir = os.path.dirname(original_pdf_path)
    
    # Extract PDF page as image (page_num is 0-based, page_number is 1-based)
    image_path = extract_pdf_page_as_image(original_pdf_path, int(page_number) - 1, temp_dir)
    
    # Relative path to the image
    if image_path:
        image_rel_path = os.path.relpath(image_path, temp_dir)
    else:
        image_rel_path = ""
    
    # Add CSS font link
    font_link = ''
    if include_font_path:
        font_link = '<link rel="stylesheet" href="fontiran.css">'
    
    # Check if there are images to add
    has_images = images and len(images) > 0
    
    # Prepare image HTML - Include images inline with text when possible
    images_html = ""
    if has_images:
        images_html = "<div class='page-images'>\n"
        for img in images:
            images_html += f"    <img src='{img['relative_path']}' class='page-image' alt='Page {page_number} image' />\n"
        images_html += "</div>\n"
    
    # Create HTML content with dual page layout
    html_content = f"""<!DOCTYPE html>
<html lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_name}</title>
    {font_link}
    <!-- Add Prism CSS for syntax highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css">
    <style>
        @page {{
            size: A4 landscape;
            margin: 0;
        }}
        html, body {{
            height: 100%;
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: 'IRANSansX', 'Tahoma', 'Arial', sans-serif;
            line-height: 1.5;
            background-color: #f8f9fa;
            /* A3 landscape size to accommodate two A4 pages side by side */
            width: 42cm;
            height: 29.7cm;
        }}
        .dual-page-container {{
            display: flex;
            width: 100%;
            height: 100%;
        }}
        .page-container {{
            width: 50%;
            height: 100%;
            box-sizing: border-box;
            padding: 0.5cm;
            overflow: hidden;
        }}
        .persian-page {{
            background-color: white;
            height: 100%;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            padding: 1cm;
            direction: rtl;
            overflow-y: auto;
        }}
        .original-page {{
            background-color: white;
            height: 100%;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }}
        .original-pdf-image {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }}
        .persian-translation {{
            text-align: right;
            direction: rtl;
            font-size: 1em;
            font-family: 'IRANSansX', 'Tahoma', 'Arial', sans-serif;
            margin-bottom: 20px;
            /* Don't hide any overflow text, let it flow naturally */
            overflow: visible;
        }}
        /* Style for code blocks */
        pre[class*="language-"] {{
            direction: ltr;
            text-align: left;
            border-radius: 5px;
            margin: 1em 0;
            font-size: 0.9em;
            overflow-x: auto;
            white-space: pre-wrap;
        }}
        code {{
            direction: ltr;
            font-family: 'Courier New', Courier, monospace;
            background-color: #f5f5f5;
            border-radius: 3px;
            padding: 2px 4px;
        }}
        .page-images {{
            margin: 1cm 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1cm;
        }}
        .page-image {{
            max-width: 100%;
            height: auto;
            object-fit: contain;
        }}
        .page-number {{
            text-align: center;
            font-size: 1em;
            color: #444;
            font-weight: bold;
            padding: 5px 0;
            border-top: 1px solid #ddd;
            margin-top: 1.5em;
            margin-bottom: 2em;
        }}
        @media print {{
            body {{
                background: none;
                width: 42cm;
                height: 29.7cm;
            }}
            .persian-page, .original-page {{
                box-shadow: none;
                border: 1px solid #ddd;
            }}
            /* Ensure code blocks print with background colors */
            pre[class*="language-"] {{
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="dual-page-container">
        <!-- Persian Translation (Right Side) -->
        <div class="page-container">
            <div class="persian-page">
                {persian_html}
                
                {images_html}
                
                <div class="page-number">
                    صفحه -{page_number}-
                </div>
            </div>
        </div>
        
        <!-- Original PDF Page (Left Side) -->
        <div class="page-container">
            <div class="original-page">
                <img src="{image_rel_path}" class="original-pdf-image" alt="Original PDF Page {page_number}" />
            </div>
        </div>
    </div>
    
    <!-- Add Prism JS for syntax highlighting -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
    <script>
        // Initialize Prism highlighting
        document.addEventListener('DOMContentLoaded', (event) => {{
            /* Add line-numbers class to all pre elements if not already there */
            document.querySelectorAll('pre').forEach(block => {{
                if (!block.classList.contains('line-numbers')) {{
                    block.classList.add('line-numbers');
                }}
                
                /* If language class is not specified, add 'language-clike' as default */
                let hasLanguageClass = false;
                block.classList.forEach(className => {{
                    if (className.startsWith('language-')) {{
                        hasLanguageClass = true;
                    }}
                }});
                
                if (!hasLanguageClass) {{
                    block.classList.add('language-clike');
                }}
                
                /* Ensure code elements inside pre also have the correct language class */
                const codeElement = block.querySelector('code');
                if (codeElement) {{
                    if (!hasLanguageClass) {{
                        codeElement.classList.add('language-clike');
                    }} else {{
                        /* Copy the language class from pre to code if code doesn't have it */
                        block.classList.forEach(className => {{
                            if (className.startsWith('language-') && !codeElement.classList.contains(className)) {{
                                codeElement.classList.add(className);
                            }}
                        }});
                    }}
                }}
            }});
            
            /* Re-highlight all code blocks */
            if (window.Prism) {{
                Prism.highlightAll();
            }}
        }});
    </script>
</body>
</html>"""

    # Create an empty string for the overflow HTML (in case images don't fit and need a new page)
    overflow_html = ""
    
    return html_content, overflow_html

def extract_and_translate_pdf(pdf_path, api_key, limit=None):
    """Extract and translate a PDF file"""
    
    pdf_dir = os.path.dirname(pdf_path)
    pdf_filename = os.path.basename(pdf_path)
    file_base_name = os.path.splitext(pdf_filename)[0]
    sanitized_name = sanitize_filename(file_base_name)
    
    # Create output directory if it doesn't exist
    output_dir_base = os.path.join(os.getcwd(), "output")
    if not os.path.exists(output_dir_base):
        os.makedirs(output_dir_base)
    
    # Create a subdirectory with the PDF name in the output directory
    pdf_output_dir = os.path.join(output_dir_base, sanitized_name)
    if not os.path.exists(pdf_output_dir):
        os.makedirs(pdf_output_dir)
        print(f"Created output directory: {pdf_output_dir}")
    else:
        print(f"Using existing output directory: {pdf_output_dir}")
        
    # Define output HTML paths in the PDF-specific output directory
    translation_html = os.path.join(pdf_output_dir, f"{file_base_name}_Farsi.html")
    dual_view_html = os.path.join(pdf_output_dir, f"{file_base_name}_Dual_View.html")
    
    # Create directory for this book if it doesn't exist, or keep existing one
    temp_dir = os.path.join(pdf_dir, sanitized_name)
    temp_dir_exists = os.path.exists(temp_dir)
    
    if not temp_dir_exists:
        os.makedirs(temp_dir)
        print(f"Created directory: {temp_dir}")
    else:
        print(f"Using existing directory: {temp_dir}")
    
    # Copy font files to output directory if needed
    fonts_path = os.path.join(temp_dir, "fontiran.css")
    fonts_copied = os.path.exists(fonts_path)
    
    if not fonts_copied:
        fonts_copied = copy_font_assets(temp_dir)
        if fonts_copied:
            print("Font files copied successfully.")
        else:
            print("Font file copying encountered issues.")
    
    # Find existing translated HTML files to determine the last processed page
    existing_html_files = glob.glob(os.path.join(temp_dir, "page_*_fa.html"))
    processed_page_numbers = []
    
    for html_file in existing_html_files:
        page_match = re.search(r'page_(\d+)_fa\.html', html_file)
        if page_match:
            processed_page_numbers.append(int(page_match.group(1)))
    
    # Initialize the lists of HTML files
    html_files = []
    # Add existing HTML files to the list
    html_files.extend(existing_html_files)
    
    # Lists to store headings for table of contents
    toc_headings = []
    
    try:
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            
            print(f"Processing: {pdf_filename} ({num_pages} pages)")
            
            # Apply page limit if specified
            pages_to_process = num_pages
            if limit and limit < num_pages:
                pages_to_process = limit
                print(f"Limited to {pages_to_process} pages out of {num_pages} pages")
            
            # Check if all pages have been processed
            if processed_page_numbers and len(processed_page_numbers) > 0:
                # Sort HTML files by page number
                html_files.sort(key=lambda x: int(re.search(r'page_(\d+)_fa', x).group(1)))
                
                # Count the number of expected pages vs. processed pages
                expected_pages = min(pages_to_process, num_pages)
                processed_pages_in_range = sum(1 for p in processed_page_numbers if p <= expected_pages)
                
                # If all pages are processed but HTML books don't exist or failed to create
                if processed_pages_in_range >= expected_pages:
                    print(f"All {expected_pages} pages have already been translated.")
                    
                    create_both = False
                    if not os.path.exists(translation_html):
                        print("Translation-only HTML book doesn't exist. Attempting to create it from existing translations...")
                        create_both = True
                    
                    if not os.path.exists(dual_view_html):
                        print("Dual-view HTML book doesn't exist. Attempting to create it from existing translations...")
                        create_both = True
                    
                    if not create_both:
                        print(f"Both HTML books already exist.")
                        return True
                    
                    # Create both books from existing translations
                    translation_success = create_html_book(html_files, translation_html, pdf_output_dir, file_base_name, toc_headings)
                    dual_view_success = create_dual_page_book(html_files, dual_view_html, pdf_output_dir, file_base_name, pdf_path, toc_headings)
                    
                    if translation_success and dual_view_success:
                        print(f"Both HTML books created successfully.")
                        return True
                    else:
                        print("Failed to create HTML books from existing translations.")
                        return False
                else:
                    # Continue from where we left off
                    last_processed_page = max(processed_page_numbers) if processed_page_numbers else 0
                    start_page = last_processed_page
                    print(f"Resuming from page {start_page + 1} (found {len(processed_page_numbers)} processed pages out of {expected_pages})")
            else:
                # Start from the beginning
                start_page = 0
            
            # 1. Extract text and images from PDF for unprocessed pages
            extracted_pages = []
            page_images = {}  # Dictionary to store images for each page
            
            # Extract text and images from each unprocessed page and save to file
            for page_num in tqdm(range(start_page, pages_to_process), desc="Extracting text and images", unit="page"):
                # Skip already processed pages
                if page_num + 1 in processed_page_numbers:
                    continue
                
                # Get page
                page = pdf_reader.pages[page_num]
                
                # Extract text
                text = page.extract_text()
                
                # Detect headings in the text
                if text and text.strip():
                    headings = detect_heading(text, page_num)
                    if headings:
                        # Add headings to the table of contents list
                        toc_headings.extend(headings)
                
                # Output file path (numbered from 1)
                output_file = os.path.join(temp_dir, f"page_{page_num + 1:04d}.txt")
                
                # Only save non-empty files to the list of pages to process
                if text and text.strip():
                    extracted_pages.append(output_file)
                    # Save text to file
                    with open(output_file, 'w', encoding='utf-8') as txt_file:
                        txt_file.write(text)
                else:
                    # Still save empty files, but don't add to processing list
                    with open(output_file, 'w', encoding='utf-8') as txt_file:
                        txt_file.write("")
                    print(f"  Page {page_num + 1} is empty, skipping")
                
                # Extract images from current page
                images = extract_images_from_pdf_page(pdf_path, page_num, temp_dir)
                if images:
                    page_images[f"page_{page_num + 1:04d}"] = images
                    
                    # If page has images but no text, create a simple HTML for it
                    if not text or not text.strip():
                        base_name = f"page_{page_num + 1:04d}"
                        html_file = os.path.join(temp_dir, f"{base_name}_fa.html")
                        
                        # Skip if this file already exists
                        if os.path.exists(html_file):
                            if html_file not in html_files:
                                html_files.append(html_file)
                            continue
                        
                        # Create HTML contents
                        page_html, _ = create_html_content(
                            "این صفحه فقط شامل تصاویر است.", # "This page contains only images"
                            base_name,
                            fonts_copied,
                            images=images
                        )
                        
                        # Save HTML file
                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(page_html)
                        html_files.append(html_file)
    
    except Exception as e:
        print(f"Error processing {pdf_filename}: {str(e)}")
        return False
    
    # 2. Translate each page's text to Persian and create HTML with translated text and images
    translated_files = 0
    failed_files = 0
    
    # Create a conversation for this PDF file
    conversation = None
    
    for txt_file in tqdm(extracted_pages, desc="Translating", unit="page"):
        file_name = os.path.basename(txt_file)
        base_name = os.path.splitext(file_name)[0]
        
        # Path for translated HTML file
        html_file = os.path.join(temp_dir, f"{base_name}_fa.html")
        
        # Skip if this file is already translated
        if html_file in existing_html_files or os.path.exists(html_file):
            print(f"  Page {base_name} already translated, skipping")
            if html_file not in html_files and os.path.exists(html_file):
                html_files.append(html_file)
            continue
        
        try:
            # Read original text
            with open(txt_file, 'r', encoding='utf-8') as f:
                original_text = f.read()
            
            # Skip empty files (shouldn't get here due to earlier check, but just in case)
            if not original_text.strip():
                print(f"  Page {base_name} is empty, skipping translation")
                continue
            
            # Translate text using the conversation context
            translated_text, conversation = translate_text_to_persian(original_text, api_key, conversation)
            
            if translated_text:
                # Check for images for this page
                page_images_list = page_images.get(base_name, [])
                
                # For regular view, just show the translation
                page_html, _ = create_html_content(
                    translated_text, 
                    base_name, 
                    fonts_copied,
                    images=page_images_list
                )
                
                # Save HTML file
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(page_html)
                
                html_files.append(html_file)
                translated_files += 1
                
                # Prevent API rate limits with a small pause between requests
                time.sleep(1)
            else:
                print(f"\n  Error translating {file_name}")
                failed_files += 1
        
        except Exception as e:
            print(f"\n  Error processing {file_name}: {str(e)}")
            failed_files += 1
    
    # Add any image-only pages that weren't in extracted_pages
    for page_num in range(pages_to_process):
        base_name = f"page_{page_num + 1:04d}"
        html_file = os.path.join(temp_dir, f"{base_name}_fa.html")
        
        # Skip if this file is already created
        if html_file in html_files or os.path.exists(html_file):
            if html_file not in html_files and os.path.exists(html_file):
                html_files.append(html_file)
            continue
            
        # If this page has images but no text file was processed for it
        if base_name in page_images:
            images = page_images[base_name]
            
            # Create HTML with just images
            page_html, _ = create_html_content(
                "این صفحه فقط شامل تصاویر است.", # "This page contains only images"
                base_name,
                fonts_copied,
                images=images
            )
            
            # Save HTML file
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(page_html)
            
            html_files.append(html_file)
    
    # Sort files by page number
    html_files.sort(key=lambda x: int(re.search(r'page_(\d+)_fa', x).group(1)))
    
    # Display translation summary
    print("\nTranslation Summary:")
    print(f"  Previously processed pages: {len(processed_page_numbers)}")
    print(f"  Newly translated pages: {translated_files}")
    print(f"  Translation errors: {failed_files}")
    print(f"  Pages with images: {len(page_images)}")
    
    # Save the headings to a JSON file for later use
    headings_file = os.path.join(temp_dir, "headings.json")
    with open(headings_file, 'w', encoding='utf-8') as f:
        json.dump(toc_headings, f, ensure_ascii=False, indent=2)
    
    # Extract all PDF pages as images for dual-page view
    print("\nExtracting original PDF pages as images...")
    for page_num in tqdm(range(pages_to_process), desc="Extracting page images", unit="page"):
        # Skip if the image already exists
        image_path = os.path.join(temp_dir, f"page_{page_num + 1:04d}_original", "original_page.png")
        if not os.path.exists(image_path):
            extract_pdf_page_as_image(pdf_path, page_num, temp_dir)
    
    # After translation is complete, create both HTML books from HTML files
    if html_files:
        # Create translation-only book first
        translation_success = create_html_book(html_files, translation_html, pdf_output_dir, file_base_name, toc_headings)
        if translation_success:
            print(f"Translation-only HTML book created: {translation_html}")
        else:
            print("Failed to create translation-only HTML book.")
        
        # Create dual-view book
        dual_view_success = create_dual_page_book(html_files, dual_view_html, pdf_output_dir, file_base_name, pdf_path, toc_headings)
        if dual_view_success:
            print(f"Dual-view HTML book created: {dual_view_html}")
        else:
            print("Failed to create dual-view HTML book.")
        
        # Return success if at least one book was created successfully
        return translation_success or dual_view_success
    else:
        print("No HTML files were created. Translation failed.")
        return False

def create_dual_page_book(html_files, output_html, output_dir, file_base_name, pdf_path, toc_headings=None):
    """Create a single HTML book file with dual page layout (original PDF + translation)"""
    try:
        print(f"\nCreating dual-page HTML book: {output_html}")
        print(f"  Combining {len(html_files)} pages into a dual-page book...")
        
        # Filter out non-existent files
        existing_files = [f for f in html_files if os.path.exists(f)]
        if not existing_files:
            print("No HTML files found for combining.")
            return False
        
        # Sort files by page number
        existing_files.sort(key=lambda x: int(re.search(r'page_(\d+)_fa', x).group(1)))
        
        # Create book structure
        book_html = """<!DOCTYPE html>
<html lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>""" + file_base_name + """ - Dual View</title>
    <style>
        @page {
            size: A3 landscape;
            margin: 0;
        }
        body {
            font-family: 'IRANSansX', 'Tahoma', 'Arial', sans-serif;
            line-height: 1.5;
            background-color: #f8f9fa;
            margin: 0;
            padding: 0;
        }
        .book {
            width: 100%;
            margin: 0 auto;
            background-color: white;
        }
        .dual-page-container {
            display: flex;
            width: 100%;
            height: 29.7cm; /* A4 height */
            page-break-after: always;
        }
        .dual-page-container:last-child {
            page-break-after: auto;
        }
        .page-container {
            width: 50%;
            height: 100%;
            box-sizing: border-box;
            padding: 0.5cm;
            overflow: hidden;
        }
        .persian-page {
            background-color: white;
            height: 100%;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            padding: 1cm;
            direction: rtl;
            overflow-y: auto;
        }
        .original-page {
            background-color: white;
            height: 100%;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }
        .original-pdf-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }
        .persian-translation {
            text-align: right;
            direction: rtl;
            font-size: 1em;
        }
        .page-images {
            margin: 1cm 0;
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1cm;
        }
        .page-image {
            max-width: 90%;
            height: auto;
            object-fit: contain;
        }
        .page-number {
            text-align: center;
            font-size: 1em;
            color: #444;
            font-weight: bold;
            padding: 5px 0;
            border-top: 1px solid #ddd;
            margin-top: 1.5em;
        }
        .cover-page {
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            height: 100%;
            width: 100%;
            text-align: center;
        }
        .book-title {
            font-size: 2.5em;
            margin-bottom: 1cm;
        }
        .book-subtitle {
            font-size: 1.8em;
            margin-bottom: 2cm;
            color: #555;
        }
        /* Style for code blocks */
        pre[class*="language-"] {
            direction: ltr;
            text-align: left;
            border-radius: 5px;
            margin: 1em 0;
            font-size: 0.9em;
            overflow-x: auto;
            white-space: pre-wrap;
            background-color: #f5f5f5;
            padding: 1em;
        }
        code {
            direction: ltr;
            font-family: 'Courier New', Courier, monospace;
            background-color: #f5f5f5;
            border-radius: 3px;
            padding: 2px 4px;
        }
        @media print {
            body {
                background: none;
            }
            .book {
                box-shadow: none;
                margin: 0;
            }
            .persian-page, .original-page {
                box-shadow: none;
                border: 1px solid #eee;
            }
            pre[class*="language-"] {
                print-color-adjust: exact;
                -webkit-print-color-adjust: exact;
            }
        }
        /* TOC Styles */
        .toc {
            text-align: right;
            direction: rtl;
            padding: 0 1cm;
        }
        .toc-entry {
            margin-bottom: 0.5em;
        }
        .toc-entry a {
            text-decoration: none;
            color: #333;
            display: flex;
            justify-content: space-between;
        }
        .toc-entry a:hover {
            text-decoration: underline;
        }
        .toc-page {
            float: left;
        }
        .toc-level1 {
            font-weight: bold;
            margin-top: 0.8em;
        }
        .toc-level2 {
            margin-left: 1.5em;
        }
        .toc-level3 {
            margin-left: 3em;
            font-size: 0.9em;
        }
    </style>
    <!-- Add Prism CSS for syntax highlighting -->
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css">
</head>
<body>
    <div class="book">
        <!-- Cover Page -->
        <div class="dual-page-container">
            <div class="cover-page">
                <h1 class="book-title">""" + file_base_name + """</h1>
                <h2 class="book-subtitle">نسخه ترجمه شده</h2>
                <p>تاریخ ایجاد: """ + time.strftime("%Y/%m/%d") + """</p>
            </div>
        </div>
        
        <!-- Table of Contents -->
        <div class="dual-page-container">
            <div class="page-container" style="width: 100%;">
                <div class="persian-page">
                    <div class="toc">
                        <h2 class="toc-title" style="text-align: center; font-size: 1.8em; margin-bottom: 1.5cm;">فهرست مطالب</h2>
"""
        
        # Generate table of contents entries
        page_number = 3  # Start after cover and TOC
        
        # Use extracted headings if available, otherwise create basic TOC from page numbers
        if toc_headings and len(toc_headings) > 0:
            # Sort headings by page number
            toc_headings.sort(key=lambda x: (x['page'], x['level']))
            
            # Group headings by level for hierarchical display
            current_level1 = None
            current_level2 = None
            
            for heading in toc_headings:
                level = heading['level']
                heading_text = heading['text']
                heading_page = heading['page']
                
                # Calculate the book page number (offset by 2 for cover and TOC)
                book_page = heading_page + 2
                
                # First level headings
                if level == 1:
                    current_level1 = heading_text
                    current_level2 = None
                    book_html += f'                        <div class="toc-entry toc-level1"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                # Second level headings
                elif level == 2:
                    current_level2 = heading_text
                    if current_level1:
                        book_html += f'                        <div class="toc-entry toc-level2"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                    else:
                        book_html += f'                        <div class="toc-entry toc-level1"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                # Third level headings
                elif level >= 3:
                    if current_level2:
                        book_html += f'                        <div class="toc-entry toc-level3"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                    elif current_level1:
                        book_html += f'                        <div class="toc-entry toc-level2"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
                    else:
                        book_html += f'                        <div class="toc-entry toc-level1"><a href="#page-{book_page}">{heading_text}<span class="toc-page">{book_page}</span></a></div>\n'
        else:
            # Default to page-based TOC if no headings detected
            for i, html_file in enumerate(existing_files):
                page_match = re.search(r'page_(\d+)_fa', html_file)
                if page_match:
                    original_page = int(page_match.group(1))
                    book_html += f'                        <div class="toc-entry"><a href="#page-{i+3}">صفحه {original_page}<span class="toc-page">{page_number}</span></a></div>\n'
                    page_number += 1
        
        # Close TOC section
        book_html += """                    </div>
                </div>
            </div>
        </div>
"""

        # Process and integrate each HTML file content
        for i, html_file in enumerate(existing_files):
            print(f"  Processing page {i+1}/{len(existing_files)}: {os.path.basename(html_file)}")
            
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Get original page number
                page_match = re.search(r'page_(\d+)_fa', html_file)
                if page_match:
                    original_page_num = int(page_match.group(1))
                else:
                    original_page_num = i + 1
                
                # Extract content from the individual HTML
                translation_match = re.search(r'<div\s+dir=[\'"]rtl[\'"]\s+class=[\'"]persian-translation[\'"]>(.*?)</div>', content, re.DOTALL)
                text_content = ""
                if translation_match:
                    text_content = translation_match.group(1).strip()
                
                # Find image tags
                image_match = re.search(r'<div\s+class=[\'"]page-images[\'"]>(.*?)</div>', content, re.DOTALL)
                images_content = ""
                if image_match:
                    # Update image paths to be relative to the output directory
                    images_content = image_match.group(0)
                    
                    # Copy any images referenced into the output directory
                    img_tags = re.findall(r'<img\s+src=[\'"]([^\'"]+)[\'"]', images_content)
                    for img_src in img_tags:
                        source_path = os.path.join(os.path.dirname(html_file), img_src)
                        target_dir = os.path.join(output_dir, os.path.dirname(img_src))
                        target_path = os.path.join(output_dir, img_src)
                        
                        # Create directories if they don't exist
                        if not os.path.exists(target_dir):
                            os.makedirs(target_dir)
                        
                        # Copy image file
                        if os.path.exists(source_path):
                            shutil.copy2(source_path, target_path)
                
                # Get the path to the original PDF page image from the temp directory
                temp_dir = os.path.dirname(html_file)
                image_path = os.path.join(temp_dir, f"page_{original_page_num:04d}_original", "original_page.png")
                
                # If the image exists in the temp directory, copy it to the output directory
                if os.path.exists(image_path):
                    # Create output directory for original page image
                    output_image_dir = os.path.join(output_dir, f"page_{original_page_num:04d}_original")
                    os.makedirs(output_image_dir, exist_ok=True)
                    
                    # Copy the image to the output directory
                    output_image_path = os.path.join(output_image_dir, "original_page.png")
                    shutil.copy2(image_path, output_image_path)
                    
                    # Calculate relative path to the image from the output directory
                    image_rel_path = os.path.relpath(output_image_path, os.path.dirname(output_html))
                else:
                    # Fallback message if image doesn't exist
                    image_rel_path = ""
                    image_content = "<div style='text-align: center; padding: 2cm;'>Original PDF page could not be loaded</div>"
                
                # Add dual-page layout to book
                book_html += f'''
        <!-- Page {i+1} -->
        <div class="dual-page-container" id="page-{i+3}">
            <!-- Persian Translation (Right Side) -->
            <div class="page-container">
                <div class="persian-page">
                    <div dir="rtl" class="persian-translation">{text_content}</div>
                    {images_content}
                    <div class="page-number">صفحه {original_page_num}</div>
                </div>
            </div>
            
            <!-- Original PDF Page (Left Side) -->
            <div class="page-container">
                <div class="original-page">
                    <img src="{image_rel_path}" class="original-pdf-image" alt="Original PDF Page {original_page_num}" />
                </div>
            </div>
        </div>
'''
                
            except Exception as e:
                print(f"  Error processing {html_file}: {str(e)}")
        
        # Add closing tags to the book HTML
        book_html += """
    </div>
    
    <!-- Add Prism JS for syntax highlighting -->
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
    <script>
        // Initialize Prism highlighting
        document.addEventListener('DOMContentLoaded', (event) => {{
            /* Re-highlight all code blocks */
            if (window.Prism) {{
                Prism.highlightAll();
            }}
        }});
    </script>
</body>
</html>
"""
        
        # Format the book HTML with the actual values
        book_html = book_html.replace("{file_base_name}", file_base_name)
        
        # Save the combined book HTML
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(book_html)
        
        print(f"  Dual-page HTML book created successfully: {output_html}")
        return True
    
    except Exception as e:
        print(f"Error during dual-page HTML book creation: {str(e)}")
        return False

def process_all_pdfs(books_dir, api_key, limit=None):
    """Process all PDF files in the specified directory"""
    # Check if directory exists
    if not os.path.exists(books_dir):
        print(f"Error: Directory '{books_dir}' does not exist.")
        return
    
    # Find all PDF files
    pdf_files = glob.glob(os.path.join(books_dir, "*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in '{books_dir}'.")
        return
    
    print(f"Found {len(pdf_files)} PDF files for processing.")
    
    successful = 0
    failed = 0
    
    # Process each PDF
    for pdf_path in pdf_files:
        print(f"\n{'='*50}")
        print(f"Processing file: {os.path.basename(pdf_path)}")
        print(f"{'='*50}")
        
        # Process the PDF - both normal and dual-page versions will be created
        result = extract_and_translate_pdf(pdf_path, api_key, limit)
        
        if result:
            successful += 1
        else:
            failed += 1
    
    # Display overall summary
    print("\n" + "="*30)
    print("Overall Processing Summary:")
    print(f"  Total PDF files: {len(pdf_files)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Output format: Both translation-only and dual-page views")
    print("="*30)

def retranslate_page(pdf_path, page_number, api_key):
    """Re-translate a specific page from a PDF file and update the final output"""
    pdf_dir = os.path.dirname(pdf_path)
    pdf_filename = os.path.basename(pdf_path)
    file_base_name = os.path.splitext(pdf_filename)[0]
    sanitized_name = sanitize_filename(file_base_name)
    
    # Get the temp and output directories
    temp_dir = os.path.join(pdf_dir, sanitized_name)
    output_dir_base = os.path.join(os.getcwd(), "output")
    pdf_output_dir = os.path.join(output_dir_base, sanitized_name)
    translation_html = os.path.join(pdf_output_dir, f"{file_base_name}_Farsi.html")
    dual_view_html = os.path.join(pdf_output_dir, f"{file_base_name}_Dual_View.html")
    
    # Check if the directories exist
    if not os.path.exists(temp_dir):
        print(f"Error: Processing directory not found for {pdf_filename}")
        return False
    
    if not os.path.exists(pdf_output_dir):
        os.makedirs(pdf_output_dir)
    
    # Extract the specified page from the PDF
    try:
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            
            if page_number <= 0 or page_number > num_pages:
                print(f"Error: Page number {page_number} is out of range (1-{num_pages})")
                return False
            
            # Extract text from the specified page (page_number is 1-based, index is 0-based)
            page = pdf_reader.pages[page_number - 1]
            text = page.extract_text()
            
            if not text.strip():
                print(f"Warning: Page {page_number} appears to be empty.")
            
            # Save the text to a temporary file
            page_file = os.path.join(temp_dir, f"page_{page_number:04d}.txt")
            with open(page_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Extract images from the page
            images = extract_images_from_pdf_page(pdf_path, page_number - 1, temp_dir)
            
            # Extract the original PDF page as an image
            extract_pdf_page_as_image(pdf_path, page_number - 1, temp_dir)
            
            # Copy font files if needed
            fonts_path = os.path.join(temp_dir, "fontiran.css")
            fonts_copied = os.path.exists(fonts_path)
            if not fonts_copied:
                fonts_copied = copy_font_assets(temp_dir)
            
            # Translate the text
            translated_text, _ = translate_text_to_persian(text, api_key)
            
            if not translated_text:
                print(f"Error: Failed to translate page {page_number}")
                return False
            
            # Create HTML content with the translation
            page_html, _ = create_html_content(
                translated_text,
                f"page_{page_number:04d}",
                fonts_copied,
                images=images
            )
            
            # Save the HTML file
            html_file = os.path.join(temp_dir, f"page_{page_number:04d}_fa.html")
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(page_html)
            
            print(f"Page {page_number} has been re-translated successfully.")
            
            # Rebuild the complete HTML books
            html_files = glob.glob(os.path.join(temp_dir, "page_*_fa.html"))
            if not html_files:
                print("Error: No HTML files found to create the books.")
                return False
            
            # Load existing headings if available
            headings_file = os.path.join(temp_dir, "headings.json")
            toc_headings = []
            if os.path.exists(headings_file):
                try:
                    with open(headings_file, 'r', encoding='utf-8') as f:
                        toc_headings = json.load(f)
                except Exception as e:
                    print(f"Error loading headings: {str(e)}")
            
            # Rebuild both books
            translation_success = create_html_book(html_files, translation_html, pdf_output_dir, file_base_name, toc_headings)
            dual_view_success = create_dual_page_book(html_files, dual_view_html, pdf_output_dir, file_base_name, pdf_path, toc_headings)
            
            if translation_success and dual_view_success:
                print(f"Both HTML books have been updated with the re-translated page.")
                return True
            elif translation_success:
                print(f"Translation-only HTML book has been updated, but dual-view book creation failed.")
                return True
            elif dual_view_success:
                print(f"Dual-view HTML book has been updated, but translation-only book creation failed.")
                return True
            else:
                print("Error: Failed to update the HTML books.")
                return False
            
    except Exception as e:
        print(f"Error during re-translation: {str(e)}")
        return False

if __name__ == "__main__":
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Extract, translate and convert PDF files to Persian HTML')
    parser.add_argument('--api-key', default="AIzaSyD1HS27l8i8N5jBnSCixhGH3sRiH81i9HQ", help='Gemini API key')
    parser.add_argument('--books-dir', default=os.path.join(os.getcwd(), "books"), help='Directory containing PDF files')
    parser.add_argument('--limit', type=int, help='Maximum number of pages to process from each book')
    parser.add_argument('--retranslate', nargs=2, metavar=('PDF_FILE', 'PAGE_NUMBER'), 
                        help='Re-translate a specific page from a PDF file. Format: --retranslate "pdf_file.pdf" 42')
    
    args = parser.parse_args()
    
    # Check if re-translation is requested
    if args.retranslate:
        pdf_file, page_num = args.retranslate
        try:
            page_num = int(page_num)
            # Check if the PDF file exists
            pdf_path = pdf_file
            if not os.path.exists(pdf_path):
                # Try with books directory
                pdf_path = os.path.join(args.books_dir, pdf_file)
                if not os.path.exists(pdf_path):
                    print(f"Error: PDF file '{pdf_file}' not found.")
                    exit(1)
            
            print(f"Re-translating page {page_num} of '{pdf_file}'...")
            retranslate_page(pdf_path, page_num, args.api_key)
        except ValueError:
            print(f"Error: Invalid page number '{page_num}'. Must be an integer.")
            exit(1)
    else:
        # Normal processing mode
        print(f"Using books directory: {args.books_dir}")
        
        # Process all PDFs
        process_all_pdfs(
            books_dir=args.books_dir,
            api_key=args.api_key,
            limit=args.limit
        )
        
        print("Processing completed.") 