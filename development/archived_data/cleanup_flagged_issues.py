#!/usr/bin/env python3
"""
Cleanup script to remove invalid obituary entries and resolve flags.

This script:
1. Removes obituaries with URLs that match problematic patterns (send-flowers, etc.)
2. Resolves flags for removed entries
3. Cleans up the obituary data files
"""

import json
import os
from typing import List, Dict, Any
from datetime import datetime

# File paths
OBITUARIES_FILE = 'obituaries_all_detailed.json'
FLAGS_FILE = 'obituary_flags.json'
BACKUP_SUFFIX = '_backup'

# Patterns that indicate invalid obituary entries
INVALID_PATTERNS = [
    '/send-flowers',
    'send-flowers',
    'tributearchive.com',
    'google.com',
    'search?q=',
    '/obituaries',  # listing pages, not individual obituaries
    '/listings',    # listing pages
    'mailto:',
    'javascript:',
    '.pdf',
    '.jpg',
    '.png',
    '.gif'
]

def load_json_file(filepath: str) -> Dict[str, Any]:
    """Load JSON file, return empty dict if file doesn't exist."""
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            print(f"Warning: Could not load {filepath}")
    return {}

def save_json_file(filepath: str, data: Dict[str, Any]) -> None:
    """Save data to JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def backup_file(filepath: str) -> None:
    """Create a backup of the file."""
    if os.path.exists(filepath):
        backup_path = filepath + BACKUP_SUFFIX
        with open(filepath, 'r', encoding='utf-8') as src:
            with open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())
        print(f"Backup created: {backup_path}")

def is_invalid_obituary_url(url: str) -> bool:
    """Check if URL matches invalid patterns."""
    url_lower = url.lower()
    return any(pattern.lower() in url_lower for pattern in INVALID_PATTERNS)

def cleanup_obituaries():
    """Remove invalid obituary entries from the main data file."""
    print("Loading obituaries data...")
    
    if not os.path.exists(OBITUARIES_FILE):
        print(f"No obituaries file found at {OBITUARIES_FILE}")
        return
    
    # Backup the original file
    backup_file(OBITUARIES_FILE)
    
    # Load obituaries
    with open(OBITUARIES_FILE, 'r', encoding='utf-8') as f:
        obituaries = json.load(f)
    
    print(f"Total obituaries before cleanup: {len(obituaries)}")
    
    # Filter out invalid entries
    valid_obituaries = []
    removed_urls = []
    
    for obit in obituaries:
        url = obit.get('url', '')
        if is_invalid_obituary_url(url):
            removed_urls.append(url)
            print(f"Removing invalid entry: {url}")
        else:
            valid_obituaries.append(obit)
    
    print(f"Removed {len(removed_urls)} invalid entries")
    print(f"Valid obituaries remaining: {len(valid_obituaries)}")
    
    # Save cleaned data
    with open(OBITUARIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(valid_obituaries, f, indent=2, ensure_ascii=False)
    
    return removed_urls

def resolve_flags_for_removed_entries(removed_urls: List[str]):
    """Mark flags as resolved for removed obituary entries."""
    print("Updating flags...")
    
    if not os.path.exists(FLAGS_FILE):
        print(f"No flags file found at {FLAGS_FILE}")
        return
    
    # Backup the original file
    backup_file(FLAGS_FILE)
    
    # Load flags
    flags_data = load_json_file(FLAGS_FILE)
    
    resolved_count = 0
    for flag_key, flag_info in flags_data.items():
        obituary_url = flag_info.get('obituary_url', '')
        
        # Check if this obituary was removed
        if any(removed_url == obituary_url for removed_url in removed_urls):
            # Mark all flags for this obituary as resolved
            for flag in flag_info.get('flags', []):
                if not flag.get('resolved', False):
                    flag['resolved'] = True
                    flag['resolved_at'] = datetime.now().isoformat()
                    flag['resolution_reason'] = 'Invalid obituary entry removed from data'
                    resolved_count += 1
            
            flag_info['updated_at'] = datetime.now().isoformat()
    
    print(f"Resolved {resolved_count} flags for removed entries")
    
    # Save updated flags
    save_json_file(FLAGS_FILE, flags_data)

def print_remaining_flags():
    """Print summary of remaining unresolved flags."""
    flags_data = load_json_file(FLAGS_FILE)
    
    unresolved_flags = {}
    for flag_key, flag_info in flags_data.items():
        obituary_url = flag_info.get('obituary_url', '')
        funeral_home = flag_info.get('funeral_home', 'Unknown')
        
        for flag in flag_info.get('flags', []):
            if not flag.get('resolved', False):
                flag_type = flag.get('type', 'unknown')
                if flag_type not in unresolved_flags:
                    unresolved_flags[flag_type] = []
                unresolved_flags[flag_type].append({
                    'url': obituary_url,
                    'funeral_home': funeral_home,
                    'notes': flag.get('notes', '')
                })
    
    print("\n" + "="*60)
    print("REMAINING UNRESOLVED FLAGS:")
    print("="*60)
    
    if not unresolved_flags:
        print("🎉 No unresolved flags remaining!")
        return
    
    for flag_type, flags in unresolved_flags.items():
        print(f"\n{flag_type.upper()} ({len(flags)} remaining):")
        for flag in flags:
            print(f"  - {flag['funeral_home']}: {flag['url']}")
            if flag['notes']:
                print(f"    Notes: {flag['notes']}")

def main():
    """Main cleanup function."""
    print("Starting cleanup of flagged issues...")
    print("="*60)
    
    # Remove invalid obituaries
    removed_urls = cleanup_obituaries()
    
    if removed_urls:
        # Resolve flags for removed entries
        resolve_flags_for_removed_entries(removed_urls)
    
    # Show remaining issues
    print_remaining_flags()
    
    print("\n" + "="*60)
    print("✅ Cleanup complete!")
    print("📁 Backup files created with '_backup' suffix")
    print("🔄 Run scraper again to collect clean data with new skip patterns")

if __name__ == "__main__":
    main()
