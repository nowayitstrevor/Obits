#!/usr/bin/env python3
"""
Quick test to verify our enhanced date extraction selectors work.
"""

import requests
from bs4 import BeautifulSoup

def quick_test():
    """Quick test of the specific selectors we found."""
    
    url = "https://www.robertsonfh.com/obituary/JARRETT-HAWKINS"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Test the selectors we found
            birth_elem = soup.select_one('span.dob')
            death_elem = soup.select_one('span.dod')
            
            birth_date = birth_elem.get_text(strip=True) if birth_elem else "Not found"
            death_date = death_elem.get_text(strip=True) if death_elem else "Not found"
            
            print(f"Robertson Test:")
            print(f"Birth Date: {birth_date}")
            print(f"Death Date: {death_date}")
        else:
            print(f"HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

    # Test Foss
    url2 = "https://www.fossfuneralhome.com/obituary/morris-henderson"
    
    try:
        response = requests.get(url2, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Test the lifespan selector we found
            lifespan_elem = soup.select_one('p.lifespan')
            
            if lifespan_elem:
                lifespan_text = lifespan_elem.get_text(strip=True)
                print(f"\nFoss Test:")
                print(f"Lifespan text: {lifespan_text}")
                
                # Parse the lifespan
                if ' - ' in lifespan_text:
                    parts = lifespan_text.split(' - ')
                    if len(parts) == 2:
                        print(f"Birth Date: {parts[0].strip()}")
                        print(f"Death Date: {parts[1].strip()}")
            else:
                print(f"\nFoss Test: No lifespan element found")
        else:
            print(f"HTTP Error: {response.status_code}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    quick_test()
