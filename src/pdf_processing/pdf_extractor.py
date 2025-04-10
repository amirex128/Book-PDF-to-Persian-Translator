import os
import re
import time
import fitz  # PyMuPDF
import tempfile
import shutil
import concurrent.futures
from pathlib import Path

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def extract_text_from_pdf(pdf_path, limit=None, skip_pages=None):
    """Extract text from PDF file
    
    Args:
        pdf_path (str): Path to PDF file
        limit (int, optional): Limit number of pages to extract. Defaults to None.
        skip_pages (list, optional): List of page numbers to skip. Defaults to None.
        
    Returns:
        tuple: Dictionary mapping page numbers to text, and count of pages extracted
    """
    print(f"Extracting text from {pdf_path}...")
    
    # Open the PDF
    pdf_document = fitz.open(pdf_path)
    
    # Get total number of pages
    total_pages = pdf_document.page_count
    print(f"Total pages: {total_pages}")
    
    # If limit is set, adjust to not exceed total pages
    if limit:
        limit = min(limit, total_pages)
        print(f"Limited to first {limit} pages")
    else:
        limit = total_pages
    
    # Initialize skip_pages if not provided
    if skip_pages is None:
        skip_pages = []
    
    # Extract text from each page
    extracted_text = {}
    
    for page_num in range(limit):
        if page_num + 1 in skip_pages:
            print(f"Skipping page {page_num + 1} as requested")
            continue
        
        try:
            page = pdf_document.load_page(page_num)
            text = page.get_text()
            
            # Skip if page is empty
            if not text.strip():
                print(f"Page {page_num + 1} is empty, skipping")
                continue
            
            extracted_text[page_num + 1] = text
            
            if (page_num + 1) % 10 == 0:
                print(f"Extracted text from {page_num + 1} pages")
        
        except Exception as e:
            print(f"Error extracting text from page {page_num + 1}: {e}")
    
    # Close the PDF
    pdf_document.close()
    
    print(f"Successfully extracted text from {len(extracted_text)} pages")
    return extracted_text, len(extracted_text)

def extract_images_from_pdf(pdf_path, output_dir, limit=None, skip_pages=None):
    """Extract images from PDF file
    
    Args:
        pdf_path (str): Path to PDF file
        output_dir (str): Directory to save extracted images
        limit (int, optional): Limit number of pages to extract. Defaults to None.
        skip_pages (list, optional): List of page numbers to skip. Defaults to None.
        
    Returns:
        tuple: List of all extracted images and dictionary mapping page numbers to images
    """
    print(f"Extracting images from {pdf_path}...")
    
    # Open the PDF
    pdf_document = fitz.open(pdf_path)
    
    # Get total number of pages
    total_pages = pdf_document.page_count
    
    # If limit is set, adjust to not exceed total pages
    if limit:
        limit = min(limit, total_pages)
    else:
        limit = total_pages
    
    # Initialize skip_pages if not provided
    if skip_pages is None:
        skip_pages = []
    
    # Create images directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Extract images from each page
    extracted_images = []
    pages_images = {}
    
    for page_num in range(limit):
        if page_num + 1 in skip_pages:
            print(f"Skipping page {page_num + 1} as requested")
            continue
        
        try:
            # Create a directory for this page's images
            page_dir = os.path.join(output_dir, f"page_{page_num + 1:04d}")
            os.makedirs(page_dir, exist_ok=True)
            
            # Create a directory for original page image
            original_page_dir = os.path.join(output_dir, f"page_{page_num + 1:04d}_original")
            os.makedirs(original_page_dir, exist_ok=True)
            
            # Save the whole page as an image
            page = pdf_document.load_page(page_num)
            
            # Save original page as image
            original_page_path = os.path.join(original_page_dir, "original_page.png")
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            pix.save(original_page_path)
            
            # Extract embedded images
            image_list = page.get_images(full=True)
            
            # Initialize page images list
            page_images = []
            
            # If no images found on this page
            if not image_list:
                image_data = {
                    "page_number": page_num + 1,
                    "images": [],
                    "original_page": {
                        "path": original_page_path,
                        "relative_path": f"page_{page_num + 1:04d}_original/original_page.png"
                    }
                }
                extracted_images.append(image_data)
                pages_images[page_num + 1] = []
                continue
            
            # Process and save each image
            for img_index, img in enumerate(image_list):
                # Get image properties
                xref = img[0]
                img_name = f"image_{img_index + 1}.png"
                img_path = os.path.join(page_dir, img_name)
                
                try:
                    # Extract and save the image
                    base_img = pdf_document.extract_image(xref)
                    img_data = base_img["image"]
                    
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)
                    
                    # Add image info to the list
                    image_info = {
                        "index": img_index + 1,
                        "path": img_path,
                        "relative_path": f"page_{page_num + 1:04d}/{img_name}"
                    }
                    page_images.append(image_info)
                
                except Exception as img_error:
                    print(f"Error extracting image {img_index + 1} from page {page_num + 1}: {img_error}")
            
            # Add page info to the extracted images list
            image_data = {
                "page_number": page_num + 1,
                "images": page_images,
                "original_page": {
                    "path": original_page_path,
                    "relative_path": f"page_{page_num + 1:04d}_original/original_page.png"
                }
            }
            extracted_images.append(image_data)
            pages_images[page_num + 1] = page_images
            
            print(f"Extracted {len(page_images)} images from page {page_num + 1}")
        
        except Exception as e:
            print(f"Error processing page {page_num + 1}: {e}")
    
    # Close the PDF
    pdf_document.close()
    
    # Count total images extracted
    total_images = sum(len(page["images"]) for page in extracted_images)
    print(f"Successfully extracted {total_images} images from {len(extracted_images)} pages")
    
    return extracted_images, pages_images

