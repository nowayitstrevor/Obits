#!/usr/bin/env python3
"""
Master Data Parser
Consolidates all individual funeral home JSON files into unified dataset
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

class MasterDataParser:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.unified_data = []
        self.funeral_home_stats = {}
        
        # Define mapping of funeral home files to display names
        self.file_mappings = {
            "obituaries_fossfuneralhome.json": "Foss Funeral Home",
            "obituaries_robertsonfh.json": "Robertson Funeral Home", 
            "obituaries_slctx.json": "SLC Texas Funeral Services",
            "obituaries_mcdowellfuneralhome.json": "McDowell Funeral Home",
            "obituaries_gracegardensfh.json": "Grace Gardens Funeral Home",
            "obituaries_gracegardens.json": "Grace Gardens Funeral Home",  # Alternative name
            "obituaries_lakeshore.json": "Lake Shore Funeral Home",
            "obituaries_aderholdfuneralhome.json": "Aderhold Funeral Home",
            "obituaries_pecangrovefuneral.json": "Pecan Grove Funeral Home",
            "obituaries_oakcrestwaco.json": "Oak Crest Funeral Home",
            "obituaries_wacofhmp.json": "Waco Funeral Home Memorial Park",
            "obituaries_whbfamily.json": "WHB Family Funeral Home"
        }

    def load_funeral_home_data(self, file_path: Path, funeral_home_name: str) -> List[Dict]:
        """Load obituary data from a funeral home JSON file."""
        
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            obituaries = []
            
            # Handle different JSON structures
            if isinstance(data, list):
                # Direct list of obituaries
                obituaries = data
            elif isinstance(data, dict):
                if "obituaries" in data:
                    # Nested structure with "obituaries" key
                    nested_data = data["obituaries"]
                    if isinstance(nested_data, dict):
                        # Dictionary of obituaries (convert values to list)
                        obituaries = list(nested_data.values())
                    elif isinstance(nested_data, list):
                        # List within "obituaries" key
                        obituaries = nested_data
                else:
                    # Single obituary object
                    obituaries = [data]
            
            # Normalize obituary format and add funeral home info
            normalized_obituaries = []
            for obit in obituaries:
                if isinstance(obit, dict):
                    normalized_obit = self.normalize_obituary_format(obit, funeral_home_name)
                    if normalized_obit:
                        normalized_obituaries.append(normalized_obit)
            
            return normalized_obituaries
            
        except Exception as e:
            print(f"  ❌ Error loading {file_path}: {e}")
            return []

    def normalize_obituary_format(self, obituary: Dict, funeral_home_name: str) -> Optional[Dict]:
        """Normalize obituary data to consistent format."""
        
        # Skip if no meaningful content
        if not obituary.get('name') and not obituary.get('url'):
            return None
        
        # Extract and clean name
        name = obituary.get('name', 'Unknown')
        if isinstance(name, str):
            # Clean up name format (remove title suffixes, pipes, etc.)
            name = name.split('|')[0].strip()  # Remove "| 1950 - 2025 | Obituary" parts
            if ' - ' in name and name.count(' - ') == 1:
                # Handle "Name - Birth - Death" format
                name = name.split(' - ')[0].strip()
        
        # Determine age
        age = obituary.get('age', 'Unknown')
        birth_date = obituary.get('birth_date', '')
        death_date = obituary.get('death_date', '')
        
        if age == 'Unknown' and birth_date and death_date:
            try:
                # Try to calculate age from dates
                from datetime import datetime
                if len(birth_date) >= 4 and len(death_date) >= 4:
                    birth_year = int(birth_date[-4:])
                    death_year = int(death_date[-4:])
                    age = death_year - birth_year
            except:
                age = 'Unknown'
        
        # Clean and extract summary
        summary = obituary.get('obituary_text', obituary.get('summary', obituary.get('content', '')))
        if summary:
            # Clean up summary (remove excessive whitespace, web elements)
            summary = ' '.join(summary.split())  # Normalize whitespace
            if len(summary) > 1000:
                # Truncate very long summaries but try to end at sentence
                summary = summary[:997]
                last_period = summary.rfind('.')
                if last_period > 800:
                    summary = summary[:last_period + 1]
                else:
                    summary += "..."
        
        # Standardize URL
        url = obituary.get('url', '')
        if url and not url.startswith('http'):
            url = 'https://' + url.lstrip('/')
        
        # Extract photo URL
        photo_url = obituary.get('photo_url', obituary.get('image_url', ''))
        
        # Build normalized obituary
        normalized = {
            "id": len(self.unified_data) + 1,
            "name": name,
            "funeral_home": funeral_home_name,
            "death_date": death_date or 'Unknown',
            "birth_date": birth_date or '',
            "age": str(age) if age else 'Unknown',
            "summary": summary,
            "photo_url": photo_url,
            "url": url,
            "scraped_at": obituary.get('scraped_date', obituary.get('scraped_at', datetime.now().isoformat())),
            "services": obituary.get('services', ''),
            "family": obituary.get('family', '')
        }
        
        return normalized

    def parse_all_data(self) -> Dict[str, Any]:
        """Parse all funeral home data files and create unified dataset."""
        
        print("📊 MASTER DATA PARSER")
        print("=" * 50)
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Process each funeral home file
        for filename, funeral_home_name in self.file_mappings.items():
            file_path = self.base_dir / filename
            
            print(f"🔄 Processing {funeral_home_name}...")
            
            obituaries = self.load_funeral_home_data(file_path, funeral_home_name)
            
            if obituaries:
                self.unified_data.extend(obituaries)
                self.funeral_home_stats[funeral_home_name] = len(obituaries)
                print(f"  ✅ Loaded {len(obituaries)} obituaries")
            else:
                print(f"  ⚠️  No obituaries found")
                self.funeral_home_stats[funeral_home_name] = 0
        
        # Sort obituaries by death date (most recent first)
        self.unified_data.sort(key=lambda x: x.get('death_date', ''), reverse=True)
        
        # Re-assign sequential IDs after sorting
        for i, obituary in enumerate(self.unified_data):
            obituary['id'] = i + 1
        
        # Create summary statistics
        summary = {
            "generated_at": datetime.now().isoformat(),
            "total_obituaries": len(self.unified_data),
            "funeral_homes": self.funeral_home_stats,
            "working_funeral_homes": len([h for h, count in self.funeral_home_stats.items() if count > 0]),
            "most_recent_obituary": self.unified_data[0]['death_date'] if self.unified_data else None,
            "date_range": self.get_date_range()
        }
        
        # Create final dataset
        unified_dataset = {
            "summary": summary,
            "obituaries": self.unified_data
        }
        
        self.print_summary()
        return unified_dataset

    def get_date_range(self) -> Dict[str, str]:
        """Get the date range of obituaries."""
        if not self.unified_data:
            return {"earliest": None, "latest": None}
        
        dates = [obit.get('death_date', '') for obit in self.unified_data if obit.get('death_date') and obit.get('death_date') != 'Unknown']
        
        if not dates:
            return {"earliest": None, "latest": None}
        
        return {
            "earliest": min(dates),
            "latest": max(dates)
        }

    def print_summary(self):
        """Print parsing summary."""
        
        print(f"\n📊 PARSING SUMMARY")
        print("=" * 50)
        print(f"📰 Total obituaries: {len(self.unified_data)}")
        print(f"🏠 Funeral homes with data: {len([h for h, count in self.funeral_home_stats.items() if count > 0])}")
        
        if self.unified_data:
            date_range = self.get_date_range()
            if date_range['earliest'] and date_range['latest']:
                print(f"📅 Date range: {date_range['earliest']} to {date_range['latest']}")
        
        print(f"\n📈 OBITUARIES BY FUNERAL HOME:")
        sorted_homes = sorted(self.funeral_home_stats.items(), key=lambda x: x[1], reverse=True)
        
        for home_name, count in sorted_homes:
            if count > 0:
                print(f"  ✅ {home_name}: {count} obituaries")
            else:
                print(f"  ⚠️  {home_name}: 0 obituaries")

    def save_unified_dataset(self, unified_dataset: Dict[str, Any]):
        """Save the unified dataset to files."""
        
        print(f"\n💾 SAVING UNIFIED DATASET")
        print("=" * 50)
        
        # Save complete dataset with metadata
        complete_file = self.base_dir / "website_obituaries.json"
        with open(complete_file, 'w', encoding='utf-8') as f:
            json.dump(unified_dataset, f, indent=2, ensure_ascii=False)
        print(f"✅ Complete dataset: {complete_file}")
        
        # Save obituaries-only file (for website integration)
        obituaries_file = self.base_dir / "obituaries_for_website.json"
        with open(obituaries_file, 'w', encoding='utf-8') as f:
            json.dump(unified_dataset['obituaries'], f, indent=2, ensure_ascii=False)
        print(f"✅ Obituaries only: {obituaries_file}")
        
        # Save detailed consolidated file (for analysis)
        detailed_file = self.base_dir / "obituaries_all_detailed.json"
        with open(detailed_file, 'w', encoding='utf-8') as f:
            json.dump(unified_dataset['obituaries'], f, indent=2, ensure_ascii=False)
        print(f"✅ Detailed analysis: {detailed_file}")
        
        # Calculate file sizes
        complete_size = complete_file.stat().st_size / 1024
        obituaries_size = obituaries_file.stat().st_size / 1024
        
        print(f"\n📊 File sizes:")
        print(f"  🗂️  Complete dataset: {complete_size:.1f} KB")
        print(f"  📄 Obituaries only: {obituaries_size:.1f} KB")
        
        print(f"\n🎉 SUCCESS! Unified dataset ready with {len(unified_dataset['obituaries'])} obituaries")

if __name__ == "__main__":
    parser = MasterDataParser()
    
    try:
        unified_dataset = parser.parse_all_data()
        parser.save_unified_dataset(unified_dataset)
        
        print(f"\n🎯 Next steps:")
        print(f"  🌐 Start website: py website_server.py")
        print(f"  📊 View analysis: py analyze_funeral_homes.py")
        
    except Exception as e:
        print(f"\n💥 Error during parsing: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
