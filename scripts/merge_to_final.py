import os
import glob
import json

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    list_dir = os.path.join(data_dir, "raw", "list_by_city")
    detail_dir = os.path.join(data_dir, "raw", "detail")
    final_dir = os.path.join(data_dir, "raw", "final")
    
    os.makedirs(final_dir, exist_ok=True)
    
    list_files = sorted(glob.glob(os.path.join(list_dir, "*_filtered.json")))
    if not list_files:
        print("No list files found.")
        return
        
    print(f"Merging lists with details. Saving output to {final_dir}...")
    
    for list_file in list_files:
        try:
            with open(list_file, "r", encoding="utf-8") as f:
                city_data = json.load(f)
        except Exception as e:
            print(f"Error reading list file {list_file}: {e}")
            continue
            
        meta = city_data.get("meta", {})
        city_en = meta.get("city_name_en")
        city_ko = meta.get("city_name_ko")
        
        # Merge attractions
        attractions = city_data.get("attractions", [])
        for attr in attractions:
            content_id = str(attr.get("contentid", ""))
            if not content_id:
                continue
            detail_path = os.path.join(detail_dir, f"{content_id}.json")
            detail_obj = {"common": {}, "intro": {}}
            if os.path.exists(detail_path):
                try:
                    with open(detail_path, "r", encoding="utf-8") as df:
                        detail_obj = json.load(df)
                except Exception as e:
                    print(f"Error reading detail for content_id {content_id}: {e}")
            attr["detail"] = detail_obj
            
        # Merge festivals
        festivals = city_data.get("festivals", [])
        for fest in festivals:
            content_id = str(fest.get("contentid", ""))
            if not content_id:
                continue
            detail_path = os.path.join(detail_dir, f"{content_id}.json")
            detail_obj = {"common": {}, "intro": {}}
            if os.path.exists(detail_path):
                try:
                    with open(detail_path, "r", encoding="utf-8") as df:
                        detail_obj = json.load(df)
                except Exception as e:
                    print(f"Error reading detail for content_id {content_id}: {e}")
            fest["detail"] = detail_obj
            
        # Write merged file
        final_file_name = f"{city_en}.json"
        final_file_path = os.path.join(final_dir, final_file_name)
        try:
            with open(final_file_path, "w", encoding="utf-8") as out_f:
                json.dump(city_data, out_f, ensure_ascii=False, indent=2)
            print(f"  Merged {city_ko} ({city_en}) -> {final_file_name} ({len(attractions)} attractions, {len(festivals)} festivals)")
        except Exception as e:
            print(f"Error writing final file for {city_en}: {e}")

    print("Merge process completed successfully.")

if __name__ == "__main__":
    main()
