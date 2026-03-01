"""
Test script to validate the enhanced configurations work properly
"""

import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

def load_enhanced_config(site_id):
    """Load configuration for a specific site."""
    with open('enhanced_configs.json', 'r') as f:
        configs = json.load(f)
    return configs.get(site_id)

def test_slctx_enhanced():
    """Test SLCTX with enhanced configuration."""
    print("Testing SLCTX Enhanced Configuration")
    print("=" * 45)
    
    config = load_enhanced_config('slctx_enhanced')
    if not config:
        print("❌ Configuration not found")
        return
    
    url = config['url']
    skip_patterns = config['skip_patterns']
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Apply the enhanced filtering
        all_links = soup.find_all('a', href=True)
        valid_obituaries = []
        filtered_out = []
        
        for link in all_links:
            href = link.get('href')
            text = link.get_text().strip()
            
            if href and '/obituary/' in href:
                full_url = urljoin(url, href)
                
                # Apply skip patterns
                should_skip = any(pattern in href.lower() for pattern in skip_patterns)
                
                if should_skip:
                    filtered_out.append(f"  ❌ {text[:30]}: {href} (skip pattern)")
                else:
                    valid_obituaries.append(f"  ✅ {text[:30]}: {href}")
        
        print(f"Results:")
        print(f"  Valid obituaries found: {len(valid_obituaries)}")
        print(f"  Filtered out: {len(filtered_out)}")
        
        print(f"\\nSample valid obituaries:")
        for item in valid_obituaries[:5]:
            print(item)
        
        print(f"\\nSample filtered out:")
        for item in filtered_out[:5]:
            print(item)
            
        # Test content validation on one obituary
        if valid_obituaries:
            # Extract URL from first valid obituary
            first_url = valid_obituaries[0].split(': ')[1]
            print(f"\\nTesting content validation on: {first_url}")
            
            try:
                resp = requests.get(first_url, headers=headers, timeout=30)
                content_soup = BeautifulSoup(resp.content, 'html.parser')
                
                # Extract name using selectors
                name_selectors = config['custom_selectors']['name_selector'].split(', ')
                name_found = None
                
                for selector in name_selectors:
                    elements = content_soup.select(selector.strip())
                    if elements:
                        name_found = elements[0].get_text().strip()
                        break
                
                if name_found:
                    print(f"  ✅ Name extracted: {name_found}")
                else:
                    print(f"  ⚠️  No name found with selectors: {name_selectors}")
                
                # Check content length
                content = content_soup.get_text().strip()
                min_length = config['validation_rules']['min_content_length']
                
                if len(content) >= min_length:
                    print(f"  ✅ Content length OK: {len(content)} chars (min: {min_length})")
                else:
                    print(f"  ❌ Content too short: {len(content)} chars (min: {min_length})")
                
                # Check forbidden content
                forbidden = config['validation_rules']['forbidden_content']
                found_forbidden = [item for item in forbidden if item.lower() in content.lower()]
                
                if found_forbidden:
                    print(f"  ❌ Found forbidden content: {found_forbidden}")
                else:
                    print(f"  ✅ No forbidden content found")
                    
            except Exception as e:
                print(f"  ❌ Error testing content: {e}")
        
    except Exception as e:
        print(f"❌ Error testing SLCTX: {e}")

def test_waco_enhanced():
    """Test Waco with enhanced configuration."""
    print("\\n\\nTesting Waco Enhanced Configuration")
    print("=" * 45)
    
    config = load_enhanced_config('wacofhmp_enhanced')
    if not config:
        print("❌ Configuration not found")
        return
    
    url = config['url']
    headers = config.get('custom_headers', {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        print(f"Status: {response.status_code}")
        print(f"Content length: {len(response.text)} characters")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Try to find content using custom selectors
            list_selectors = config['custom_selectors']['obituary_list'].split(', ')
            
            found_containers = []
            for selector in list_selectors:
                elements = soup.select(selector.strip())
                if elements:
                    found_containers.append({
                        'selector': selector.strip(),
                        'count': len(elements),
                        'sample': elements[0].get_text().strip()[:100]
                    })
            
            if found_containers:
                print(f"\\n✅ Found obituary containers:")
                for container in found_containers:
                    print(f"  {container['selector']}: {container['count']} elements")
                    print(f"    Sample: {container['sample'][:50]}...")
            else:
                print(f"\\n⚠️  No containers found with selectors: {list_selectors}")
            
            # Look for obituary links
            link_selectors = config['custom_selectors']['obituary_link'].split(', ')
            obituary_links = []
            
            for selector in link_selectors:
                links = soup.select(selector.strip())
                for link in links:
                    href = link.get('href')
                    text = link.get_text().strip()
                    if href:
                        obituary_links.append({
                            'url': urljoin(url, href),
                            'text': text,
                            'selector': selector.strip()
                        })
            
            if obituary_links:
                print(f"\\n✅ Found obituary links: {len(obituary_links)}")
                for link in obituary_links[:5]:
                    print(f"  {link['text'][:30]}: {link['url']} (via {link['selector']})")
            else:
                print(f"\\n⚠️  No obituary links found with selectors: {link_selectors}")
                
                # Let's try a more general search
                all_links = soup.find_all('a', href=True)
                potential_obits = []
                
                for link in all_links:
                    href = link.get('href', '').lower()
                    text = link.get_text().strip()
                    
                    if any(keyword in href for keyword in ['obituary', 'memorial', 'tribute']):
                        potential_obits.append(f"  {text[:30]}: {link.get('href')}")
                
                if potential_obits:
                    print(f"\\nFound potential obituary links via general search:")
                    for link in potential_obits[:5]:
                        print(link)
                else:
                    print(f"\\n❌ No obituary-related links found at all")
        
        else:
            print(f"❌ HTTP Error: {response.status_code}")
            if response.status_code == 403:
                print("  This suggests IP blocking or rate limiting")
                print("  Try accessing the site manually in a browser")
    
    except Exception as e:
        print(f"❌ Error testing Waco: {e}")

def main():
    """Run tests for both sites."""
    test_slctx_enhanced()
    test_waco_enhanced()
    
    print("\\n\\n" + "="*60)
    print("CONCLUSIONS & NEXT STEPS")
    print("="*60)
    print("1. SLCTX: Enhanced filtering should work well")
    print("2. Waco: May need IP rotation or different access method")
    print("3. Test these configs with the enhanced_generic_scraper.py")
    print("4. Monitor results and adjust as needed")

if __name__ == "__main__":
    main()
