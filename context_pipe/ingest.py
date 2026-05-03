# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import os

def main():
    """
    A simple wrapper for MarkItDown.
    Reads from stdin (filename or raw content) and emits Markdown.
    """
    input_data = sys.stdin.read().strip()
    if not input_data:
        return

    # If the input is a valid file path, try to convert it
    if os.path.exists(input_data):
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(input_data)
            sys.stdout.write(result.text_content)
        except ImportError:
            sys.stderr.write("[Context-Pipe] MarkItDown not installed. Run 'pip install context-pipe[multi-modal]'.\n")
            # Fallback: just emit the path so the next node can handle it
            sys.stdout.write(input_data)
        except Exception as e:
            sys.stderr.write(f"[Context-Pipe] Ingestion failed: {str(e)}\n")
            sys.stdout.write(input_data)
    else:
        # If it's not a path, it's already raw content
        sys.stdout.write(input_data)

if __name__ == "__main__":
    main()
