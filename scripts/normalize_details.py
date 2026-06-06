import os
import sys
import json
import glob
from datetime import datetime

# Transliterator mapping for English filenames
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

def get_province_english(prov_name):
    if "강원" in prov_name:
        return "GW"
    if "경상북도" in prov_name or "경북" in prov_name:
        return "GB"
    return "KR"

def get_base_korean_name(sig_nm):
    for k in ENGLISH_NAMES.keys():
        if k in sig_nm:
            return k
    return sig_nm

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    list_dir = os.path.join(data_dir, "raw", "list_by_city")
    detail_dir = os.path.join(data_dir, "raw", "detail")
    city_dir = os.path.join(data_dir, "city")
    
    os.makedirs(city_dir, exist_ok=True)
    
    print("Starting data normalization over cached details...")
    
    # Load city coordinates from excel file if present
    city_coords = {}
    excel_path = os.path.join(os.path.dirname(base_dir), "korea_region_latitude_longitude.xlsx")
    if os.path.exists(excel_path):
        try:
            import pandas as pd
            df = pd.read_excel(excel_path, sheet_name="location")
            for _, row in df.iterrows():
                do_val = str(row.get("do", ""))
                city_val = str(row.get("city", ""))
                lat_val = row.get("latitude")
                lng_val = row.get("longitude")
                if do_val in ["강원", "경상"] and pd.notna(lat_val) and pd.notna(lng_val):
                    city_coords[(do_val, city_val)] = (float(lat_val), float(lng_val))
            print(f"[Coordinates Loader] Loaded {len(city_coords)} official city coordinates from Excel.")
        except Exception as e:
            print(f"[Coordinates Loader] Warning: Could not load city coordinates from Excel: {e}")
            
    # Aggregated cities dictionary: city_en -> city_data
    aggregated_cities = {}
    
    list_files = glob.glob(os.path.join(list_dir, "*_filtered.json"))
    for list_file in sorted(list_files):
        with open(list_file, "r", encoding="utf-8") as f:
            list_data = json.load(f)
            
        meta = list_data.get("meta", {})
        city_ko = meta.get("city_name_ko")
        city_en = meta.get("city_name_en")
        rgn_nm = meta.get("province")
        
        attrs_list = list_data.get("attractions", [])
        fests_list = list_data.get("festivals", [])
        
        prov_en = get_province_english(rgn_nm)
        
        if city_en not in aggregated_cities:
            aggregated_cities[city_en] = {
                "city_id": f"KR-{prov_en}-{city_en.upper()}",
                "city_name_ko": city_ko,
                "city_name_en": city_en,
                "province": rgn_nm,
                "district_type": "시" if city_ko.endswith("시") else ("군" if city_ko.endswith("군") else "구"),
                "location": f"{rgn_nm} {city_ko}",
                "attractions": [],
                "festivals": []
            }
            
        city_data = aggregated_cities[city_en]
        
        # 1. Normalize Attractions
        for attr in attrs_list:
            content_id = attr["contentid"]
            content_type_id = attr["contenttypeid"]
            theme = attr["_assigned_theme"]
            
            cache_path = os.path.join(detail_dir, f"{content_id}.json")
            if not os.path.exists(cache_path):
                continue
                
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    detail = json.load(f)
                
                common = detail.get("common") or {}
                intro = detail.get("intro") or {}
                
                opening_hours = ""
                use_fee = ""
                
                overview = common.get("overview", "")
                opening_hours = ""
                use_fee = ""
                
                if content_type_id == "12" or content_type_id == "14":
                    opening_hours = intro.get("usetime", "")
                    use_fee = intro.get("usefee", "")
                elif content_type_id == "39":
                    opening_hours = intro.get("opentimefood", "")
                    use_fee = ""
                    treatmenu = intro.get("treatmenu", "")
                    if treatmenu:
                        if overview:
                            overview += f"\n\n[대표 메뉴]\n{treatmenu}"
                        else:
                            overview = f"[대표 메뉴]\n{treatmenu}"
                elif content_type_id == "38":
                    opening_hours = intro.get("opentime", "")
                    use_fee = ""
                
                try:
                    lat = float(common.get("mapy")) if common.get("mapy") else float(attr.get("mapy", 0))
                    lng = float(common.get("mapx")) if common.get("mapx") else float(attr.get("mapx", 0))
                except ValueError:
                    lat = 0.0
                    lng = 0.0
                    
                theme_val = theme if theme != "테마 없음" else None
                collected_time = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M:%S")
                
                norm_attr = {
                    "attraction_id": f"ATT-{content_id}",
                    "city_id": city_data["city_id"],
                    "content_id": content_id,
                    "content_type_id": content_type_id,
                    "theme": theme_val,
                    "name": attr.get("title", ""),
                    "address": common.get("addr1") or attr.get("addr1", ""),
                    "description": overview,
                    "site_url": common.get("homepage", ""),
                    "opening_hours": opening_hours,
                    "opening_period": intro.get("usetime", "") if content_type_id != "39" else "",
                    "latitude": lat,
                    "longitude": lng,
                    "admission_fee": use_fee,
                    "photo_url": common.get("firstimage") or attr.get("firstimage", ""),
                    "areacode": attr.get("areacode", ""),
                    "sigungucode": attr.get("sigungucode", ""),
                    "source_name": "TourAPI",
                    "source_url": f"http://apis.data.go.kr/B551011/KorService2/detailCommon2?contentId={content_id}",
                    "collected_at": collected_time,
                    "data_confidence": "needs_review" if (opening_hours or use_fee) else "collected",
                    "verified_at": None,
                    "verified_source_url": None,
                    "verification_note": None
                }
                city_data["attractions"].append(norm_attr)
            except Exception as e:
                print(f"  Error parsing attraction {content_id}: {e}")

        # 2. Normalize Festivals
        for fest in fests_list:
            content_id = fest["contentid"]
            content_type_id = fest["contenttypeid"]
            theme = fest["_assigned_theme"]
            
            cache_path = os.path.join(detail_dir, f"{content_id}.json")
            if not os.path.exists(cache_path):
                continue
                
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    detail = json.load(f)
                
                common = detail.get("common") or {}
                intro = detail.get("intro") or {}
                
                evt_start = intro.get("eventstartdate", "")
                evt_end = intro.get("eventenddate", "")
                month_val = ""
                if evt_start and len(evt_start) >= 6:
                    month_val = evt_start[4:6]
                    
                try:
                    lat = float(common.get("mapy")) if common.get("mapy") else float(fest.get("mapy", 0))
                    lng = float(common.get("mapx")) if common.get("mapx") else float(fest.get("mapx", 0))
                except ValueError:
                    lat = 0.0
                    lng = 0.0
                    
                theme_val = theme if theme != "테마 없음" else None
                collected_time = datetime.fromtimestamp(os.path.getmtime(cache_path)).strftime("%Y-%m-%d %H:%M:%S")
                
                norm_fest = {
                    "festival_id": f"FEST-{content_id}",
                    "city_id": city_data["city_id"],
                    "content_id": content_id,
                    "theme": theme_val,
                    "name": fest.get("title", ""),
                    "address": common.get("addr1") or fest.get("addr1", ""),
                    "description": common.get("overview", ""),
                    "site_url": common.get("homepage", ""),
                    "photo_url": common.get("firstimage") or fest.get("firstimage", ""),
                    "period_text": intro.get("playtime", ""),
                    "start_date": evt_start,
                    "end_date": evt_end,
                    "month": month_val,
                    "latitude": lat,
                    "longitude": lng,
                    "areacode": fest.get("areacode", ""),
                    "sigungucode": fest.get("sigungucode", ""),
                    "source_name": "TourAPI",
                    "source_url": f"http://apis.data.go.kr/B551011/KorService2/detailCommon2?contentId={content_id}",
                    "collected_at": collected_time,
                    "verified_at": None,
                    "verified_source_url": None,
                    "verification_note": None
                }
                city_data["festivals"].append(norm_fest)
            except Exception as e:
                print(f"  Error parsing festival {content_id}: {e}")

    # Write out Compiled Cities
    print("\nWriting normalized city JSON files...")
    for idx, (city_en, city) in enumerate(sorted(aggregated_cities.items()), 1):
        normalized_attrs = city["attractions"]
        normalized_fests = city["festivals"]
        
        # Look up official city coordinates
        prov_nm = city["province"]
        city_nm = city["city_name_ko"]
        do_key = "경상" if ("경상" in prov_nm or "경북" in prov_nm) else ("강원" if "강원" in prov_nm else "")
        lookup_key = (do_key, city_nm)
        
        if lookup_key in city_coords:
            city_lat, city_lng = city_coords[lookup_key]
        else:
            # Calculate centroid based on all normalized coordinates
            city_lat = 0.0
            city_lng = 0.0
            if normalized_attrs:
                city_lat = sum(a["latitude"] for a in normalized_attrs) / len(normalized_attrs)
                city_lng = sum(a["longitude"] for a in normalized_attrs) / len(normalized_attrs)
            elif normalized_fests:
                city_lat = sum(f["latitude"] for f in normalized_fests) / len(normalized_fests)
                city_lng = sum(f["longitude"] for f in normalized_fests) / len(normalized_fests)
            else:
                city_lat = 36.5
                city_lng = 128.0
            
        city_output = {
            "city": {
                "city_id": city["city_id"],
                "city_name_ko": city["city_name_ko"],
                "city_name_en": city["city_name_en"],
                "province": city["province"],
                "district_type": city["district_type"],
                "location": city["location"],
                "latitude": city_lat,
                "longitude": city_lng,
                "description": f"{city['city_name_ko']} 관광 정보",
                "climate": "기상청 API 연계 예정",
                "site_url": ""
            },
            "attractions": normalized_attrs,
            "festivals": normalized_fests,
            "metadata": {
                "status": "collected",
                "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
        
        city_file = os.path.join(city_dir, f"{city_en}.json")
        with open(city_file, "w", encoding="utf-8") as f:
            json.dump(city_output, f, ensure_ascii=False, indent=2)
            
        print(f"  [{idx}/{len(aggregated_cities)}] Compiled: {city['city_name_ko']} ({city_en}) → {city_file} ({len(normalized_attrs)} attr, {len(normalized_fests)} fest)")

    print("\nStage 2: Normalization and compilation complete.")

if __name__ == "__main__":
    main()
