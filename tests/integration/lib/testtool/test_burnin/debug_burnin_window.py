"""
Debug tool to monitor BurnIN window title changes

This script helps diagnose window title issues by:
1. Listing all open windows
2. Monitoring BurnIN window title changes over time
3. Testing different title matching strategies
"""

import time
from pywinauto import Desktop

def list_all_windows():
    """List all open windows with their titles"""
    print("\n" + "="*70)
    print("ALL OPEN WINDOWS")
    print("="*70)
    
    desktop = Desktop(backend="uia")
    windows = desktop.windows()
    
    for i, window in enumerate(windows, 1):
        try:
            title = window.window_text()
            if title:  # Only show windows with titles
                print(f"[{i}] {title}")
        except Exception as e:
            print(f"[{i}] <Error reading window: {e}>")
    
    print("="*70)

def monitor_burnin_window(duration_seconds=60, interval=2):
    """
    Monitor BurnIN window title changes
    
    Args:
        duration_seconds: How long to monitor (seconds)
        interval: Check interval (seconds)
    """
    print(f"\nMonitoring BurnIN window for {duration_seconds} seconds...")
    print(f"Check interval: {interval} seconds")
    print("-"*70)
    
    start_time = time.time()
    last_title = None
    
    while time.time() - start_time < duration_seconds:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        
        burnin_windows = []
        for window in windows:
            try:
                title = window.window_text()
                if 'burnin' in title.lower():
                    burnin_windows.append(title)
            except Exception:
                continue
        
        if burnin_windows:
            current_title = burnin_windows[0]
            if current_title != last_title:
                elapsed = time.time() - start_time
                print(f"[{elapsed:6.1f}s] Title changed: {current_title}")
                last_title = current_title
        else:
            if last_title is not None:
                elapsed = time.time() - start_time
                print(f"[{elapsed:6.1f}s] BurnIN window not found!")
                last_title = None
        
        time.sleep(interval)
    
    print("-"*70)
    print("Monitoring complete")

def test_title_matching():
    """Test different title matching strategies"""
    print("\n" + "="*70)
    print("TESTING TITLE MATCHING STRATEGIES")
    print("="*70)
    
    patterns = [
        "BurnInTest",
        "PassMark BurnInTest",
        "BurnIn",
        "PassMark",
    ]
    
    desktop = Desktop(backend="uia")
    windows = desktop.windows()
    
    all_titles = []
    for window in windows:
        try:
            title = window.window_text()
            if title:
                all_titles.append(title)
        except Exception:
            continue
    
    for pattern in patterns:
        print(f"\nPattern: '{pattern}'")
        matches = [t for t in all_titles if pattern.lower() in t.lower()]
        if matches:
            print(f"  ✓ Found {len(matches)} match(es):")
            for match in matches:
                print(f"    - {match}")
        else:
            print(f"  ✗ No matches")
    
    print("="*70)

if __name__ == "__main__":
    import sys
    
    print("BurnIN Window Debug Tool")
    print("="*70)
    
    # Check if BurnIN is running
    list_all_windows()
    test_title_matching()
    
    # Ask user if they want to monitor
    if len(sys.argv) > 1 and sys.argv[1] == "--monitor":
        duration = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        monitor_burnin_window(duration_seconds=duration)
    else:
        print("\nTo monitor window title changes, run:")
        print("  python debug_burnin_window.py --monitor [duration_seconds]")
