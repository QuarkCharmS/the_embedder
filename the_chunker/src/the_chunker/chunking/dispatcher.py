# dispatcher.py
import os
from .chunker_config import get_language_from_extension, is_chunkable
from .tree_chunker import extract_code_blocks
from .fallback_chunker import fallback_chunk
from .read_file_content import read_file_content 


def chunk_file(file_path: str, model_name: str, debug_level : str) -> list[dict]:
    """
    Main entry point for chunking files.
    Returns list of dictionaries with 'content' and 'tokens' keys.
    """
    # Use the centralized language resolution from config
    language = get_language_from_extension(file_path)
    if debug_level == "VERBOSE":
        print(f"[INFO] Identified language: {language} for file: {os.path.basename(file_path)}")
    
    try:
        content = read_file_content(file_path)
        
        if content == "":
            print("[INFO] File is empty")
            return []

    except Exception as e:
        print(f"[ERROR] Could not read file {file_path}: {e}")
        return []
    
    if is_chunkable(language):
        if debug_level == "VERBOSE":
            print(f"[INFO] Using tree-sitter chunking for {language}")
        try:
            code_blocks = extract_code_blocks(content, language, model_name, debug_level)
            if code_blocks == []:
                if debug_level=="VERBOSE":
                    print("[INFO] No code blocks were extracted from file, using fallback strategy instead")
                return fallback_chunk(content, model_name, debug_level)
            return code_blocks
        except BaseException as e:
            # Catch EVERYTHING - even system errors
            # Tree-sitter C++ crashes might leak through as SystemError/RuntimeError
            print(f"[WARNING] Tree-sitter chunking failed for {language}: {e}")
            print(f"[INFO] Falling back to Chonkie chunking")
            return fallback_chunk(content, model_name, debug_level)
    else:
        if debug_level == "VERBOSE":
            print(f"[INFO] Using fallback chunking for {language}")
        return fallback_chunk(content, model_name, debug_level)
