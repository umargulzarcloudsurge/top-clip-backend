#!/usr/bin/env python3
"""
YouTube Cookie Management CLI Tool
Provides easy management of YouTube cookies for the video processing system
"""

import os
import sys
import argparse
import asyncio
from datetime import datetime
from pathlib import Path

# Add the parent directory to sys.path so we can import our utils
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from utils.cookie_refresh_service import cookie_refresh_service
from utils.youtube_proxy_service import proxy_service

def format_status_emoji(status: str) -> str:
    """Return appropriate emoji for status"""
    return {
        'valid': '✅',
        'invalid': '❌', 
        'expires_soon': '⚠️',
        'refreshed': '🔄',
        'disabled': '⏸️',
        'enabled': '▶️'
    }.get(status.lower(), '❓')

async def validate_cookies(args):
    """Validate current cookies"""
    print("🔍 Validating YouTube cookies...\n")
    
    # Find cookie file
    cookie_file = None
    for path in cookie_refresh_service.cookie_paths:
        if os.path.exists(path):
            cookie_file = path
            break
    
    if not cookie_file:
        print("❌ No cookie file found!")
        print("   Checked paths:")
        for path in cookie_refresh_service.cookie_paths:
            print(f"   - {path}")
        return
    
    print(f"📁 Cookie file: {cookie_file}")
    
    # Validate cookies
    validation = await cookie_refresh_service.validate_cookie_freshness(cookie_file)
    
    # Display results
    print("\n📊 Validation Results:")
    print(f"   Status: {format_status_emoji('valid' if validation['valid'] else 'invalid')} {'Valid' if validation['valid'] else 'Invalid'}")
    print(f"   Cookies found: {validation['cookies_found']}")
    print(f"   YouTube accessible: {'✅ Yes' if validation['youtube_accessible'] else '❌ No'}")
    print(f"   Expires soon: {'⚠️ Yes' if validation['expires_soon'] else '✅ No'}")
    
    if validation['oldest_expiry']:
        print(f"   Oldest expiry: {validation['oldest_expiry']}")
    
    if validation['error']:
        print(f"   Error: {validation['error']}")

async def extend_cookies(args):
    """Extend cookie expiration dates"""
    cookie_file = args.file
    years = args.years
    
    if not cookie_file:
        # Auto-find cookie file
        for path in cookie_refresh_service.cookie_paths:
            if os.path.exists(path):
                cookie_file = path
                break
    
    if not cookie_file:
        print("❌ No cookie file found or specified!")
        return
    
    print(f"🔄 Extending cookies in: {cookie_file}")
    print(f"📅 Extending expiration by: {years} years")
    
    # Create backup first
    backup_file = f"{cookie_file}.backup.{int(datetime.now().timestamp())}"
    import shutil
    shutil.copy2(cookie_file, backup_file)
    print(f"📋 Created backup: {backup_file}")
    
    # Extend cookies
    success = cookie_refresh_service.extend_cookie_expiration(cookie_file, years)
    
    if success:
        print("✅ Cookie expiration extended successfully!")
        
        # Re-validate
        validation = await cookie_refresh_service.validate_cookie_freshness(cookie_file)
        if validation['valid']:
            print("✅ Validation passed - cookies are working!")
        else:
            print("⚠️ Extended expiration but validation failed - may need fresh cookies")
            
    else:
        print("❌ Failed to extend cookie expiration")

async def auto_refresh(args):
    """Run automatic cookie refresh"""
    print("🔄 Running automatic cookie refresh...\n")
    
    result = await cookie_refresh_service.auto_validate_and_refresh()
    
    status = result.get('status', 'unknown')
    print(f"Status: {format_status_emoji(status)} {status.title()}")
    
    if 'cookie_file' in result:
        print(f"Cookie file: {result['cookie_file']}")
    
    if 'validation' in result:
        validation = result['validation']
        print(f"Cookies valid: {'✅ Yes' if validation['valid'] else '❌ No'}")
        print(f"Cookies found: {validation['cookies_found']}")
    
    if 'actions_taken' in result:
        if result['actions_taken']:
            print("\nActions taken:")
            for action in result['actions_taken']:
                print(f"   - {action}")
        else:
            print("\nNo actions needed")

