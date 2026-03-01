#!/usr/bin/env python3
"""
Repository cleanup script - Move development/debug files to organized folders
"""

import os
import shutil
from pathlib import Path

def organize_repository():
    """Organize the repository by moving development files to appropriate folders."""
    
    base_dir = Path("c:/Users/Noway/OneDrive/Documents/Obit Scraper")
    dev_dir = base_dir / "development"
    
    print("🧹 ORGANIZING OBITUARY SCRAPER REPOSITORY")
    print("=" * 50)
    
    # Define file categories and their destinations
    file_moves = {
        # Debug scripts
        "development/debug_scripts": [
            "debug_aderhold.py",
            "debug_funeral_home.py", 
            "debug_grace_gardens.py",
            "debug_oak_crest.py",
            "debug_obituaries.py",
            "debug_page_structure.py",
            "debug_pecan_grove.py",
            "debug_single_scraper.py",
            "debug_waco_fhmp.py",
            "debug_whb.py",
            "diagnose_scraping.py",
            "show_grace_gardens_obits.py"
        ],
        
        # Test scripts  
        "development/test_scripts": [
            "test_aderhold_fix.py",
            "test_aderhold_headers.py",
            "test_api_scraper.py",
            "test_date_extraction.py",
            "test_detailed_api.py",
            "test_enhanced_configs.py",
            "test_final_configs.py",
            "test_firefox.py",
            "test_grace_gardens_selenium.py",
            "test_grace_obituaries.py",
            "test_individual_obituary.py",
            "test_lakeshore.py",
            "test_lakeshore_selenium.py",
            "test_pecan_grove.py",
            "test_pecan_grove_obituaries.py",
            "test_problematic_sites.py",
            "test_scraper.py",
            "test_selenium.py",
            "test_slctx_improved.py",
            "test_tukios_selenium.py",
            "test_updated_api.py",
            "test_waco_access.py",
            "test_whb_endpoints.py",
            "test_whb_scrape.py",
            "test_whb_simple.py",
            "simple_selenium_test.py",
            "quick_grace_test.py",
            "quick_test.py",
            "quick_test_lakeshore.py",
            "run_scraper_test.py"
        ],
        
        # HTML debug files
        "development/html_debug": [
            "debug_page_source.html",
            "firefox_page_source.html",
            "grace_gardens_funeral_home_debug.html",
            "grace_gardens_funeral_home_selenium_debug.html",
            "grace_gardens_obituaries.html",
            "grace_gardens_selenium_debug.html",
            "lakeshore_debug.html",
            "oak_crest_funeral_home_selenium_debug.html",
            "pecan_grove_funeral_home_selenium_debug.html",
            "vernon_hoppe_debug.html",
            "waco_funeral_home_memorial_park_selenium_debug.html",
            "whb_family_funeral_home_debug.html",
            "whb_family_funeral_home_selenium_debug.html",
            "whb_obituaries_debug.html",
            "whb_obituaries_page.html"
        ],
        
        # Archived/experimental scripts
        "development/archived_data": [
            "analyze_failing_pages.py",
            "analyze_waco_deep.py",
            "analyze_whb_dynamic.py",
            "auto_resolve_flags.py",
            "check_whb_sitemap.py", 
            "cleanup_flagged_issues.py",
            "cleanup_not_obituary.py",
            "deep_analyze_slctx.py",
            "demo.py",
            "enhanced_configs.json",
            "find_api.py",
            "fix_slctx_config.py",
            "get_flag_summary.py",
            "inspect_whb_structure.py",
            "obituary_flags.json_backup",
            "obituaries_all_detailed.json_backup",
            "sample_detailed_data.json",
            "verify_web_ui.py",
            "website_analyzer.py",
            "analysis_www_slctx_com_listings.json",
            "analysis_www_wacofhmp_com_obituaries.json"
        ]
    }
    
    # Track what gets moved
    moved_files = 0
    skipped_files = []
    
    # Move files to their designated folders
    for dest_folder, files in file_moves.items():
        dest_path = base_dir / dest_folder
        dest_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\n📁 Moving files to {dest_folder}:")
        
        for filename in files:
            source_file = base_dir / filename
            dest_file = dest_path / filename
            
            if source_file.exists():
                try:
                    shutil.move(str(source_file), str(dest_file))
                    print(f"  ✅ {filename}")
                    moved_files += 1
                except Exception as e:
                    print(f"  ❌ {filename} - Error: {e}")
                    skipped_files.append(filename)
            else:
                print(f"  ⚠️  {filename} - File not found")
                skipped_files.append(filename)
    
    print(f"\n📊 CLEANUP SUMMARY:")
    print(f"  ✅ Files moved: {moved_files}")
    print(f"  ⚠️  Files skipped: {len(skipped_files)}")
    
    # Show remaining production files
    print(f"\n🚀 PRODUCTION FILES REMAINING:")
    production_files = [
        "funeral_homes_config.json",
        "scrape_obituaries_detailed.py", 
        "generic_selenium_scraper.py",
        "enhanced_generic_scraper.py",
        "scrape_generic_obituaries.py",
        "analyze_funeral_homes.py",
        "bundle_for_website.py",
        "website_server.py",
        "website_preview.html",
        "aggregate_obituaries.py"
    ]
    
    for filename in production_files:
        file_path = base_dir / filename
        if file_path.exists():
            print(f"  ✅ {filename}")
        else:
            print(f"  ❌ {filename} - MISSING!")
    
    # Show data files
    print(f"\n💾 DATA FILES:")
    data_files = list(base_dir.glob("obituaries_*.json"))
    data_files.extend(list(base_dir.glob("website_*.json")))
    data_files.extend(list(base_dir.glob("*.json")))
    
    for file_path in sorted(data_files):
        if file_path.name not in ["enhanced_configs.json"]:  # Skip moved files
            size_kb = file_path.stat().st_size / 1024
            print(f"  📄 {file_path.name} ({size_kb:.1f} KB)")
    
    print(f"\n🎉 Repository cleanup complete!")
    print(f"   📁 Development files organized in ./development/")
    print(f"   🚀 Production files remain in root directory")

if __name__ == "__main__":
    organize_repository()
