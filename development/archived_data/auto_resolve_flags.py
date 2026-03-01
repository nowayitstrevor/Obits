#!/usr/bin/env python3
"""
Auto-resolve flags when the underlying data issues have been fixed.
"""

import json
from datetime import datetime

def auto_resolve_fixed_flags():
    """Auto-resolve flags where the data has been corrected."""
    
    # Load current data
    with open('obituaries_all_detailed.json', 'r', encoding='utf-8') as f:
        obituaries = json.load(f)
    
    with open('obituary_flags.json', 'r', encoding='utf-8') as f:
        flags_data = json.load(f)
    
    # Create URL lookup for obituaries
    obituary_lookup = {}
    for obit in obituaries:
        obituary_lookup[obit['url']] = obit
    
    resolved_count = 0
    
    # Check each flag
    for flag_key, flag_info in flags_data.items():
        url = flag_info['obituary_url']
        
        # Check if obituary exists in current data
        if url in obituary_lookup:
            obituary = obituary_lookup[url]
            
            # Check each flag in the entry
            for flag in flag_info['flags']:
                if flag.get('resolved', False):
                    continue  # Already resolved
                
                should_resolve = False
                resolution_reason = ""
                
                # Check NO_DATE flags
                if flag['type'] == 'no_date':
                    birth_date = obituary.get('birth_date', '').strip()
                    death_date = obituary.get('death_date', '').strip()
                    
                    if birth_date and death_date:
                        should_resolve = True
                        resolution_reason = f"Dates now available: Birth={birth_date}, Death={death_date}"
                    elif death_date:
                        should_resolve = True
                        resolution_reason = f"Death date now available: {death_date}"
                
                # Check INCOMPLETE_CONTENT flags  
                elif flag['type'] == 'incomplete_content':
                    content = obituary.get('obituary_text', '').strip()
                    if len(content) > 200:  # Minimum content threshold
                        should_resolve = True
                        resolution_reason = f"Content now complete ({len(content)} characters)"
                
                # Resolve the flag
                if should_resolve:
                    flag['resolved'] = True
                    flag['resolved_at'] = datetime.now().isoformat()
                    flag['resolution_reason'] = resolution_reason
                    flag_info['updated_at'] = datetime.now().isoformat()
                    resolved_count += 1
                    print(f"✅ RESOLVED: {flag['type']} for {obituary['name']} - {resolution_reason}")
    
    # Save updated flags
    with open('obituary_flags.json', 'w', encoding='utf-8') as f:
        json.dump(flags_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n🎉 Auto-resolved {resolved_count} flags!")
    return resolved_count

if __name__ == "__main__":
    auto_resolve_fixed_flags()
