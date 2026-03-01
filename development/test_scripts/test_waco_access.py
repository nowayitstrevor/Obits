"""
Quick test to check Waco Funeral Home Memorial Park access issues
"""

import requests
from urllib.parse import urlparse
import time

def test_waco_access():
    """Test different ways to access Waco Funeral Home site."""
    
    # Different URLs to try
    test_urls = [
        "https://www.wacofhmp.com/obituaries",
        "https://www.wacofhmp.com/",
        "https://wacofhmp.com/obituaries",
        "https://wacofhmp.com/"
    ]
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    for url in test_urls:
        print(f"\nTesting: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"  Status: {response.status_code}")
            print(f"  Content length: {len(response.text)} characters")
            
            if response.status_code == 200:
                print(f"  First 200 chars: {response.text[:200]}")
                
                # Check for redirects
                if response.history:
                    print(f"  Redirected from: {[r.url for r in response.history]}")
                    print(f"  Final URL: {response.url}")
                    
            elif response.status_code in [301, 302, 303, 307, 308]:
                print(f"  Redirect to: {response.headers.get('Location', 'Unknown')}")
                
        except requests.exceptions.Timeout:
            print(f"  ❌ Timeout after 10 seconds")
        except requests.exceptions.ConnectionError:
            print(f"  ❌ Connection error")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        time.sleep(1)  # Be respectful

if __name__ == "__main__":
    test_waco_access()
