import re
import time
import google.generativeai as genai
import datetime
import os
import random
from typing import List, Dict, Tuple, Optional, Any

# Global API key usage tracking
api_key_usage = {}

def clean_markdown_blocks(text):
    """Remove markdown code blocks and other artifacts from text"""
    # Remove code block markers with language specifiers
    text = re.sub(r'```\w*\n', '', text)
    text = re.sub(r'```', '', text)
    
    # Remove inline code markers
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove AI response prefixes
    text = re.sub(r'^(AI:|Assistant:|آنالیز:|ترجمه:)\s*', '', text, flags=re.MULTILINE)
    
    # Remove any HTML comments
    text = re.sub(r'<!--.*?-->', '', text, flags=re.DOTALL)
    
    # Clean up duplicate newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text

class APIKeyManager:
    """
    Class to manage multiple API keys, track usage and avoid rate limits
    """
    def __init__(self, primary_key: str, additional_keys: List[str] = None):
        """
        Initialize the API key manager with a primary key and optional additional keys
        """
        self.primary_key = primary_key
        self.additional_keys = additional_keys or []
        self.all_keys = [primary_key] + self.additional_keys
        
        # Initialize usage tracking for all keys
        global api_key_usage
        for key in self.all_keys:
            if key not in api_key_usage:
                api_key_usage[key] = {
                    'count': 0,
                    'last_used': None,
                    'rate_limited_until': None,
                    'rate_limit_count': 0
                }
    
    def get_next_available_key(self) -> str:
        """
        Get the next available API key that's not rate limited
        
        Returns:
            The next available API key
        """
        global api_key_usage
        now = datetime.datetime.now()
        
        # Filter out rate-limited keys
        available_keys = []
        for key in self.all_keys:
            if key not in api_key_usage:
                available_keys.append(key)
                continue
                
            rate_limited_until = api_key_usage[key].get('rate_limited_until')
            if rate_limited_until is None or now > rate_limited_until:
                available_keys.append(key)
        
        if not available_keys:
            # If all keys are rate-limited, pick the one that will be available soonest
            soon_available = sorted(
                self.all_keys, 
                key=lambda k: api_key_usage[k].get('rate_limited_until', now) if api_key_usage[k].get('rate_limited_until') is not None else now
            )[0]
            
            if api_key_usage[soon_available].get('rate_limited_until') is not None:
                wait_time = (api_key_usage[soon_available]['rate_limited_until'] - now).total_seconds()
                print(f"All API keys are rate limited. Using key with shortest wait time: {wait_time:.1f} seconds")
            else:
                print("All API keys are rate limited. Using key with no rate limit information.")
            
            return soon_available
            
        # Sort available keys by usage count (prefer least used keys)
        available_keys.sort(key=lambda k: api_key_usage[k]['count'])
        
        # Select a key with some randomness (80% chance of using least used key, 20% chance of using others)
        if len(available_keys) > 1 and random.random() > 0.8:
            # Randomly select from all available keys except the most used one
            return random.choice(available_keys[:-1])
        else:
            # Use the least used key
            return available_keys[0]
    
    def mark_key_used(self, key: str):
        """
        Mark an API key as used, updating its usage statistics
        
        Args:
            key: The API key that was used
        """
        global api_key_usage
        api_key_usage[key]['count'] += 1
        api_key_usage[key]['last_used'] = datetime.datetime.now()
    
    def mark_key_rate_limited(self, key: str, duration_minutes: int = 1):
        """
        Mark an API key as rate limited for a specified duration
        
        Args:
            key: The API key that hit a rate limit
            duration_minutes: How long to avoid using this key
        """
        global api_key_usage
        now = datetime.datetime.now()
        api_key_usage[key]['rate_limited_until'] = now + datetime.timedelta(minutes=duration_minutes)
        api_key_usage[key]['rate_limit_count'] += 1
        
        # Increase cooldown period based on number of rate limits this key has hit
        # This helps prevent repeatedly hitting limits on problematic keys
        rate_limit_count = api_key_usage[key]['rate_limit_count']
        if rate_limit_count > 1:
            # Progressive backoff: 1 min, 2 min, 4 min, 8 min max
            backoff_minutes = min(8, 1 * (2 ** (rate_limit_count - 1)))
            api_key_usage[key]['rate_limited_until'] = now + datetime.timedelta(minutes=backoff_minutes)
            print(f"Key has hit rate limit {rate_limit_count} times. Increasing cooldown to {backoff_minutes} minutes")
    
    def try_all_keys_for_translation(self, text: str, model_name: str, conversation=None, max_attempts=20) -> Tuple[str, Any]:
        """
        Try each available API key until translation succeeds or all keys have been tried
        
        Args:
            text: The text to translate
            model_name: The name of the model to use
            conversation: An optional existing conversation to continue
            max_attempts: Maximum number of attempts across all keys
            
        Returns:
            Tuple of translated text and conversation object
            
        Raises:
            Exception: If all keys fail after multiple attempts
        """
        total_attempts = 0
        keys_tried = set()
        
        # We'll keep trying until we've made max_attempts or tried all keys
        while total_attempts < max_attempts and len(keys_tried) < len(self.all_keys):
            # Get the next available key
            current_key = self.get_next_available_key()
            keys_tried.add(current_key)
            
            try:
                # Configure API key
                genai.configure(api_key=current_key)
                
                # Get generative model
                model = genai.GenerativeModel(model_name)
                
                # Create or continue conversation
                if conversation is None:
                    conversation = model.start_chat(history=[])
                
                # Add prompt for translation
                prompt = f"""
            من قصد دارم متن‌های انگلیسی فنی را به شما بدهم تا به فارسی ترجمه کنید. خودت را به عنوان یک مهندس نرم افزار در نظر بگیر که میخواهد یک متن انگلیسی را به فارسی ترجمه کند . باید اصطلاحات و کلمات فنی مهندسی نرم افزار را به انگلیسی نگهدارد و بقیه متن را به فارسی ترجمه کند .
            لطفاً به دستورالعمل‌های زیر دقت کنید و همیشه آن‌ها را در ترجمه‌های خود رعایت کنید:
                        
            1. اصطلاحات تخصصی و فنی را به انگلیسی نگه دارید و ترجمه نکنید. هیچ اصطلاح تخصصی را ترجمه نکنید و ما بقی متن را به فارسی ترجمه کنید
                        
            2. موارد زیر را هرگز ترجمه نکنید و عیناً به انگلیسی نگه دارید و مابقی را به فارسی ترجمه کنید :
            
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
            
            3. قانون‌های کلیدی برای تشخیص اصطلاحات فنی انگلیسی که نباید ترجمه شود
               - هر کلمه‌ای که حتی یک حرف بزرگ انگلیسی دارد، یک اصطلاح فنی است و نباید ترجمه شود.
               - هر کلمه‌ای که با حروف بزرگ نوشته شده یا اختصار است، نباید ترجمه شود.
               - هر عبارتی که با حروف مخفف (acronym) نوشته شده مانند API، REST، SOAP، نباید ترجمه شود.
               - هر عبارتی که با خط تیره یا زیرخط جدا شده (مانند client-side یا snake_case)، احتمالاً اصطلاح فنی است.
               - اصطلاحات شناخته شده مهندسی نرم‌افزار مانند endpoint، service، handler، را ترجمه نکنید.
            
            4. میتوانی از این مثال ها یاد بگیری که چطور یک متن انگلیسی را به فارسی ترجمه باید بکنی بدون ترجمه اصطلاحات فنی مهندسی نرم افزار
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
            
            5.  مطلقاً هیچ کلمه‌ای را که فکر می‌کنید ممکن است یک اصطلاح فنی باشد ترجمه نکنید. اگر در مورد ترجمه یک کلمه یا عبارت شک دارید، آن را به انگلیسی نگه دارید و مابقی متن را به زبان فارسی ترجمه کنید
            
            6. اگر بخش‌هایی از متن حاوی کد برنامه‌نویسی است، آن را داخل تگ‌های <pre><code class="language-زبان_برنامه_نویسی"> و </code></pre> قرار دهید.
               برای مثال، کد جاوا را به این صورت قرار دهید: <pre><code class="language-java">کد جاوا</code></pre>
            
            7. بسیار مهم: ساختار متن اصلی را حفظ کنید. پاراگراف‌بندی، سرفصل‌ها، لیست‌ها و بخش‌های کد را با تگ‌های HTML مناسب حفظ کنید:
               - تیترها و عنوان‌ها: از <h3> برای عنوان اصلی و <h4> برای زیرعنوان استفاده کنید
               - پاراگراف‌ها: هر پاراگراف را با <p> محصور کنید
               - لیست‌های نقطه‌ای: از <ul><li>آیتم اول</li><li>آیتم دوم</li></ul> استفاده کنید
               - لیست‌های شماره‌دار: از <ol><li>آیتم اول</li><li>آیتم دوم</li></ol> استفاده کنید
               - کدها: از <pre><code class="language-xxx">کد</code></pre> استفاده کنید
               - تأکید: از <strong> برای متن پررنگ و <em> برای متن ایتالیک استفاده کنید
               - جداول: ساختار <table>, <tr>, <td> را حفظ کنید

            8.عنوان ها یا سرفصل ها سر تیتر ها یا هر مورد دیگری که به ظرت باید bold باشد با تگ html بهش این قابلیت رو بده.

            9. متن شما باید یک متن html با شد که زیبا سازی شده باشد و فضا های اضافه برای زیبا سازی ایجاد شده باشد و یک متن تمیز و زیبا با استفاده از تگ های html ساخته شده باشد 
                
            10.شما نباید یک قالب کامل html بسازی و برگردانی برای من . بلکه باید یک div ّرگردانی که تمام مواردی که من از تو خواسته ام به شکل تگ های html باشد که من از ان ها در صفحات html خودم استفاده کنم

            11.مستقیم فقط تگ div ای برگردان که داخلش متن من به فارسی ترجمه شده باشد بدون ترجمه اصطلاحات فنی مهندسی نرم افزار و متن را داخل markdown نزاشته باشی و فقط یک تگ div که تمام ترجمه با خواسته های من داخلش باشد
            متن برای ترجمه به زبان فارسی با در نظر گرفتن تمام نکات و قواعد قبلی :
                
            {text}
                """
                
                # Generate response
                response = conversation.send_message(prompt)
                
                # Track successful usage
                self.mark_key_used(current_key)
                
                # Return the successful translation
                return response.text, conversation
                
            except Exception as e:
                error_str = str(e).lower()
                total_attempts += 1
                
                # Handle rate limiting specifically
                if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                    # Mark current key as rate limited
                    print(f"API key hit rate limit. Rotating to next key...")
                    self.mark_key_rate_limited(current_key)
                    
                    # If all keys are rate limited, wait before trying again
                    now = datetime.datetime.now()
                    all_limited = all(
                        k in api_key_usage and 
                        api_key_usage[k].get('rate_limited_until') is not None and
                        api_key_usage[k].get('rate_limited_until') > now 
                        for k in self.all_keys
                    )
                    
                    if all_limited:
                        # Find the key that will be available soonest
                        best_key = min(
                            self.all_keys,
                            key=lambda k: api_key_usage[k].get('rate_limited_until', now)
                        )
                        wait_time = (api_key_usage[best_key]['rate_limited_until'] - now).total_seconds()
                        print(f"All keys are rate limited. Waiting {wait_time:.1f} seconds for a key to become available...")
                        time.sleep(min(wait_time + 1, 60))  # Wait up to 60 seconds max
                else:
                    # For other errors, wait a shorter time
                    print(f"Error during translation with key {current_key[:6]}...: {str(e)}")
                    time.sleep(2)  # Brief pause before trying next key
        
        # If we've tried all keys multiple times and none worked
        raise Exception(f"Failed to translate after {total_attempts} attempts with {len(keys_tried)} different API keys")
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get usage statistics for all API keys
        
        Returns:
            Dictionary containing usage statistics for all keys
        """
        return api_key_usage

def translate_text_to_persian(text: str, api_key: str, model_name: str = "models/gemini-2.0-flash-lite", 
                             conversation=None, api_keys: List[str] = None) -> Tuple[str, Any]:
    """
    Translate text to Persian using Google's generative AI model with persistent retry logic
    
    This function will persistently try to translate text, rotating between API keys and 
    waiting for rate limits to expire before giving up.

    Args:
        text: The text to translate
        api_key: The primary API key to use for translation
        model_name: The name of the model to use
        conversation: An optional existing conversation to continue
        api_keys: A list of additional API keys to use for rotation

    Returns:
        The translated text and the conversation for continuation
    """
    # Create API key manager if multiple keys are provided
    if api_keys:
        key_manager = APIKeyManager(api_key, api_keys)
        # Use the enhanced key manager to try all keys
        return key_manager.try_all_keys_for_translation(text, model_name, conversation, max_attempts=30)
    
    # If only a single key is provided, use simpler logic
    retry_count = 0
    max_retries = 5
    base_wait_time = 2  # seconds
    
    while retry_count <= max_retries:
        try:
            # Configure API key
            genai.configure(api_key=api_key)
            
            # Get generative model
            model = genai.GenerativeModel(model_name)
            
            # Create or continue conversation
            if conversation is None:
                conversation = model.start_chat(history=[])
            
            # Add prompt for translation
            prompt = f"""
            من قصد دارم متن‌های انگلیسی فنی را به شما بدهم تا به فارسی ترجمه کنید. خودت را به عنوان یک مهندس نرم افزار در نظر بگیر که میخواهد یک متن انگلیسی را به فارسی ترجمه کند . باید اصطلاحات و کلمات فنی مهندسی نرم افزار را به انگلیسی نگهدارد و بقیه متن را به فارسی ترجمه کند .
            لطفاً به دستورالعمل‌های زیر دقت کنید و همیشه آن‌ها را در ترجمه‌های خود رعایت کنید:
                        
            1. اصطلاحات تخصصی و فنی را به انگلیسی نگه دارید و ترجمه نکنید. هیچ اصطلاح تخصصی را ترجمه نکنید و ما بقی متن را به فارسی ترجمه کنید
                        
            2. موارد زیر را هرگز ترجمه نکنید و عیناً به انگلیسی نگه دارید و مابقی را به فارسی ترجمه کنید :
            
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
            
            3. قانون‌های کلیدی برای تشخیص اصطلاحات فنی انگلیسی که نباید ترجمه شود
               - هر کلمه‌ای که حتی یک حرف بزرگ انگلیسی دارد، یک اصطلاح فنی است و نباید ترجمه شود.
               - هر کلمه‌ای که با حروف بزرگ نوشته شده یا اختصار است، نباید ترجمه شود.
               - هر عبارتی که با حروف مخفف (acronym) نوشته شده مانند API، REST، SOAP، نباید ترجمه شود.
               - هر عبارتی که با خط تیره یا زیرخط جدا شده (مانند client-side یا snake_case)، احتمالاً اصطلاح فنی است.
               - اصطلاحات شناخته شده مهندسی نرم‌افزار مانند endpoint، service، handler، را ترجمه نکنید.
            
            4. میتوانی از این مثال ها یاد بگیری که چطور یک متن انگلیسی را به فارسی ترجمه باید بکنی بدون ترجمه اصطلاحات فنی مهندسی نرم افزار
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
            
            5.  مطلقاً هیچ کلمه‌ای را که فکر می‌کنید ممکن است یک اصطلاح فنی باشد ترجمه نکنید. اگر در مورد ترجمه یک کلمه یا عبارت شک دارید، آن را به انگلیسی نگه دارید و مابقی متن را به زبان فارسی ترجمه کنید
            
            6. اگر بخش‌هایی از متن حاوی کد برنامه‌نویسی است، آن را داخل تگ‌های <pre><code class="language-زبان_برنامه_نویسی"> و </code></pre> قرار دهید.
               برای مثال، کد جاوا را به این صورت قرار دهید: <pre><code class="language-java">کد جاوا</code></pre>
            
            7. بسیار مهم: ساختار متن اصلی را حفظ کنید. پاراگراف‌بندی، سرفصل‌ها، لیست‌ها و بخش‌های کد را با تگ‌های HTML مناسب حفظ کنید:
               - تیترها و عنوان‌ها: از <h3> برای عنوان اصلی و <h4> برای زیرعنوان استفاده کنید
               - پاراگراف‌ها: هر پاراگراف را با <p> محصور کنید
               - لیست‌های نقطه‌ای: از <ul><li>آیتم اول</li><li>آیتم دوم</li></ul> استفاده کنید
               - لیست‌های شماره‌دار: از <ol><li>آیتم اول</li><li>آیتم دوم</li></ol> استفاده کنید
               - کدها: از <pre><code class="language-xxx">کد</code></pre> استفاده کنید
               - تأکید: از <strong> برای متن پررنگ و <em> برای متن ایتالیک استفاده کنید
               - جداول: ساختار <table>, <tr>, <td> را حفظ کنید

            8.عنوان ها یا سرفصل ها سر تیتر ها یا هر مورد دیگری که به ظرت باید bold باشد با تگ html بهش این قابلیت رو بده.

            9. متن شما باید یک متن html با شد که زیبا سازی شده باشد و فضا های اضافه برای زیبا سازی ایجاد شده باشد و یک متن تمیز و زیبا با استفاده از تگ های html ساخته شده باشد 
                
            10.شما نباید یک قالب کامل html بسازی و برگردانی برای من . بلکه باید یک div ّرگردانی که تمام مواردی که من از تو خواسته ام به شکل تگ های html باشد که من از ان ها در صفحات html خودم استفاده کنم

            11.مستقیم فقط تگ div ای برگردان که داخلش متن من به فارسی ترجمه شده باشد بدون ترجمه اصطلاحات فنی مهندسی نرم افزار و متن را داخل markdown نزاشته باشی و فقط یک تگ div که تمام ترجمه با خواسته های من داخلش باشد
            متن برای ترجمه به زبان فارسی با در نظر گرفتن تمام نکات و قواعد قبلی :
                
            {text}
            """
            
            # Generate response
            response = conversation.send_message(prompt)
            
            return response.text, conversation
            
        except Exception as e:
            error_str = str(e).lower()
            retry_count += 1
            
            # Handle rate limiting specifically
            if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                # If only a single key is available, we need to wait
                wait_time = 60  # Wait 1 minute for rate limit to reset
                print(f"Rate limit encountered with the only available API key. Waiting {wait_time} seconds before retry {retry_count}/{max_retries}")
                time.sleep(wait_time)
            else:
                # For other errors, wait a shorter time
                print(f"Error during translation: {str(e)}")
                print(f"Retrying in {retry_count * 2} seconds... ({retry_count}/{max_retries})")
                time.sleep(retry_count * 2)
            
            # If we've exhausted all retries, raise the error
            if retry_count > max_retries:
                raise Exception(f"Failed to translate after {max_retries} retries: {str(e)}")
    
    # This should not be reached due to the exception above, but just in case
    raise Exception(f"Failed to translate after {max_retries} retries")

def get_api_key_usage_stats():
    """
    Get current API key usage statistics
    
    Returns:
        Dictionary containing usage statistics for all keys
    """
    return api_key_usage 