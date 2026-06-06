import os
import sys
import requests
import json
import time
from datetime import datetime


class TourAPIClient:
    def __init__(self):
        self.keys = []
        # Find .env file in parent directory
        env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k in ["TOUR_API_KEYS", "TOUR_API_KEY"]:
                            # Split by comma to support both array/list format and single key format
                            parsed_keys = [x.strip() for x in v.split(",") if x.strip()]
                            if parsed_keys:
                                self.keys = parsed_keys

        if not self.keys:
            # Fallback to OS environment variables
            keys_str = os.getenv("TOUR_API_KEYS") or os.getenv("TOUR_API_KEY")
            if keys_str:
                self.keys = [x.strip() for x in keys_str.split(",") if x.strip()]

        if not self.keys:
            raise EnvironmentError(
                "API keys not found. Configure TOUR_API_KEY or TOUR_API_KEYS in .env."
            )

        self.current_key_index = 0
        print(f"[API Client] Loaded {len(self.keys)} API key(s) in pool.")

    def get_service_key(self):
        return self.keys[self.current_key_index]

    def rotate_key(self):
        if self.current_key_index + 1 < len(self.keys):
            self.current_key_index += 1
            print(
                f"\n[Key Rotation] Switched to API key index {self.current_key_index} ({self.get_service_key()[:10]}...)"
            )
            return True
        else:
            print("\n[Key Rotation] All API keys in the pool are exhausted!")
            return False

    def request(self, endpoint, params, timeout=30):
        url = f"http://apis.data.go.kr/B551011/KorService2/{endpoint}"

        while True:
            current_params = params.copy()
            current_params["serviceKey"] = self.get_service_key()
            current_params["MobileOS"] = "ETC"
            current_params["MobileApp"] = "Lovv"
            current_params["_type"] = "json"

            try:
                resp = requests.get(url, params=current_params, timeout=timeout)
                resp.raise_for_status()

                # Check for XML error response (sometimes returned as 200 OK)
                content_type = resp.headers.get("Content-Type", "")
                if "xml" in content_type or resp.text.strip().startswith("<"):
                    text = resp.text
                    if "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDED" in text:
                        print("[Limit Exceeded] XML limit error detected.")
                        if self.rotate_key():
                            continue
                        else:
                            raise RuntimeError("QUOTA_EXHAUSTED: All keys exhausted.")
                    else:
                        raise RuntimeError(f"XML Error Response: {text[:200]}")

                data = resp.json()
                header = data.get("response", {}).get("header", {})
                result_code = header.get("resultCode", "0000")
                result_msg = header.get("resultMsg", "OK")

                if (
                    result_code == "0022"
                    or "LIMIT" in result_msg.upper()
                    or "EXCEEDED" in result_msg.upper()
                ):
                    print(f"[Limit Exceeded] Code {result_code}: {result_msg}")
                    if self.rotate_key():
                        continue
                    else:
                        raise RuntimeError("QUOTA_EXHAUSTED: All keys exhausted.")

                return data
            except (requests.RequestException, ValueError) as e:
                # Retry on connection issues, raise on key exhaust
                print(f"Request error: {e}. Retrying in 1s...")
                time.sleep(1)
                continue


