import os
import sys
import json
import time
import glob
import requests
from datetime import datetime
from collections import defaultdict

class BigDataClient:
    def __init__(self):
        self.keys = []
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base_dir, ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k in ["TOUR_API_KEYS", "TOUR_API_KEY"]:
                            parsed_keys = [x.strip() for x in v.split(",") if x.strip()]
                            if parsed_keys:
                                self.keys = parsed_keys

        if not self.keys:
            raise EnvironmentError("API keys not found in .env file.")

        self.current_key_index = 0
        self.consecutive_errors = 0
        print(f"[API Client] Loaded {len(self.keys)} API key(s) in pool.")

    def get_service_key(self):
        return self.keys[self.current_key_index]

    def rotate_key(self):
        if self.current_key_index + 1 < len(self.keys):
            self.current_key_index += 1
            print(f"\n[Key Rotation] Switched to API key index {self.current_key_index} ({self.get_service_key()[:10]}...)")
            return True
        else:
            print("\n[Key Rotation] All API keys in the pool are exhausted!")
            return False

    def is_quota_limit_error(self, code, message):
        code_str = str(code).strip()
        msg_upper = str(message).upper()
        if code_str in ["22", "0022"] or "LIMIT" in msg_upper or "EXCEEDED" in msg_upper:
            return True
        return False

    def request(self, endpoint, params, timeout=45):
        url = f"http://apis.data.go.kr/B551011/DataLabService/{endpoint}"
        max_retries = 3

        while True:
            current_params = params.copy()
            current_params["serviceKey"] = self.get_service_key()
            current_params["MobileOS"] = "ETC"
            current_params["MobileApp"] = "Lovv"
            current_params["_type"] = "json"

            if self.consecutive_errors > 0:
                extra_sleep = min(self.consecutive_errors * 3, 15)
                print(f"[Dynamic Delay] Consecutive errors = {self.consecutive_errors}. Waiting {extra_sleep}s.")
                time.sleep(extra_sleep)

            retries_left = max_retries
            while retries_left > 0:
                try:
                    resp = requests.get(url, params=current_params, timeout=timeout)
                    
                    if resp.status_code == 429 or "API token quota exceeded" in resp.text:
                        print("[Rate Limit Exceeded] HTTP 429 or quota exceeded. Rotating key...")
                        if self.rotate_key():
                            self.consecutive_errors = 0
                            break
                        else:
                            raise RuntimeError("All keys exhausted on 429.")

                    resp.raise_for_status()

                    content_type = resp.headers.get("Content-Type", "")
                    if "xml" in content_type or resp.text.strip().startswith("<"):
                        text = resp.text
                        import re
                        code_match = re.search(r"<returnReasonCode>(.*?)</returnReasonCode>", text)
                        msg_match = re.search(r"<returnAuthMsg>(.*?)</returnAuthMsg>", text) or re.search(r"<errMsg>(.*?)</errMsg>", text)
                        
                        code = code_match.group(1) if code_match else "99"
                        msg = msg_match.group(1) if msg_match else "XML_ERROR"

                        if self.is_quota_limit_error(code, msg):
                            print(f"[Limit Exceeded] XML limit error: {msg}. Rotating key...")
                            if self.rotate_key():
                                break
                            else:
                                raise RuntimeError("All keys exhausted on XML limit.")
                        else:
                            raise RuntimeError(f"XML Error {code}: {msg}")

                    data = resp.json()
                    if isinstance(data, str):
                        raise ValueError(f"Expected dict, got str: {data}")

                    header = data.get("response", {}).get("header", {})
                    result_code = header.get("resultCode", "0000")
                    result_msg = header.get("resultMsg", "OK")

                    if result_code not in ["0000", "00", "OK"]:
                        if self.is_quota_limit_error(result_code, result_msg):
                            print(f"[Limit Exceeded] JSON limit error: {result_msg}. Rotating key...")
                            if self.rotate_key():
                                break
                            else:
                                raise RuntimeError("All keys exhausted on JSON limit.")
                        else:
                            raise RuntimeError(f"JSON Error {result_code}: {result_msg}")

                    self.consecutive_errors = 0
                    return data

                except Exception as e:
                    self.consecutive_errors += 1
                    retries_left -= 1
                    print(f"Request failed: {e}. Retries left: {retries_left}.")
                    if retries_left > 0:
                        time.sleep((max_retries - retries_left) * 2)
                    else:
                        raise e

