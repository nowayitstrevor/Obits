"""
Website Structure Analyzer for Obituary Scraping

This tool analyzes funeral home websites to understand their structure
and provide recommendations for scraping configuration.
"""

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.firefox.options import Options
from webdriver_manager.firefox import GeckoDriverManager
import json
import re
from urllib.parse import urljoin, urlparse
from typing import Dict, List, Any
import time

class WebsiteAnalyzer:
    def __init__(self, url: str):
        self.base_url = url
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def analyze_website(self) -> Dict[str, Any]:
        """Comprehensive website analysis."""
        print(f"Analyzing website: {self.base_url}")
        
        analysis = {
            'url': self.base_url,
            'status': 'unknown',
            'requires_javascript': False,
            'platform_type': 'custom',
            'obituary_section': None,
            'page_structure': {},
            'suggested_config': {},
            'issues_found': [],
            'recommendations': []
        }
        
        try:
            # Step 1: Basic HTTP request analysis
            print("  1. Testing basic HTTP access...")
            response = self.session.get(self.base_url, timeout=30)
            
            if response.status_code != 200:
                analysis['status'] = 'error'
                analysis['issues_found'].append(f"HTTP {response.status_code} error")
                return analysis
            
            html_content = response.text
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Step 2: Detect if JavaScript is required
            print("  2. Checking JavaScript requirements...")
            js_required = self.detect_javascript_requirement(soup, html_content)
            analysis['requires_javascript'] = js_required
            
            if js_required:
                print("     JavaScript required, using Selenium...")
                html_content = self.get_javascript_content()
                soup = BeautifulSoup(html_content, 'html.parser')
            
            # Step 3: Detect platform type
            print("  3. Detecting platform type...")
            platform = self.detect_platform_type(soup, html_content)
            analysis['platform_type'] = platform
            
            # Step 4: Find obituary section
            print("  4. Locating obituary section...")
            obituary_info = self.find_obituary_section(soup)
            analysis['obituary_section'] = obituary_info
            
            # Step 5: Analyze page structure
            print("  5. Analyzing page structure...")
            structure = self.analyze_page_structure(soup)
            analysis['page_structure'] = structure
            
            # Step 6: Generate suggested configuration
            print("  6. Generating configuration recommendations...")
            config = self.generate_suggested_config(analysis)
            analysis['suggested_config'] = config
            
            # Step 7: Generate recommendations
            recommendations = self.generate_recommendations(analysis)
            analysis['recommendations'] = recommendations
            
            analysis['status'] = 'success'
            
        except Exception as e:
            analysis['status'] = 'error'
            analysis['issues_found'].append(f"Analysis error: {str(e)}")
        
        return analysis
    
    def detect_javascript_requirement(self, soup: BeautifulSoup, html_content: str) -> bool:
        """Detect if the site requires JavaScript for content."""
        # Check for minimal content
        text_content = soup.get_text().strip()
        if len(text_content) < 500:
            return True
        
        # Check for loading indicators
        loading_indicators = ['loading', 'please wait', 'javascript required']
        text_lower = text_content.lower()
        if any(indicator in text_lower for indicator in loading_indicators):
            return True
        
        # Check for React/Vue/Angular indicators
        js_frameworks = ['react', 'vue', 'angular', 'ng-app', 'data-react']
        if any(framework in html_content.lower() for framework in js_frameworks):
            return True
        
        # Check for obituary indicators in static content
        obituary_indicators = ['obituary', 'obituaries', 'memorial', 'tribute']
        if not any(indicator in text_lower for indicator in obituary_indicators):
            return True
        
        return False
    
    def get_javascript_content(self) -> str:
        """Get page content using Selenium for JavaScript sites."""
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        try:
            service = Service(GeckoDriverManager().install())
            driver = webdriver.Firefox(service=service, options=options)
            driver.get(self.base_url)
            time.sleep(5)  # Wait for content to load
            content = driver.page_source
            driver.quit()
            return content
        except Exception as e:
            print(f"     Selenium failed: {e}")
            return ""
    
    def detect_platform_type(self, soup: BeautifulSoup, html_content: str) -> str:
        """Detect the platform/CMS used by the website."""
        html_lower = html_content.lower()
        
        # Check for third-party obituary platforms
        if 'tribute.com' in html_lower or 'tributearchive' in html_lower:
            return 'tribute'
        elif 'frontrunnerpro' in html_lower or 'frontrunner' in html_lower:
            return 'frontrunner'
        elif 'batesville.com' in html_lower or 'batesville' in html_lower:
            return 'batesville'
        elif 'wordpress' in html_lower or 'wp-content' in html_lower:
            return 'wordpress'
        elif 'drupal' in html_lower:
            return 'drupal'
        elif 'joomla' in html_lower:
            return 'joomla'
        elif 'squarespace' in html_lower:
            return 'squarespace'
        elif 'wix.com' in html_lower:
            return 'wix'
        
        return 'custom'
    
    def find_obituary_section(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Find and analyze the obituary section of the website."""
        obituary_info = {
            'found': False,
            'url_patterns': [],
            'section_selectors': [],
            'link_count': 0,
            'sample_links': []
        }
        
        # Look for obituary navigation links
        nav_links = soup.find_all('a', href=True)
        obituary_nav_links = []
        
        for link in nav_links:
            href = link.get('href', '').lower()
            text = link.get_text().lower().strip()
            
            if any(keyword in href or keyword in text for keyword in ['obituary', 'obituaries', 'memorial', 'tribute']):
                full_url = urljoin(self.base_url, link.get('href'))
                obituary_nav_links.append({
                    'url': full_url,
                    'text': link.get_text().strip(),
                    'href': link.get('href')
                })
        
        if obituary_nav_links:
            obituary_info['found'] = True
            obituary_info['navigation_links'] = obituary_nav_links
            
            # Try to analyze the main obituary listing page
            main_obit_url = obituary_nav_links[0]['url']
            try:
                listing_analysis = self.analyze_obituary_listing_page(main_obit_url)
                obituary_info.update(listing_analysis)
            except Exception as e:
                obituary_info['analysis_error'] = str(e)
        
        return obituary_info
    
    def analyze_obituary_listing_page(self, url: str) -> Dict[str, Any]:
        """Analyze the obituary listing page structure."""
        print(f"     Analyzing obituary listing: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            if response.status_code != 200:
                return {'error': f'HTTP {response.status_code}'}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find potential obituary links
            all_links = soup.find_all('a', href=True)
            obituary_links = []
            
            for link in all_links:
                href = link.get('href')
                text = link.get_text().strip()
                
                if self.looks_like_obituary_link(href, text):
                    full_url = urljoin(url, href)
                    obituary_links.append({
                        'url': full_url,
                        'text': text,
                        'href': href
                    })
            
            # Analyze link patterns
            url_patterns = self.extract_url_patterns([link['href'] for link in obituary_links])
            
            # Find common container selectors
            container_selectors = self.find_container_selectors(soup, obituary_links)
            
            return {
                'link_count': len(obituary_links),
                'sample_links': obituary_links[:5],  # First 5 for examination
                'url_patterns': url_patterns,
                'container_selectors': container_selectors
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    def looks_like_obituary_link(self, href: str, text: str) -> bool:
        """Determine if a link looks like it leads to an obituary."""
        if not href:
            return False
        
        href_lower = href.lower()
        text_lower = text.lower()
        
        # Skip obviously non-obituary links
        skip_patterns = [
            'contact', 'about', 'home', 'service', 'location', 'staff',
            'javascript:', 'mailto:', '#', 'tel:', 'send-flowers', 'flowers',
            'guestbook', 'guest-book', 'share', 'print'
        ]
        
        if any(pattern in href_lower for pattern in skip_patterns):
            return False
        
        # Positive indicators in URL
        positive_url_patterns = [
            'obituary', 'obit', 'memorial', 'tribute', 'deceased',
            '/death/', '/listing/', '/view/', '/details/'
        ]
        
        if any(pattern in href_lower for pattern in positive_url_patterns):
            return True
        
        # Check if text looks like a person's name (basic heuristic)
        if text and 2 <= len(text.split()) <= 5:  # 2-5 words (likely a name)
            # Must contain letters
            if any(c.isalpha() for c in text):
                # Should not contain common non-name words
                non_name_words = ['read', 'more', 'view', 'click', 'here', 'obituary', 'memorial']
                if not any(word in text_lower for word in non_name_words):
                    return True
        
        return False
    
    def extract_url_patterns(self, urls: List[str]) -> List[str]:
        """Extract common URL patterns from obituary links."""
        if not urls:
            return []
        
        patterns = set()
        
        for url in urls:
            # Extract path pattern
            parsed = urlparse(url)
            path_parts = [part for part in parsed.path.split('/') if part]
            
            if path_parts:
                # Look for common patterns
                if 'obituary' in path_parts:
                    patterns.add('/obituary/')
                if 'obituaries' in path_parts:
                    patterns.add('/obituaries/')
                if 'memorial' in path_parts:
                    patterns.add('/memorial/')
                if 'tribute' in path_parts:
                    patterns.add('/tribute/')
        
        return list(patterns)
    
    def find_container_selectors(self, soup: BeautifulSoup, obituary_links: List[Dict]) -> List[str]:
        """Find CSS selectors for obituary containers."""
        selectors = set()
        
        if not obituary_links:
            return []
        
        # Find parent elements of obituary links
        for link_info in obituary_links[:10]:  # Check first 10 links
            # Find the <a> element in the soup
            link_elements = soup.find_all('a', href=link_info['href'])
            
            for link_elem in link_elements:
                # Check parent elements for common classes
                current = link_elem
                depth = 0
                
                while current and depth < 5:  # Don't go too deep
                    if current.name and current.get('class'):
                        classes = current.get('class')
                        for class_name in classes:
                            if any(keyword in class_name.lower() for keyword in 
                                   ['card', 'item', 'entry', 'post', 'obit', 'memorial', 'listing']):
                                selector = f".{class_name}"
                                selectors.add(selector)
                    
                    current = current.parent
                    depth += 1
        
        return list(selectors)[:5]  # Return top 5 selectors
    
    def analyze_page_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """Analyze the overall page structure."""
        structure = {
            'has_header': bool(soup.find(['header', '.header', '#header'])),
            'has_navigation': bool(soup.find(['nav', '.nav', '.navigation', '.menu'])),
            'has_sidebar': bool(soup.find(['.sidebar', '.side-bar', '.aside', 'aside'])),
            'has_footer': bool(soup.find(['footer', '.footer', '#footer'])),
            'main_content_selectors': [],
            'total_links': len(soup.find_all('a', href=True)),
            'total_images': len(soup.find_all('img')),
            'has_pagination': False
        }
        
        # Find main content areas
        main_content_candidates = [
            'main', '.main', '#main', '.content', '#content',
            '.main-content', '#main-content', '.page-content'
        ]
        
        for selector in main_content_candidates:
            if soup.select(selector):
                structure['main_content_selectors'].append(selector)
        
        # Check for pagination
        pagination_indicators = [
            '.pagination', '.pager', '.page-nav', '.next', '.prev',
            '[class*="page"]', '[id*="page"]'
        ]
        
        for indicator in pagination_indicators:
            if soup.select(indicator):
                structure['has_pagination'] = True
                break
        
        return structure
    
    def generate_suggested_config(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Generate suggested scraper configuration based on analysis."""
        config = {
            'scraper_type': 'enhanced_generic',
            'requires_javascript': analysis.get('requires_javascript', False),
            'custom_selectors': {},
            'url_patterns': {},
            'skip_patterns': [
                '/send-flowers', '/flowers', '/sympathy', '/plant-tree',
                '/share', '/guestbook', '/guest-book', '/print'
            ],
            'validation_rules': {
                'min_content_length': 100,
                'required_elements': ['name']
            }
        }
        
        # Add platform-specific configurations
        platform = analysis.get('platform_type', 'custom')
        if platform == 'tribute':
            config['skip_patterns'].extend(['/tribute-store', '/memory', '/candles'])
        elif platform == 'frontrunner':
            config['skip_patterns'].extend(['/services', '/directions', '/flowers'])
        
        # Add obituary section specific configurations
        obituary_section = analysis.get('obituary_section', {})
        if obituary_section.get('found'):
            # Use detected container selectors
            container_selectors = obituary_section.get('container_selectors', [])
            if container_selectors:
                config['custom_selectors']['obituary_list'] = ', '.join(container_selectors)
            
            # Use detected URL patterns
            url_patterns = obituary_section.get('url_patterns', [])
            if url_patterns:
                config['url_patterns']['obituary_indicators'] = url_patterns
        
        return config
    
    def generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate human-readable recommendations."""
        recommendations = []
        
        if analysis.get('status') != 'success':
            recommendations.append("❌ Website analysis failed. Manual investigation required.")
            return recommendations
        
        # JavaScript recommendations
        if analysis.get('requires_javascript'):
            recommendations.append("⚠️  Website requires JavaScript. Use Selenium-based scraping.")
        else:
            recommendations.append("✅ Website works with simple HTTP requests.")
        
        # Platform recommendations
        platform = analysis.get('platform_type', 'custom')
        if platform != 'custom':
            recommendations.append(f"📋 Detected platform: {platform.title()}. Consider platform-specific configurations.")
        
        # Obituary section recommendations
        obituary_section = analysis.get('obituary_section', {})
        if obituary_section.get('found'):
            link_count = obituary_section.get('link_count', 0)
            if link_count > 0:
                recommendations.append(f"✅ Found {link_count} potential obituary links.")
                
                container_selectors = obituary_section.get('container_selectors', [])
                if container_selectors:
                    recommendations.append(f"🎯 Use container selectors: {', '.join(container_selectors[:3])}")
                
                url_patterns = obituary_section.get('url_patterns', [])
                if url_patterns:
                    recommendations.append(f"🔗 URL patterns detected: {', '.join(url_patterns)}")
            else:
                recommendations.append("⚠️  Obituary section found but no obituary links detected.")
        else:
            recommendations.append("❌ No obituary section found. Manual URL investigation needed.")
        
        # Structure recommendations
        structure = analysis.get('page_structure', {})
        if structure.get('has_pagination'):
            recommendations.append("📄 Pagination detected. Consider implementing pagination handling.")
        
        return recommendations
    
    def print_analysis_report(self, analysis: Dict[str, Any]) -> None:
        """Print a formatted analysis report."""
        print("\\n" + "="*60)
        print(f"WEBSITE ANALYSIS REPORT")
        print(f"URL: {analysis['url']}")
        print(f"Status: {analysis['status'].upper()}")
        print("="*60)
        
        if analysis['status'] != 'success':
            print("\\n❌ ANALYSIS FAILED")
            for issue in analysis.get('issues_found', []):
                print(f"   • {issue}")
            return
        
        print(f"\\n📊 BASIC INFO")
        print(f"   JavaScript Required: {analysis.get('requires_javascript', 'Unknown')}")
        print(f"   Platform Type: {analysis.get('platform_type', 'Unknown').title()}")
        
        obituary_section = analysis.get('obituary_section', {})
        if obituary_section.get('found'):
            print(f"\\n🎯 OBITUARY SECTION")
            print(f"   Links Found: {obituary_section.get('link_count', 0)}")
            
            nav_links = obituary_section.get('navigation_links', [])
            if nav_links:
                print(f"   Navigation URLs:")
                for link in nav_links[:3]:
                    print(f"     • {link['text']}: {link['url']}")
            
            container_selectors = obituary_section.get('container_selectors', [])
            if container_selectors:
                print(f"   Container Selectors: {', '.join(container_selectors)}")
            
            url_patterns = obituary_section.get('url_patterns', [])
            if url_patterns:
                print(f"   URL Patterns: {', '.join(url_patterns)}")
        
        print(f"\\n💡 RECOMMENDATIONS")
        for rec in analysis.get('recommendations', []):
            print(f"   {rec}")
        
        print(f"\\n⚙️  SUGGESTED CONFIGURATION")
        config = analysis.get('suggested_config', {})
        print(json.dumps(config, indent=2))

def main():
    """Main function to run the analyzer."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python website_analyzer.py <funeral_home_url>")
        print("Example: python website_analyzer.py https://www.example-funeral-home.com")
        return
    
    url = sys.argv[1]
    
    analyzer = WebsiteAnalyzer(url)
    analysis = analyzer.analyze_website()
    analyzer.print_analysis_report(analysis)
    
    # Save analysis to file
    output_file = f"analysis_{analyzer.base_url.replace('https://', '').replace('http://', '').replace('/', '_').replace('.', '_')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    print(f"\\n📄 Analysis saved to: {output_file}")

if __name__ == "__main__":
    main()
