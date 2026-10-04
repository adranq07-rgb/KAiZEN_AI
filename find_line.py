with open('accounting/source_registry.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with 'Ozdogrular'
for i, line in enumerate(lines):
    if 'Ozdogrular' in line and 'ozdogrular.com' in line:
        print(f'Line {i}: {repr(lines[i])}')
        # Print next 30 lines
        for j in range(i, min(i+30, len(lines))):
            print(f'Line {j}: {repr(lines[j])}')
        break