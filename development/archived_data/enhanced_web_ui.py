"""
Enhanced Web UI for Waco Area Obituary Aggregator

This Flask application provides a comprehensive web interface to view, manage,
search, and archive obituary listings from multiple funeral homes in the Waco, TX area.
"""

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import subprocess
import sys
import re
import uuid

app = Flask(__name__)
CORS(app)

# Configuration files
CONFIG_FILE = 'funeral_homes_config.json'
ARCHIVE_FILE = 'archived_obituaries.json'
FLAGS_FILE = 'obituary_flags.json'

# Define available flag types
FLAG_TYPES = {
    'not_obituary': {
        'label': 'Not an Obituary',
        'description': 'This entry is not actually an obituary (e.g., service page, contact page)',
        'severity': 'high',
        'color': '#dc3545'  # Red
    },
    'no_date': {
        'label': 'No Date/Incorrect Date',
        'description': 'Missing birth/death dates or dates are incorrect',
        'severity': 'medium',
        'color': '#ffc107'  # Yellow
    },
    'incorrect_age': {
        'label': 'Incorrect Age',
        'description': 'Age information is missing or incorrect',
        'severity': 'low',
        'color': '#17a2b8'  # Blue
    },
    'no_photo': {
        'label': 'No Photo Displayed',
        'description': 'Photo is missing or not loading properly',
        'severity': 'low',
        'color': '#6c757d'  # Gray
    },
    'incomplete_content': {
        'label': 'Incomplete Content',
        'description': 'Obituary text is truncated or missing important information',
        'severity': 'medium',
        'color': '#fd7e14'  # Orange
    },
    'duplicate': {
        'label': 'Duplicate Entry',
        'description': 'This obituary appears to be a duplicate of another entry',
        'severity': 'medium',
        'color': '#e83e8c'  # Pink
    }
}

def load_config() -> Dict[str, Any]:
    """Load funeral homes configuration."""
    if not os.path.exists(CONFIG_FILE):
        return {'funeral_homes': {}, 'archived_obituaries': {}, 'settings': {}}
    
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {'funeral_homes': {}, 'archived_obituaries': {}, 'settings': {}}

def save_config(config: Dict[str, Any]) -> bool:
    """Save funeral homes configuration."""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving config: {e}")
        return False

