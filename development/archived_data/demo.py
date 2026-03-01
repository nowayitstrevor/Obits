"""
Quick demo script to show the Waco Obituary Aggregator system in action.

This script will:
1. Run the detailed scraper to get obituary information
2. Display the results in a summary format
3. Show instructions for running the web UI
"""

import subprocess
import json
import os
import sys
from datetime import datetime

def run_command(command, description):
    """Run a command and return the result."""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=180)
        
        if result.stdout:
            print("📝 Output:")
            print(result.stdout)
        
        if result.stderr:
            print("⚠️ Errors/Warnings:")
            print(result.stderr)
        
        return result.returncode == 0, result.stdout, result.stderr
    
    except subprocess.TimeoutExpired:
        print("❌ Command timed out after 3 minutes")
        return False, "", "Timeout"
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False, "", str(e)

def display_obituary_summary():
    """Display a summary of collected obituaries."""
    print(f"\n{'='*60}")
    print("📊 OBITUARY SUMMARY")
    print(f"{'='*60}")
    
    # Check basic storage
    basic_file = "seen_obituaries.json"
    detailed_file = "obituaries_detailed.json"
    
    basic_count = 0
    detailed_count = 0
    
    if os.path.exists(basic_file):
        try:
            with open(basic_file, 'r') as f:
                data = json.load(f)
                basic_count = len(data.get('seen_ids', []))
        except:
            pass
    
    if os.path.exists(detailed_file):
        try:
            with open(detailed_file, 'r') as f:
                data = json.load(f)
                detailed_count = len(data.get('obituaries', {}))
                
                print(f"📈 Total detailed obituaries: {detailed_count}")
                print(f"📅 Last updated: {data.get('last_updated', 'Unknown')}")
                
                if detailed_count > 0:
                    print(f"\n📝 Recent obituaries:")
                    
                    # Show the 5 most recent
                    obituaries = list(data['obituaries'].values())
                    # Sort by scraped_at if available
                    obituaries.sort(key=lambda x: x.get('scraped_at', ''), reverse=True)
                    
                    for i, obit in enumerate(obituaries[:5], 1):
                        name = obit.get('name', 'Unknown')
                        age = f" (Age {obit['age']})" if obit.get('age') else ""
                        death_date = f" - {obit['death_date']}" if obit.get('death_date') else ""
                        print(f"   {i}. {name}{age}{death_date}")
                
        except Exception as e:
            print(f"❌ Error reading detailed file: {e}")
    
    print(f"📊 Basic tracker: {basic_count} obituaries")
    print(f"📊 Detailed tracker: {detailed_count} obituaries")

def main():
    """Run the demo."""
    print("🏠 WACO AREA OBITUARY AGGREGATOR - DEMO")
    print("=" * 60)
    print("This demo will show you the obituary scraping system in action.")
    print("We'll scrape Lake Shore Funeral Home and display the results.")
    
    # Get the python executable path
    python_exe = r"C:/Users/Noway/OneDrive/Documents/Obit Scraper/.venv/Scripts/python.exe"
    
    # Test 1: Run the detailed scraper
    success, output, error = run_command(
        f'"{python_exe}" scrape_obituaries_detailed.py',
        "Running detailed obituary scraper for Lake Shore Funeral Home"
    )
    
    if not success:
        print("❌ Detailed scraper failed. Let's try the basic scraper...")
        
        # Fallback to basic scraper
        success, output, error = run_command(
            f'"{python_exe}" scrape_obituaries_firefox.py',
            "Running basic obituary scraper as fallback"
        )
    
    # Display summary of what we found
    display_obituary_summary()
    
    # Instructions for web UI
    print(f"\n{'='*60}")
    print("🌐 WEB INTERFACE INSTRUCTIONS")
    print(f"{'='*60}")
    print("To start the web interface:")
    print("1. Double-click 'start_web_ui.bat' (easier)")
    print("   OR")
    print("2. Run manually:")
    print(f'   "{python_exe}" web_ui.py')
    print("")
    print("Then open your browser to: http://localhost:5000")
    print("")
    print("Features you can try:")
    print("• View all collected obituaries with details")
    print("• Scrape individual funeral homes")
    print("• Use 'Scrape All' to update everything")
    print("• View detailed logs of scraping operations")
    
    print(f"\n{'='*60}")
    print("✅ DEMO COMPLETE")
    print(f"{'='*60}")
    print("The system is ready to use! Check the README.md for full documentation.")

if __name__ == "__main__":
    main()
