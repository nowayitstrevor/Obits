#!/usr/bin/env python3
"""
Simple API server to serve obituary data for the website
"""

from flask import Flask, jsonify
from flask_cors import CORS
import json
import os
import threading
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)  # Enable CORS for web requests
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SCRAPE_STATUS = {
    "state": "idle",
    "message": "No scrape started yet.",
    "startedAt": None,
    "finishedAt": None,
    "totalSources": 0,
    "completedSources": 0,
    "currentSourceKey": None,
    "currentSourceName": None,
    "safeMode": False,
    "skippedSources": 0,
    "totalObituaries": 0,
    "sources": [],
}
SCRAPE_LOCK = threading.Lock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_scrape_status(updates: dict) -> None:
    with SCRAPE_LOCK:
        SCRAPE_STATUS.update(updates)


def _build_initial_source_status(sources: dict[str, dict]) -> list[dict]:
    items: list[dict] = []
    for source_key, config in sources.items():
        items.append(
            {
                "sourceKey": source_key,
                "sourceName": config.get("name", source_key),
                "status": "pending",
                "obituariesScraped": 0,
                "durationMs": 0,
                "error": None,
            }
        )
    return items


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_falsy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"0", "false", "no", "off"}


def is_railway_environment() -> bool:
    return bool(os.environ.get("RAILWAY_PROJECT_ID") or os.environ.get("RAILWAY_ENVIRONMENT"))


def is_scraper_safe_mode_enabled() -> bool:
    configured = os.environ.get("SCRAPER_SAFE_MODE")
    if _is_truthy(configured):
        return True
    if _is_falsy(configured):
        return False
    return is_railway_environment()


def split_sources_for_safe_mode(all_sources: dict[str, dict], safe_mode: bool) -> tuple[dict[str, dict], list[dict], set[str]]:
    runnable_sources: dict[str, dict] = {}
    status_items: list[dict] = []
    skipped_keys: set[str] = set()

    for source_key, config in all_sources.items():
        source_name = config.get("name", source_key)
        scraper_type = str(config.get("scraper_type", "")).lower()
        if safe_mode and scraper_type == "selenium":
            skipped_keys.add(source_key)
            status_items.append(
                {
                    "sourceKey": source_key,
                    "sourceName": source_name,
                    "status": "skipped",
                    "obituariesScraped": 0,
                    "durationMs": 0,
                    "error": "Skipped in safe mode (selenium source).",
                }
            )
            continue

        runnable_sources[source_key] = config
        status_items.append(
            {
                "sourceKey": source_key,
                "sourceName": source_name,
                "status": "pending",
                "obituariesScraped": 0,
                "durationMs": 0,
                "error": None,
            }
        )

    return runnable_sources, status_items, skipped_keys


def load_previous_selected_records(selected_scraper) -> list:
    output_path = selected_scraper.OUTPUT_PATH
    if not output_path.exists():
        return []

    try:
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    records: list = []
    for item in payload.get("obituaries", []):
        if not isinstance(item, dict):
            continue
        try:
            records.append(selected_scraper.ObituaryRecord(**item))
        except Exception:
            continue
    return records


def merge_records_with_previous(new_records: list, previous_records: list, refreshed_source_keys: set[str]) -> list:
    merged = list(new_records)
    for item in previous_records:
        source_key = getattr(item, "sourceKey", None)
        if source_key in refreshed_source_keys:
            continue
        merged.append(item)
    return merged


