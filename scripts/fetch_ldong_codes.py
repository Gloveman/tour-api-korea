import os
import requests
import json
import sys

# Load env variables manually to avoid dependency on python-dotenv
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    if '=' in line:
                        key, val = line.split('=', 1)
                        os.environ[key.strip()] = val.strip()

load_env()
SERVICE_KEY = os.getenv("TOUR_API_KEY")
if not SERVICE_KEY:
    print("Error: TOUR_API_KEY not found in .env")
    sys.exit(1)

BASE_URL = "http://apis.data.go.kr/B551011/KorService2"

# Standard Sido mappings
TARGET_SIDOS = {
    "강원특별자치도": "51",
    "경상북도": "47"
}

def fetch_sigungu_codes(sido_name, sido_code):
    print(f"Fetching legal dong codes for {sido_name} ({sido_code})...")
    params = {
        "serviceKey": SERVICE_KEY,
        "MobileOS": "ETC",
        "MobileApp": "TourApp",
        "_type": "json",
        "numOfRows": 200,
        "pageNo": 1,
        "lDongRegnCd": sido_code,
        "lDongListYn": "Y"
    }
    
    try:
        r = requests.get(f"{BASE_URL}/ldongCode2", params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        
        header = data.get("response", {}).get("header", {})
        if header.get("resultCode") != "0000":
            print(f"API Error for {sido_name}: {header.get('resultMsg')}")
            return []
            
        body = data.get("response", {}).get("body", {})
        items_container = body.get("items")
        if not items_container or not items_container.get("item"):
            print(f"No items found for {sido_name}")
            return []
            
        items = items_container["item"]
        if not isinstance(items, list):
            items = [items]
            
        print(f"Successfully fetched {len(items)} items for {sido_name}")
        return items
    except Exception as e:
        print(f"Request failed for {sido_name}: {e}")
        return []

def main():
    all_items = []
    for sido_name, sido_code in TARGET_SIDOS.items():
        items = fetch_sigungu_codes(sido_name, sido_code)
        all_items.extend(items)
        
    output_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
    os.makedirs(output_dir, exist_ok=True)
    
    output_path = os.path.join(output_dir, 'ldong_sigungu.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_items, f, ensure_ascii=False, indent=2)
        
    print(f"Saved {len(all_items)} sigungu codes to {output_path}")

if __name__ == "__main__":
    main()
