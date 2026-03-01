#!/usr/bin/env python3
"""
Test script to validate enhanced date extraction for specific funeral homes.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from typing import Dict, Any

def extract_text_safely(soup, selector: str, attribute: str = None) -> str:
    """Safely extract text from soup using CSS selector."""
    try:
        element = soup.select_one(selector)
        if element:
            if attribute:
                return element.get(attribute, '').strip()
            return element.get_text(strip=True)
    except Exception:
        pass
    return ''

def parse_combined_dates(date_text: str) -> tuple:
    """Parse combined birth/death date text."""
    birth_date = ''
    death_date = ''
    
    # Handle formats like "Born: Jan 1, 1950 - Died: Dec 31, 2020"
    if 'born' in date_text.lower() and ('died' in date_text.lower() or 'passed' in date_text.lower()):
        birth_match = re.search(r'born[:\s]*([^-–—]+)', date_text, re.IGNORECASE)
        death_match = re.search(r'(?:died|passed)[:\s]*([^,\n]+)', date_text, re.IGNORECASE)
        
        if birth_match:
            birth_date = birth_match.group(1).strip()
        if death_match:
            death_date = death_match.group(1).strip()
    
    # Handle formats like "Jan 1, 1950 - Dec 31, 2020"
    elif ' - ' in date_text or ' – ' in date_text or ' — ' in date_text:
        parts = re.split(r'\s*[-–—]\s*', date_text, 1)
        if len(parts) == 2:
            birth_date = parts[0].strip()
            death_date = parts[1].strip()
    
    return birth_date, death_date

def extract_dates_enhanced(soup, config: Dict[str, Any]) -> tuple:
    """Enhanced date extraction using custom selectors and patterns."""
    custom_selectors = config.get('custom_selectors', {})
    date_patterns = config.get('date_patterns', [])
    
    birth_date = ''
    death_date = ''
    
    # Try specific birth/death date selectors first
    birth_selectors = custom_selectors.get('birth_date', ['.birth-date', '.born', '.date-birth', 'span.dob'])
    death_selectors = custom_selectors.get('death_date', ['.death-date', '.died', '.date-death', '.passed', 'span.dod'])
    
    # Extract birth date
    if isinstance(birth_selectors, str):
        birth_selectors = [birth_selectors]
    for selector in birth_selectors:
        birth_date = extract_text_safely(soup, selector)
        if birth_date:
            break
    
    # Extract death date
    if isinstance(death_selectors, str):
        death_selectors = [death_selectors]
    for selector in death_selectors:
        death_date = extract_text_safely(soup, selector)
        if death_date:
            break
    
    # Try date container selectors
    if not birth_date or not death_date:
        date_container_selectors = custom_selectors.get('date_container', ['.dates', '.life-dates', '.obit-dates', 'p.lifespan'])
        if isinstance(date_container_selectors, str):
            date_container_selectors = [date_container_selectors]
            
        for selector in date_container_selectors:
            date_text = extract_text_safely(soup, selector)
            if date_text:
                extracted_birth, extracted_death = parse_combined_dates(date_text)
                if extracted_birth and not birth_date:
                    birth_date = extracted_birth
                if extracted_death and not death_date:
                    death_date = extracted_death
                if birth_date and death_date:
                    break
    
    # Use regex patterns from config if available
    if date_patterns and (not birth_date or not death_date):
        full_text = soup.get_text()
        for pattern in date_patterns:
            try:
                matches = re.findall(pattern, full_text, re.IGNORECASE)
                if matches:
                    for match in matches:
                        if isinstance(match, tuple):
                            match = ' '.join(match)
                        
                        # Default to death date if unclear
                        if not death_date:
                            death_date = match.strip()
                            break
            except re.error:
                continue
    
    return birth_date.strip(), death_date.strip()

def test_date_extraction():
    """Test date extraction on problematic URLs."""
    
    # Load config
    with open('funeral_homes_config.json', 'r') as f:
        config_data = json.load(f)
    
    # Test URLs that were flagged for missing dates
    test_urls = [
        ("Robertson Funeral Home", "https://www.robertsonfh.com/obituary/JARRETT-HAWKINS", "robertson"),
        ("Foss Funeral Home", "https://www.fossfuneralhome.com/obituary/morris-henderson", "foss"),
        ("McDowell Funeral Home", "https://www.mcdowellfuneralhome.com/obituary/Larry-Turner", "mcdowell")
    ]
    
    for funeral_home, url, config_key in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {funeral_home}")
        print(f"URL: {url}")
        print(f"{'='*60}")
        
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                config = config_data['funeral_homes'].get(config_key, {})
                
                # Test enhanced date extraction
                birth_date, death_date = extract_dates_enhanced(soup, config)
                
                print(f"Birth Date: '{birth_date}'")
                print(f"Death Date: '{death_date}'")
                
                # Also show some raw text to help debug
                name = extract_text_safely(soup, 'h1') or 'Name not found'
                print(f"Name: {name}")
                
                # Show date containers found
                date_containers = config.get('custom_selectors', {}).get('date_container', [])
                if date_containers:
                    print(f"Date containers checked:")
                    for selector in date_containers:
                        text = extract_text_safely(soup, selector)
                        if text:
                            print(f"  {selector}: '{text[:100]}...'")
                
            else:
                print(f"HTTP Error: {response.status_code}")
                
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    test_date_extraction()
