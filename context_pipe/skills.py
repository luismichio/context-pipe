# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Luis Kobayashi. All rights reserved.

import sys
import os
import argparse

def main():
    parser = argparse.ArgumentParser(description="Context-Pipe Skill Node Wrapper")
    parser.add_argument("skill_name", help="Name of the skill to apply")
    parser.add_argument("--mandate-dir", default=None, help="Directory to look for skill mandates")
    
    args = parser.parse_args()
    
    # 1. Load Input Data
    input_data = sys.stdin.read()
    if not input_data:
        return

    # 2. Resolve Mandate Path
    # We look for skill-name.md or skill-name.toml
    mandate_dir = args.mandate_dir or os.environ.get("PIPE_SKILL_DIR", ".gemini/skills")
    mandate_path = os.path.join(mandate_dir, f"{args.skill_name}.md")
    
    if not os.path.exists(mandate_path):
        # Fallback to current working directory if not found in default
        mandate_path = os.path.join(os.getcwd(), f"{args.skill_name}.md")

    # 3. Apply Skill Lens
    if os.path.exists(mandate_path):
        with open(mandate_path, "r", encoding="utf-8") as f:
            mandate_text = f.read()
        
        # PRE-PROCESSING LENS
        # For now, we prepend the mandate to the content.
        # In a real "Studio of Two" implementation, this would trigger a local SLM
        # to re-write the context based on the skill's instructions.
        output = f"--- [Skill Lens: {args.skill_name}] ---\n{mandate_text}\n\n[Content]\n{input_data}"
        sys.stdout.write(output)
    else:
        # If mandate not found, just act as a pass-through with a warning
        sys.stderr.write(f"[Context-Pipe] Warning: Skill mandate '{args.skill_name}' not found at {mandate_path}.\n")
        sys.stdout.write(input_data)

if __name__ == "__main__":
    main()
