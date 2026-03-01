#!/usr/bin/env python3
"""
Master Scraper Orchestrator
Runs all individual funeral home scrapers and consolidates results
"""

import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
import concurrent.futures
from typing import Dict, List, Any

class FuneralHomeScrapeOrchestrator:
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.individual_scrapers_dir = self.base_dir / "individual_scrapers"
        self.results = {}
        
        # Configuration for each funeral home
        self.funeral_homes = {
            "foss": {
                "name": "Foss Funeral Home",
                "script": "scrape_foss.py",
                "output_file": "obituaries_fossfuneralhome.json",
                "active": True,
                "priority": 1
            },
            "robertson": {
                "name": "Robertson Funeral Home", 
                "script": "scrape_robertson.py",
                "output_file": "obituaries_robertsonfh.json",
                "active": True,
                "priority": 2
            },
            "slctx": {
                "name": "SLC Texas Funeral Services",
                "script": "scrape_slctx.py", 
                "output_file": "obituaries_slctx.json",
                "active": True,
                "priority": 3
            },
            "mcdowell": {
                "name": "McDowell Funeral Home",
                "script": "scrape_mcdowell.py",
                "output_file": "obituaries_mcdowellfuneralhome.json", 
                "active": True,
                "priority": 4
            },
            "gracegardens": {
                "name": "Grace Gardens Funeral Home",
                "script": "scrape_gracegardens.py",
                "output_file": "obituaries_gracegardensfh.json",
                "active": True,
                "priority": 5
            },
            "lakeshore": {
                "name": "Lake Shore Funeral Home",
                "script": "scrape_lakeshore.py",
                "output_file": "obituaries_lakeshore.json",
                "active": False,  # Enable when ready
                "priority": 6
            },
            "aderhold": {
                "name": "Aderhold Funeral Home", 
                "script": "scrape_aderhold.py",
                "output_file": "obituaries_aderholdfuneralhome.json",
                "active": False,  # Enable when ready
                "priority": 7
            }
        }

    def run_single_scraper(self, funeral_home_key: str, config: Dict) -> Dict:
        """Run a single funeral home scraper."""
        start_time = time.time()
        
        print(f"🔄 Starting {config['name']}...")
        
        try:
            script_path = self.individual_scrapers_dir / config['script']
            
            if not script_path.exists():
                return {
                    "funeral_home": config['name'],
                    "success": False,
                    "error": f"Script not found: {config['script']}",
                    "duration": 0,
                    "obituaries_count": 0
                }
            
            # Run the individual scraper
            result = subprocess.run([
                sys.executable, str(script_path)
            ], capture_output=True, text=True, timeout=300)  # 5 minute timeout
            
            duration = time.time() - start_time
            
            # Check if output file was created/updated
            output_file = self.base_dir / config['output_file']
            obituaries_count = 0
            
            if output_file.exists():
                try:
                    with open(output_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict) and "obituaries" in data:
                            obituaries_count = len(data["obituaries"])
                        elif isinstance(data, list):
                            obituaries_count = len(data)
                except Exception as e:
                    print(f"  ⚠️  Could not count obituaries: {e}")
            
            success = result.returncode == 0
            
            if success:
                print(f"  ✅ {config['name']}: {obituaries_count} obituaries ({duration:.1f}s)")
            else:
                print(f"  ❌ {config['name']}: Failed ({duration:.1f}s)")
                if result.stderr:
                    print(f"     Error: {result.stderr[:200]}...")
            
            return {
                "funeral_home": config['name'],
                "success": success,
                "duration": duration,
                "obituaries_count": obituaries_count,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            print(f"  ⏰ {config['name']}: Timeout after {duration:.1f}s")
            return {
                "funeral_home": config['name'],
                "success": False,
                "error": "Script timeout (>5 minutes)",
                "duration": duration,
                "obituaries_count": 0
            }
        except Exception as e:
            duration = time.time() - start_time
            print(f"  ❌ {config['name']}: Exception - {e}")
            return {
                "funeral_home": config['name'],
                "success": False,
                "error": str(e),
                "duration": duration,
                "obituaries_count": 0
            }

    def run_all_scrapers(self, parallel: bool = True, max_workers: int = 3):
        """Run all active funeral home scrapers."""
        
        print("🚀 FUNERAL HOME SCRAPER ORCHESTRATOR")
        print("=" * 60)
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Get active funeral homes sorted by priority
        active_homes = {
            k: v for k, v in self.funeral_homes.items() 
            if v.get('active', True)
        }
        
        sorted_homes = sorted(
            active_homes.items(), 
            key=lambda x: x[1].get('priority', 999)
        )
        
        print(f"📊 Running {len(sorted_homes)} active funeral home scrapers")
        
        start_time = time.time()
        
        if parallel and len(sorted_homes) > 1:
            print(f"⚡ Running in parallel (max {max_workers} workers)")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_home = {
                    executor.submit(self.run_single_scraper, key, config): key
                    for key, config in sorted_homes
                }
                
                for future in concurrent.futures.as_completed(future_to_home):
                    home_key = future_to_home[future]
                    try:
                        result = future.result()
                        self.results[home_key] = result
                    except Exception as e:
                        print(f"❌ Exception in {home_key}: {e}")
                        self.results[home_key] = {
                            "funeral_home": self.funeral_homes[home_key]['name'],
                            "success": False,
                            "error": str(e),
                            "duration": 0,
                            "obituaries_count": 0
                        }
        else:
            print("🔄 Running sequentially")
            for key, config in sorted_homes:
                result = self.run_single_scraper(key, config)
                self.results[key] = result
        
        total_duration = time.time() - start_time
        
        # Generate summary
        self.print_summary(total_duration)
        return self.results

    def print_summary(self, total_duration: float):
        """Print execution summary."""
        
        print("\n📊 SCRAPING SUMMARY")
        print("=" * 60)
        
        successful = [r for r in self.results.values() if r['success']]
        failed = [r for r in self.results.values() if not r['success']]
        total_obituaries = sum(r['obituaries_count'] for r in successful)
        
        print(f"✅ Successful: {len(successful)}")
        print(f"❌ Failed: {len(failed)}")
        print(f"📰 Total obituaries: {total_obituaries}")
        print(f"⏱️  Total time: {total_duration:.1f} seconds")
        
        if successful:
            print(f"\n✅ SUCCESSFUL FUNERAL HOMES:")
            for result in sorted(successful, key=lambda x: x['obituaries_count'], reverse=True):
                print(f"  📊 {result['funeral_home']}: {result['obituaries_count']} obituaries ({result['duration']:.1f}s)")
        
        if failed:
            print(f"\n❌ FAILED FUNERAL HOMES:")
            for result in failed:
                error = result.get('error', 'Unknown error')[:50]
                print(f"  🚨 {result['funeral_home']}: {error}")
        
        print(f"\n🎯 Next: Run 'py parse_all_data.py' to consolidate into unified dataset")

    def save_execution_log(self):
        """Save execution results to log file."""
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "results": self.results,
            "summary": {
                "total_funeral_homes": len(self.results),
                "successful": len([r for r in self.results.values() if r['success']]),
                "failed": len([r for r in self.results.values() if not r['success']]),
                "total_obituaries": sum(r['obituaries_count'] for r in self.results.values() if r['success'])
            }
        }
        
        log_file = self.base_dir / "scraper_execution_log.json"
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(log_data, f, indent=2, ensure_ascii=False)
        
        print(f"📝 Execution log saved to: {log_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Run all funeral home scrapers")
    parser.add_argument("--sequential", action="store_true", help="Run scrapers sequentially instead of parallel")
    parser.add_argument("--workers", type=int, default=3, help="Number of parallel workers (default: 3)")
    
    args = parser.parse_args()
    
    orchestrator = FuneralHomeScrapeOrchestrator()
    
    try:
        results = orchestrator.run_all_scrapers(
            parallel=not args.sequential,
            max_workers=args.workers
        )
        orchestrator.save_execution_log()
        
        # Return appropriate exit code
        failed_count = len([r for r in results.values() if not r['success']])
        sys.exit(1 if failed_count > 0 else 0)
        
    except KeyboardInterrupt:
        print("\n⏹️  Scraping interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Fatal error: {e}")
        sys.exit(1)