def run_scrape_job() -> None:
    try:
        import scrape_selected_obituaries as selected_scraper
        import bundle_for_website

        all_sources = selected_scraper.load_selected_sources(include_inactive=False, source_keys=None)
        safe_mode = is_scraper_safe_mode_enabled()
        sources, source_status, skipped_keys = split_sources_for_safe_mode(all_sources, safe_mode=safe_mode)
        skipped_count = len(skipped_keys)
        started_message = "Preparing sources in safe mode..." if safe_mode else "Preparing sources..."
        _set_scrape_status(
            {
                "state": "running",
                "message": started_message,
                "startedAt": now_iso(),
                "finishedAt": None,
                "totalSources": len(source_status),
                "completedSources": skipped_count,
                "currentSourceKey": None,
                "currentSourceName": None,
                "safeMode": safe_mode,
                "skippedSources": skipped_count,
                "totalObituaries": 0,
                "sources": source_status,
            }
        )

        all_records: list = []
        all_results: list = []

        for index, (source_key, config) in enumerate(sources.items()):
            source_name = config.get("name", source_key)
            _set_scrape_status(
                {
                    "message": f"Scraping {source_name}...",
                    "currentSourceKey": source_key,
                    "currentSourceName": source_name,
                }
            )

            source_records, source_result = selected_scraper.scrape_source(
                source_key,
                config,
                max_obituaries=selected_scraper.MAX_OBITUARIES_PER_SOURCE,
            )
            source_records = selected_scraper.filter_records_to_lookback(
                source_records,
                lookback_days=selected_scraper.DEFAULT_LOOKBACK_DAYS,
            )
            source_result.obituariesScraped = len(source_records)
            if source_result.status == "ok" and not source_records:
                source_result.status = "no-data"

            all_records.extend(source_records)
            all_results.append(source_result)

            with SCRAPE_LOCK:
                for item in SCRAPE_STATUS["sources"]:
                    if item["sourceKey"] != source_key:
                        continue
                    item["status"] = source_result.status
                    item["obituariesScraped"] = source_result.obituariesScraped
                    item["durationMs"] = source_result.durationMs
                    item["error"] = source_result.error
                    break
                SCRAPE_STATUS["completedSources"] = skipped_count + index + 1
                SCRAPE_STATUS["totalObituaries"] = len(all_records)

        refreshed_keys = set(sources.keys())
        previous_records = load_previous_selected_records(selected_scraper)
        merged_records = merge_records_with_previous(all_records, previous_records, refreshed_source_keys=refreshed_keys)

        for source_key in skipped_keys:
            source_name = all_sources.get(source_key, {}).get("name", source_key)
            all_results.append(
                selected_scraper.SourceScrapeResult(
                    source=source_name,
                    sourceKey=source_key,
                    status="skipped",
                    listingUrl=str(all_sources.get(source_key, {}).get("obituaries_url", "")),
                    pagesDiscovered=0,
                    obituariesScraped=0,
                    durationMs=0,
                    error="Skipped in safe mode (selenium source).",
                )
            )

        selected_scraper.write_output(merged_records, all_results)
        bundle_for_website.create_unified_dataset()

        mode_suffix = " (safe mode)" if safe_mode else ""

        _set_scrape_status(
            {
                "state": "completed",
                "message": f"Scrape and bundle complete{mode_suffix}.",
                "finishedAt": now_iso(),
                "currentSourceKey": None,
                "currentSourceName": None,
                "totalObituaries": len(merged_records),
            }
        )
    except Exception as error:
        _set_scrape_status(
            {
                "state": "error",
                "message": f"Scrape failed: {error}",
                "finishedAt": now_iso(),
                "currentSourceKey": None,
                "currentSourceName": None,
            }
        )

