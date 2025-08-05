#!/usr/bin/env python3
"""
Script to update YouTube cookie expiration dates to 100 years from now
"""
import json
import time
from datetime import datetime, timedelta

def update_cookie_expiry():
    # Read the current cookies file
    with open('youtube_cookies.txt', 'r') as f:
        content = f.read().strip()
    
    # Parse the JSON (skip the first character '1|' if present)
    if content.startswith('1|'):
        content = content[2:]
    
    cookies = json.loads(content)
    
    # Calculate expiration date 100 years from now
    future_date = datetime.now() + timedelta(days=100*365)
    future_timestamp = future_date.timestamp()
    
    print(f"Current time: {datetime.now()}")
    print(f"New expiration date: {future_date}")
    print(f"New expiration timestamp: {future_timestamp}")
    
    # Update each cookie's expiration date
    for cookie in cookies:
        old_expiry = cookie.get('expirationDate', 0)
        cookie['expirationDate'] = future_timestamp
        
        # Convert timestamps to readable dates for comparison
        old_date = datetime.fromtimestamp(old_expiry) if old_expiry else "No expiry"
        new_date = datetime.fromtimestamp(future_timestamp)
        
        print(f"Cookie {cookie['name']}: {old_date} -> {new_date}")
    
    # Write back to file with the same format
    updated_content = f"1|{json.dumps(cookies)}"
    
    with open('youtube_cookies.txt', 'w') as f:
        f.write(updated_content)
    
    print(f"\n✅ Successfully updated {len(cookies)} cookies with new expiration dates!")
    
    # Verify the cookies are suitable for YouTube downloads
    print("\n🔍 Cookie Analysis:")
    essential_cookies = ['SID', '__Secure-1PSID', '__Secure-3PSID', 'LOGIN_INFO']
    found_essential = []
    
    for cookie in cookies:
        if cookie['name'] in essential_cookies:
            found_essential.append(cookie['name'])
            print(f"✅ Found essential cookie: {cookie['name']}")
    
    missing_essential = set(essential_cookies) - set(found_essential)
    if missing_essential:
        print(f"⚠️  Missing essential cookies: {missing_essential}")
    
    # Check for LOGIN_INFO specifically (indicates user is logged in)
    login_info = next((c for c in cookies if c['name'] == 'LOGIN_INFO'), None)
    if login_info:
        print("✅ LOGIN_INFO cookie found - user appears to be logged in")
    else:
        print("❌ LOGIN_INFO cookie missing - user may not be logged in")
    
    # Check domain coverage
    domains = set(cookie['domain'] for cookie in cookies)
    print(f"📍 Cookie domains: {domains}")
    
    if '.youtube.com' in domains:
        print("✅ YouTube domain cookies present")
    if '.google.com' in domains:
        print("✅ Google domain cookies present")
    
    print(f"\n🎯 Recommendation: {'These cookies should work well for YouTube downloads!' if login_info and len(found_essential) >= 3 else 'These cookies may have limited functionality - consider refreshing from a logged-in browser session.'}")

if __name__ == "__main__":
    update_cookie_expiry()
