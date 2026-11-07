#!/usr/bin/env python3
import re

def fix_painel_syntax():
    # Read the file
    with open('ofertas/painel.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the CAMPOS array
    # We need to locate the exact boundaries of the CAMPOS array
    lines = content.split('\n')
    
    # Find the start and end of CAMPOS array
    start_line = -1
    end_line = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('CAMPOS = ['):
            start_line = i
        elif start_line != -1 and line.strip() == ']' and end_line == -1:
            end_line = i
            break
    
    if start_line == -1 or end_line == -1:
        print("Could not find CAMPOS array boundaries")
        return
    
    print(f"Found CAMPOS array from line {start_line+1} to {end_line+1}")
    
    # Check for syntax errors in the CAMPOS array
    # The issue is that the Facebook PAGE_ID line has extra elements
    # that make the entire CAMPOS array syntactically invalid
    
    # Let's extract the CAMPOS array content
    campos_lines = lines[start_line:end_line+1]
    campos_text = '\n'.join(campos_lines)
    
    # Check if the CAMPOS array has balanced parentheses
    open_parens = campos_text.count('(')
    close_parens = campos_text.count(')')
    
    if open_parens != close_parens:
        print(f"Unbalanced parentheses in CAMPOS array: {open_parens} open, {close_parens} close")
        
        # The issue is with the Facebook PAGE_ID line having extra elements
        # Let's fix it by reconstructing the Facebook PAGE_ID line
        
        # Find the Facebook PAGE_ID line (it should be the line starting with "FACEBOOK_PAGE_ID")
        for i, line in enumerate(campos_lines):
            if 'FACEBOOK_PAGE_ID' in line:
                print(f"Found Facebook PAGE_ID line at index {i}: {line.strip()}")
                
                # Check if this line has the correct number of elements
                # It should be: ("FACEBOOK_PAGE_ID", "ID da Página do Facebook", "Facebook", False),
                
                # Count the number of commas in the line (each comma separates an element)
                comma_count = line.count(',')
                print(f"Comma count in Facebook PAGE_ID line: {comma_count}")
                
                if comma_count > 3:  # More than 3 commas means it has more than 4 elements
                    print("Facebook PAGE_ID line has too many elements, fixing...")
                    
                    # Fix the Facebook PAGE_ID line
                    # Remove the extra elements (the help text and link)
                    fixed_line = '    ("FACEBOOK_PAGE_ID", "ID da Página do Facebook", "Facebook", False),'
                    campos_lines[i] = fixed_line
                    print(f"Fixed line: {fixed_line}")
                
                break
    
    # Replace the CAMPOS array in the original content
    new_content = '\n'.join(lines[:start_line] + campos_lines + lines[end_line+1:])
    
    # Write back
    with open('ofertas/painel.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("Fixed painel.py CAMPOS array syntax")

if __name__ == '__main__':
    fix_painel_syntax()