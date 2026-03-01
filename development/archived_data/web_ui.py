"""
Web UI for Waco Area Obituary Aggregator

This Flask application provides a simple web interface to view and manage
obituary listings from multiple funeral homes in the Waco, TX area.
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime
from typing import List, Dict, Any
import subprocess
import sys

app = Flask(__name__)
CORS(app)

# Configuration
FUNERAL_HOMES = {
    'lakeshore': {
        'name': 'Lake Shore Funeral Home',
        'script': 'scrape_real_obituaries.py',
        'url': 'https://www.lakeshorefuneralhome.com',
        'storage_file': 'obituaries_detailed.json'
    },
    'lakeshore_basic': {
        'name': 'Lake Shore (Basic Scraper)',
        'script': 'scrape_obituaries_firefox.py',
        'url': 'https://www.lakeshorefuneralhome.com',
        'storage_file': 'seen_obituaries.json'
    },
    # We'll add more funeral homes here
}

def load_obituaries_from_storage(storage_file: str) -> List[Dict[str, Any]]:
    """Load obituary data from storage file."""
    if not os.path.exists(storage_file):
        return []
    
    try:
        with open(storage_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        obituaries = []
        
        # Handle detailed obituary format
        if 'obituaries' in data and isinstance(data['obituaries'], dict):
            for ob_id, details in data['obituaries'].items():
                obituary = {
                    'id': ob_id,
                    'name': details.get('name', f'Obituary #{ob_id}'),
                    'birth_date': details.get('birth_date'),
                    'death_date': details.get('death_date'),
                    'age': details.get('age'),
                    'summary': details.get('summary'),
                    'service_info': details.get('service_info'),
                    'photo_url': details.get('photo_url'),
                    'url': details.get('url', f'https://www.lakeshorefuneralhome.com/obituaries/obituary?obId={ob_id}'),
                    'funeral_home': details.get('funeral_home', 'Lake Shore Funeral Home'),
                    'last_seen': details.get('scraped_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                }
                obituaries.append(obituary)
        
        # Handle basic format (just IDs)
        elif 'seen_ids' in data:
            for ob_id in data.get('seen_ids', []):
                obituaries.append({
                    'id': ob_id,
                    'name': f'Obituary #{ob_id}',  # Placeholder - we'll enhance this
                    'birth_date': None,
                    'death_date': None,
                    'age': None,
                    'summary': None,
                    'service_info': None,
                    'photo_url': None,
                    'url': f'https://www.lakeshorefuneralhome.com/obituaries/obituary?obId={ob_id}',
                    'funeral_home': 'Lake Shore Funeral Home',
                    'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
        
        return obituaries
    except Exception as e:
        print(f"Error loading obituaries: {e}")
        return []

def run_scraper(script_name: str) -> Dict[str, Any]:
    """Run a scraper script and return the results."""
    try:
        # Get the Python executable path
        python_path = os.path.join(os.getcwd(), '.venv', 'Scripts', 'python.exe')
        
        # Run the scraper
        result = subprocess.run([python_path, script_name], 
                              capture_output=True, text=True, timeout=120)
        
        return {
            'success': result.returncode == 0,
            'output': result.stdout,
            'error': result.stderr,
            'return_code': result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': '',
            'error': 'Script timed out after 120 seconds',
            'return_code': -1
        }
    except Exception as e:
        return {
            'success': False,
            'output': '',
            'error': str(e),
            'return_code': -1
        }

@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('index.html', funeral_homes=FUNERAL_HOMES)

@app.route('/api/obituaries')
def get_obituaries():
    """API endpoint to get all obituaries."""
    all_obituaries = []
    
    for home_id, home_info in FUNERAL_HOMES.items():
        storage_file = home_info['storage_file']
        obituaries = load_obituaries_from_storage(storage_file)
        all_obituaries.extend(obituaries)
    
    # Sort by death date (most recent deaths first), then by scraped date as fallback
    def get_sort_key(obituary):
        # Try to parse death date for proper sorting
        death_date = obituary.get('death_date', '')
        if death_date:
            try:
                # Handle various date formats
                import re
                from datetime import datetime
                
                # Clean up the date string
                date_clean = re.sub(r'\s+', ' ', death_date.strip())
                
                # Try different date formats
                date_formats = [
                    '%B %d, %Y',      # "July 22, 2025"
                    '%b %d, %Y',      # "Jul 22, 2025"
                    '%m/%d/%Y',       # "7/22/2025"
                    '%m-%d-%Y',       # "7-22-2025"
                    '%Y-%m-%d'        # "2025-07-22"
                ]
                
                for fmt in date_formats:
                    try:
                        return datetime.strptime(date_clean, fmt)
                    except ValueError:
                        continue
                        
                # If no format works, try parsing partial dates
                if '2025' in date_clean:
                    return datetime(2025, 7, 1)  # Default to July 2025 for sorting
                        
            except:
                pass
        
        # Fallback to scraped_at date
        scraped_at = obituary.get('scraped_at', obituary.get('last_seen', '1900-01-01T00:00:00'))
        try:
            from datetime import datetime
            return datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))
        except:
            return datetime(1900, 1, 1)
    
    all_obituaries.sort(key=get_sort_key, reverse=True)
    
    return jsonify({
        'obituaries': all_obituaries,
        'total': len(all_obituaries),
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/scrape/<home_id>')
def scrape_funeral_home(home_id: str):
    """API endpoint to trigger scraping for a specific funeral home."""
    if home_id not in FUNERAL_HOMES:
        return jsonify({'error': 'Unknown funeral home'}), 404
    
    home_info = FUNERAL_HOMES[home_id]
    script_name = home_info['script']
    
    if not os.path.exists(script_name):
        return jsonify({'error': f'Script {script_name} not found'}), 404
    
    result = run_scraper(script_name)
    
    return jsonify({
        'funeral_home': home_info['name'],
        'success': result['success'],
        'output': result['output'],
        'error': result['error'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/scrape/all')
def scrape_all():
    """API endpoint to scrape all funeral homes."""
    results = {}
    
    for home_id, home_info in FUNERAL_HOMES.items():
        script_name = home_info['script']
        
        if os.path.exists(script_name):
            result = run_scraper(script_name)
            results[home_id] = {
                'name': home_info['name'],
                'success': result['success'],
                'output': result['output'],
                'error': result['error']
            }
        else:
            results[home_id] = {
                'name': home_info['name'],
                'success': False,
                'output': '',
                'error': f'Script {script_name} not found'
            }
    
    return jsonify({
        'results': results,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    print("Starting Waco Obituary Aggregator...")
    print("Access the web interface at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
