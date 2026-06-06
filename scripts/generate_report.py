import os
import json
import glob
from collections import defaultdict

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    list_dir = os.path.join(base_dir, "data", "raw", "list_by_city")
    
    # Target themes
    target_themes = ['온천·휴양', '바다·해안', '역사·전통', '미식·노포', '자연·트레킹', '예술·감성']
    
    # Structure: report_data[province][sigungu][theme] = {'attractions': 0, 'festivals': 0}
    report_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: {'attractions': 0, 'festivals': 0})))
    
    filtered_files = glob.glob(os.path.join(list_dir, "*_filtered.json"))
    
    for file_path in filtered_files:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        meta = data.get("meta", {})
        prov = meta.get("province", "Unknown")
        sigungu = meta.get("city_name_ko", "Unknown")
        
        # Count attractions
        for item in data.get("attractions", []):
            theme = item.get("_assigned_theme", "No Theme")
            report_data[prov][sigungu][theme]['attractions'] += 1
            
        # Count festivals
        for item in data.get("festivals", []):
            theme = item.get("_assigned_theme", "No Theme")
            report_data[prov][sigungu][theme]['festivals'] += 1

    # Generate Markdown content
    lines = []
    lines.append("# Filtered TourAPI Data Report (Gangwon & Gyeongbuk)")
    lines.append("")
    lines.append("This report summarizes the filtered counts of attractions and festivals across the target sigungus in Gangwon-do and Gyeongbuk-do, grouped by theme.")
    lines.append("")
    
    # Overall summary table
    lines.append("## Overall Summary by Theme")
    lines.append("")
    lines.append("| Theme | Attractions Count | Festivals Count | Total Count |")
    lines.append("|---|---|---|---|")
    
    theme_totals = {t: {'attractions': 0, 'festivals': 0} for t in target_themes}
    for prov, sigungus in report_data.items():
        for sigungu, themes in sigungus.items():
            for theme, counts in themes.items():
                if theme in theme_totals:
                    theme_totals[theme]['attractions'] += counts['attractions']
                    theme_totals[theme]['festivals'] += counts['festivals']
                    
    total_attrs = 0
    total_fests = 0
    for theme in target_themes:
        attrs = theme_totals[theme]['attractions']
        fests = theme_totals[theme]['festivals']
        total = attrs + fests
        lines.append(f"| **{theme}** | {attrs} | {fests} | {total} |")
        total_attrs += attrs
        total_fests += fests
    lines.append(f"| **TOTAL** | **{total_attrs}** | **{total_fests}** | **{total_attrs + total_fests}** |")
    lines.append("")
    
    # Detailed tables by Province
    for prov in sorted(report_data.keys()):
        lines.append(f"## {prov} Detailed Summary")
        lines.append("")
        lines.append("| Sigungu | Theme | Attractions | Festivals | Total |")
        lines.append("|---|---|---|---|---|")
        
        prov_attrs = 0
        prov_fests = 0
        
        sigungus_data = report_data[prov]
        for sigungu in sorted(sigungus_data.keys()):
            themes_data = sigungus_data[sigungu]
            # Print only themes that have data to keep the table readable
            has_data = False
            for theme in target_themes:
                counts = themes_data.get(theme, {'attractions': 0, 'festivals': 0})
                attrs = counts['attractions']
                fests = counts['festivals']
                if attrs > 0 or fests > 0:
                    has_data = True
                    lines.append(f"| {sigungu} | {theme} | {attrs} | {fests} | {attrs + fests} |")
                    prov_attrs += attrs
                    prov_fests += fests
            if not has_data:
                lines.append(f"| {sigungu} | - | 0 | 0 | 0 |")
                
        lines.append(f"| **{prov} TOTAL** | | **{prov_attrs}** | **{prov_fests}** | **{prov_attrs + prov_fests}** |")
        lines.append("")

    # Save to artifact directory
    artifact_path = r"C:\Users\Playdata\.gemini\antigravity\brain\f53c9c8d-4acc-448a-8991-2d33af013ef5\filtered_data_report.md"
    os.makedirs(os.path.dirname(artifact_path), exist_ok=True)
    with open(artifact_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    print(f"Report successfully generated at {artifact_path}")

if __name__ == "__main__":
    main()
