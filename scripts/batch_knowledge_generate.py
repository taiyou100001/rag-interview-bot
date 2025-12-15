# batch_knowledge_generator.py
import ollama
import json
import os
from datetime import datetime

class BatchKnowledgeGenerator:
    def __init__(self, model="llama3.1:8b"):
        self.model = model
    
    # 各行業職位清單
    POSITIONS = {
        # 科技產業
        "tech": [
            "軟體工程師", "後端工程師", "前端工程師", "全端工程師",
            "資料科學家", "資料分析師", "機器學習工程師",
            "DevOps 工程師", "系統管理員", "網路工程師",
            "QA 測試工程師", "UI/UX 設計師", "產品經理"
        ],
        
        # 商業管理
        "business": [
            "行銷企劃", "數位行銷專員", "品牌經理",
            "業務代表", "業務經理", "客戶經理",
            "專案管理師", "產品經理", "營運經理",
            "人力資源專員", "財務分析師", "會計師"
        ],
        
        # 服務業
        "service": [
            "餐飲服務人員", "廚師", "調酒師",
            "飯店櫃檯人員", "房務人員", "導遊",
            "零售門市人員", "店長", "客服專員",
            "美容美髮師", "健身教練", "按摩師"
        ],
        
        # 醫療保健
        "healthcare": [
            "護理師", "藥師", "醫檢師",
            "物理治療師", "職能治療師", "營養師",
            "醫務行政人員", "醫療器材業務"
        ],
        
        # 教育培訓
        "education": [
            "國小教師", "國中教師", "高中教師",
            "補習班老師", "英文家教", "幼教老師",
            "企業培訓講師", "線上課程講師"
        ],
        
        # 創意設計
        "creative": [
            "平面設計師", "網頁設計師", "動畫設計師",
            "影片剪輯師", "攝影師", "文案企劃",
            "社群小編", "內容創作者", "Podcaster"
        ],
        
        # 製造工程
        "manufacturing": [
            "機械工程師", "電機工程師", "品保工程師",
            "生產管理", "供應鏈管理", "採購專員",
            "工廠作業員", "品管人員"
        ],
        
        # 金融保險
        "finance": [
            "理財專員", "保險業務", "銀行櫃員",
            "投資顧問", "風險管理師", "稽核人員"
        ],
        
        # 法律政府
        "legal": [
            "律師", "法務人員", "專利工程師",
            "公務員", "社工", "警察"
        ],
        
        # 媒體傳播
        "media": [
            "記者", "編輯", "主播",
            "公關專員", "活動企劃", "廣告AE"
        ]
    }
    
    def generate_knowledge(self, position: str, industry_zh: str):
        """用 LLM 生成單一職位的知識庫"""
        
        prompt = f"""你是職涯專家，請為「{position}」生成面試知識庫。

產業：{industry_zh}

請生成 JSON 格式（務必使用繁體中文）：

{{
  "position": "{position}",
  "industry": "{industry_zh}",
  "skill_areas": [
    {{
      "area": "核心技能領域名稱",
      "importance": "核心/重要/加分",
      "key_concepts": ["概念1", "概念2", "概念3", "概念4"],
      "evaluation_points": ["評估點1", "評估點2", "評估點3"],
      "example_scenarios": ["情境1", "情境2"]
    }}
  ],
  "interview_dimensions": [
    {{
      "dimension": "評估維度",
      "stages": ["階段1", "階段2", "階段3"],
      "description": "說明"
    }}
  ]
}}

要求：
1. skill_areas 至少 3 個
2. 符合台灣職場實況
3. 務必使用繁體中文
4. 只輸出 JSON，無其他文字

JSON："""
        
        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': '你是台灣的職涯專家，只使用繁體中文。'},
                    {'role': 'user', 'content': prompt}
                ],
                options={'temperature': 0.3, 'num_predict': 2048}
            )
            
            content = response['message']['content']
            
            # 提取 JSON
            if '```json' in content:
                json_str = content.split('```json')[1].split('```')[0]
            elif '```' in content:
                json_str = content.split('```')[1].split('```')[0]
            else:
                json_str = content
            
            return json.loads(json_str.strip())
            
        except Exception as e:
            print(f"  生成失敗: {e}")
            return None
    
    def batch_generate(self, categories: list = None):
        """批次生成多個類別"""
        
        if categories is None:
            categories = list(self.POSITIONS.keys())
        
        industry_map = {
            "tech": "科技",
            "business": "商業",
            "service": "服務業",
            "healthcare": "醫療保健",
            "education": "教育",
            "creative": "創意",
            "manufacturing": "製造",
            "finance": "金融",
            "legal": "法律",
            "media": "媒體"
        }
        
        total = sum(len(self.POSITIONS[cat]) for cat in categories)
        current = 0
        
        print(f"開始生成 {total} 個職位的知識庫...\n")
        
        for category in categories:
            industry_zh = industry_map.get(category, "其他")
            positions = self.POSITIONS[category]
            
            print(f"【{industry_zh}】({len(positions)} 個職位)")
            
            for position in positions:
                current += 1
                print(f"[{current}/{total}] 生成: {position}...", end=" ")
                
                data = self.generate_knowledge(position, industry_zh)
                
                if data:
                    self._save_knowledge(data, category, position)
                    print("✓")
                else:
                    print("✗")
            
            print()
    
    def _save_knowledge(self, data: dict, category: str, position: str):
        """儲存知識庫"""
        dir_path = f"knowledge_base/{category}"
        os.makedirs(dir_path, exist_ok=True)
        
        # 檔案名稱（移除特殊字元）
        filename = position.replace('/', '_').replace(' ', '_') + '.json'
        filepath = os.path.join(dir_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    generator = BatchKnowledgeGenerator()
    
    print("=" * 60)
    print("知識庫批次生成器")
    print("=" * 60)
    print("\n請選擇要生成的類別：")
    print("1. 全部生成（100+ 職位，約需 30-60 分鐘）")
    print("2. 科技產業")
    print("3. 商業管理")
    print("4. 服務業")
    print("5. 自訂（輸入類別代碼，如: tech,business）")
    
    choice = input("\n請選擇 (1-5): ").strip()
    
    if choice == "1":
        generator.batch_generate()
    elif choice == "2":
        generator.batch_generate(["tech"])
    elif choice == "3":
        generator.batch_generate(["business"])
    elif choice == "4":
        generator.batch_generate(["service"])
    elif choice == "5":
        cats = input("輸入類別（逗號分隔）: ").strip().split(',')
        generator.batch_generate([c.strip() for c in cats])
    else:
        print("無效選擇")
    
    print("\n" + "=" * 60)
    print("完成！知識庫已儲存到 knowledge_base/ 目錄")