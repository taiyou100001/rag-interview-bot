# monitor.py - 監控爬蟲進度
import json
import time
from pathlib import Path

def monitor_progress():
    """監控爬蟲進度"""
    output_file = Path('output/scraped_data.json')
    
    print("開始監控爬蟲...")
    last_size = 0
    
    while True:
        if output_file.exists():
            with open(output_file, 'r', encoding='utf-8') as f:
                try:
                    data = json.load(f)
                    current_size = len(data)
                    
                    if current_size != last_size:
                        print(f"\n已爬取: {current_size} 筆")
                        
                        # 統計各職位數量
                        position_counts = {}
                        for item in data:
                            pos = item['position']
                            position_counts[pos] = position_counts.get(pos, 0) + 1
                        
                        for pos, count in position_counts.items():
                            print(f"  {pos}: {count} 筆")
                        
                        last_size = current_size
                except:
                    pass
        
        time.sleep(5)

if __name__ == "__main__":
    monitor_progress()
    