def process_pdf_concurrently(pdf_path, output_dir, num_workers=4, limit=None):
    """Process PDF file concurrently, extracting both text and images
    
    Args:
        pdf_path (str): Path to PDF file
        output_dir (str): Directory to save extracted content
        num_workers (int, optional): Number of worker threads. Defaults to 4.
        limit (int, optional): Limit number of pages to process. Defaults to None.
        
    Returns:
        tuple: Tuple of (extracted_text, extracted_images)
    """
    # Create a temporary directory for processing
    temp_dir = tempfile.mkdtemp()
    print(f"Created temporary directory: {temp_dir}")
    
    try:
        # Open the PDF to get page count
        pdf_document = fitz.open(pdf_path)
        total_pages = pdf_document.page_count
        pdf_document.close()
        
        # Adjust limit if needed
        if limit:
            total_pages = min(limit, total_pages)
        
        # Divide pages among workers
        page_ranges = []
        pages_per_worker = total_pages // num_workers
        remainder = total_pages % num_workers
        
        start_page = 0
        for i in range(num_workers):
            # Add one extra page to some workers if there's a remainder
            extra = 1 if i < remainder else 0
            end_page = start_page + pages_per_worker + extra
            if end_page > total_pages:
                end_page = total_pages
            
            if start_page < end_page:
                page_ranges.append((start_page, end_page))
            
            start_page = end_page
        
        # Process each range in a separate thread
        extracted_text = []
        extracted_images = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
            # Submit text extraction tasks
            text_futures = []
            for start, end in page_ranges:
                text_future = executor.submit(extract_text_range, pdf_path, start, end)
                text_futures.append(text_future)
            
            # Submit image extraction tasks
            image_futures = []
            for start, end in page_ranges:
                worker_temp_dir = os.path.join(temp_dir, f"worker_{start}_{end}")
                os.makedirs(worker_temp_dir, exist_ok=True)
                image_future = executor.submit(extract_images_range, pdf_path, worker_temp_dir, start, end)
                image_futures.append(image_future)
            
            # Collect text results
            for future in concurrent.futures.as_completed(text_futures):
                try:
                    result = future.result()
                    extracted_text.extend(result)
                except Exception as e:
                    print(f"Error in text extraction thread: {e}")
            
            # Collect image results
            for future in concurrent.futures.as_completed(image_futures):
                try:
                    result = future.result()
                    extracted_images.extend(result)
                except Exception as e:
                    print(f"Error in image extraction thread: {e}")
        
        # Sort results by page number
        extracted_text.sort(key=lambda x: x["page_number"])
        extracted_images.sort(key=lambda x: x["page_number"])
        
        # Copy image files to output directory
        os.makedirs(output_dir, exist_ok=True)
        for page in extracted_images:
            page_num = page["page_number"]
            
            # Copy original page image
            orig_src = page["original_page"]["path"]
            orig_dst_dir = os.path.join(output_dir, f"page_{page_num:04d}_original")
            os.makedirs(orig_dst_dir, exist_ok=True)
            orig_dst = os.path.join(orig_dst_dir, "original_page.png")
            shutil.copy2(orig_src, orig_dst)
            
            # Copy embedded images
            for img in page["images"]:
                src = img["path"]
                dst_dir = os.path.join(output_dir, f"page_{page_num:04d}")
                os.makedirs(dst_dir, exist_ok=True)
                dst = os.path.join(dst_dir, os.path.basename(src))
                shutil.copy2(src, dst)
        
        return extracted_text, extracted_images
    
    finally:
        # Clean up temporary directory
        print(f"Cleaning up temporary directory: {temp_dir}")
        shutil.rmtree(temp_dir, ignore_errors=True)