def status(args):
    """Show service status"""
    print("📊 Cookie Refresh Service Status:\n")
    
    status_info = cookie_refresh_service.get_status()
    
    # Auto refresh status
    auto_status = 'enabled' if status_info['auto_refresh_enabled'] else 'disabled'
    print(f"Auto refresh: {format_status_emoji(auto_status)} {auto_status.title()}")
    
    # Last validation
    last_validation = status_info['last_validation']
    if last_validation:
        print(f"Last validation: {last_validation}")
    else:
        print("Last validation: Never")
    
    # Validation interval
    interval_hours = status_info['validation_interval_hours']
    print(f"Validation interval: {interval_hours} hours")
    
    # Cookie paths
    print(f"\nCookie file search paths:")
    for path in status_info['cookie_paths_checked']:
        exists = "✅" if os.path.exists(path) else "❌"
        print(f"   {exists} {path}")

def enable_auto_refresh(args):
    """Enable automatic cookie refresh"""
    cookie_refresh_service.enable_auto_refresh()
    print("✅ Automatic cookie refresh enabled")

def disable_auto_refresh(args):
    """Disable automatic cookie refresh"""
    cookie_refresh_service.disable_auto_refresh()
    print("⚠️ Automatic cookie refresh disabled")

async def test_proxies(args):
    """Test proxy service"""
    print("🌐 Testing proxy service...\n")
    
    try:
        # Get proxy for yt-dlp
        proxy_url = proxy_service.get_proxy_for_ytdlp()
        if proxy_url:
            print(f"✅ Got proxy: {proxy_url.split('@')[-1] if '@' in proxy_url else proxy_url}")
        else:
            print("❌ No working proxies available")
        
        # Show proxy stats
        stats = proxy_service.get_stats()
        print(f"\nProxy statistics:")
        print(f"   Total proxies: {stats['total_proxies']}")
        print(f"   Working proxies: {stats['working_proxies']}")
        print(f"   Banned proxies: {stats['banned_proxies']}")
        
    except Exception as e:
        print(f"❌ Proxy service error: {e}")

def create_long_lasting(args):
    """Create long-lasting cookie file"""
    source = args.source
    output = args.output
    years = args.years
    
    if not source or not os.path.exists(source):
        print(f"❌ Source file not found: {source}")
        return
    
    print(f"📋 Creating long-lasting cookies...")
    print(f"   Source: {source}")
    print(f"   Years: {years}")
    
    result_file = cookie_refresh_service.create_long_lasting_cookies(source, output, years)
    
    if result_file != source:
        print(f"✅ Created: {result_file}")
    else:
        print("❌ Failed to create long-lasting cookies")

def main():
    parser = argparse.ArgumentParser(
        description='YouTube Cookie Management Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cookie_manager.py validate                    # Validate current cookies
  python cookie_manager.py extend --years 50          # Extend cookies by 50 years
  python cookie_manager.py auto-refresh               # Run auto refresh
  python cookie_manager.py status                     # Show service status
  python cookie_manager.py test-proxies               # Test proxy service
  
  python cookie_manager.py create-long --source youtube_cookies.txt --years 100
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate current cookies')
    
    # Extend command
    extend_parser = subparsers.add_parser('extend', help='Extend cookie expiration')
    extend_parser.add_argument('--file', help='Cookie file path (auto-detected if not specified)')
    extend_parser.add_argument('--years', type=int, default=100, help='Years to extend (default: 100)')
    
    # Auto refresh command
    auto_parser = subparsers.add_parser('auto-refresh', help='Run automatic cookie refresh')
    
    # Status command
    status_parser = subparsers.add_parser('status', help='Show service status')
    
    # Enable/disable auto refresh
    enable_parser = subparsers.add_parser('enable-auto', help='Enable automatic refresh')
    disable_parser = subparsers.add_parser('disable-auto', help='Disable automatic refresh')
    
    # Test proxies
    proxy_parser = subparsers.add_parser('test-proxies', help='Test proxy service')
    
    # Create long-lasting
    create_parser = subparsers.add_parser('create-long', help='Create long-lasting cookie file')
    create_parser.add_argument('--source', required=True, help='Source cookie file')
    create_parser.add_argument('--output', help='Output file (auto-generated if not specified)')
    create_parser.add_argument('--years', type=int, default=100, help='Years to extend (default: 100)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Map commands to functions
    async_commands = {
        'validate': validate_cookies,
        'extend': extend_cookies,
        'auto-refresh': auto_refresh,
        'test-proxies': test_proxies
    }
    
    sync_commands = {
        'status': status,
        'enable-auto': enable_auto_refresh,
        'disable-auto': disable_auto_refresh,
        'create-long': create_long_lasting
    }
    
    if args.command in async_commands:
        asyncio.run(async_commands[args.command](args))
    elif args.command in sync_commands:
        sync_commands[args.command](args)
    else:
        print(f"Unknown command: {args.command}")

if __name__ == '__main__':
    main()
