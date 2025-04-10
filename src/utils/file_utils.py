import os
import re
import shutil
import glob

def sanitize_filename(filename):
    """Remove invalid characters from filename"""
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def ensure_directory_exists(directory_path):
    """Ensure that a directory exists, creating it if necessary"""
    if not os.path.exists(directory_path):
        os.makedirs(directory_path, exist_ok=True)
        return True
    return False

def copy_assets(source_dir, dest_dir, glob_pattern="*.*"):
    """Copy assets from source directory to destination directory
    
    Args:
        source_dir (str): Source directory
        dest_dir (str): Destination directory
        glob_pattern (str): Glob pattern for files to copy
        
    Returns:
        int: Number of files copied
    """
    ensure_directory_exists(dest_dir)
    files_copied = 0
    
    for file_path in glob.glob(os.path.join(source_dir, glob_pattern)):
        if os.path.isfile(file_path):
            shutil.copy2(file_path, dest_dir)
            files_copied += 1
    
    return files_copied

def get_file_base_name(file_path):
    """Get base name of a file without extension
    
    Args:
        file_path (str): File path
        
    Returns:
        str: Base name without extension
    """
    return os.path.splitext(os.path.basename(file_path))[0]

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