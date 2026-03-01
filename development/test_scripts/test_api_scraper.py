"""
Simple test script to check scraper functionality and trigger via web API.
"""

import requests
import json
import time

def test_scraper_via_api():
    """Test the scraper via the web API."""
    
    base_url = "http://localhost:5000"
    
    print("🔄 Testing scraper via web API...")
    
    try:
        # Test if the web server is running
        response = requests.get(f"{base_url}/api/obituaries", timeout=10)
        print(f"✅ Web server is responding: {response.status_code}")
        
        # Trigger the detailed scraper
        print("🚀 Triggering detailed scraper...")
        scrape_response = requests.get(f"{base_url}/api/scrape/lakeshore", timeout=300)
        
        if scrape_response.status_code == 200:
            data = scrape_response.json()
            print("📄 Scraper response:")
            print(json.dumps(data, indent=2))
            
            if data.get('success'):
                print("✅ Scraping completed successfully!")
                
                # Get updated obituaries
                time.sleep(2)
                obituaries_response = requests.get(f"{base_url}/api/obituaries")
                if obituaries_response.status_code == 200:
                    obituaries_data = obituaries_response.json()
                    print(f"📊 Found {obituaries_data.get('total', 0)} obituaries")
                    
                    for i, obit in enumerate(obituaries_data.get('obituaries', [])[:3], 1):
                        print(f"  {i}. {obit.get('name', 'Unknown')} - {obit.get('death_date', 'Date unknown')}")
                        if obit.get('photo_url'):
                            print(f"     📸 Photo: {obit['photo_url']}")
                        
            else:
                print(f"❌ Scraping failed: {data.get('error', 'Unknown error')}")
        else:
            print(f"❌ Scraper request failed: {scrape_response.status_code}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to web server. Make sure Flask app is running on localhost:5000")
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_scraper_via_api()
