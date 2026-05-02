# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import os
import argparse
import tempfile
from typing import Optional

def get_markitdown():
    try:
        from markitdown import MarkItDown
        return MarkItDown()
    except ImportError:
        return None

def main():
    parser = argparse.ArgumentParser(description="Context-Pipe Multi-Modal Ingestor")
    parser.add_argument("file_path", nargs="?", help="Path to the file to ingest. If omitted, reads from stdin.")
    
    args = parser.parse_args()
    
    md = get_markitdown()
    if not md:
        print("Error: markitdown not installed. Please run 'pip install markitdown'.")
        sys.exit(1)
        
    try:
        if args.file_path:
            # Direct file ingestion
            result = md.convert(args.file_path)
            sys.stdout.write(result.text_content)
        else:
            # Stream ingestion (requires a temp file because markitdown likes paths/extensions)
            # Defaulting to .html for unknown streams as it's common
            content = sys.stdin.read()
            if not content:
                return
                
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w", encoding="utf-8") as tf:
                tf.write(content)
                temp_path = tf.name
            
            try:
                result = md.convert(temp_path)
                sys.stdout.write(result.text_content)
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
    except Exception as e:
        print(f"Error during ingestion: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
