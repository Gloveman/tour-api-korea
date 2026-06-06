import os
import sys
import requests
import json
import time
import glob
from datetime import datetime


class TourAPIError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(f"API Error {code}: {message}")


class TourAPIClient:
    def __init__(self):
        self.keys = []
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
        self.consecutive_errors = 0
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

    def is_quota_limit_error(self, code, message):
        """Checks if the error code or message indicates a request quota limit exhaustion."""
        code_str = str(code).strip()
        msg_upper = str(message).upper()
        
        # 22 (XML) or 0022 (JSON)
        if code_str in ["22", "0022"]:
            return True
            
        # Fallback check for quota limits in message
        if "LIMIT" in msg_upper or "EXCEEDED" in msg_upper:
            return True
            
        return False

    def request(self, endpoint, params, timeout=30):
        url = f"http://apis.data.go.kr/B551011/KorService2/{endpoint}"
        max_retries = 3

        while True:
            current_params = params.copy()
            current_params["serviceKey"] = self.get_service_key()
            current_params["MobileOS"] = "ETC"
            current_params["MobileApp"] = "Lovv"
            current_params["_type"] = "json"

            # Check consecutive errors to adjust sleep interval dynamically
            if getattr(self, "consecutive_errors", 0) > 0:
                consec = self.consecutive_errors
                extra_sleep = 2 if consec == 1 else (5 if consec == 2 else (10 if consec == 3 else 15))
                print(f"[Dynamic Delay] Consecutive errors = {consec}. Adding {extra_sleep}s extra sleep.")
                time.sleep(extra_sleep)

            retries_left = max_retries
            while retries_left > 0:
                try:
                    resp = requests.get(url, params=current_params, timeout=timeout)
                    resp.raise_for_status()

                    content_type = resp.headers.get("Content-Type", "")
                    if "xml" in content_type or resp.text.strip().startswith("<"):
                        text = resp.text
                        import re
                        code_match = re.search(r"<returnReasonCode>(.*?)</returnReasonCode>", text)
                        msg_match = re.search(r"<returnAuthMsg>(.*?)</returnAuthMsg>", text)
                        if not msg_match:
                            msg_match = re.search(r"<errMsg>(.*?)</errMsg>", text)
                        
                        code = code_match.group(1) if code_match else "99"
                        msg = msg_match.group(1) if msg_match else "XML_ERROR"

                        if self.is_quota_limit_error(code, msg):
                            print(f"[Limit Exceeded] XML limit error detected: {msg}")
                            if self.rotate_key():
                                # Break out of inner retry loop, restart outer loop with new key
                                break
                            else:
                                raise TourAPIError("22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")
                        else:
                            raise TourAPIError(code, msg)

                    data = resp.json()
                    header = data.get("response", {}).get("header", {})
                    result_code = header.get("resultCode", "0000")
                    result_msg = header.get("resultMsg", "OK")

                    if result_code not in ["0000", "00", "OK"]:
                        if self.is_quota_limit_error(result_code, result_msg):
                            print(f"[Limit Exceeded] JSON limit error detected (code={result_code}): {result_msg}")
                            if self.rotate_key():
                                break
                            else:
                                raise TourAPIError("22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")
                        else:
                            raise TourAPIError(result_code, result_msg)

                    # Successful response!
                    self.consecutive_errors = 0
                    return data

                except (requests.RequestException, ValueError, TourAPIError) as e:
                    # Check for HTTP 429 rate limit
                    if isinstance(e, requests.HTTPError) and e.response is not None and e.response.status_code == 429:
                        print(f"[Rate Limit Exceeded] HTTP 429 Too Many Requests. Rotating key...")
                        if self.rotate_key():
                            self.consecutive_errors = 0
                            break  # restart outer loop with new key
                        else:
                            raise TourAPIError("22", "LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR")

                    # If it's a quota limit error, the outer loop handles rotation
                    if isinstance(e, TourAPIError):
                        if self.is_quota_limit_error(e.code, e.message):
                            break
                        # Check if it is a permanent error where retries are useless
                        if e.code in ["12", "0012", "10", "0010", "11", "0011", "30", "0030", "31", "0031", "32", "0032"]:
                            print(f"[Permanent Error] Code {e.code}: {e.message}. Skipping retries.")
                            raise e

                    self.consecutive_errors = getattr(self, "consecutive_errors", 0) + 1
                    retries_left -= 1
                    print(f"Request attempt failed (Error: {e}). Retries left: {retries_left}. Consecutive errors: {self.consecutive_errors}")
                    
                    if retries_left > 0:
                        sleep_time = (max_retries - retries_left) * 2
                        time.sleep(sleep_time)
                    else:
                        raise e



