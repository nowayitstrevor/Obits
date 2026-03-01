#!/usr/bin/env python3
"""
Quick test of Lake Shore with the existing Selenium scraper.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

try:
    # Test the existing Lake Shore scraper
    from scrape_real_obituaries import scrape_obituaries_with_details
    
    print("🚀 Testing Lake Shore Selenium scraper...")
    
    # Run the scraper
    obituaries = scrape_obituaries_with_details()
    
    if obituaries:
        print(f"✅ SUCCESS: Found {len(obituaries)} obituaries from Lake Shore!")
        for i, obit in enumerate(obituaries[:3]):  # Show first 3
            print(f"  {i+1}. {obit.get('name', 'Unknown')} - {obit.get('url', 'No URL')}")
    else:
        print("❌ No obituaries found from Lake Shore")
        
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("💡 The scrape_real_obituaries.py file might not have the expected function")
    
except Exception as e:
    print(f"❌ Error testing Lake Shore: {e}")
