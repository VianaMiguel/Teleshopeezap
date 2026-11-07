#!/usr/bin/env python3
import sys

def fix_painel_syntax():
    # Read the file
    with open('ofertas/painel.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the problematic CAMPOS array
    # The issue is with the Facebook PAGE_ID line having extra elements
    # We need to find the line with "FACEBOOK_PAGE_ID" and fix it
    
    lines = content.split('\n')
    fixed_lines = []
    
    for i, line in enumerate(lines):
        if '"FACEBOOK_PAGE_ID"' in line:
            # This is the Facebook PAGE_ID line that needs to be fixed
            # It should be a simple 4-element tuple like:
            #     ("FACEBOOK_PAGE_ID", "ID da Página do Facebook", "Facebook", False),
            
            # Find the end of this line (it might be split across multiple lines)
            j = i
            line_parts = [line]
            while not line_parts[-1].strip().endswith('),') and j + 1 < len(lines):
                j += 1
                line_parts.append(lines[j])
            
            # Replace with correct 4-element tuple
            fixed_lines.append('    ("FACEBOOK_PAGE_ID", "ID da Página do Facebook", "Facebook", False),')
            
            # Skip the rest of the broken line
            for k in range(i + 1, j + 1):
                if k != i:
                    pass  # Skip these lines
            
            i = j  # Skip to the end of the broken line
        else:
            fixed_lines.append(line)
    
    # Write back
    with open('ofertas/painel.py', 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    
    print("Fixed painel.py syntax")

if __name__ == '__main__':
    fix_painel_syntax()