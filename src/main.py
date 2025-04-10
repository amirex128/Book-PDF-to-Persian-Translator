import os
import argparse
import sys
import datetime  # Add proper datetime import
from dotenv import load_dotenv

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pdf_processing.pdf_extractor import extract_text_from_pdf, extract_images_from_pdf, extract_pdf_page_as_image
from src.translation.translator import translate_text_to_persian, get_api_key_usage_stats
from src.html_generation.html_generator import create_html_content, create_html_book, create_dual_page_book, copy_font_assets
from src.utils.file_utils import sanitize_filename, ensure_directory_exists

def load_api_keys_from_env():
    """Load API keys from .env file"""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get primary API key from environment variables
    primary_key = os.getenv('PRIMARY_API_KEY')
    
    # Get additional API keys from environment variables
    additional_keys_str = os.getenv('ADDITIONAL_API_KEYS', '')
    additional_keys = [key.strip() for key in additional_keys_str.split(',') if key.strip()]
    
    # If no primary key found, provide error message
    if not primary_key:
        print("Error: PRIMARY_API_KEY not found in .env file")
        print("Please create a .env file in the project root with the following format:")
        print("PRIMARY_API_KEY=your_primary_api_key")
        print("ADDITIONAL_API_KEYS=key1,key2,key3")
        sys.exit(1)
    
    total_keys = len(additional_keys) + 1
    print(f"Loaded {total_keys} API key{'s' if total_keys > 1 else ''} from .env file")
    if additional_keys:
        print(f"Using API key rotation with {total_keys} keys to minimize rate limiting")
    
    return primary_key, additional_keys

