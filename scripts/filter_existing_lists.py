import os
import json
import glob

def should_exclude(item):
    name = item.get("name", "")
    middle = item.get("middle_category", "")
    large = item.get("large_category", "")
    
    exclude_large = {"체험관광"}
    exclude_middle = {"기타문화관광지", "레저스포츠시설", "교육시설", "공연시설", "복합관광시설"}
    exclude_names = {"기타주점", "클럽", "기타간이음식", "북한관광지", "기타안보관광지", "기타 종교성지", "약수터"}
    
    if large in exclude_large:
        return True
    if middle in exclude_middle:
        return True
    if name in exclude_names:
        return True
    return False

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    raw_dir = os.path.join(data_dir, "raw", "list")

    # Load mappings
    theme_path = os.path.join(data_dir, "theme_mapping.json")
    fest_path = os.path.join(data_dir, "festival_mapping.json")

    if not os.path.exists(theme_path) or not os.path.exists(fest_path):
        print("Error: Mapping files not found.")
        return

    with open(theme_path, "r", encoding="utf-8") as f:
        theme_map_raw = json.load(f)
    with open(fest_path, "r", encoding="utf-8") as f:
        fest_map_raw = json.load(f)

    # Build code-to-theme maps
    target_themes = {'온천·휴양', '바다·해안', '역사·전통', '미식·노포', '자연·트레킹', '예술·감성'}
    
    attraction_code_to_theme = {}
    for theme, items in theme_map_raw.items():
        if theme in target_themes:
            for item in items:
                if should_exclude(item):
                    continue
                attraction_code_to_theme[item["code"]] = theme

    festival_code_to_theme = {}
    for theme, items in fest_map_raw.items():
        if theme in target_themes:
            for item in items:
                if should_exclude(item):
                    continue
                festival_code_to_theme[item["code"]] = theme

    # Find all *_raw.json files
    raw_files = glob.glob(os.path.join(raw_dir, "*_raw.json"))
    print(f"Found {len(raw_files)} raw JSON files to process.")

    total_raw_attrs = 0
    total_filtered_attrs = 0
    total_raw_fests = 0
    total_filtered_fests = 0

    for file_path in raw_files:
        filename = os.path.basename(file_path)
        parts = filename.replace("_raw.json", "").split("_")
        if len(parts) != 2:
            continue
        regn_cd, sig_cd = parts

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_attrs = data.get("raw_attractions", [])
        raw_fests = data.get("raw_festivals", [])

        # Filter attractions
        filtered_attrs = []
        for item in raw_attrs:
            if item.get("lclsSystm1") == "C01":
                continue
            code = item.get("lclsSystm3") or item.get("cat3", "")
            theme = attraction_code_to_theme.get(code)
            if theme:
                item_copy = item.copy()
                item_copy["_assigned_theme"] = theme
                # Remove legacy category keys
                for k in ["cat1", "cat2", "cat3"]:
                    if k in item_copy:
                        del item_copy[k]
                filtered_attrs.append(item_copy)

        # Filter festivals
        filtered_fests = []
        
        # Override dictionary by contentid to classify general festival categories into specific themes
        fest_overrides = {
            # 바다·해안 (Sea & Coast)
            "2607445": "바다·해안",  # 강릉비치비어페스티벌
            "674023": "바다·해안",   # 병오년 해맞이 행사
            "3330805": "바다·해안",  # 묵호 도째비페스타
            "3497291": "바다·해안",  # 영일대샌드페스티벌
            "588175": "바다·해안",   # 포항국제불빛축제
            "2609985": "바다·해안",  # 삼척 비치 썸 페스티벌
            "2611034": "바다·해안",  # 속초 칠링비치페스티벌
            "421977": "바다·해안",   # 고성명태축제
            "2488259": "바다·해안",  # 저도 대문어축제
            "1892201": "바다·해안",  # 울진대게와 붉은대게 축제
            
            # 온천·휴양 (Wellness & Spa)
            "140897": "온천·휴양",   # 경산 갓바위소원성취축제
            
            # 미식·노포 (Gastronomy/Food)
            "3028462": "미식·노포",  # 구미라면 축제
            "2406168": "미식·노포",  # 원주문화의거리 치맥축제
            "825295": "미식·노포",   # 강릉커피축제
            "3497502": "미식·노포",  # 경산카페축제
            "3377995": "미식·노포",  # 김천김밥축제
            "921212": "미식·노포",   # 청송사과축제
            "2996726": "미식·노포",  # 공근 소맥축제
            "1684261": "미식·노포",  # 둔내고랭지토마토축제
            "2027215": "미식·노포",  # 안흥찐빵축제
            "3513492": "미식·노포",  # 태백 쇠바우골 탄광문화 고기축제
            "506766": "미식·노포",   # 경북영주 풍기인삼축제
            
            # 자연·트레킹 (Nature & Trekking)
            "695592": "자연·트레킹",  # 강릉 경포벚꽃축제
            "1634216": "자연·트레킹", # 두위봉 철쭉축제&산맥페스티벌
            "1882134": "자연·트레킹", # 철원 한탄강 얼음트레킹 축제
            "1769697": "자연·트레킹", # 홍천강 꽁꽁축제
            "507599": "자연·트레킹",  # 얼음나라화천 산천어축제
            "1831344": "자연·트레킹", # 평창더위사냥축제
            "386053": "자연·트레킹",  # 평창송어축제
            "968157": "자연·트레킹",  # 산수유마을꽃맞이행사
            "3484079": "자연·트레킹", # 양양 남대천 벚꽃축제
            "391883": "자연·트레킹",  # 대관령눈꽃축제
            
            # 역사·전통 (History & Tradition)
            "4060101": "역사·전통",  # 동아시아문화도시 안동
            "506670": "역사·전통",   # 안동국제탈춤페스티벌
            "3486887": "역사·전통",  # 왜관 성베네딕도 수도원 홀리 페스티벌
            "1844150": "역사·전통",  # 칠곡낙동강평화축제
            "3527675": "역사·전통",  # 춘천 ONE도심 페스타
            "734219": "역사·전통",   # 동해 무릉제
            "2541883": "역사·전통",  # 강릉 국가유산 야행
            "506895": "역사·전통",   # 정선아리랑제
            "506295": "역사·전통",   # 문경찻사발축제
            "2495286": "역사·전통",  # 실향민문화축제
            "2666150": "역사·전통",  # 예천 금당야행
            "581063": "역사·전통",   # 동강뗏목축제
            "2667017": "역사·전통",  # 고령 대가야축제
            "3021124": "역사·전통",  # 보현사 산사천년문화제
        }
        
        for item in raw_fests:
            if item.get("lclsSystm1") == "C01":
                continue
            cid = str(item.get("contentid"))
            code = item.get("lclsSystm3") or item.get("cat3", "")
            
            # Use override if available, otherwise fallback to code mapping
            if cid in fest_overrides:
                theme = fest_overrides[cid]
            else:
                theme = festival_code_to_theme.get(code)
                
            if theme:
                item_copy = item.copy()
                item_copy["_assigned_theme"] = theme
                # Remove legacy category keys
                for k in ["cat1", "cat2", "cat3"]:
                    if k in item_copy:
                        del item_copy[k]
                filtered_fests.append(item_copy)

        # Update stats
        total_raw_attrs += len(raw_attrs)
        total_filtered_attrs += len(filtered_attrs)
        total_raw_fests += len(raw_fests)
        total_filtered_fests += len(filtered_fests)

        # Save filtered list
        filtered_output = {
            "meta": data.get("meta", {}),
            "attractions_count_filtered": len(filtered_attrs),
            "festivals_count_filtered": len(filtered_fests),
            "attractions": filtered_attrs,
            "festivals": filtered_fests
        }

        filtered_file_path = os.path.join(raw_dir, f"{regn_cd}_{sig_cd}_filtered.json")
        with open(filtered_file_path, "w", encoding="utf-8") as f:
            json.dump(filtered_output, f, ensure_ascii=False, indent=2)

    print("\nOffline Filtering Completed:")
    print(f"Attractions: {total_raw_attrs} raw -> {total_filtered_attrs} filtered")
    print(f"Festivals: {total_raw_fests} raw -> {total_filtered_fests} filtered")

if __name__ == "__main__":
    main()
