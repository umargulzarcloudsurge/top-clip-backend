#!/usr/bin/env python3
"""
Quick fix for duplicate prefix in cookies file
"""

# Read the file
with open('youtube_cookies.txt', 'r') as f:
    content = f.read()

# Fix the duplicate prefix
if content.startswith('1|1|'):
    content = content[2:]  # Remove the first '1|'
    print("Fixed duplicate prefix")

# Write back
with open('youtube_cookies.txt', 'w') as f:
    f.write(content)

print("Cookies file fixed!")
