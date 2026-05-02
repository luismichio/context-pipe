# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import re
import argparse

# Common Secret Patterns
SECRET_PATTERNS = {
    "GitHub PAT": r"ghp_[a-zA-Z0-9]{36}",
    "AWS Key": r"AKIA[0-9A-Z]{16}",
    "Generic Secret": r"(?i)(password|passwd|secret|api_key|token|auth|key)[\s:=]+['\"]?([a-zA-Z0-9_\-\.]{12,})['\"]?",
    "Email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
}

def mask_text(text: str) -> str:
    """Detects and masks secrets in the provided text."""
    masked = text
    
    # 1. Specific High-Fidelity Patterns
    for label, pattern in SECRET_PATTERNS.items():
        if label == "Generic Secret":
            # For key-value pairs, we only mask the value part (group 2)
            masked = re.sub(pattern, r"\1: [REDACTED]", masked)
        else:
            masked = re.sub(pattern, f"[{label.upper()} REDACTED]", masked)
            
    return masked

def main():
    parser = argparse.ArgumentParser(description="Context-Pipe Privacy Guard")
    parser.add_argument("--label", action="store_true", help="Include redaction labels")
    
    # Read from stdin
    input_data = sys.stdin.read()
    if not input_data:
        return
        
    # Masking
    result = mask_text(input_data)
    
    # Output
    sys.stdout.write(result)

if __name__ == "__main__":
    main()
