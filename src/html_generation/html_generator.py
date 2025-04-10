import os
import re
import shutil
from bs4 import BeautifulSoup

def ensure_directory_exists(directory_path):
    """Ensure that a directory exists, creating it if necessary"""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path, exist_ok=True)
        return True
    return False

def wrap_code_block(content, file_extension=None):
    """Wrap content in appropriate code block tags based on file extension"""
    language_map = {
        'py': 'python',
        'js': 'javascript',
        'ts': 'typescript',
        'json': 'json',
        'yml': 'yaml',
        'yaml': 'yaml',
        'toml': 'toml',
        'ini': 'ini',
        'sh': 'bash',
        'bash': 'bash',
        'ps1': 'powershell',
        'c': 'c',
        'cpp': 'cpp',
        'cc': 'cpp',
        'cs': 'csharp',
        'go': 'go',
        'rs': 'rust',
        'sql': 'sql',
        'rb': 'ruby',
        'kt': 'kotlin',
        'swift': 'swift',
        'dart': 'dart',
        'scala': 'scala',
        'gql': 'graphql',
        'md': 'markdown',
        'tex': 'latex'
    }
    
    language = language_map.get(file_extension, 'plaintext') if file_extension else 'plaintext'
    return '<pre class="line-numbers"><code class="language-{}">{}</code></pre>'.format(language, content)

def process_code_blocks(text_content):
    """Process and wrap code blocks with appropriate syntax highlighting"""
    if not text_content:
        return text_content
        
    lines = text_content.split('\n')
    processed_lines = []
    in_code_block = False
    code_block_lines = []
    current_extension = None
    
    for line in lines:
        if line.strip().startswith('```') and not in_code_block:
            in_code_block = True
            lang = line.strip().replace('```', '').strip()
            if lang:
                current_extension = lang
            continue
        elif line.strip() == '```' and in_code_block:
            in_code_block = False
            code_content = '\n'.join(code_block_lines)
            processed_lines.append(wrap_code_block(code_content, current_extension))
            code_block_lines = []
            current_extension = None
            continue
            
        if in_code_block:
            code_block_lines.append(line)
        else:
            processed_lines.append(line)
            
    if in_code_block:
        # Handle unclosed code block
        code_content = '\n'.join(code_block_lines)
        processed_lines.append(wrap_code_block(code_content, current_extension))
            
    return '\n'.join(processed_lines)

def process_html_content(content):
    """Process HTML content to make it better suited for Persian display"""
    try:
        # If content is just plain text (no HTML), wrap in paragraph tags
        if not re.search(r'<(p|h[1-6]|div)\b', content, re.IGNORECASE):
            content = f"<p>{content}</p>"
        
        # Parse the HTML content
        soup = BeautifulSoup(content, 'html.parser')
        
        # Find all text nodes and apply directional attributes where needed
        for text in soup.find_all(text=True):
            # Skip text in script, style, code, or pre tags
            if text.parent.name in ['script', 'style', 'code', 'pre']:
                continue
                
            # Add ltr direction to English text segments that are not already wrapped
            if re.search(r'[a-zA-Z0-9_]', text):
                # Only process if there's substantial English text (more than just a couple characters)
                english_segments = re.findall(r'[a-zA-Z0-9_]{2,}', text)
                if english_segments:
                    # Create a new string with wrapped segments
                    new_text = text
                    for seg in english_segments:
                        if len(seg) > 1:  # Only wrap segments with more than 1 character
                            wrapped = f'<span dir="ltr">{seg}</span>'
                            new_text = new_text.replace(seg, wrapped)
                    
                    # Replace the text node with the new wrapped content
                    text.replace_with(BeautifulSoup(new_text, 'html.parser'))
        
        # Convert soup back to string
        processed_content = str(soup)
        return processed_content
    
    except Exception as e:
        print(f"Error processing HTML content: {e}")
        return content

