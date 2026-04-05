#!/usr/bin/env python3
"""
Fix YAML syntax errors in OpenAPI spec - quote values with colons.
"""
import re
import sys

def fix_yaml_colons(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed = []
    changes = 0
    
    for i, line in enumerate(lines, 1):
        # Skip lines that are already quoted
        if re.search(r'^\s*\w+:\s*[\'"].*[\'"]', line):
            fixed.append(line)
            continue
        
        # Skip URL lines
        if 'http://' in line or 'https://' in line:
            fixed.append(line)
            continue
        
        # Skip MAC address examples
        if re.search(r'example:\s*[0-9a-fA-F]{2}(:[0-9a-fA-F]{2})+', line):
            fixed.append(line)
            continue
        
        # Find lines with colons in values (not key: value pairs)
        # Pattern: indentation + key: value: extra
        match = re.match(r'^(\s*)(\w+):\s*(.+?):\s*(.+)$', line)
        if match:
            indent, key, value, extra = match.groups()
            # Quote the value if it contains a colon
            if not value.startswith("'") and not value.startswith('"'):
                new_line = f'{indent}{key}: \'{value}: {extra}\'\n'
                fixed.append(new_line)
                changes += 1
                print(f"Fixed line {i}: {key}")
                continue
        
        fixed.append(line)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(fixed)
    
    return changes

if __name__ == '__main__':
    filepath = sys.argv[1] if len(sys.argv) > 1 else 'docs/openapi.yaml'
    changes = fix_yaml_colons(filepath)
    print(f"\nTotal fixes: {changes}")
