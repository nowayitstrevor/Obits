#!/usr/bin/env python3
"""
Simple API server to serve obituary data for the website
"""

from flask import Flask, jsonify, render_template_string
from flask_cors import CORS
import json
import os

app = Flask(__name__)
CORS(app)  # Enable CORS for web requests

# Load the obituary data
def load_obituary_data():
    """Load the unified obituary dataset."""
    try:
        with open('website_obituaries.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"error": "Obituary data not found. Please run bundle_for_website.py first."}

@app.route('/')
def index():
    """Serve the main website page."""
    try:
        with open('website_preview.html', 'r', encoding='utf-8') as f:
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

if __name__ == '__main__':
    print("🌐 Starting Obituary Website Server...")
    print("=" * 50)
    
    # Check if data files exist
    if os.path.exists('website_obituaries.json'):
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
    print("   📱 Website: http://localhost:5000")
    print("   🔗 API: http://localhost:5000/api/obituaries")
    print("   📊 Status: http://localhost:5000/api/status")
    print("\n   Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        print(f"\n❌ Server error: {e}")
        print("💡 You may need to install Flask: pip install flask flask-cors")