def fetch_all_items(client, endpoint, params):
    all_items = []
    page = 1
    params_copy = params.copy()
    params_copy["numOfRows"] = 500

    while True:
        params_copy["pageNo"] = page
        data = client.request(endpoint, params_copy)

        body = data.get("response", {}).get("body", {})
        items_container = body.get("items")

        if not items_container or not items_container.get("item"):
            break

        items = items_container["item"]
        if not isinstance(items, list):
            items = [items]

        all_items.extend(items)
        total = int(body.get("totalCount", 0))

        if len(all_items) >= total or len(items) < 500:
            break
        page += 1
        time.sleep(0.3)

    return all_items


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
    os.makedirs(raw_dir, exist_ok=True)

    # Load targets
    targets_path = os.path.join(data_dir, "ldong_sigungu.json")
    if not os.path.exists(targets_path):
        print(f"Error: Target file not found at {targets_path}")
        sys.exit(1)

    with open(targets_path, "r", encoding="utf-8") as f:
        sigungus = json.load(f)

    # Load mappings
    theme_path = os.path.join(data_dir, "theme_mapping.json")
    fest_path = os.path.join(data_dir, "festival_mapping.json")

    if not os.path.exists(theme_path) or not os.path.exists(fest_path):
        print("Error: Theme mapping files not found.")
        sys.exit(1)

    with open(theme_path, "r", encoding="utf-8") as f:
        theme_map_raw = json.load(f)
    with open(fest_path, "r", encoding="utf-8") as f:
        fest_map_raw = json.load(f)

    # Build code-to-theme maps for fast lookup
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

    try:
        client = TourAPIClient()
    except Exception as e:
        print(e)
        sys.exit(1)

    print(f"Starting List Retrieval for {len(sigungus)} sigungus...")

    for idx, sig in enumerate(sigungus, 1):
        regn_cd = sig["lDongRegnCd"]
        sig_cd = sig["lDongSignguCd"]
        sig_nm = sig["lDongSignguNm"]
        rgn_nm = sig["lDongRegnNm"]

        print(
            f"\n[{idx}/{len(sigungus)}] Processing {rgn_nm} {sig_nm} (Regn={regn_cd}, Sigungu={sig_cd})..."
        )

        # 1. Fetch Attractions (areaBasedList2 without contentTypeId)
        params_attr = {"lDongRegnCd": regn_cd, "lDongSignguCd": sig_cd}

        # 2. Fetch Festivals (searchFestival2 with eventStartDate=20250101)
        params_fest = {
            "lDongRegnCd": regn_cd,
            "lDongSignguCd": sig_cd,
            "eventStartDate": "20250101",
        }

        try:
            print("  Fetching attractions list...")
            raw_attrs = fetch_all_items(client, "areaBasedList2", params_attr)

            print("  Fetching festivals list...")
            raw_fests = fetch_all_items(client, "searchFestival2", params_fest)

            # Save raw data
            raw_output = {
                "meta": {
                    "province": rgn_nm,
                    "sigungu": sig_nm,
                    "regn_cd": regn_cd,
                    "sigungu_cd": sig_cd,
                    "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
                "attractions_count_raw": len(raw_attrs),
                "festivals_count_raw": len(raw_fests),
                "raw_attractions": raw_attrs,
                "raw_festivals": raw_fests,
            }

            raw_file_path = os.path.join(raw_dir, f"{regn_cd}_{sig_cd}_raw.json")
            with open(raw_file_path, "w", encoding="utf-8") as f:
                json.dump(raw_output, f, ensure_ascii=False, indent=2)

            # Filter items locally
            filtered_attrs = []
            for item in raw_attrs:
                if item.get("lclsSystm1") == "C01":
                    continue
                code = item.get("lclsSystm3") or item.get("cat3", "")
                theme = attraction_code_to_theme.get(code)
                if theme and theme != "제외(기타/숙박/코스/축제)":
                    item_copy = item.copy()
                    item_copy["_assigned_theme"] = theme
                    for k in ["cat1", "cat2", "cat3"]:
                        if k in item_copy:
                            del item_copy[k]
                    filtered_attrs.append(item_copy)

            filtered_fests = []
            for item in raw_fests:
                if item.get("lclsSystm1") == "C01":
                    continue
                code = item.get("lclsSystm3") or item.get("cat3", "")
                theme = festival_code_to_theme.get(code)
                if theme and theme != "제외":
                    item_copy = item.copy()
                    item_copy["_assigned_theme"] = theme
                    for k in ["cat1", "cat2", "cat3"]:
                        if k in item_copy:
                            del item_copy[k]
                    filtered_fests.append(item_copy)

            # Save filtered lists
            filtered_output = {
                "meta": raw_output["meta"],
                "attractions_count_filtered": len(filtered_attrs),
                "festivals_count_filtered": len(filtered_fests),
                "attractions": filtered_attrs,
                "festivals": filtered_fests,
            }

            filtered_file_path = os.path.join(
                raw_dir, f"{regn_cd}_{sig_cd}_filtered.json"
            )
            with open(filtered_file_path, "w", encoding="utf-8") as f:
                json.dump(filtered_output, f, ensure_ascii=False, indent=2)

            print(
                f"  → Attractions: {len(raw_attrs)} raw, {len(filtered_attrs)} filtered"
            )
            print(
                f"  → Festivals: {len(raw_fests)} raw, {len(filtered_fests)} filtered"
            )

        except RuntimeError as re:
            if "QUOTA_EXHAUSTED" in str(re):
                print(
                    "\n[Halt] Stopped list retrieval due to API quota exhaustion on all keys."
                )
                break
            else:
                print(f"  Error processing: {re}")
        except Exception as ex:
            print(f"  Unexpected error: {ex}")

        time.sleep(0.5)

    print("\nStage 1: List Retrieval complete.")


if __name__ == "__main__":
    main()