def copy_font_assets(output_dir):
    """Copy font assets to the output directory for proper Persian display"""
    try:
        # Create font directories
        assets_dir = os.path.join(os.getcwd(), "assets")
        if not os.path.exists(assets_dir):
            assets_dir = os.path.join(os.path.dirname(os.getcwd()), "assets")
        
        # If assets directory doesn't exist, create it and its subdirectories
        if not os.path.exists(assets_dir):
            os.makedirs(assets_dir, exist_ok=True)
            os.makedirs(os.path.join(assets_dir, "Webfonts", "fonts", "woff"), exist_ok=True)
            os.makedirs(os.path.join(assets_dir, "Webfonts", "fonts", "woff2"), exist_ok=True)
            print(f"Created assets directory: {assets_dir}")
            print("Please add your font files to the assets directory.")
            
            # Create a basic fontiran.css in the output directory
            with open(os.path.join(output_dir, "fontiran.css"), 'w', encoding='utf-8') as f:
                f.write("""@font-face {
    font-family: IRANSansX;
    font-style: normal;
    font-weight: normal;
    src: url('fonts/woff/IRANSansXWeb.woff') format('woff'),
         url('fonts/woff2/IRANSansXWeb.woff2') format('woff2');
}

@font-face {
    font-family: IRANSansX;
    font-style: normal;
    font-weight: bold;
    src: url('fonts/woff/IRANSansXWeb-Bold.woff') format('woff'),
         url('fonts/woff2/IRANSansXWeb-Bold.woff2') format('woff2');
}

@font-face {
    font-family: IRANSansX;
    font-style: normal;
    font-weight: 500;
    src: url('fonts/woff/IRANSansXWeb-Medium.woff') format('woff'),
         url('fonts/woff2/IRANSansXWeb-Medium.woff2') format('woff2');
}

* {
    font-family: IRANSansX, Tahoma, Arial, sans-serif !important;
    text-align: right;
}

body {
    font-family: IRANSansX, Tahoma, Arial, sans-serif;
    text-align: right;
    direction: rtl;
}

h1, h2, h3, h4, h5, h6 {
    font-family: IRANSansX, Tahoma, Arial, sans-serif;
    font-weight: bold;
    text-align: right;
}

p, div, span {
    text-align: right;
}""")
            
            # Create default font directories in the output directory
            woff_dir = os.path.join(output_dir, "fonts", "woff")
            woff2_dir = os.path.join(output_dir, "fonts", "woff2")
            os.makedirs(woff_dir, exist_ok=True)
            os.makedirs(woff2_dir, exist_ok=True)
            
            # Generate a warning message for the user
            print("WARNING: No font files found. Default CSS created but you need to add font files to ensure proper text display.")
            return True
        
        # Create font directories in the output directory
        woff_dir = os.path.join(output_dir, "fonts", "woff")
        woff2_dir = os.path.join(output_dir, "fonts", "woff2")
        
        os.makedirs(woff_dir, exist_ok=True)
        os.makedirs(woff2_dir, exist_ok=True)
        
        # Copy CSS file
        font_found = False
        fontiran_css = os.path.join(assets_dir, "Webfonts", "css", "fontiran.css")
        
        if os.path.exists(fontiran_css):
            shutil.copy2(fontiran_css, os.path.join(output_dir, "fontiran.css"))
            font_found = True
        else:
            # Try to find the CSS file in different locations
            alt_css_path = os.path.join(assets_dir, "css", "fontiran.css")
            if os.path.exists(alt_css_path):
                shutil.copy2(alt_css_path, os.path.join(output_dir, "fontiran.css"))
                font_found = True
            else:
                # Create a basic fontiran.css if it doesn't exist
                with open(os.path.join(output_dir, "fontiran.css"), 'w', encoding='utf-8') as f:
                    f.write("""@font-face {
    font-family: IRANSansX;
    font-style: normal;
    font-weight: normal;
    src: url('fonts/woff/IRANSansXWeb.woff') format('woff'),
         url('fonts/woff2/IRANSansXWeb.woff2') format('woff2');
}

@font-face {
    font-family: IRANSansX;
    font-style: normal;
    font-weight: bold;
    src: url('fonts/woff/IRANSansXWeb-Bold.woff') format('woff'),
         url('fonts/woff2/IRANSansXWeb-Bold.woff2') format('woff2');
}

@font-face {
    font-family: IRANSansX;
    font-style: normal;
    font-weight: 500;
    src: url('fonts/woff/IRANSansXWeb-Medium.woff') format('woff'),
         url('fonts/woff2/IRANSansXWeb-Medium.woff2') format('woff2');
}

* {
    font-family: IRANSansX, Tahoma, Arial, sans-serif !important;
    text-align: right;
}

body {
    font-family: IRANSansX, Tahoma, Arial, sans-serif;
    text-align: right;
    direction: rtl;
}

h1, h2, h3, h4, h5, h6 {
    font-family: IRANSansX, Tahoma, Arial, sans-serif;
    font-weight: bold;
    text-align: right;
}

p, div, span {
    text-align: right;
}""")
        
        # Copy woff font files
        font_count = 0
        source_woff = os.path.join(assets_dir, "Webfonts", "fonts", "woff")
        if os.path.exists(source_woff):
            for font_file in os.listdir(source_woff):
                if font_file.endswith('.woff'):
                    shutil.copy2(os.path.join(source_woff, font_file), woff_dir)
                    font_found = True
                    font_count += 1
        else:
            # Try alternative path
            alt_woff_path = os.path.join(assets_dir, "fonts", "woff")
            if os.path.exists(alt_woff_path):
                for font_file in os.listdir(alt_woff_path):
                    if font_file.endswith('.woff'):
                        shutil.copy2(os.path.join(alt_woff_path, font_file), woff_dir)
                        font_found = True
                        font_count += 1
        
        # Copy woff2 font files
        source_woff2 = os.path.join(assets_dir, "Webfonts", "fonts", "woff2")
        if os.path.exists(source_woff2):
            for font_file in os.listdir(source_woff2):
                if font_file.endswith('.woff2'):
                    shutil.copy2(os.path.join(source_woff2, font_file), woff2_dir)
                    font_found = True
                    font_count += 1
        else:
            # Try alternative path
            alt_woff2_path = os.path.join(assets_dir, "fonts", "woff2")
            if os.path.exists(alt_woff2_path):
                for font_file in os.listdir(alt_woff2_path):
                    if font_file.endswith('.woff2'):
                        shutil.copy2(os.path.join(alt_woff2_path, font_file), woff2_dir)
                        font_found = True
                        font_count += 1
        
        if font_found:
            print(f"  Copied {font_count} font files to output directory.")
        else:
            print("  WARNING: No font files found. Default CSS created but text display may be affected.")
            
            # If no fonts found, try to create a fallback CSS with web fonts
            with open(os.path.join(output_dir, "fontiran.css"), 'w', encoding='utf-8') as f:
                f.write("""@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;700&display=swap');

body {
    font-family: 'Vazirmatn', Tahoma, Arial, sans-serif;
}
""")
        
        return True
    
    except Exception as e:
        print(f"Error copying font assets: {e}")
        return False

