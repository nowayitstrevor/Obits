"""
Simple startup script for the enhanced web UI with debug output.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from enhanced_web_ui import app

if __name__ == "__main__":
    print("Starting Enhanced Obituary Web UI...")
    print(f"Current directory: {os.getcwd()}")
    print("Server will be available at: http://localhost:5000")
    print("-" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=True)
