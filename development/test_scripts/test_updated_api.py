"""
Test the updated /api/obituaries endpoint to verify it includes detailed obituaries.
"""

from enhanced_web_ui import app

def test_updated_api():
    with app.test_client() as client:
        print("Testing updated /api/obituaries endpoint...")
        response = client.get('/api/obituaries')
        data = response.get_json()
        
        print(f"Total obituaries: {data['total']}")
        print(f"Last updated: {data.get('last_updated', 'Unknown')}")
        
        if data['obituaries']:
            # Group by funeral home to see the breakdown
            funeral_homes = {}
            for obit in data['obituaries']:
                fh = obit.get('funeral_home', 'Unknown')
                funeral_homes[fh] = funeral_homes.get(fh, 0) + 1
            
            print("\nBreakdown by funeral home:")
            for fh, count in sorted(funeral_homes.items()):
                print(f"  {fh}: {count} obituaries")
            
            print("\nSample obituaries:")
            for i, obit in enumerate(data['obituaries'][:5]):
                print(f"  {i+1}. {obit['name']} - {obit['funeral_home']}")
        
        return data['total']

if __name__ == "__main__":
    count = test_updated_api()
    print(f"\nFinal result: {count} obituaries available in web UI")
