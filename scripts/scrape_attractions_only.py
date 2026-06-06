import os
import sys
import json
import glob
import time
from datetime import datetime

# Add scripts directory to path to import TourAPIClient from scrape_details
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scrape_details import TourAPIClient, TourAPIError

def fetch_detail_direct(client, content_id, content_type_id):
    """Fetches details for content_id and returns the merged dictionary."""
    # detailCommon2
    params_common = {
        "contentId": content_id,
    }
    common_data = client.request("detailCommon2", params_common)

    # detailIntro2
    params_intro = {"contentId": content_id, "contentTypeId": content_type_id}
    intro_data = client.request("detailIntro2", params_intro)

    common_items = common_data.get("response", {}).get("body", {}).get("items", {})
    intro_items = intro_data.get("response", {}).get("body", {}).get("items", {})

    common_item = common_items.get("item", {}) if isinstance(common_items, dict) else {}
    intro_item = intro_items.get("item", {}) if isinstance(intro_items, dict) else {}

    # Normalize list wrapper if list
    if isinstance(common_item, list) and len(common_item) > 0:
        common_item = common_item[0]
    if isinstance(intro_item, list) and len(intro_item) > 0:
        intro_item = intro_item[0]

    return {
        "common": common_item if common_item else {},
        "intro": intro_item if intro_item else {}
    }

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    list_dir = os.path.join(data_dir, "raw", "list_by_city")
    attraction_detail_dir = os.path.join(data_dir, "detail", "attraction")
    
    os.makedirs(attraction_detail_dir, exist_ok=True)
    
    # Find all city list files
    list_files = sorted(glob.glob(os.path.join(list_dir, "*_filtered.json")))
    if not list_files:
        print(f"Error: No city list files found in {list_dir}.")
        sys.exit(1)
        
    try:
        client = TourAPIClient()
    except Exception as e:
        print(f"Error initializing API client: {e}")
        sys.exit(1)
        
    quota_exhausted = False
    
    for idx, list_file in enumerate(list_files, 1):
        with open(list_file, "r", encoding="utf-8") as f:
            list_data = json.load(f)
            
        meta = list_data.get("meta", {})
        city_en = meta.get("city_name_en")
        city_ko = meta.get("city_name_ko")
        province = meta.get("province", "Unknown")
        
        # City-level attraction detail path
        city_detail_path = os.path.join(attraction_detail_dir, f"{city_en}_details.json")
        
        # Load existing details or initialize
        if os.path.exists(city_detail_path):
            with open(city_detail_path, "r", encoding="utf-8") as f:
                city_details = json.load(f)
        else:
            city_details = {
                "meta": {
                    "city_name_en": city_en,
                    "city_name_ko": city_ko,
                    "province": province,
                    "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "details": {}
            }
            
        attractions = list_data.get("attractions", [])
        # Filter out festivals (contentTypeId 15)
        attractions = [a for a in attractions if str(a.get("contenttypeid")) != "15"]
        
        if not attractions:
            continue
            
        # Determine which attractions are missing details
        missing_attractions = [a for a in attractions if str(a["contentid"]) not in city_details["details"]]
        
        if not missing_attractions:
            print(f"[{idx}/{len(list_files)}] {city_ko} ({city_en}) - All {len(attractions)} attractions already detailed.")
            continue
            
        print(f"\n[{idx}/{len(list_files)}] Processing {city_ko} ({city_en}): {len(missing_attractions)} / {len(attractions)} details missing.")
        
        success_count = 0
        for m_idx, attr in enumerate(missing_attractions, 1):
            content_id = str(attr["contentid"])
            content_type_id = attr["contenttypeid"]
            title = attr.get("title", "")
            
            print(f"  ({m_idx}/{len(missing_attractions)}) Querying detail for '{title}' (ID: {content_id})...")
            
            try:
                details = fetch_detail_direct(client, content_id, content_type_id)
                city_details["details"][content_id] = details
                city_details["meta"]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Write to file immediately after each success to prevent progress loss
                with open(city_detail_path, "w", encoding="utf-8") as f:
                    json.dump(city_details, f, ensure_ascii=False, indent=2)
                    
                success_count += 1
                import random
                time.sleep(random.uniform(0.2, 0.6))
                
            except TourAPIError as tae:
                print(f"    -> TourAPIError ({tae.code}): {tae.message}")
                if client.is_quota_limit_error(tae.code, tae.message):
                    print("[Halt] API Quota exhausted. Stopping scraper.")
                    quota_exhausted = True
                    break
                else:
                    # Record the logical error details to prevent querying this invalid ID again
                    city_details["details"][content_id] = {
                        "error": tae.code,
                        "message": tae.message,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    city_details["meta"]["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with open(city_detail_path, "w", encoding="utf-8") as f:
                        json.dump(city_details, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"    -> Unexpected error: {e}")
                # We do not record temporary system/network failures so we can retry them later

                
        if quota_exhausted:
            break
            
    print("\nDetail scraping run completed/paused.")

if __name__ == "__main__":
    main()