def create_html_content(text_content, base_name=None, fonts_copied=False, images=None, images_content=None, page_number=None):
    """Create HTML content with Persian translation and images"""
    # Handle parameter variations
    if page_number is None and base_name:
        # Extract page number from base_name
        page_match = re.search(r'(\d+)', base_name)
        page_number = page_match.group(1) if page_match else "1"
        page_number = page_number.lstrip('0') or '1'  # Remove leading zeros
    elif page_number is None:
        page_number = "1"
    
    # Process HTML content for better Persian display
    processed_text = process_html_content(text_content)
    
    # Create images content HTML if images parameter is provided
    if images_content is None and images:
        images_content = ""
        for img in images:
            if 'relative_path' in img:
                img_path = img['relative_path']
                images_content += f'<img src="{img_path}" alt="Image from page {page_number}" />\n'
    elif images_content is None:
        images_content = ""
    
    # Add font link if fonts were copied
    font_link = '<link rel="stylesheet" href="fontiran.css">' if fonts_copied else ''
    
    # Create HTML content
    html_content = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>صفحه {page_number}</title>
    {font_link}
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css" rel="stylesheet" />
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: IRANSansX, Tahoma, Arial, sans-serif;
            line-height: 1.8;
            text-align: right;
            direction: rtl;
            margin: 0;
            padding: 20px;
            box-sizing: border-box;
            background-color: white;
        }}
        .chapter-content {{
            margin-bottom: 20px;
            text-align: right;
            direction: rtl;
        }}
        .persian-translation {{
            font-size: 14pt;
            margin-bottom: 15px;
            text-align: right;
            direction: rtl;
        }}
        .page-images {{
            text-align: center;
            margin: 20px 0;
            page-break-before: always;
        }}
        .page-images img {{
            max-width: 100%;
            height: auto;
            margin: 10px 0;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        pre {{
            direction: ltr;
            text-align: left;
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 15px 0;
        }}
        code {{
            font-family: 'Courier New', Courier, monospace;
            direction: ltr;
            text-align: left;
        }}
        span[dir="ltr"] {{
            display: inline-block;
            direction: ltr;
            text-align: left;
        }}
        h3, h4 {{
            color: #2c3e50;
            margin-top: 25px;
            margin-bottom: 15px;
            text-align: right;
            direction: rtl;
        }}
        ul, ol {{
            padding-right: 20px;
            padding-left: 0;
            text-align: right;
            direction: rtl;
        }}
        li {{
            margin-bottom: 10px;
            text-align: right;
            direction: rtl;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            text-align: right;
            direction: rtl;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px;
            text-align: right;
            direction: rtl;
        }}
        th {{
            background-color: #f8f9fa;
        }}
        @media print {{
            body {{
                margin: 0;
                padding: 0;
            }}
            .page-break {{
                page-break-before: always;
            }}
        }}
    </style>
</head>
<body>
    <div class="chapter-content">
        <div dir="rtl" class="persian-translation">
            {processed_text}
        </div>
    </div>
    <div class="page-images">
        {images_content}
    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', (event) => {{
            if (window.Prism) {{
                Prism.highlightAll();
            }}
        }});
    </script>