def extract_and_translate_pdf(pdf_path, api_key, limit=None, skip_pages=None, force=False, 
                           output_format="both", check_existing=True, conversation=None, additional_api_keys=None):
    """Extract text and images from a PDF file and translate it to Persian"""
    try:
        # Create output directory
        pdf_filename = os.path.basename(pdf_path)
        base_name, _ = os.path.splitext(pdf_filename)
        output_dir = os.path.join(os.getcwd(), "output", base_name)
        
        if not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            print(f"Using output directory: {output_dir}")
        else:
            print(f"Using existing output directory: {output_dir}")
        
        # Extract text from the PDF
        print(f"Processing PDF: {pdf_path}")
        
        if limit:
            print(f"Limited to first {limit} pages")
            
        if skip_pages:
            print(f"Skipping pages: {skip_pages}")
            
        if force:
            print("Force mode: Overwriting existing translations")
        
        if additional_api_keys:
            num_keys = len(additional_api_keys) + 1  # +1 for primary key
            print(f"Using {num_keys} API keys with smart rotation for rate limit management")
        
        # First, check for already translated pages to give proper statistics
        if check_existing and not force:
            already_translated_count = 0
            pages_needing_translation = []
            
            # Extract text from PDF
            print(f"Extracting text from {pdf_path}...")
            extracted_text, num_extracted = extract_text_from_pdf(pdf_path, limit, skip_pages)
            
            # Check which pages already have translations
            for page_num in extracted_text.keys():
                page_str = f"{page_num:04d}"
                trans_file = os.path.join(output_dir, f"page_{page_str}_fa.txt")
                html_file = os.path.join(output_dir, f"page_{page_str}_fa.html")
                
                if os.path.exists(trans_file) and os.path.exists(html_file):
                    already_translated_count += 1
                else:
                    pages_needing_translation.append(page_num)
            
            # Inform the user about pages status
            if already_translated_count > 0:
                print(f"Found {already_translated_count} already translated pages")
                
                if pages_needing_translation:
                    print(f"Need to translate {len(pages_needing_translation)} pages: {', '.join(map(str, pages_needing_translation))}")
                else:
                    print("All pages have already been translated! Nothing to do.")
                    
                    # If all pages are translated, just generate the books and finish
                    if not pages_needing_translation and already_translated_count > 0:
                        # Construct the list of HTML files for book creation
                        html_files = []
                        for page_num in extracted_text.keys():
                            page_str = f"{page_num:04d}"
                            html_file = os.path.join(output_dir, f"page_{page_str}_fa.html")
                            html_files.append(html_file)
                        
                        # Create HTML books
                        if html_files:
                            # Create translation-only book
                            translation_success = create_html_book(html_files, os.path.join(output_dir, f"{base_name}_Farsi.html"), output_dir, base_name)
                            if translation_success:
                                print(f"Translation-only HTML book created: {os.path.join(output_dir, f'{base_name}_Farsi.html')}")
                            
                            # Create dual-view book
                            dual_view_success = create_dual_page_book(html_files, os.path.join(output_dir, f"{base_name}_Dual_View.html"), output_dir, base_name, pdf_path)
                            if dual_view_success:
                                print(f"Dual-view HTML book created: {os.path.join(output_dir, f'{base_name}_Dual_View.html')}")
                            
                            return translation_success or dual_view_success
        
        # Extract text from PDF if we haven't done so already
        if not 'extracted_text' in locals():
            print(f"Extracting text from {pdf_path}...")
            extracted_text, num_extracted = extract_text_from_pdf(pdf_path, limit, skip_pages)
        
        # Extract images from PDF
        print(f"Extracting images from {pdf_path}...")
        all_images, pages_images = extract_images_from_pdf(pdf_path, output_dir, limit, skip_pages)
        
        # Prepare HTML files list
        html_files = []
        total_images = 0
        rate_limited_count = 0
        successful_translations = 0
        skipped_count = 0
        new_translations_count = 0
        
        # Process each extracted page
        for i, (page_num, text) in enumerate(extracted_text.items()):
            page_images = pages_images.get(page_num, [])
            total_images += len(page_images)
            
            # Create corresponding file paths
            page_str = f"{page_num:04d}"
            orig_file = os.path.join(output_dir, f"page_{page_str}.txt")
            trans_file = os.path.join(output_dir, f"page_{page_str}_fa.txt")
            html_file = os.path.join(output_dir, f"page_{page_str}_fa.html")
            
            # Add to list of HTML files for book creation
            html_files.append(html_file)
            
            # Save original text
            with open(orig_file, 'w', encoding='utf-8') as f:
                f.write(text)
            
            # Check if translation already exists
            if os.path.exists(trans_file) and os.path.exists(html_file) and check_existing and not force:
                print(f"Page {page_num} already translated, skipping")
                skipped_count += 1
                successful_translations += 1
                continue
            
            # Translate text to Persian
            try:
                print(f"  Translating page {i+1}/{len(extracted_text)}: page_{page_str}")
                translated_text, conversation = translate_text_to_persian(
                    text, 
                    api_key, 
                    model_name="models/gemini-2.0-flash",
                    conversation=conversation,
                    api_keys=additional_api_keys
                )
                
                # Save translated text
                with open(trans_file, 'w', encoding='utf-8') as f:
                    f.write(translated_text)
                
                # Create base name for HTML file
                base_name_html = f"page_{page_str}"
                
                # Copy font files
                fonts_copied = copy_font_assets(output_dir)
                if fonts_copied and new_translations_count == 0:  # Only print once for first newly translated page
                    print("  Font files copied to output directory.")
                
                # Create HTML file with translation and images
                html_content, _ = create_html_content(translated_text, base_name_html, fonts_copied, page_images)
                
                # Save HTML content
                with open(html_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                successful_translations += 1
                new_translations_count += 1
                
            except Exception as e:
                error_str = str(e).lower()
                if "429" in error_str or "rate limit" in error_str or "quota" in error_str:
                    rate_limited_count += 1
                print(f"Error processing page {page_num}: {str(e)}")
                continue
        
        # Print translation stats
        print("\nTranslation Statistics:")
        print(f"  Total pages in PDF: {num_extracted}")
        print(f"  Pages processed: {len(extracted_text)}")
        print(f"  Pages already translated (skipped): {skipped_count}")
        print(f"  Pages newly translated: {new_translations_count}")
        print(f"  Total images extracted: {total_images}")
        if rate_limited_count > 0:
            print(f"  Rate limit errors encountered: {rate_limited_count}")
        
        # Print API key usage statistics
        if additional_api_keys:
            print("\nAPI Key Usage Statistics:")
            usage_stats = get_api_key_usage_stats()
            for key, stats in usage_stats.items():
                # Mask the API key for security
                masked_key = key[:6] + '...' + key[-4:] if len(key) > 10 else "Unknown"
                status = "RATE LIMITED" if stats.get('rate_limited_until') else "ACTIVE"
                count = stats.get('count', 0)
                rate_limit_count = stats.get('rate_limit_count', 0)
                
                cooldown_info = ""
                if stats.get('rate_limited_until'):
                    # Directly use the datetime module
                    now = datetime.datetime.now()
                    if stats['rate_limited_until'] > now:
                        time_left = (stats['rate_limited_until'] - now).total_seconds() / 60
                        cooldown_info = f", cooldown for {time_left:.1f} min"
                
                print(f"  {masked_key}: {count} requests, Rate limits: {rate_limit_count}, Status: {status}{cooldown_info}")
        
        # 4. Extract all PDF pages as images for dual-page view
        print("\nExtracting original PDF pages as images...")
        for page_num in range(min(len(extracted_text), limit or len(extracted_text))):
            extract_pdf_page_as_image(pdf_path, page_num, output_dir)
        
        # 5. Create HTML books
        if html_files:
            # Create translation-only book
            translation_success = create_html_book(html_files, os.path.join(output_dir, f"{base_name}_Farsi.html"), output_dir, base_name)
            if translation_success:
                print(f"Translation-only HTML book created: {os.path.join(output_dir, f'{base_name}_Farsi.html')}")
            else:
                print("Failed to create translation-only HTML book.")
            
            # Create dual-view book
            dual_view_success = create_dual_page_book(html_files, os.path.join(output_dir, f"{base_name}_Dual_View.html"), output_dir, base_name, pdf_path)
            if dual_view_success:
                print(f"Dual-view HTML book created: {os.path.join(output_dir, f'{base_name}_Dual_View.html')}")
            else:
                print("Failed to create dual-view HTML book.")
            
            return translation_success or dual_view_success
        else:
            print("No HTML files were created. Translation failed.")
            return False
    except Exception as e:
        print(f"Error processing PDF: {str(e)}")
        return False

def process_all_pdfs(books_dir, api_key, additional_api_keys=None, limit=None, skip_pages=None, force=False, 
               output_format="both", check_existing=True, output_dir="output"):
    """Process all PDF files in the specified directory"""
    # Check if directory exists
    if not os.path.exists(books_dir):
        print(f"Error: Directory '{books_dir}' does not exist.")
        return
    
    # Find all PDF files
    pdf_files = [f for f in os.listdir(books_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in '{books_dir}'.")
        return
    
    print(f"Found {len(pdf_files)} PDF files for processing.")
    
    successful = 0
    failed = 0
    
    # Process each PDF
    for pdf_file in pdf_files:
        pdf_path = os.path.join(books_dir, pdf_file)
        print(f"\n{'='*50}")
        print(f"Processing file: {pdf_file}")
        print(f"{'='*50}")
        
        # Process the PDF
        result = extract_and_translate_pdf(
            pdf_path, 
            api_key, 
            limit=limit, 
            skip_pages=skip_pages, 
            force=force, 
            output_format=output_format, 
            check_existing=check_existing,
            additional_api_keys=additional_api_keys
        )
        
        if result:
            successful += 1
        else:
            failed += 1
    
    # Display overall summary
    print("\n" + "="*50)
    print("Overall Processing Summary:")
    print(f"  Total PDF files: {len(pdf_files)}")
    print(f"  Successful: {successful}")
    print(f"  Failed: {failed}")
    print(f"  Output format: {output_format.replace('_', ' ').title()}")
    if additional_api_keys:
        print(f"  API keys used: {len(additional_api_keys) + 1}")
    print("="*50)
    print("Processing completed.")

def main():
    """Main entry point for the application"""
    parser = argparse.ArgumentParser(description='Extract and translate PDF files')
    parser.add_argument('--books_dir', type=str, default='books', help='Directory containing PDF files')
    parser.add_argument('--output_dir', type=str, default='output', help='Directory to save output')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of pages to process')
    parser.add_argument('--skip_pages', type=str, default=None, help='Comma-separated list of pages to skip')
    parser.add_argument('--force', action='store_true', help='Force overwrite existing translations')
    parser.add_argument('--output_format', type=str, default='both', choices=['html', 'dual_page', 'both'], 
                        help='Output format: html, dual_page, or both')
    parser.add_argument('--check_existing', action='store_false', default=True, 
                        help='Skip checking for existing translations')
    
    args = parser.parse_args()
    
    # Convert skip_pages to list if provided
    skip_pages = None
    if args.skip_pages:
        skip_pages = [int(p) for p in args.skip_pages.split(',')]
    
    # Load API keys from .env file
    primary_api_key, additional_api_keys = load_api_keys_from_env()
    
    # Check if output directory exists
    output_dir = os.path.join(os.getcwd(), args.output_dir)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        print(f"Created output directory: {output_dir}")
    
    # Process all PDFs in the books directory
    process_all_pdfs(
        books_dir=args.books_dir,
        output_dir=args.output_dir,
        api_key=primary_api_key,
        additional_api_keys=additional_api_keys,
        limit=args.limit,
        skip_pages=skip_pages,
        force=args.force,
        output_format=args.output_format,
        check_existing=args.check_existing
    )

if __name__ == "__main__":
    main() 