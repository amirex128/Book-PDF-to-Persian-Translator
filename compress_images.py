import os
import json
from PIL import Image
from pathlib import Path

CONFIG_FILE = "compressed_files.json"

def get_compression_settings(file_size_kb):
    """
    Determine compression settings based on file size
    Returns quality and optimization settings
    """
    if file_size_kb > 1000:  # Large files (>1MB)
        return 40, True  # More aggressive compression for large files
    elif file_size_kb > 500:  # Medium files (>500KB)
        return 50, True
    else:  # Small files
        return 60, True

def load_compressed_files():
    """Load the list of already compressed files from config"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                content = f.read().strip()
                if not content:  # If file is empty
                    return []
                return json.loads(content)
        except json.JSONDecodeError:
            # If file exists but is corrupted/invalid JSON
            return []
    return []

def save_compressed_file(file_path):
    """Save a newly compressed file path to the config"""
    compressed_files = load_compressed_files()
    if file_path not in compressed_files:
        compressed_files.append(file_path)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(compressed_files, f)

def compress_image(input_path):
    """
    Compress an image and replace the original file with optimized settings
    """
    # Check if file has already been compressed
    compressed_files = load_compressed_files()
    if input_path in compressed_files:
        print(f"Skipping already compressed file: {input_path}")
        return

    try:
        # Get original file size
        original_size = os.path.getsize(input_path) / 1024  # Size in KB
        
        # Open the image
        with Image.open(input_path) as img:
            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img = img.convert('RGB')
            
            # Get compression settings based on file size
            quality, optimize = get_compression_settings(original_size)
            
            # Save the compressed image with progressive encoding and subsampling
            img.save(
                input_path,
                'JPEG',
                quality=quality,
                optimize=optimize,
                progressive=True,
                subsampling=2  # Use 4:2:0 subsampling for more compression
            )
            
            # Calculate compression ratio
            new_size = os.path.getsize(input_path) / 1024  # Size in KB
            compression_ratio = (1 - (new_size / original_size)) * 100
            
            print(f"Compressed: {input_path}")
            print(f"Original size: {original_size:.1f}KB -> New size: {new_size:.1f}KB (Reduced by {compression_ratio:.1f}%)")
            
            # If compression ratio is less than 50%, try again with even lower quality
            if compression_ratio < 50:
                print("Compression ratio below 50%, applying additional compression...")
                quality = max(30, quality - 10)  # Reduce quality further but not below 30
                img.save(
                    input_path,
                    'JPEG',
                    quality=quality,
                    optimize=optimize,
                    progressive=True,
                    subsampling=2
                )
                new_size = os.path.getsize(input_path) / 1024
                compression_ratio = (1 - (new_size / original_size)) * 100
                print(f"Additional compression: New size: {new_size:.1f}KB (Reduced by {compression_ratio:.1f}%)")
            
            # Save the file path to config after successful compression
            save_compressed_file(input_path)
            
    except Exception as e:
        print(f"Error processing {input_path}: {str(e)}")

def process_directory(input_dir):
    """
    Process all images in the input directory and its subdirectories
    """
    # Supported image extensions
    image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif'}
    
    # Walk through all directories
    for root, _, files in os.walk(input_dir):
        for file in files:
            # Get file extension
            ext = os.path.splitext(file)[1].lower()
            
            if ext in image_extensions:
                # Get full input path
                input_path = os.path.join(root, file)
                
                # Compress the image
                compress_image(input_path)

if __name__ == "__main__":
    # Set input directory
    input_dir = "output"
    
    print(f"Starting image compression in {input_dir}")
    process_directory(input_dir)
    print("Image compression completed!") 