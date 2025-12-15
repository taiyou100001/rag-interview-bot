# knowledge_generator.py
import ollama
import json
import os

class KnowledgeBaseGenerator:
    def __init__(self, model="llama3.1:8b"):
        self.model = model
    
    def generate_position_knowledge(self, position: str, industry: str, category: str):
        """為特定職位生成知識庫"""
        
        prompt = f"""請為「{position}」職位生成完整的面試知識庫。

產業分類: {industry}

請以 JSON 格式輸出，必須包含:

1. position: 職位名稱
2. industry: 產業類別
3. skill_areas: 至少 4 個核心技能領域，每個包含:
   - area: 技能名稱
   - importance: 核心/進階/加分
   - key_concepts: 至少 4 個核心概念
   - evaluation_points: 至少 3 個評估要點
   - example_scenarios: 至少 2 個實際情境

4. interview_dimensions: 至少 2 個面試維度，每個包含:
   - dimension: 維度名稱
   - stages: 評估階段（至少3個）
   - description: 說明

請確保內容專業、具體、可評估。使用繁體中文。

JSON:"""

        try:
            response = ollama.chat(
                model=self.model,
                messages=[{'role': 'user', 'content': prompt}],
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
            
            # 解析
            data = json.loads(json_str.strip())
            
            # 補充資訊
            if 'position' not in data:
                data['position'] = position
            if 'industry' not in data:
                data['industry'] = industry
            
            return data
            
        except Exception as e:
            print(f"生成失敗: {e}")
            return None
    
    def save_knowledge(self, data: dict, category: str, filename: str):
        """儲存知識庫到檔案"""
        dir_path = os.path.join("knowledge_base", category)
        os.makedirs(dir_path, exist_ok=True)
        
        filepath = os.path.join(dir_path, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"✓ 已儲存: {filepath}")
    
    def batch_generate(self, positions_config: list):
        """批次生成多個職位"""
        for config in positions_config:
            print(f"\n生成: {config['position']}...")
            
            data = self.generate_position_knowledge(
                position=config['position'],
                industry=config['industry'],
                category=config['category']
            )
            
            if data:
                self.save_knowledge(
                    data=data,
                    category=config['category'],
                    filename=config['filename']
                )
                print(f"✓ {config['position']} 完成")
            else:
                print(f"✗ {config['position']} 失敗")


# 執行生成
if __name__ == "__main__":
    generator = KnowledgeBaseGenerator()
    
    # 定義要生成的職位
    positions = [
        # 科技產業
        {"position": "軟體工程師", "industry": "科技", "category": "tech", "filename": "software_engineer.json"},
        {"position": "後端工程師", "industry": "科技", "category": "tech", "filename": "backend_engineer.json"},
        {"position": "前端工程師", "industry": "科技", "category": "tech", "filename": "frontend_engineer.json"},
        {"position": "資料分析師", "industry": "科技", "category": "tech", "filename": "data_analyst.json"},
        
        # 商業
        {"position": "行銷企劃", "industry": "商業", "category": "business", "filename": "marketing.json"},
        {"position": "業務銷售", "industry": "商業", "category": "business", "filename": "sales.json"},
        {"position": "專案管理師", "industry": "商業", "category": "business", "filename": "project_manager.json"},
        
        # 服務業
        {"position": "餐飲服務人員", "industry": "服務業", "category": "service", "filename": "restaurant.json"},
        {"position": "零售門市人員", "industry": "服務業", "category": "service", "filename": "retail.json"},
        
        # 創意產業
        {"position": "UI/UX 設計師", "industry": "創意", "category": "creative", "filename": "designer.json"},
        {"position": "內容創作者", "industry": "創意", "category": "creative", "filename": "content_creator.json"},
    ]
    
    # 批次生成
    generator.batch_generate(positions)
    
    print("\n" + "=" * 60)
    print("知識庫生成完成!")