def fetch_and_cache_detail(client, detail_dir, content_id, content_type_id):
    cache_path = os.path.join(detail_dir, f"{content_id}.json")

    # 1. Load from cache if exists
    if os.path.exists(cache_path):
        return True

    # 2. Call APIs
    print(f"    [API Detail] Querying contentid={content_id}...", end=" ")

    # detailCommon2
    params_common = {
        "contentId": content_id,
    }
    common_data = client.request("detailCommon2", params_common)

    # detailIntro2
    params_intro = {"contentId": content_id, "contentTypeId": content_type_id}
    intro_data = client.request("detailIntro2", params_intro)

    # Merge and write to cache
    items_common = common_data.get("response", {}).get("body", {}).get("items", {})
    items_intro = intro_data.get("response", {}).get("body", {}).get("items", {})

    common_item = items_common.get("item", {}) if isinstance(items_common, dict) else {}
    intro_item = items_intro.get("item", {}) if isinstance(items_intro, dict) else {}

    # Merge and write to cache
    merged = {
        "common": common_item,
        "intro": intro_item,
    }

    # Normalize list wrapper if list
    if isinstance(merged["common"], list) and len(merged["common"]) > 0:
        merged["common"] = merged["common"][0]
    if isinstance(merged["intro"], list) and len(merged["intro"]) > 0:
        merged["intro"] = merged["intro"][0]

    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print("Done")
    import random
    time.sleep(random.uniform(0.2, 0.6))
    return True


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, "data")
    list_dir = os.path.join(data_dir, "raw", "list_by_city")
    detail_dir = os.path.join(data_dir, "raw", "detail")

    os.makedirs(detail_dir, exist_ok=True)

    # Find sorted list files
    list_files = sorted(glob.glob(os.path.join(list_dir, "*_filtered.json")))
    if not list_files:
        print(f"Error: No city list files found in {list_dir}. Run scripts/group_lists_by_city.py first.")
        sys.exit(1)

    # Load Checkpoint Progress for Download Stage
    progress_path = os.path.join(data_dir, "download_progress.json")
    progress = {"completed_cities": [], "failed_cities": [], "city_progress": {}}
    if os.path.exists(progress_path):
        try:
            with open(progress_path, "r", encoding="utf-8") as f:
                progress = json.load(f)
        except Exception:
            pass

    if "city_progress" not in progress:
        progress["city_progress"] = {}
    if "completed_cities" not in progress:
        progress["completed_cities"] = []
    if "failed_cities" not in progress:
        progress["failed_cities"] = []

    try:
        client = TourAPIClient()
    except Exception as e:
        print(e)
        sys.exit(1)

    print(f"Starting Detail Raw Data Scraping and Caching (City-level)...")

    quota_exhausted = False

    for idx, list_file in enumerate(list_files, 1):
        with open(list_file, "r", encoding="utf-8") as f:
            list_data = json.load(f)
            
        meta = list_data.get("meta", {})
        city_ko = meta.get("city_name_ko")
        city_en = meta.get("city_name_en")
        rgn_nm = meta.get("province")

        # Skip if already completed in city_progress
        c_progress = progress["city_progress"].get(city_en)
        if c_progress and c_progress.get("status") == "completed":
            print(
                f"[{idx}/{len(list_files)}] Skipping Download for {city_ko} ({city_en}) (already completed)"
            )
            continue

        print(
            f"\n[{idx}/{len(list_files)}] Scraping {rgn_nm} {city_ko} ({city_en})..."
        )

        attrs_list = list_data.get("attractions", [])
        fests_list = list_data.get("festivals", [])

        # Initialize or load progress structure for this city
        if not c_progress:
            c_progress = {
                "status": "in_progress",
                "total_attractions": len(attrs_list),
                "total_festivals": len(fests_list),
                "scraped_attractions": 0,
                "scraped_festivals": 0,
                "last_processed_idx": 0,
                "last_processed_type": None,
                "last_result_code": "00",
                "last_result_msg": "OK",
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            progress["city_progress"][city_en] = c_progress

        c_progress["status"] = "in_progress"

        # Download details for Attractions
        print(f"  Downloading details for {len(attrs_list)} attractions...")
        for a_idx, attr in enumerate(attrs_list, 1):
            content_id = attr["contentid"]
            content_type_id = attr["contenttypeid"]

            cache_path = os.path.join(detail_dir, f"{content_id}.json")
            if os.path.exists(cache_path):
                c_progress["scraped_attractions"] = max(c_progress["scraped_attractions"], a_idx)
                c_progress["last_processed_idx"] = a_idx
                c_progress["last_processed_type"] = "attraction"
                continue

            try:
                fetch_and_cache_detail(client, detail_dir, content_id, content_type_id)
                c_progress["scraped_attractions"] = a_idx
                c_progress["last_processed_idx"] = a_idx
                c_progress["last_processed_type"] = "attraction"
                c_progress["last_result_code"] = "00"
                c_progress["last_result_msg"] = "OK"
                c_progress["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Periodically save progress
                if a_idx % 10 == 0:
                    with open(progress_path, "w", encoding="utf-8") as f:
                        json.dump(progress, f, ensure_ascii=False, indent=2)
            except TourAPIError as tae:
                c_progress["status"] = "failed"
                c_progress["last_result_code"] = tae.code
                c_progress["last_result_msg"] = tae.message
                c_progress["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(progress_path, "w", encoding="utf-8") as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                
                print(f"\n[Halt] Stopped downloading details due to API error: {tae}")
                quota_exhausted = True
                break
            except Exception as e:
                print(f"    Unexpected error: {e}")

        if quota_exhausted:
            break

        # Download details for Festivals
        print(f"  Downloading details for {len(fests_list)} festivals...")
        for f_idx, fest in enumerate(fests_list, 1):
            content_id = fest["contentid"]
            content_type_id = fest["contenttypeid"]

            cache_path = os.path.join(detail_dir, f"{content_id}.json")
            if os.path.exists(cache_path):
                c_progress["scraped_festivals"] = max(c_progress["scraped_festivals"], f_idx)
                c_progress["last_processed_idx"] = f_idx
                c_progress["last_processed_type"] = "festival"
                continue

            try:
                fetch_and_cache_detail(client, detail_dir, content_id, content_type_id)
                c_progress["scraped_festivals"] = f_idx
                c_progress["last_processed_idx"] = f_idx
                c_progress["last_processed_type"] = "festival"
                c_progress["last_result_code"] = "00"
                c_progress["last_result_msg"] = "OK"
                c_progress["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if f_idx % 10 == 0:
                    with open(progress_path, "w", encoding="utf-8") as f:
                        json.dump(progress, f, ensure_ascii=False, indent=2)
            except TourAPIError as tae:
                c_progress["status"] = "failed"
                c_progress["last_result_code"] = tae.code
                c_progress["last_result_msg"] = tae.message
                c_progress["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with open(progress_path, "w", encoding="utf-8") as f:
                    json.dump(progress, f, ensure_ascii=False, indent=2)
                
                print(f"\n[Halt] Stopped downloading details due to API error: {tae}")
                quota_exhausted = True
                break
            except Exception as e:
                print(f"    Unexpected error: {e}")

        if quota_exhausted:
            break

        # Mark completed successfully
        c_progress["status"] = "completed"
        c_progress["last_result_code"] = "00"
        c_progress["last_result_msg"] = "Completed successfully"
        c_progress["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update completed/failed arrays
        if city_en not in progress["completed_cities"]:
            progress["completed_cities"].append(city_en)

        progress["failed_cities"] = [c for c in progress["failed_cities"] if c != city_en]

        with open(progress_path, "w", encoding="utf-8") as f:
            json.dump(progress, f, ensure_ascii=False, indent=2)

        time.sleep(0.5)

    print("\nDetail raw scraping phase finished/paused.")


if __name__ == "__main__":
    main()
