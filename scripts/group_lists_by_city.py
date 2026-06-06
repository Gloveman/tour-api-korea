import os
import sys
import json
import glob
from datetime import datetime

# Add parent dir to path to import ENGLISH_NAMES if needed
# But to make it self-contained, we can define the mapping here
ENGLISH_NAMES = {
    # Gangwon
    "춘천시": "Chuncheon", "원주시": "Wonju", "강릉시": "Gangneung", "동해시": "Donghae",
    "태백시": "Taebaek", "속초시": "Sokcho", "삼척시": "Samcheok", "홍천군": "Hongcheon",
    "횡성군": "Hoengseong", "영월군": "Yeongwol", "평창군": "Pyeongchang", "정선군": "Jeongseon",
    "철원군": "Cheorwon", "화천군": "Hwacheon", "양구군": "Yanggu", "인제군": "Inje",
    "고성군": "Goseong", "양양군": "Yangyang",
    # Gyeongbuk
    "포항시": "Pohang", "경주시": "Gyeongju", "김천시": "Gimcheon", "안동시": "Andong",
    "구미시": "Gumi", "영주시": "Yeongju", "영천시": "Yeongcheon", "상주시": "Sangju",
    "문경시": "Mungyeong", "경산시": "Gyeongsan", "의성군": "Uiseong", "청송군": "Cheongsong",
    "영양군": "Yeongyang", "영덕군": "Yeongdeok", "청도군": "Cheongdo", "고령군": "Goryeong",
    "성주군": "Seongju", "칠곡군": "Chilgok", "예천군": "Yecheon", "봉화군": "Bonghwa",
    "울진군": "Uljin", "울릉군": "Ulleung"
}

def get_english_name(ko_name):
    for k, v in ENGLISH_NAMES.items():
        if k in ko_name:
            return v
    return ko_name.replace(" ", "_")

def get_base_korean_name(sig_nm):
    for k in ENGLISH_NAMES.keys():
        if k in sig_nm:
            return k
    return sig_nm

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    list_dir = os.path.join(data_dir, "raw", "list")
    output_dir = os.path.join(data_dir, "raw", "list_by_city")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Read target sigungus
    targets_path = os.path.join(data_dir, "ldong_sigungu.json")
    if not os.path.exists(targets_path):
        print(f"Error: Target file not found at {targets_path}")
        sys.exit(1)
        
    with open(targets_path, "r", encoding="utf-8") as f:
        sigungus = json.load(f)
        
    # Group sigungus by city
    # city_en -> list of sigungus
    city_groups = {}
    for sig in sigungus:
        regn_cd = sig["lDongRegnCd"]
        sig_cd = sig["lDongSignguCd"]
        sig_nm = sig["lDongSignguNm"]
        rgn_nm = sig["lDongRegnNm"]
        
        city_en = get_english_name(sig_nm)
        base_ko = get_base_korean_name(sig_nm)
        
        if city_en not in city_groups:
            city_groups[city_en] = {
                "city_name_ko": base_ko,
                "city_name_en": city_en,
                "province": rgn_nm,
                "sigungus": []
            }
        city_groups[city_en]["sigungus"].append({
            "regn_cd": regn_cd,
            "sig_cd": sig_cd,
            "sig_nm": sig_nm
        })
        
    print(f"Grouped {len(sigungus)} sigungus into {len(city_groups)} cities.")
    
    # Merge filtered list data for each city
    for city_en, info in sorted(city_groups.items()):
        merged_attractions = []
        merged_festivals = []
        sigungus_included = []
        
        seen_attr_ids = set()
        seen_fest_ids = set()
        
        for sig in info["sigungus"]:
            list_file = os.path.join(list_dir, f"{sig['regn_cd']}_{sig['sig_cd']}_filtered.json")
            if not os.path.exists(list_file):
                continue
                
            sigungus_included.append(sig["sig_nm"])
            
            with open(list_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            # Merge attractions
            for attr in data.get("attractions", []):
                cid = attr["contentid"]
                ctid = attr.get("contenttypeid")
                # If restaurant (contentTypeId == 39), only keep if lclsSystm3 is FD010100 (관광식당)
                if ctid == "39" and attr.get("lclsSystm3") != "FD010100":
                    continue
                    
                if cid not in seen_attr_ids:
                    seen_attr_ids.add(cid)
                    merged_attractions.append(attr)
                    
            # Merge festivals
            for fest in data.get("festivals", []):
                cid = fest["contentid"]
                if cid not in seen_fest_ids:
                    seen_fest_ids.add(cid)
                    merged_festivals.append(fest)
                    
        # Write merged city file if we included any sigungus
        if sigungus_included:
            output_file = os.path.join(output_dir, f"{city_en}_filtered.json")
            city_list_data = {
                "meta": {
                    "province": info["province"],
                    "city_name_ko": info["city_name_ko"],
                    "city_name_en": city_en,
                    "sigungus_included": sigungus_included,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                },
                "attractions_count_filtered": len(merged_attractions),
                "festivals_count_filtered": len(merged_festivals),
                "attractions": merged_attractions,
                "festivals": merged_festivals
            }
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(city_list_data, f, ensure_ascii=False, indent=2)
                
            print(f"  Compiled: {info['city_name_ko']} ({city_en}) -> {output_file} (Attr: {len(merged_attractions)}, Fest: {len(merged_festivals)})")

    print("\nList grouping by city completed successfully.")

if __name__ == "__main__":
    main()
