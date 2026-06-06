import os
import json

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

    # Paths
    theme_path = os.path.join(data_dir, "theme_mapping.json")
    fest_path = os.path.join(data_dir, "festival_mapping.json")
    dict_path = os.path.join(data_dir, "classification_dict.json")

    if not os.path.exists(theme_path) or not os.path.exists(fest_path):
        print("Error: Mapping source files not found.")
        return

    with open(theme_path, "r", encoding="utf-8") as f:
        theme_map = json.load(f)
    with open(fest_path, "r", encoding="utf-8") as f:
        fest_map = json.load(f)

    classification_dict = {}
    target_themes = {'온천·휴양', '바다·해안', '역사·전통', '미식·노포', '자연·트레킹', '예술·감성'}

    # 1. Process Attraction Themes
    for theme, items in theme_map.items():
        if theme in target_themes:
            for item in items:
                if should_exclude(item):
                    continue
                code = item["code"]
                classification_dict[code] = {
                    "code": code,
                    "name": item["name"],
                    "middle_category": item.get("middle_category", ""),
                    "large_category": item.get("large_category", ""),
                    "theme": theme,
                    "type": "Attraction"
                }

    # 2. Process Festival Themes (Merge/Overwrite if code matches)
    for theme, items in fest_map.items():
        if theme in target_themes:
            for item in items:
                if should_exclude(item):
                    continue
                code = item["code"]
                classification_dict[code] = {
                    "code": code,
                    "name": item["name"],
                    "middle_category": item.get("middle_category", ""),
                    "large_category": item.get("large_category", ""),
                    "theme": theme,
                    "type": "Festival"
                }

    # Save mapping dictionary
    with open(dict_path, "w", encoding="utf-8") as f:
        json.dump(classification_dict, f, ensure_ascii=False, indent=2)

    print(f"Classification dictionary successfully generated at {dict_path}.")
    print(f"Total mapped codes: {len(classification_dict)}")

if __name__ == "__main__":
    main()