def get_days_in_month(month_str):
    year, month = map(int, month_str.split("-"))
    days_map = {
        1: 31, 2: 28, 3: 31, 4: 30, 5: 31, 6: 30,
        7: 31, 8: 31, 9: 30, 10: 31, 11: 30, 12: 31
    }
    return days_map.get(month, 30)

def load_sigungu_codes():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    final_dir = os.path.join(base_dir, "data", "raw", "final")
    files = glob.glob(os.path.join(final_dir, "*.json"))
    
    mapping = {}
    for f_path in files:
        try:
            with open(f_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            meta = data.get("meta", {})
            city_en = meta.get("city_name_en")
            city_ko = meta.get("city_name_ko")
            
            for attr in data.get("attractions", []):
                detail = attr.get("detail", {})
                common = detail.get("common", {})
                regn = common.get("lDongRegnCd")
                signgu = common.get("lDongSignguCd")
                if regn and signgu:
                    mapping[f"{regn}{signgu}"] = {
                        "city_en": city_en,
                        "city_ko": city_ko
                    }
                    break
        except Exception:
            pass
            
    return mapping

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sigungu_map = load_sigungu_codes()
    if not sigungu_map:
        print("Error: Could not load sigungu codes.")
        sys.exit(1)
        
    print(f"Loaded {len(sigungu_map)} target sigungu codes.")
    
    client = BigDataClient()
    
    # We will query month-by-month for the year 2025
    months = [
        ("20250101", "20250131", "2025-01", 31),
        ("20250201", "20250228", "2025-02", 28),
        ("20250301", "20250331", "2025-03", 31),
        ("20250401", "20250430", "2025-04", 30),
        ("20250501", "20250531", "2025-05", 31),
        ("20250601", "20250630", "2025-06", 30),
        ("20250701", "20250731", "2025-07", 31),
        ("20250801", "20250831", "2025-08", 31),
        ("20250901", "20250930", "2025-09", 30),
        ("20251001", "20251031", "2025-10", 31),
        ("20251101", "20251130", "2025-11", 30),
        ("20251201", "20251231", "2025-12", 31),
    ]
    
    # Store aggregated monthly data for each city: city_en -> month -> visitor_type (1, 2, 3) -> sum of touNum
    # And we also keep the daily records for each month to verify
    city_monthly_sums = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    
    for start_ymd, end_ymd, month_name, days_count in months:
        print(f"\n--- Scraping Month: {month_name} ({start_ymd} to {end_ymd}) ---")
        page_no = 1
        num_of_rows = 5000
        month_records_count = 0
        
        while True:
            print(f"[{month_name}] Querying page {page_no}...")
            params = {
                "startYmd": start_ymd,
                "endYmd": end_ymd,
                "numOfRows": num_of_rows,
                "pageNo": page_no
            }
            
            try:
                resp_data = client.request("locgoRegnVisitrDDList", params)
                response = resp_data.get("response", {})
                body = response.get("body", {})
                items = body.get("items", {})
                item_list = items.get("item", []) if isinstance(items, dict) else []
                
                if not isinstance(item_list, list):
                    if isinstance(item_list, dict):
                        item_list = [item_list]
                    else:
                        item_list = []
                        
                if not item_list:
                    break
                    
                filtered_in_page = 0
                for item in item_list:
                    sig_code = str(item.get("signguCode", "")).strip()
                    if sig_code in sigungu_map:
                        city_en = sigungu_map[sig_code]["city_en"]
                        tou_div_cd = int(item.get("touDivCd", 0))
                        tou_num = float(item.get("touNum", 0.0))
                        
                        city_monthly_sums[city_en][month_name][tou_div_cd] += tou_num
                        filtered_in_page += 1
                        month_records_count += 1
                
                print(f"  Page {page_no}: Got {len(item_list)} items. Filtered {filtered_in_page}. Month total so far: {month_records_count}")
                
                total_count = int(body.get("totalCount", 0))
                if page_no * num_of_rows >= total_count:
                    break
                    
                page_no += 1
                time.sleep(0.5)
                
            except Exception as e:
                print(f"Error scraping month {month_name}, page {page_no}: {e}")
                sys.exit(1)
                
    # Now compute averages and prepare summaries
    print("\nComputing monthly averages and merging...")
    all_summaries = {}
    
    for city_en, months_data in city_monthly_sums.items():
        city_ko = sigungu_map[next(k for k, v in sigungu_map.items() if v["city_en"] == city_en)]["city_ko"]
        signgu_code = next(k for k, v in sigungu_map.items() if v["city_en"] == city_en)
        
        city_stat_list = []
        months_sorted = sorted(months_data.keys())
        
        for month_str in months_sorted:
            days = get_days_in_month(month_str)
            div_data = months_data[month_str]
            
            locals_total = div_data.get(1, 0.0)
            out_of_town_total = div_data.get(2, 0.0)
            foreigners_total = div_data.get(3, 0.0)
            total_visitors = locals_total + out_of_town_total + foreigners_total
            
            city_stat_list.append({
                "month": month_str,
                "days": days,
                "locals_total": round(locals_total, 2),
                "locals_daily_avg": round(locals_total / days, 2) if days > 0 else 0.0,
                "out_of_town_total": round(out_of_town_total, 2),
                "out_of_town_daily_avg": round(out_of_town_total / days, 2) if days > 0 else 0.0,
                "foreigners_total": round(foreigners_total, 2),
                "foreigners_daily_avg": round(foreigners_total / days, 2) if days > 0 else 0.0,
                "total_visitors": round(total_visitors, 2),
                "total_daily_avg": round(total_visitors / days, 2) if days > 0 else 0.0
            })
            
        total_locals_year = sum(m["locals_total"] for m in city_stat_list)
        total_out_of_town_year = sum(m["out_of_town_total"] for m in city_stat_list)
        total_foreigners_year = sum(m["foreigners_total"] for m in city_stat_list)
        total_visitors_year = sum(m["total_visitors"] for m in city_stat_list)
        total_days_year = sum(m["days"] for m in city_stat_list)
        
        all_summaries[city_en] = {
            "city_ko": city_ko,
            "signguCode": signgu_code,
            "year": 2025,
            "annual_totals": {
                "locals": round(total_locals_year, 2),
                "out_of_town": round(total_out_of_town_year, 2),
                "foreigners": round(total_foreigners_year, 2),
                "total_visitors": round(total_visitors_year, 2)
            },
            "annual_daily_averages": {
                "locals": round(total_locals_year / total_days_year, 2) if total_days_year > 0 else 0.0,
                "out_of_town": round(total_out_of_town_year / total_days_year, 2) if total_days_year > 0 else 0.0,
                "foreigners": round(total_foreigners_year / total_days_year, 2) if total_days_year > 0 else 0.0,
                "total_visitors": round(total_visitors_year / total_days_year, 2) if total_days_year > 0 else 0.0
            },
            "monthly_statistics": city_stat_list
        }
        
    # Write aggregated data back to final city files
    final_dir = os.path.join(base_dir, "data", "raw", "final")
    updated_files_count = 0
    for city_en, stats in all_summaries.items():
        city_file_path = os.path.join(final_dir, f"{city_en}.json")
        if os.path.exists(city_file_path):
            try:
                with open(city_file_path, "r", encoding="utf-8") as f:
                    city_data = json.load(f)
                    
                city_data["visitor_statistics"] = {
                    "year": stats["year"],
                    "annual_totals": stats["annual_totals"],
                    "annual_daily_averages": stats["annual_daily_averages"],
                    "monthly_statistics": stats["monthly_statistics"]
                }
                
                with open(city_file_path, "w", encoding="utf-8") as f:
                    json.dump(city_data, f, ensure_ascii=False, indent=2)
                    
                updated_files_count += 1
            except Exception as e:
                print(f"Error updating file {city_file_path}: {e}")
                
    print(f"Successfully updated visitor_statistics in {updated_files_count} final city JSON files.")
    
    # Save standalone summary
    summary_output_dir = os.path.join(base_dir, "data", "visitor")
    os.makedirs(summary_output_dir, exist_ok=True)
    summary_path = os.path.join(summary_output_dir, "monthly_visitor_averages.json")
    
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_summaries, f, ensure_ascii=False, indent=2)
        
    print(f"Saved global visitor statistics summary to {summary_path}")

if __name__ == "__main__":
    main()
