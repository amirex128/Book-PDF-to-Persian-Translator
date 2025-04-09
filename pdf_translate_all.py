import os
import glob
import re
import shutil
import time
import argparse
from tqdm import tqdm
import PyPDF2
import google.generativeai as genai
import fitz  # PyMuPDF
import requests
import json
from bs4 import BeautifulSoup

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
    
    try:
        # Configure the Gemini API
        genai.configure(api_key=api_key)
        
        # Set up the model - using gemini-1.5-flash-8b as specified
        model = genai.GenerativeModel("models/gemini-1.5-flash-8b")
        
        # Create or continue a conversation
        if conversation_history is None:
            conversation = model.start_chat(history=[])
        else:
            conversation = conversation_history
        
        # Prompt for translation with context awareness
        prompt = """
        لطفا متن زیر را به فارسی ترجمه کنید. این متن بخشی از یک کتاب فنی است. 
        لطفا از ترجمه‌های قبلی در این گفتگو استفاده کنید تا سبک و اصطلاحات یکسان باشند.
        متن را با دقت و روان ترجمه کنید و اصطلاحات تخصصی را به درستی برگردانید.
        کلمات و اصطلاحات فنی مهندسی نرم افزار و معماری نباید به فارسی ترجمه شود
        فقط متن ترجمه شده را برگردانید، بدون هیچ توضیح اضافی.
        در نهایت متن را با یک فاصله گذاری هوشمند و مرتب بر اساس انتخاب خودت تنظیم کن
        متن برای ترجمه:
        
        """ + text
        
        # Get the response from Gemini
        response = conversation.send_message(prompt)
        translated_text = response.text
        
        # Return the translated text and the conversation for future use
        return translated_text, conversation
    
    except Exception as e:
        error_message = str(e)
        print(f"Translation error: {error_message}")
        return "", error_message

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
    # Clean any potential HTML tags from the input
    persian_text = persian_html
    
    # Remove any existing HTML tags
    persian_text = re.sub(r'<[^>]+>', '', persian_text)
    
    # Wrap the clean text in Persian translation div
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
    
    # Add HTML code for images
    images_html = ""
    if images and len(images) > 0:
        images_html = "<div class='page-images'>\n"
        for img in images:
            images_html += f"    <img src='{img['relative_path']}' class='page-image' alt='Page {page_number} image' />\n"
        images_html += "</div>\n"
    
    # JavaScript code as a properly formatted string in the HTML template
    js_code = """
        document.addEventListener('DOMContentLoaded', function() {
            const imageContainer = document.querySelector('.page-images');
            if (imageContainer) {
                const images = imageContainer.querySelectorAll('.page-image');
                document.documentElement.style.setProperty('--image-count', images.length);
                
                // Further adjust if text is large
                const textElement = document.querySelector('.persian-translation');
                const textHeight = textElement.offsetHeight;
                const containerHeight = document.querySelector('.container').offsetHeight;
                
                // If text takes more than 40% of container, reduce image max-height
                if (textHeight > containerHeight * 0.4) {
                    const remainingHeight = containerHeight - textHeight - 50; // 50px for margins
                    const imageMaxHeight = remainingHeight / images.length;
                    images.forEach(img => {
                        img.style.maxHeight = imageMaxHeight + 'px';
                    });
                }
            }
        });
    """
    
    html_content = f"""<!DOCTYPE html>
<html lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_name}</title>
    {font_link}
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
            /* Strict A4 size enforcement */
            width: 21cm;
            height: 29.7cm;
            overflow: hidden; /* Critical: prevents content overflow */
        }}
        .container {{
            width: 100%;
            height: 100%;
            max-width: 100%;
            max-height: 100%;
            background-color: white;
            padding: 1.5cm;
            box-sizing: border-box;
            margin: 0 auto;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        .persian-translation {{
            text-align: right;
            direction: rtl;
            font-size: 1em;
            font-family: 'IRANSansX', 'Tahoma', 'Arial', sans-serif;
            margin-bottom: 20px;
            /* Dynamic text size adjustment */
            max-height: 40%;
            overflow: hidden;
            /* Text will shrink if there are large images */
            flex: 0 1 auto;
        }}
        .page-images {{
            text-align: center;
            margin: 10px auto;
            /* Images area takes remaining space */
            flex: 1 1 auto;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            overflow: hidden;
        }}
        .page-image {{
            display: block;
            width: auto;
            height: auto;
            max-width: 100%;
            /* Dynamic height - will shrink if there are multiple images */
            max-height: calc((100% - 20px) / var(--image-count, 1));
            margin: 5px auto;
            object-fit: contain;
        }}
        .page-number {{
            text-align: center;
            margin-top: 10px;
            font-size: 0.9em;
            color: #777;
            flex: 0 0 auto;
        }}
        @media print {{
            body {{
                background: none;
                width: 21cm;
                height: 29.7cm;
            }}
            .container {{
                box-shadow: none;
                padding: 0;
                height: 100%;
            }}
            .persian-translation {{
                /* Ensure text doesn't overflow in print */
                overflow: hidden;
            }}
            .page-images {{
                /* Ensure images don't cause page breaks */
                page-break-inside: avoid;
                overflow: hidden;
            }}
            .page-image {{
                /* Ensure images are scaled properly for print */
                max-height: calc((100% - 20px) / var(--image-count, 1));
            }}
        }}
    </style>
    <script>
{js_code}
    </script>
</head>
<body>
    <div class="container">
        {persian_html}
        
        {images_html}
        
        <div class="page-number">
            {page_number}
        </div>
    </div>
</body>
</html>"""
    return html_content

