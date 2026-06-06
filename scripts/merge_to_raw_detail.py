import glob
import os
import json
import re

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    
    # Inputs
    attraction_dir = os.path.join(data_dir, "detail", "attraction")
    festival_dir = os.path.join(data_dir, "detail", "festival")
    
    # Output
    raw_detail_dir = os.path.join(data_dir, "raw", "detail")
    os.makedirs(raw_detail_dir, exist_ok=True)
    
    print("Starting merge of detail data...")
    
    # 1. Process Attractions
    attraction_files = glob.glob(os.path.join(attraction_dir, "*_details.json"))
    attraction_count = 0
    
    for f_path in attraction_files:
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                city_data = json.load(f)
            details = city_data.get("details", {})
            for content_id, detail_obj in details.items():
                out_path = os.path.join(raw_detail_dir, f"{content_id}.json")
                with open(out_path, "w", encoding="utf-8") as out_f:
                    json.dump(detail_obj, out_f, ensure_ascii=False, indent=2)
                attraction_count += 1
        except Exception as e:
            print(f"Error processing attraction file {os.path.basename(f_path)}: {e}")
            
    print(f"Merged {attraction_count} attraction detail files.")
    
    # 2. Process Festivals
    festival_files = glob.glob(os.path.join(festival_dir, "*.json"))
    festival_count = 0
    
    for f_path in festival_files:
        filename = os.path.basename(f_path)
        # Extract content_id (everything after the last underscore and before .json)
        match = re.search(r"_(\d+)\.json$", filename)
        if not match:
            print(f"Skipping festival file with unexpected name: {filename}")
            continue
            
        content_id = match.group(1)
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                detail_obj = json.load(f)
            out_path = os.path.join(raw_detail_dir, f"{content_id}.json")
            with open(out_path, "w", encoding="utf-8") as out_f:
                json.dump(detail_obj, out_f, ensure_ascii=False, indent=2)
            festival_count += 1
        except Exception as e:
            print(f"Error processing festival file {filename}: {e}")
            
    print(f"Merged {festival_count} festival detail files.")
    print(f"Total merged files in data/raw/detail/: {attraction_count + festival_count}")

if __name__ == "__main__":
    main()
