"""
Direct runner for the detailed obituary scraper to test the system.
"""

import subprocess
import sys
import os
from pathlib import Path

def run_detailed_scraper():
    """Run the detailed obituary scraper and return results."""
    
    # Get the project directory and Python executable
    project_dir = Path(r"c:\Users\Noway\OneDrive\Documents\Obit Scraper")
    python_exe = project_dir / ".venv" / "Scripts" / "python.exe"
    scraper_script = project_dir / "scrape_obituaries_detailed.py"
    
    print(f"🔄 Running detailed obituary scraper...")
    print(f"📁 Project directory: {project_dir}")
    print(f"🐍 Python executable: {python_exe}")
    print(f"📜 Scraper script: {scraper_script}")
    print("=" * 60)
    
    try:
        # Change to project directory
        original_dir = os.getcwd()
        os.chdir(project_dir)
        
        # Run the scraper
        result = subprocess.run(
            [str(python_exe), str(scraper_script)],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        print("📤 SCRAPER OUTPUT:")
        print("-" * 40)
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("⚠️ ERRORS/WARNINGS:")
            print("-" * 40)
            print(result.stderr)
        
        print(f"\n✅ Return code: {result.returncode}")
        
        # Check if output file was created
        output_file = project_dir / "obituaries_detailed.json"
        if output_file.exists():
            print(f"📄 Output file created: {output_file}")
            print(f"📊 File size: {output_file.stat().st_size} bytes")
        else:
            print("❌ No output file found")
        
        return result.returncode == 0
        
    except subprocess.TimeoutExpired:
        print("❌ Scraper timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Error running scraper: {e}")
        return False
    finally:
        # Restore original directory
        os.chdir(original_dir)

if __name__ == "__main__":
    success = run_detailed_scraper()
    if success:
        print("\n🎉 Scraper completed successfully!")
    else:
        print("\n💥 Scraper failed or encountered errors")