</body>
</html>"""
    
    # For compatibility with existing code
    return html_content, None

def create_html_book(html_files, output_html, output_dir, file_base_name, pdf_path=None, toc_headings=None):
    """Create a single HTML book from multiple HTML files"""
    try:
        print(f"\nCreating HTML book: {output_html}")
        print(f"  Combining {len(html_files)} HTML pages into a single book...")
        
        # Filter out non-existent files
        existing_files = [f for f in html_files if os.path.exists(f)]
        if not existing_files:
            print("No HTML files found for combining.")
            return False
        
        # Copy font files to output directory if needed
        fonts_copied = copy_font_assets(output_dir)
        if fonts_copied:
            print("  Font files copied to output directory.")
            
        # Get the temp directory path (where images are stored)
        temp_dir = os.path.dirname(existing_files[0])
            
        # Sort files by page number
        def get_page_number(filename):
            match = re.search(r'page_(\d+)_fa', filename)
            if match:
                return int(match.group(1))
            return 0
        
        try:
            # Sort files by page number
            existing_files.sort(key=get_page_number)
        except Exception as e:
            print(f"Warning: Error sorting HTML files by page number: {str(e)}")
            print("Falling back to basic filename sorting")
            existing_files.sort()
        
        # Create the HTML book structure
        book_html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_base_name} - فارسی</title>
    <link rel="stylesheet" href="fontiran.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css" rel="stylesheet" />
    <style>
        @page {{
            size: A4;
            margin: 2cm;
        }}
        body {{
            font-family: IRANSansX, Tahoma, Arial, sans-serif;
            line-height: 1.8;
            text-align: right;
            direction: rtl;
            margin: 0;
            padding: 20px;
            background-color: white;
        }}
        .book-title {{
            text-align: center;
            font-size: 24pt;
            margin: 3cm 0 1cm 0;
        }}
        .book-subtitle {{
            text-align: center;
            font-size: 18pt;
            margin-bottom: 3cm;
        }}
        .toc {{
            margin: 2cm 0;
            padding: 1cm;
            background-color: #f8f9fa;
            border-radius: 5px;
            page-break-after: always;
        }}
        .toc h2 {{
            margin-bottom: 1cm;
        }}
        .toc ul {{
            list-style-type: none;
            padding: 0;
        }}
        .toc li {{
            margin: 0.5cm 0;
            padding-right: 1cm;
        }}
        .toc a {{
            text-decoration: none;
            color: #2980b9;
        }}
        .chapter {{
            margin-bottom: 1cm;
            page-break-before: always;
        }}
        .chapter:first-of-type {{
            page-break-before: avoid;
        }}
        .chapter-content {{
            margin-bottom: 1cm;
        }}
        .persian-translation {{
            font-size: 14pt;
        }}
        .page-images {{
            text-align: center;
            margin: 1cm 0;
            page-break-before: always;
        }}
        .page-images img {{
            max-width: 100%;
            height: auto;
            margin: 0.5cm 0;
        }}
        pre {{
            direction: ltr;
            text-align: left;
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 15px 0;
        }}
        code {{
            font-family: 'Courier New', Courier, monospace;
            direction: ltr;
            text-align: left;
        }}
        span[dir="ltr"] {{
            display: inline-block;
            direction: ltr;
            text-align: left;
        }}
        .page-number {{
            text-align: center;
            margin-top: 1cm;
            font-size: 10pt;
            color: #7f8c8d;
        }}
    </style>
</head>
<body>
    <h1 class="book-title">{file_base_name}</h1>
    <h2 class="book-subtitle">نسخه ترجمه شده</h2>
"""
        
        # Add table of contents if headings are provided
        if toc_headings and len(toc_headings) > 0:
            book_html += """
    <div class="toc">
        <h2>فهرست مطالب</h2>
        <ul>
"""
            for heading in toc_headings:
                heading_id = f"heading-{heading['page']}-{heading['level']}"
                book_html += f'            <li><a href="#{heading_id}">{heading["text"]}</a></li>\n'
            book_html += "        </ul>\n    </div>\n"
        
        # Process each HTML file
        for i, html_file in enumerate(existing_files):
            print(f"  Processing page {i+1}/{len(existing_files)}: {os.path.basename(html_file)}")
            
            try:
                with open(html_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Get original page number
                page_match = re.search(r'page_(\d+)_fa', html_file)
                original_page = page_match.group(1) if page_match else str(i+1)
                
                # Process HTML content
                processed_content = process_html_content(content)
                
                # Extract Persian translation div content
                soup = BeautifulSoup(content, 'html.parser')
                persian_div = soup.find('div', class_='persian-translation')
                text_content = str(persian_div) if persian_div else ""
                
                # Extract images content and fix paths
                images_div = soup.find('div', class_='page-images')
                if images_div:
                    # Find all img tags and update their src attributes
                    for img in images_div.find_all('img'):
                        if 'src' in img.attrs:
                            # Get the current src
                            src = img['src']
                            # Extract the image filename and directory
                            if '/' in src:
                                img_dir, img_filename = os.path.split(src)
                                # Copy image to output directory
                                src_path = os.path.join(temp_dir, src)
                                dst_dir = os.path.join(output_dir, img_dir)
                                ensure_directory_exists(dst_dir)
                                dst_path = os.path.join(output_dir, src)
                                if os.path.exists(src_path):
                                    shutil.copy2(src_path, dst_path)
                
                images_content = str(images_div) if images_div else ""
                
                # Add page to book
                book_html += f'        <!-- Page {original_page} -->\n'
                book_html += f'        <div class="chapter" id="page-{original_page}">\n'
                book_html += f'            <div class="chapter-content">\n'
                book_html += f'                {text_content}\n'
                book_html += f'                {images_content}\n'
                book_html += f'                <div class="page-number">صفحه {original_page}</div>\n'
                book_html += f'            </div>\n'
                book_html += f'        </div>\n'
                
            except Exception as e:
                print(f"  Error processing {html_file}: {str(e)}")
        
        # Add closing tags and scripts
        book_html += """
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', (event) => {
            if (window.Prism) {
                Prism.highlightAll();
            }
        });
    </script>
</body>
</html>"""
        
        # Save the HTML book
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(book_html)
        
        print(f"  HTML book created successfully: {output_html}")
        return True
        
    except Exception as e:
        print(f"Error creating HTML book: {str(e)}")
        return False

def create_dual_page_book(html_files, output_html, output_dir, file_base_name, pdf_path=None, toc_headings=None):
    """Create a dual-page HTML book with original PDF pages and translations side by side"""
    try:
        print(f"\nCreating dual-page HTML book: {output_html}")
        print(f"  Combining {len(html_files)} HTML pages into a dual-page book...")
        
        # Filter out non-existent files
        existing_files = [f for f in html_files if os.path.exists(f)]
        if not existing_files:
            print("No HTML files found for combining.")
            return False
        
        # Get the temp directory path (where images are stored)
        temp_dir = os.path.dirname(existing_files[0])
        
        # Copy font files to output directory if needed
        fonts_copied = copy_font_assets(output_dir)
        if fonts_copied:
            print("  Font files copied to output directory.")
        
        # Sort files by page number
        def get_page_number(filename):
            match = re.search(r'page_(\d+)_fa', filename)
            if match:
                return int(match.group(1))
            return 0
        
        # Sort files properly by their numeric page values
        existing_files.sort(key=get_page_number)
        
        # Create the HTML book structure
        book_html = f"""<!DOCTYPE html>
<html lang="fa">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{file_base_name} - نسخه دوزبانه</title>
    <link rel="stylesheet" href="fontiran.css">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism.min.css" rel="stylesheet" />
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.css" rel="stylesheet" />
    <style>
        @page {{
            size: A3 landscape;
            margin: 1cm;
        }}
        body {{
            font-family: IRANSansX, Tahoma, Arial, sans-serif;
            line-height: 1.8;
            margin: 0;
            padding: 20px;
            background-color: white;
        }}
        .book-title {{
            text-align: center;
            font-size: 24pt;
            margin: 2cm 0 1cm 0;
        }}
        .book-subtitle {{
            text-align: center;
            font-size: 18pt;
            margin-bottom: 2cm;
        }}
        .dual-page-container {{
            display: flex;
            flex-wrap: wrap;
        }}
        .dual-page-spread {{
            display: flex;
            justify-content: space-between;
            width: 100%;
            margin-bottom: 1cm;
            page-break-after: always;
        }}
        .page {{
            width: 48%;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
            padding: 1cm;
            margin: 0 0.5%;
            box-sizing: border-box;
        }}
        .persian-page {{
            text-align: right;
            direction: rtl;
        }}
        .original-page {{
            text-align: center;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .original-page img {{
            max-width: 100%;
            max-height: 100%;
        }}
        .persian-translation {{
            font-size: 14pt;
        }}
        .page-images {{
            text-align: center;
            margin-top: 1cm;
        }}
        .page-images img {{
            max-width: 100%;
            height: auto;
            margin: 0.5cm 0;
        }}
        pre {{
            direction: ltr;
            text-align: left;
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            overflow-x: auto;
            margin: 15px 0;
        }}
        code {{
            font-family: 'Courier New', Courier, monospace;
            direction: ltr;
            text-align: left;
        }}
        span[dir="ltr"] {{
            display: inline-block;
            direction: ltr;
            text-align: left;
        }}
    </style>
</head>
<body>
    <h1 class="book-title">{file_base_name}</h1>
    <h2 class="book-subtitle">نسخه دوزبانه</h2>
    
    <div class="dual-page-container">
"""
        
        # Process each HTML file
        for html_file in existing_files:
            with open(html_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Get page number
            page_match = re.search(r'page_(\d+)_fa', html_file)
            if not page_match:
                continue
            
            page_num = int(page_match.group(1))
            
            # Parse HTML content
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract Persian translation content
            persian_div = soup.find('div', class_='persian-translation')
            persian_content = str(persian_div) if persian_div else ""
            
            # Process HTML content
            persian_content = process_html_content(persian_content)
            
            # Extract images content and fix paths
            images_div = soup.find('div', class_='page-images')
            if images_div:
                # Find all img tags and update their src attributes
                for img in images_div.find_all('img'):
                    if 'src' in img.attrs:
                        # Get the current src
                        src = img['src']
                        # Extract the image filename and directory
                        if '/' in src:
                            img_dir, img_filename = os.path.split(src)
                            # Copy image to output directory
                            src_path = os.path.join(temp_dir, src)
                            dst_dir = os.path.join(output_dir, img_dir)
                            ensure_directory_exists(dst_dir)
                            dst_path = os.path.join(output_dir, src)
                            if os.path.exists(src_path):
                                shutil.copy2(src_path, dst_path)
            
            images_content = str(images_div) if images_div else ""
            
            # Path to original PDF page image
            original_image_path = f"page_{page_num:04d}_original/original_page.png"
            
            # Copy original page image to output directory
            src_image_path = os.path.join(temp_dir, original_image_path)
            dst_image_dir = os.path.join(output_dir, f"page_{page_num:04d}_original")
            dst_image_path = os.path.join(output_dir, original_image_path)
            
            # Create directory if it doesn't exist
            os.makedirs(dst_image_dir, exist_ok=True)
            
            # Copy original page image if it exists
            if os.path.exists(src_image_path):
                shutil.copy2(src_image_path, dst_image_path)
            
            # Add dual-page spread
            book_html += f"""        <div class="dual-page-spread">
            <div class="page persian-page">
                {persian_content}
                {images_content}
            </div>
            <div class="page original-page">
                <img src="{original_image_path}" alt="Original Page {page_num}">
            </div>
        </div>
"""
        
        # Add closing tags and scripts
        book_html += """    </div>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/line-numbers/prism-line-numbers.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', (event) => {
            if (window.Prism) {
                Prism.highlightAll();
            }
        });
    </script>
</body>
</html>"""
        
        # Save the dual-page book
        with open(output_html, 'w', encoding='utf-8') as f:
            f.write(book_html)
        
        print(f"  Dual-page HTML book created successfully: {output_html}")
        return True
        
    except Exception as e:
        print(f"Error creating dual-page book: {str(e)}")
        return False 
