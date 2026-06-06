import os
import sys
import json
import glob
import time
from datetime import datetime

# Add scripts directory to path to import TourAPIClient from scrape_details
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from scrape_details import TourAPIClient, TourAPIError

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    list_dir = os.path.join(data_dir, "raw", "list_by_city")
    festival_dir = os.path.join(data_dir, "detail", "festival")
    
    os.makedirs(festival_dir, exist_ok=True)
    
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
        
    # Gather all festivals across all cities
    festivals_to_scrape = []
    for list_file in list_files:
        with open(list_file, "r", encoding="utf-8") as f:
            list_data = json.load(f)
        meta = list_data.get("meta", {})
        city_en = meta.get("city_name_en")
        city_ko = meta.get("city_name_ko")
        
        for fest in list_data.get("festivals", []):
            festivals_to_scrape.append({
                "contentid": fest["contentid"],
                "contenttypeid": fest["contenttypeid"],
                "title": fest.get("title", ""),
                "city_en": city_en,
                "city_ko": city_ko
            })
            
    total_festivals = len(festivals_to_scrape)
    print(f"Total festivals to scrape across all cities: {total_festivals}")
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for idx, fest in enumerate(festivals_to_scrape, 1):
        content_id = fest["contentid"]
        content_type_id = fest["contenttypeid"]
        city_en = fest["city_en"]
        title = fest["title"]
        
        filename = f"{city_en}_{content_id}.json"
        dest_path = os.path.join(festival_dir, filename)
        
        # Check if already cached
        if os.path.exists(dest_path):
            skip_count += 1
            continue
            
        print(f"[{idx}/{total_festivals}] Querying detail for festival '{title}' ({city_en}, ID: {content_id})...")
        
        try:
            # 1. Query detailCommon2
            params_common = {"contentId": content_id}
            common_data = client.request("detailCommon2", params_common)
            
            # 2. Query detailIntro2
            params_intro = {"contentId": content_id, "contentTypeId": content_type_id}
            intro_data = client.request("detailIntro2", params_intro)
            
            # Merge responses
            merged = {
                "common": common_data.get("response", {}).get("body", {}).get("items", {}).get("item", {}),
                "intro": intro_data.get("response", {}).get("body", {}).get("items", {}).get("item", {})
            }
            
            # Normalize list wrapper if list
            if isinstance(merged["common"], list) and len(merged["common"]) > 0:
                merged["common"] = merged["common"][0]
            if isinstance(merged["intro"], list) and len(merged["intro"]) > 0:
                merged["intro"] = merged["intro"][0]
                
            # Save to destination
            with open(dest_path, "w", encoding="utf-8") as f:
                json.dump(merged, f, ensure_ascii=False, indent=2)
                
            success_count += 1
            import random
            time.sleep(random.uniform(0.2, 0.6))
            
        except TourAPIError as tae:
            fail_count += 1
            print(f"  -> TourAPIError ({tae.code}): {tae.message}")
            if client.is_quota_limit_error(tae.code, tae.message):
                print("[Halt] API Quota exhausted. Stopping scraper.")
                break
        except Exception as e:
            fail_count += 1
            print(f"  -> Unexpected error: {e}")
            
    print(f"\nScraping complete. Summary:")
    print(f"- Processed: {success_count} successfully fetched")
    print(f"- Skipped (already cached): {skip_count}")
    print(f"- Failed: {fail_count}")

if __name__ == "__main__":
    main()
