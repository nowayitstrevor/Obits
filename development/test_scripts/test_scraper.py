#!/usr/bin/env python3
"""
Simple test script to verify the scraper is working
"""

import os
import sys

print("=== SCRAPER TEST ===")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# Test imports
try:
    import selenium
    print("✓ Selenium import successful")
except ImportError as e:
    print(f"✗ Selenium import failed: {e}")

try:
    from selenium import webdriver
    print("✓ Selenium webdriver import successful")
except ImportError as e:
    print(f"✗ Selenium webdriver import failed: {e}")

try:
    from selenium.webdriver.firefox.service import Service
    print("✓ Firefox service import successful")
except ImportError as e:
    print(f"✗ Firefox service import failed: {e}")

try:
    from webdriver_manager.firefox import GeckoDriverManager
    print("✓ GeckoDriverManager import successful")
except ImportError as e:
    print(f"✗ GeckoDriverManager import failed: {e}")

# Test the actual scraper import
try:
    print("\nTesting scraper import...")
    sys.path.append(os.getcwd())
    
    # Test minimal Firefox setup
    from selenium.webdriver.firefox.options import Options
    
    options = Options()
    options.add_argument('--headless')
    
    print("✓ Firefox options configured")
    print("✓ All imports successful!")
    
    # Try to test the actual function
    print("\nTrying to import the actual scraper...")
    import scrape_real_obituaries
    print("✓ Scraper module imported successfully!")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETE ===")