def load_flags() -> Dict[str, Any]:
    """Load obituary flags."""
    if not os.path.exists(FLAGS_FILE):
        return {}
    
    try:
        with open(FLAGS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading flags: {e}")
        return {}

def save_flags(flags: Dict[str, Any]) -> bool:
    """Save obituary flags."""
    try:
        with open(FLAGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(flags, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Error saving flags: {e}")
        return False

def add_flag(obituary_url: str, flag_type: str, notes: str = '', funeral_home: str = '') -> bool:
    """Add a flag to an obituary."""
    if flag_type not in FLAG_TYPES:
        return False
    
    flags = load_flags()
    
    # Create a unique key for this obituary
    flag_key = f"{funeral_home}_{obituary_url}".replace('/', '_').replace(':', '_')
    
    if flag_key not in flags:
        flags[flag_key] = {
            'obituary_url': obituary_url,
            'funeral_home': funeral_home,
            'flags': [],
            'created_at': datetime.now().isoformat()
        }
    
    # Check if this flag type already exists
    existing_flags = [f['type'] for f in flags[flag_key]['flags']]
    if flag_type not in existing_flags:
        flags[flag_key]['flags'].append({
            'type': flag_type,
            'notes': notes,
            'flagged_at': datetime.now().isoformat(),
            'resolved': False
        })
        flags[flag_key]['updated_at'] = datetime.now().isoformat()
        
        return save_flags(flags)
    
    return False  # Flag already exists

def resolve_flag(obituary_url: str, flag_type: str, funeral_home: str = '') -> bool:
    """Mark a flag as resolved."""
    flags = load_flags()
    flag_key = f"{funeral_home}_{obituary_url}".replace('/', '_').replace(':', '_')
    
    if flag_key in flags:
        for flag in flags[flag_key]['flags']:
            if flag['type'] == flag_type:
                flag['resolved'] = True
                flag['resolved_at'] = datetime.now().isoformat()
                flags[flag_key]['updated_at'] = datetime.now().isoformat()
                return save_flags(flags)
    
    return False

def get_obituary_flags(obituary_url: str, funeral_home: str = '') -> List[Dict[str, Any]]:
    """Get flags for a specific obituary."""
    flags = load_flags()
    flag_key = f"{funeral_home}_{obituary_url}".replace('/', '_').replace(':', '_')
    
    if flag_key in flags:
        return flags[flag_key]['flags']
    
    return []

def load_obituaries_from_storage(storage_file: str, funeral_home_name: str = None) -> List[Dict[str, Any]]:
    """Load obituary data from storage file."""
    if not os.path.exists(storage_file):
        return []
    
    try:
        with open(storage_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        obituaries = []
        
        # Handle list format (from scrape_all_detailed.py)
        if isinstance(data, list):
            for i, item in enumerate(data):
                obituary = {
                    'id': item.get('url', f'obituary_{i}').split('/')[-1],  # Use URL path as ID
                    'name': item.get('name', f'Obituary #{i}'),
                    'birth_date': item.get('birth_date'),
                    'death_date': item.get('death_date'),
                    'age': item.get('age'),
                    'summary': item.get('obituary_text', '')[:200] + '...' if item.get('obituary_text') else None,
                    'service_info': item.get('services'),
                    'photo_url': item.get('photo_url'),
                    'url': item.get('url', ''),
                    'funeral_home': item.get('funeral_home', funeral_home_name or 'Unknown'),
                    'last_seen': item.get('scraped_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    'archived': False,
                    'flags': get_obituary_flags(item.get('url', ''), item.get('funeral_home', funeral_home_name or ''))
                }
                obituaries.append(obituary)
        
        # Handle detailed obituary format (original format)
        elif 'obituaries' in data and isinstance(data['obituaries'], dict):
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
                    'url': details.get('url', ''),
                    'funeral_home': details.get('funeral_home', funeral_home_name or 'Unknown'),
                    'last_seen': details.get('scraped_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
                    'archived': False,
                    'flags': get_obituary_flags(details.get('url', ''), details.get('funeral_home', funeral_home_name or ''))
                }
                obituaries.append(obituary)
        
        # Handle basic format (just IDs)
        elif 'seen_ids' in data:
            for ob_id in data.get('seen_ids', []):
                obituaries.append({
                    'id': str(ob_id),
                    'name': f'Obituary #{ob_id}',
                    'birth_date': None,
                    'death_date': None,
                    'age': None,
                    'summary': None,
                    'service_info': None,
                    'photo_url': None,
                    'url': '',
                    'funeral_home': funeral_home_name or 'Unknown',
                    'last_seen': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'archived': False
                })
        
        return obituaries
    except Exception as e:
        print(f"Error loading obituaries from {storage_file}: {e}")
        return []

def search_obituaries(query: str, obituaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Search obituaries by name, date, or other criteria."""
    if not query:
        return obituaries
    
    query_lower = query.lower()
    results = []
    
    for obituary in obituaries:
        # Search in name
        if query_lower in obituary.get('name', '').lower():
            results.append(obituary)
            continue
        
        # Search in funeral home
        if query_lower in obituary.get('funeral_home', '').lower():
            results.append(obituary)
            continue
        
        # Search in summary
        if obituary.get('summary') and query_lower in obituary.get('summary', '').lower():
            results.append(obituary)
            continue
        
        # Search in dates
        if obituary.get('birth_date') and query_lower in obituary.get('birth_date', '').lower():
            results.append(obituary)
            continue
        
        if obituary.get('death_date') and query_lower in obituary.get('death_date', '').lower():
            results.append(obituary)
            continue
    
    return results

def archive_obituary(obituary_id: str, funeral_home_id: str) -> bool:
    """Archive an obituary."""
    config = load_config()
    
    # Find the obituary in the current data
    if funeral_home_id not in config['funeral_homes']:
        return False
    
    home_info = config['funeral_homes'][funeral_home_id]
    storage_file = home_info['storage_file']
    
    if not os.path.exists(storage_file):
        return False
    
    try:
        # Load current obituaries
        with open(storage_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Find and remove the obituary
        obituary_data = None
        if 'obituaries' in data and obituary_id in data['obituaries']:
            obituary_data = data['obituaries'][obituary_id]
            del data['obituaries'][obituary_id]
            
            # Save updated data
            with open(storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # Add to archived obituaries
            if 'archived_obituaries' not in config:
                config['archived_obituaries'] = {}
            
            archive_id = f"{funeral_home_id}_{obituary_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            config['archived_obituaries'][archive_id] = {
                **obituary_data,
                'original_id': obituary_id,
                'funeral_home_id': funeral_home_id,
                'archived_at': datetime.now().isoformat()
            }
            
            save_config(config)
            return True
    
    except Exception as e:
        print(f"Error archiving obituary: {e}")
        return False
    
    return False

def run_scraper(script_name: str, funeral_home_url: str = None) -> Dict[str, Any]:
    """Run a scraper script and return the results."""
    try:
        # Get the Python executable path
        python_path = os.path.join(os.getcwd(), '.venv', 'Scripts', 'python.exe')
        
        # Prepare command arguments
        cmd_args = [python_path, script_name]
        if funeral_home_url and script_name == 'scrape_generic_obituaries.py':
            cmd_args.append(funeral_home_url)
        
        # Run the scraper
        result = subprocess.run(cmd_args, 
                              capture_output=True, text=True, timeout=180)
        
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
            'error': 'Script timed out after 180 seconds',
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
    config = load_config()
    return render_template('index.html', 
                         funeral_homes=config.get('funeral_homes', {}),
                         settings=config.get('settings', {}))

@app.route('/api/obituaries')
def get_obituaries():
    """API endpoint to get all obituaries with optional search."""
    config = load_config()
    search_query = request.args.get('search', '')
    include_archived = request.args.get('archived', 'false').lower() == 'true'
    funeral_home_filter = request.args.get('funeral_home', '')
    
    all_obituaries = []
    
    # Load from detailed scraper file first (most recent and comprehensive)
    detailed_file = 'obituaries_all_detailed.json'
    if os.path.exists(detailed_file):
        try:
            detailed_obituaries = load_obituaries_from_storage(detailed_file)
            all_obituaries.extend(detailed_obituaries)
            print(f"Loaded {len(detailed_obituaries)} obituaries from detailed scraper")
        except Exception as e:
            print(f"Error loading detailed obituaries: {e}")
    
    # Load active obituaries from individual files (as backup/supplement)
    for home_id, home_info in config.get('funeral_homes', {}).items():
        if not home_info.get('active', False):
            continue
            
        if funeral_home_filter and home_id != funeral_home_filter:
            continue
            
        storage_file = home_info['storage_file']
        obituaries = load_obituaries_from_storage(storage_file, home_info['name'])
        
        # Only add obituaries that aren't already in the detailed list
        # (to avoid duplicates)
        existing_urls = {obit.get('url', '') for obit in all_obituaries}
        new_obituaries = [obit for obit in obituaries if obit.get('url', '') not in existing_urls]
        
        all_obituaries.extend(new_obituaries)
        if new_obituaries:
            print(f"Added {len(new_obituaries)} new obituaries from {home_info['name']}")
    
    # Load archived obituaries if requested
    if include_archived:
        archived = config.get('archived_obituaries', {})
        for archive_id, archived_data in archived.items():
            if funeral_home_filter and archived_data.get('funeral_home_id') != funeral_home_filter:
                continue
                
            archived_obituary = {
                'id': archived_data.get('original_id', archive_id),
                'name': archived_data.get('name', 'Unknown'),
                'birth_date': archived_data.get('birth_date'),
                'death_date': archived_data.get('death_date'),
                'age': archived_data.get('age'),
                'summary': archived_data.get('summary'),
                'service_info': archived_data.get('service_info'),
                'photo_url': archived_data.get('photo_url'),
                'url': archived_data.get('url', ''),
                'funeral_home': archived_data.get('funeral_home', 'Unknown'),
                'last_seen': archived_data.get('archived_at', ''),
                'archived': True
            }
            all_obituaries.append(archived_obituary)
    
    # Apply search filter
    if search_query:
        all_obituaries = search_obituaries(search_query, all_obituaries)
    
    # Sort by death date (most recent deaths first), then by scraped date as fallback
    def get_sort_key(obituary):
        # Try to parse death date for proper sorting
        death_date = obituary.get('death_date', '')
        if death_date:
            try:
                # Handle various date formats
                date_clean = re.sub(r'\\s+', ' ', death_date.strip())
                
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
            return datetime.fromisoformat(scraped_at.replace('Z', '+00:00'))
        except:
            return datetime(1900, 1, 1)
    
    all_obituaries.sort(key=get_sort_key, reverse=True)
    
    return jsonify({
        'obituaries': all_obituaries,
        'total': len(all_obituaries),
        'search_query': search_query,
        'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/obituaries/detailed')
def get_detailed_obituaries():
    """API endpoint to get obituaries from the detailed scraper file."""
    detailed_file = 'obituaries_all_detailed.json'
    
    if not os.path.exists(detailed_file):
        return jsonify({
            'obituaries': [],
            'total': 0,
            'message': 'No detailed obituaries file found. Run scrape_all_detailed.py first.',
            'last_updated': None
        })
    
    try:
        obituaries = load_obituaries_from_storage(detailed_file)
        
        # Apply filters if requested
        search_query = request.args.get('search', '')
        funeral_home_filter = request.args.get('funeral_home', '')
        
        if search_query:
            search_lower = search_query.lower()
            obituaries = [o for o in obituaries if 
                         search_lower in o.get('name', '').lower() or
                         search_lower in o.get('summary', '').lower() or
                         search_lower in o.get('funeral_home', '').lower()]
        
        if funeral_home_filter:
            obituaries = [o for o in obituaries if 
                         funeral_home_filter.lower() in o.get('funeral_home', '').lower()]
        
        # Get file stats
        file_stat = os.stat(detailed_file)
        last_modified = datetime.fromtimestamp(file_stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        
        return jsonify({
            'obituaries': obituaries,
            'total': len(obituaries),
            'search_query': search_query,
            'funeral_home_filter': funeral_home_filter,
            'last_updated': last_modified,
            'source_file': detailed_file
        })
        
    except Exception as e:
        return jsonify({
            'obituaries': [],
            'total': 0,
            'error': f'Error loading detailed obituaries: {str(e)}',
            'last_updated': None
        })

@app.route('/api/funeral-homes')
def get_funeral_homes():
    """API endpoint to get all funeral homes configuration."""
    config = load_config()
    return jsonify(config.get('funeral_homes', {}))

@app.route('/api/funeral-homes', methods=['POST'])
def add_funeral_home():
    """API endpoint to add a new funeral home."""
    data = request.get_json()
    
    if not data or 'name' not in data or 'url' not in data:
        return jsonify({'error': 'Name and URL are required'}), 400
    
    config = load_config()
    
    # Generate ID from name
    home_id = re.sub(r'[^a-zA-Z0-9]', '', data['name'].lower().replace(' ', ''))
    
    # Check if ID already exists
    counter = 1
    original_id = home_id
    while home_id in config.get('funeral_homes', {}):
        home_id = f"{original_id}{counter}"
        counter += 1
    
    # Add new funeral home
    new_home = {
        'name': data['name'],
        'url': data['url'],
        'address': data.get('address', 'Unknown'),
        'scraper_type': data.get('scraper_type', 'generic'),
        'script': 'scrape_generic_obituaries.py',
        'storage_file': f'obituaries_{home_id}.json',
        'active': data.get('active', False),
        'last_scraped': None,
        'priority': len(config.get('funeral_homes', {})) + 1
    }
    
    if 'funeral_homes' not in config:
        config['funeral_homes'] = {}
    
    config['funeral_homes'][home_id] = new_home
    
    if save_config(config):
        return jsonify({'success': True, 'id': home_id, 'funeral_home': new_home})
    else:
        return jsonify({'error': 'Failed to save configuration'}), 500

@app.route('/api/funeral-homes/<home_id>', methods=['PUT'])
def update_funeral_home(home_id: str):
    """API endpoint to update a funeral home."""
    data = request.get_json()
    config = load_config()
    
    if home_id not in config.get('funeral_homes', {}):
        return jsonify({'error': 'Funeral home not found'}), 404
    
    # Update the funeral home data
    for key, value in data.items():
        if key in ['name', 'url', 'address', 'scraper_type', 'active', 'priority']:
            config['funeral_homes'][home_id][key] = value
    
    if save_config(config):
        return jsonify({'success': True, 'funeral_home': config['funeral_homes'][home_id]})
    else:
        return jsonify({'error': 'Failed to save configuration'}), 500

@app.route('/api/funeral-homes/<home_id>', methods=['DELETE'])
def delete_funeral_home(home_id: str):
    """API endpoint to delete a funeral home."""
    config = load_config()
    
    if home_id not in config.get('funeral_homes', {}):
        return jsonify({'error': 'Funeral home not found'}), 404
    
    del config['funeral_homes'][home_id]
    
    if save_config(config):
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to save configuration'}), 500

@app.route('/api/scrape/<home_id>')
def scrape_funeral_home(home_id: str):
    """API endpoint to trigger scraping for a specific funeral home."""
    config = load_config()
    
    if home_id not in config.get('funeral_homes', {}):
        return jsonify({'error': 'Unknown funeral home'}), 404
    
    home_info = config['funeral_homes'][home_id]
    script_name = home_info['script']
    
    if not os.path.exists(script_name):
        return jsonify({'error': f'Script {script_name} not found'}), 404
    
    result = run_scraper(script_name, home_info.get('url'))
    
    # Update last scraped time
    config['funeral_homes'][home_id]['last_scraped'] = datetime.now().isoformat()
    save_config(config)
    
    return jsonify({
        'funeral_home': home_info['name'],
        'success': result['success'],
        'output': result['output'],
        'error': result['error'],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/scrape/all')
def scrape_all():
    """API endpoint to scrape all active funeral homes."""
    config = load_config()
    results = {}
    
    for home_id, home_info in config.get('funeral_homes', {}).items():
        if not home_info.get('active', False):
            continue
            
        script_name = home_info['script']
        
        if os.path.exists(script_name):
            result = run_scraper(script_name, home_info.get('url'))
            results[home_id] = {
                'name': home_info['name'],
                'success': result['success'],
                'output': result['output'],
                'error': result['error']
            }
            
            # Update last scraped time
            config['funeral_homes'][home_id]['last_scraped'] = datetime.now().isoformat()
        else:
            results[home_id] = {
                'name': home_info['name'],
                'success': False,
                'output': '',
                'error': f'Script {script_name} not found'
            }
    
    save_config(config)
    
    return jsonify({
        'results': results,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })

@app.route('/api/archive/<home_id>/<obituary_id>', methods=['POST'])
def archive_obituary_endpoint(home_id: str, obituary_id: str):
    """API endpoint to archive an obituary."""
    success = archive_obituary(obituary_id, home_id)
    
    if success:
        return jsonify({'success': True})
    else:
        return jsonify({'error': 'Failed to archive obituary'}), 500

@app.route('/api/flags/types')
def get_flag_types():
    """API endpoint to get available flag types."""
    return jsonify(FLAG_TYPES)

@app.route('/api/flags', methods=['POST'])
def add_obituary_flag():
    """API endpoint to add a flag to an obituary."""
    data = request.get_json()
    
    required_fields = ['obituary_url', 'flag_type', 'funeral_home']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    if data['flag_type'] not in FLAG_TYPES:
        return jsonify({'error': 'Invalid flag type'}), 400
    
    success = add_flag(
        obituary_url=data['obituary_url'],
        flag_type=data['flag_type'],
        notes=data.get('notes', ''),
        funeral_home=data['funeral_home']
    )
    
    if success:
        return jsonify({
            'success': True,
            'message': f'Flag "{FLAG_TYPES[data["flag_type"]]["label"]}" added successfully'
        })
    else:
        return jsonify({'error': 'Flag already exists or failed to save'}), 400

@app.route('/api/flags/<path:obituary_url>/resolve', methods=['POST'])
def resolve_obituary_flag(obituary_url: str):
    """API endpoint to resolve a flag."""
    data = request.get_json()
    
    if 'flag_type' not in data or 'funeral_home' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    success = resolve_flag(
        obituary_url=obituary_url,
        flag_type=data['flag_type'],
        funeral_home=data['funeral_home']
    )
    
    if success:
        return jsonify({'success': True, 'message': 'Flag resolved successfully'})
    else:
        return jsonify({'error': 'Failed to resolve flag'}), 500

@app.route('/api/flags/summary')
def get_flags_summary():
    """API endpoint to get flags summary for admin dashboard."""
    flags = load_flags()
    
    summary = {
        'total_flagged_obituaries': len(flags),
        'flags_by_type': {},
        'flags_by_severity': {'high': 0, 'medium': 0, 'low': 0},
        'unresolved_flags': 0,
        'recent_flags': []
    }
    
    for flag_key, flag_data in flags.items():
        for flag in flag_data['flags']:
            flag_type = flag['type']
            if flag_type in FLAG_TYPES:
                # Count by type
                if flag_type not in summary['flags_by_type']:
                    summary['flags_by_type'][flag_type] = {
                        'count': 0,
                        'label': FLAG_TYPES[flag_type]['label']
                    }
                summary['flags_by_type'][flag_type]['count'] += 1
                
                # Count by severity
                severity = FLAG_TYPES[flag_type]['severity']
                summary['flags_by_severity'][severity] += 1
                
                # Count unresolved
                if not flag.get('resolved', False):
                    summary['unresolved_flags'] += 1
                
                # Recent flags (last 7 days)
                flag_date = datetime.fromisoformat(flag['flagged_at'].replace('Z', '+00:00'))
                days_ago = (datetime.now() - flag_date.replace(tzinfo=None)).days
                if days_ago <= 7:
                    summary['recent_flags'].append({
                        'obituary_url': flag_data['obituary_url'],
                        'funeral_home': flag_data['funeral_home'],
                        'flag_type': flag_type,
                        'label': FLAG_TYPES[flag_type]['label'],
                        'flagged_at': flag['flagged_at'],
                        'resolved': flag.get('resolved', False)
                    })
    
    # Sort recent flags by date
    summary['recent_flags'].sort(key=lambda x: x['flagged_at'], reverse=True)
    
    return jsonify(summary)

@app.route('/api/stats')
def get_stats():
    """API endpoint to get statistics."""
    config = load_config()
    stats = {
        'total_funeral_homes': len(config.get('funeral_homes', {})),
        'active_funeral_homes': len([h for h in config.get('funeral_homes', {}).values() if h.get('active', False)]),
        'total_obituaries': 0,
        'archived_obituaries': len(config.get('archived_obituaries', {})),
        'last_scrape_times': {}
    }
    
    # Count total obituaries
    for home_id, home_info in config.get('funeral_homes', {}).items():
        storage_file = home_info['storage_file']
        obituaries = load_obituaries_from_storage(storage_file)
        stats['total_obituaries'] += len(obituaries)
        stats['last_scrape_times'][home_id] = home_info.get('last_scraped')
    
    return jsonify(stats)

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    print("Starting Enhanced Waco Obituary Aggregator...")
    print("Access the web interface at: http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