# Load the obituary data
def load_obituary_data():
    """Load the unified obituary dataset."""
    try:
        data_path = os.path.join(BASE_DIR, 'website_obituaries.json')
        with open(data_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Obituary data not found. Please run bundle_for_website.py first."}

@app.route('/')
def index():
    """Serve the main website page."""
    try:
        html_path = os.path.join(BASE_DIR, 'website_preview.html')
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        return html_content
    except FileNotFoundError:
        return """
        <h1>Obituary Website</h1>
        <p>HTML preview file not found. Please ensure website_preview.html exists.</p>
        <p><a href="/api/obituaries">View API Data</a></p>
        """

@app.route('/api/obituaries')
def get_obituaries():
    """API endpoint to get all obituaries."""
    data = load_obituary_data()
    return jsonify(data)

@app.route('/api/obituaries/recent')
def get_recent_obituaries():
    """API endpoint to get recent obituaries (last 20)."""
    data = load_obituary_data()
    if "obituaries" in data:
        recent = data["obituaries"][:20]  # Already sorted by date
        return jsonify({
            "summary": data.get("summary", {}),
            "obituaries": recent,
            "count": len(recent)
        })
    return jsonify(data)

@app.route('/api/funeral-homes')
def get_funeral_homes():
    """API endpoint to get funeral home statistics."""
    data = load_obituary_data()
    if "summary" in data and "funeral_homes" in data["summary"]:
        return jsonify(data["summary"]["funeral_homes"])
    return jsonify({"error": "No funeral home data found"})

@app.route('/api/obituaries/funeral-home/<home_name>')
def get_obituaries_by_home(home_name):
    """API endpoint to get obituaries for a specific funeral home."""
    data = load_obituary_data()
    if "obituaries" in data:
        filtered = [obit for obit in data["obituaries"] if obit.get("funeral_home") == home_name]
        return jsonify({
            "funeral_home": home_name,
            "obituaries": filtered,
            "count": len(filtered)
        })
    return jsonify({"error": "No obituary data found"})

@app.route('/api/status')
def get_status():
    """API endpoint to get system status."""
    data = load_obituary_data()
    if "summary" in data:
        summary = data["summary"]
        return jsonify({
            "status": "active",
            "total_obituaries": summary.get("total_obituaries", 0),
            "working_funeral_homes": summary.get("working_funeral_homes", 0),
            "last_updated": summary.get("generated_at", "Unknown"),
            "funeral_homes": summary.get("funeral_homes", {})
        })
    return jsonify({"status": "error", "message": "Data not available"})


@app.route('/api/scrape/status')
def get_scrape_status():
    with SCRAPE_LOCK:
        return jsonify(dict(SCRAPE_STATUS))


@app.route('/api/scrape/start', methods=['POST'])
def start_scrape():
    with SCRAPE_LOCK:
        if SCRAPE_STATUS.get("state") == "running":
            return jsonify({"error": "Scrape already running", "status": dict(SCRAPE_STATUS)}), 409
        SCRAPE_STATUS.update(
            {
                "state": "running",
                "message": "Starting scrape...",
                "startedAt": now_iso(),
                "finishedAt": None,
                "totalSources": 0,
                "completedSources": 0,
                "currentSourceKey": None,
                "currentSourceName": None,
                "safeMode": False,
                "skippedSources": 0,
                "totalObituaries": 0,
                "sources": [],
            }
        )

    worker = threading.Thread(target=run_scrape_job, daemon=True)
    worker.start()
    return jsonify({"ok": True, "message": "Scrape started"})

if __name__ == '__main__':
    print("🌐 Starting Obituary Website Server...")
    print("=" * 50)
    
    # Check if data files exist
    data_path = os.path.join(BASE_DIR, 'website_obituaries.json')
    if os.path.exists(data_path):
        data = load_obituary_data()
        if "summary" in data:
            summary = data["summary"]
            print(f"📊 Loaded {summary.get('total_obituaries', 0)} obituaries")
            print(f"🏠 From {summary.get('working_funeral_homes', 0)} funeral homes")
            print(f"📅 Last updated: {summary.get('generated_at', 'Unknown')}")
        print("✅ Data loaded successfully!")
    else:
        print("⚠️  website_obituaries.json not found")
        print("   Run 'py bundle_for_website.py' first to create the dataset")
    
    print("\n🚀 Server starting...")
    port = int(os.environ.get('PORT', 5000))
    print(f"   📱 Website: http://localhost:{port}")
    print(f"   🔗 API: http://localhost:{port}/api/obituaries")
    print(f"   📊 Status: http://localhost:{port}/api/status")
    print("\n   Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        app.run(debug=False, host='0.0.0.0', port=port)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        print("💡 You may need to install Flask: pip install flask flask-cors")