def create_pdf_from_html_files(html_files, output_pdf, output_dir):
    """Create PDF from HTML files using pdfkit"""
    if not PDFKIT_AVAILABLE:
        print("pdfkit is not available. Cannot create PDF.")
        return False
    
    try:
        print(f"\nConverting HTML files to PDF: {output_pdf}")
        print(f"  Converting {len(html_files)} HTML files to PDF...")
        
        # Sort files by page number
        html_files.sort(key=lambda x: int(re.search(r'page_(\d+)_fa', x).group(1)))
        
        # Filter out non-existent files
        existing_files = [f for f in html_files if os.path.exists(f)]
        if not existing_files:
            print("No HTML files found for conversion.")
            return False
            
        # pdfkit options for better Persian text support
        options = {
            'page-size': 'A4',
            'margin-top': '1.5cm',
            'margin-right': '1.5cm',
            'margin-bottom': '1.5cm',
            'margin-left': '1.5cm',
            'encoding': 'UTF-8',
            'enable-local-file-access': None,  # Allow access to local files
            'print-media-type': None,  # Use print media CSS
            'quiet': None  # Reduce console output
        }
        
        # Use the specific wkhtmltopdf path
        wkhtmltopdf_path = r'C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe'
        
        if os.path.exists(wkhtmltopdf_path):
            print(f"  Using wkhtmltopdf from: {wkhtmltopdf_path}")
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_path)
            
            try:
                # Create PDF with the specified configuration
                pdfkit.from_file(existing_files, output_pdf, options=options, configuration=config)
                
                # Verify PDF was created
                if os.path.exists(output_pdf):
                    print(f"  PDF created successfully: {output_pdf}")
                    return True
                else:
                    print("  Failed to create PDF")
                    return False
                    
            except Exception as pdf_error:
                print(f"  Error creating PDF: {str(pdf_error)}")
                print("\nTo create PDF manually:")
                print("1. Make sure wkhtmltopdf is installed correctly")
                print(f"2. Run: \"{wkhtmltopdf_path}\" --enable-local-file-access {' '.join(existing_files)} {output_pdf}")
                return False
        else:
            print(f"  Error: wkhtmltopdf not found at {wkhtmltopdf_path}")
            print("  Please make sure wkhtmltopdf is installed in the correct location")
            return False
            
    except Exception as e:
        print(f"Error during PDF creation: {str(e)}")
        return False

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
    
    # Define output PDF path in the output directory
    output_pdf = os.path.join(output_dir_base, f"{file_base_name}_Farsi.pdf")
    
    # Create or rebuild directory for this book
    temp_dir = os.path.join(pdf_dir, sanitized_name)
    if os.path.exists(temp_dir):
        print(f"Removing existing directory: {temp_dir}")
        shutil.rmtree(temp_dir)
    
    os.makedirs(temp_dir)
    print(f"Created directory: {temp_dir}")
    
    # Copy font files to output directory
    fonts_copied = copy_font_assets(temp_dir)
    if fonts_copied:
        print("Font files copied successfully.")
    else:
        print("Font file copying encountered issues.")
    
    # Initialize the list of HTML files
    html_files = []
    
    # 1. Extract text and images from PDF
    extracted_pages = []
    page_images = {}  # Dictionary to store images for each page
    
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
            
            # Extract text and images from each page and save to file
            for page_num in tqdm(range(pages_to_process), desc="Extracting text and images", unit="page"):
                # Get page
                page = pdf_reader.pages[page_num]
                
                # Extract text
                text = page.extract_text()
                
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
                        
                        # Create HTML with just images (no translation needed)
                        html_content = create_html_content(
                            "این صفحه فقط شامل تصاویر است.", # "This page contains only images"
                            base_name,
                            fonts_copied,
                            images=images
                        )
                        
                        # Save as HTML file
                        with open(html_file, 'w', encoding='utf-8') as f:
                            f.write(html_content)
                            
                        # Add to list of HTML files
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
        html_files.append(html_file)
        
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
                
                # Create HTML content with translation and images
                html_content = create_html_content(
                    translated_text, 
                    base_name, 
                    fonts_copied,
                    images=page_images_list
                )
                
                # Save as HTML file
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                translated_files += 1
                
                # Prevent API rate limits
                time.sleep(1)
            else:
                print(f"\n  Error translating {file_name}: {conversation}")
                failed_files += 1
                
                # Handle rate limits
                if "rate" in str(conversation).lower() or "quota" in str(conversation).lower():
                    print("  Rate limit detected. Pausing for 60 seconds...")
                    time.sleep(60)
        
        except Exception as e:
            print(f"\n  Error processing {file_name}: {str(e)}")
            failed_files += 1
    
    # Add any image-only pages that weren't in extracted_pages
    for page_num in range(pages_to_process):
        base_name = f"page_{page_num + 1:04d}"
        html_file = os.path.join(temp_dir, f"{base_name}_fa.html")
        
        # If this page has images but no text file was processed for it
        if base_name in page_images and html_file not in html_files:
            images = page_images[base_name]
            
            # Create HTML with just images
            html_content = create_html_content(
                "این صفحه فقط شامل تصاویر است.", # "This page contains only images"
                base_name,
                fonts_copied,
                images=images
            )
            
            # Save as HTML file
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # Add to list of HTML files
            html_files.append(html_file)
    
    # Display translation summary
    print("\nTranslation Summary:")
    print(f"  Total pages: {len(extracted_pages)}")
    print(f"  Translated: {translated_files}")
    print(f"  Errors: {failed_files}")
    print(f"  Pages with images: {len(page_images)}")
    
    # After translation is complete, create PDF from HTML files
    if html_files:
        # Create PDF from HTML files
        if create_pdf_from_html_files(html_files, output_pdf, temp_dir):
            print(f"Persian PDF created: {output_pdf}")
            # Clean up temporary directory
            print(f"Removing temporary files directory: {temp_dir}")
            shutil.rmtree(temp_dir)
            print("Only the translated PDF file remains in the output directory.")
            return True
        else:
            print("Failed to create PDF. Keeping HTML files for manual review.")
            return False
    else:
        print("No HTML files were created. Translation failed.")
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
    print("="*30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract, translate and convert PDF files to Persian')
    parser.add_argument('--api-key', default="AIzaSyD1HS27l8i8N5jBnSCixhGH3sRiH81i9HQ", help='Gemini API key')
    parser.add_argument('--books-dir', default=os.path.join(os.getcwd(), "books"), help='Directory containing PDF files')
    parser.add_argument('--limit', type=int, help='Maximum number of pages to process from each book')
    
    args = parser.parse_args()
    
    process_all_pdfs(
        books_dir=args.books_dir,
        api_key=args.api_key,
        limit=args.limit
    )
    
    print("Processing completed.") 