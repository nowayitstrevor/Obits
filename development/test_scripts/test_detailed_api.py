"""
Quick test of the new detailed obituaries API endpoint.
"""

from enhanced_web_ui import app

def test_detailed_api():
    with app.test_client() as client:
        response = client.get('/api/obituaries/detailed')
        data = response.get_json()
        
        print(f"API Response: {data['total']} obituaries")
        print(f"Source file: {data.get('source_file', 'Unknown')}")
        print(f"Last updated: {data.get('last_updated', 'Unknown')}")
        
        if data['obituaries']:
            print("\nSample obituaries:")
            for i, obit in enumerate(data['obituaries'][:5]):
                print(f"  {i+1}. {obit['name']} - {obit['funeral_home']}")
        
        # Test with funeral home filter
        print("\n" + "="*50)
        print("Testing with SLC Texas filter:")
        response = client.get('/api/obituaries/detailed?funeral_home=slc')
        filtered_data = response.get_json()
        print(f"Filtered results: {filtered_data['total']} obituaries")
        
        if filtered_data['obituaries']:
            for obit in filtered_data['obituaries'][:3]:
                print(f"  - {obit['name']} ({obit['funeral_home']})")

if __name__ == "__main__":
    test_detailed_api()