def extract_text_range(pdf_path, start_page, end_page):
    """Extract text from a range of pages
    
    Args:
        pdf_path (str): Path to PDF file
        start_page (int): Start page (0-indexed)
        end_page (int): End page (exclusive)
        
    Returns:
        list: List of dictionaries with page number and text
    """
    pdf_document = fitz.open(pdf_path)
    extracted_text = []
    
    for page_num in range(start_page, end_page):
        try:
            page = pdf_document.load_page(page_num)
            text = page.get_text()
            
            # Skip if page is empty
            if not text.strip():
                continue
            
            extracted_text.append({
                "page_number": page_num + 1,
                "text": text
            })
        
        except Exception as e:
            print(f"Error extracting text from page {page_num + 1}: {e}")
    
    pdf_document.close()
    return extracted_text

def extract_images_range(pdf_path, output_dir, start_page, end_page):
    """Extract images from a range of pages
    
    Args:
        pdf_path (str): Path to PDF file
        output_dir (str): Directory to save extracted images
        start_page (int): Start page (0-indexed)
        end_page (int): End page (exclusive)
        
    Returns:
        list: List of dictionaries with page number and image paths
    """
    pdf_document = fitz.open(pdf_path)
    extracted_images = []
    
    for page_num in range(start_page, end_page):
        try:
            # Create a directory for this page's images
            page_dir = os.path.join(output_dir, f"page_{page_num + 1:04d}")
            os.makedirs(page_dir, exist_ok=True)
            
            # Create a directory for original page image
            original_page_dir = os.path.join(output_dir, f"page_{page_num + 1:04d}_original")
            os.makedirs(original_page_dir, exist_ok=True)
            
            # Save the whole page as an image
            page = pdf_document.load_page(page_num)
            
            # Save original page as image
            original_page_path = os.path.join(original_page_dir, "original_page.png")
            pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72))
            pix.save(original_page_path)
            
            # Extract embedded images
            image_list = page.get_images(full=True)
            
            # If no images found on this page
            if not image_list:
                extracted_images.append({
                    "page_number": page_num + 1,
                    "images": [],
                    "original_page": {
                        "path": original_page_path,
                        "relative_path": f"page_{page_num + 1:04d}_original/original_page.png"
                    }
                })
                continue
            
            # Process and save each image
            page_images = []
            for img_index, img in enumerate(image_list):
                # Get image properties
                xref = img[0]
                img_name = f"image_{img_index + 1}.png"
                img_path = os.path.join(page_dir, img_name)
                
                try:
                    # Extract and save the image
                    base_img = pdf_document.extract_image(xref)
                    img_data = base_img["image"]
                    
                    with open(img_path, "wb") as img_file:
                        img_file.write(img_data)
                    
                    # Add image info to the list
                    page_images.append({
                        "index": img_index + 1,
                        "path": img_path,
                        "relative_path": f"page_{page_num + 1:04d}/{img_name}"
                    })
                
                except Exception as img_error:
                    print(f"Error extracting image {img_index + 1} from page {page_num + 1}: {img_error}")
            
            # Add page info to the extracted images list
            extracted_images.append({
                "page_number": page_num + 1,
                "images": page_images,
                "original_page": {
                    "path": original_page_path,
                    "relative_path": f"page_{page_num + 1:04d}_original/original_page.png"
                }
            })
        
        except Exception as e:
            print(f"Error processing page {page_num + 1}: {e}")
    
    pdf_document.close()
    return extracted_images

def extract_pdf_page_as_image(pdf_path, page_num, output_dir, dpi=300):
    """Extract a PDF page as an image"""
    try:
        # Create directory for the page
        page_dir = os.path.join(output_dir, f"page_{page_num + 1:04d}_original")
        if not os.path.exists(page_dir):
            os.makedirs(page_dir)
        
        # Path to save the image
        output_path = os.path.join(page_dir, "original_page.png")
        
        # Check if the image already exists
        if os.path.exists(output_path):
            return output_path
        
        # Open the PDF
        pdf_document = fitz.open(pdf_path)
        
        # Get the page
        page = pdf_document[page_num]
        
        # Render the page as a pixmap (image)
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi/72, dpi/72))
        
        # Save the pixmap as PNG
        pix.save(output_path)
        
        # Close the PDF
        pdf_document.close()
        
        return output_path
    
    except Exception as e:
        print(f"Error extracting page {page_num + 1} as image: {str(e)}")
        return None 