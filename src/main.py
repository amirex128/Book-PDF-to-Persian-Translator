import os
import argparse
import sys

# Add the src directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.pdf_processing.pdf_extractor import extract_text_from_pdf, extract_images_from_pdf, extract_pdf_page_as_image
from src.translation.translator import translate_text_to_persian
from src.html_generation.html_generator import create_html_content, create_html_book, create_dual_page_book, copy_font_assets
from src.utils.file_utils import sanitize_filename, ensure_directory_exists

def extract_and_translate_pdf(pdf_path, api_key, limit=None):
    """Extract and translate a PDF file"""
    print(f"Processing PDF: {pdf_path}")
    
    pdf_dir = os.path.dirname(pdf_path)
    pdf_filename = os.path.basename(pdf_path)
    file_base_name = os.path.splitext(pdf_filename)[0]
    sanitized_name = sanitize_filename(file_base_name)
    
    # Create output directory if it doesn't exist
    output_dir_base = os.path.join(os.getcwd(), "output")
    ensure_directory_exists(output_dir_base)
    
    # Create a subdirectory with the PDF name in the output directory
    pdf_output_dir = os.path.join(output_dir_base, sanitized_name)
    
    if ensure_directory_exists(pdf_output_dir):
        print(f"Created output directory: {pdf_output_dir}")
    else:
        print(f"Using existing output directory: {pdf_output_dir}")
        
    # Define output HTML paths in the PDF-specific output directory
    translation_html = os.path.join(pdf_output_dir, f"{file_base_name}_Farsi.html")
    dual_view_html = os.path.join(pdf_output_dir, f"{file_base_name}_Dual_View.html")
    
    # Create directory for this book if it doesn't exist
    temp_dir = os.path.join(pdf_dir, sanitized_name)
    
    if ensure_directory_exists(temp_dir):
        print(f"Created processing directory: {temp_dir}")
    else:
        print(f"Using existing processing directory: {temp_dir}")
    
    # Copy font files to temp directory
    fonts_copied = copy_font_assets(temp_dir)
    if fonts_copied:
        print("Font files copied successfully.")
    
    # Initialize variables
    html_files = []
    toc_headings = []
    
    # 1. Extract text from PDF
    extracted_text = extract_text_from_pdf(pdf_path, limit)
    
    if not extracted_text:
        print(f"No text extracted from {pdf_filename}. Check if PDF is empty or contains only images.")
        return False
    
    # 2. Extract images from PDF
    extracted_images = extract_images_from_pdf(pdf_path, temp_dir, limit)
    
    # Create a dictionary of images by page number
    page_images = {}
    for page in extracted_images:
        page_num = page["page_number"]
        page_name = f"page_{page_num:04d}"
        page_images[page_name] = page["images"]
    
    # 3. Translate each page's text to Persian
    conversation = None
    translated_files = 0
    
    for item in extracted_text:
        page_num = item["page_number"]
        text = item["text"]
        base_name = f"page_{page_num:04d}"
        
        # Path for translated HTML file
        html_file = os.path.join(temp_dir, f"{base_name}_fa.html")
        
        # Skip if file already exists
        if os.path.exists(html_file):
            print(f"Page {page_num} already translated, skipping")
            html_files.append(html_file)
            continue
        
        # Translate text
        translated_text, conversation = translate_text_to_persian(text, api_key, conversation)
        
        if translated_text:
            # Check for images for this page
            page_images_list = page_images.get(base_name, [])
            
            # Create HTML content
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
            print(f"Translated page {page_num}")
        else:
            print(f"Failed to translate page {page_num}")
    
    # 4. Extract all PDF pages as images for dual-page view
    print("\nExtracting original PDF pages as images...")
    for page_num in range(min(len(extracted_text), limit or len(extracted_text))):
        extract_pdf_page_as_image(pdf_path, page_num, temp_dir)
    
    # 5. Create HTML books
    if html_files:
        # Create translation-only book
        translation_success = create_html_book(html_files, translation_html, pdf_output_dir, file_base_name, toc_headings=toc_headings)
        if translation_success:
            print(f"Translation-only HTML book created: {translation_html}")
        else:
            print("Failed to create translation-only HTML book.")
        
        # Create dual-view book
        dual_view_success = create_dual_page_book(html_files, dual_view_html, pdf_output_dir, file_base_name, pdf_path, toc_headings=toc_headings)
        if dual_view_success:
            print(f"Dual-view HTML book created: {dual_view_html}")
        else:
            print("Failed to create dual-view HTML book.")
        
        return translation_success or dual_view_success
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

def main():
    """Main entry point for the script"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Extract, translate and convert PDF files to Persian HTML')
    parser.add_argument('--api-key', default="AIzaSyD1HS27l8i8N5jBnSCixhGH3sRiH81i9HQ", help='Gemini API key')
    parser.add_argument('--books-dir', default=os.path.join(os.getcwd(), "books"), help='Directory containing PDF files')
    parser.add_argument('--limit', type=int, help='Maximum number of pages to process from each book')
    
    args = parser.parse_args()
    
    # Process all PDFs
    process_all_pdfs(
        books_dir=args.books_dir,
        api_key=args.api_key,
        limit=args.limit
    )
    
    print("Processing completed.")

if __name__ == "__main__":
    main() 