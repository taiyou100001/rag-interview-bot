# create_test_data.py
import json
import os

def create_test_knowledge_base():
    """手動建立測試知識庫"""
    
    # 後端工程師
    backend = {
        "position": "後端工程師",
        "industry": "科技",
        "skill_areas": [
            {
                "area": "程式語言",
                "importance": "核心",
                "key_concepts": ["Python", "Java", "Go", "Node.js"],
                "evaluation_points": ["語言熟練度", "最佳實踐", "程式碼品質"],
                "example_scenarios": ["API 開發", "資料處理"]
            },
            {
                "area": "資料庫",
                "importance": "核心",
                "key_concepts": ["SQL", "NoSQL", "Redis", "PostgreSQL"],
                "evaluation_points": ["設計能力", "查詢優化", "資料一致性"],
                "example_scenarios": ["設計訂單系統", "優化查詢效能"]
            },
            {
                "area": "系統架構",
                "importance": "進階",
                "key_concepts": ["微服務", "RESTful API", "Docker", "Kubernetes"],
                "evaluation_points": ["架構設計", "擴展性", "維護性"],
                "example_scenarios": ["設計可擴展系統", "容器化部署"]
            }
        ],
        "interview_dimensions": [
            {
                "dimension": "技術深度",
                "stages": ["基礎概念", "實作經驗", "架構設計"],
                "description": "評估技術能力的完整性"
            },
            {
                "dimension": "問題解決",
                "stages": ["問題分析", "方案設計", "權衡取捨"],
                "description": "評估解決問題的思維"
            }
        ]
    }
    
    # 儲存
    os.makedirs('knowledge_base/tech', exist_ok=True)
    with open('knowledge_base/tech/backend_engineer.json', 'w', encoding='utf-8') as f:
        json.dump(backend, f, ensure_ascii=False, indent=2)
    
    print("✓ 已建立測試知識庫")

if __name__ == "__main__":
    create_test_knowledge_base()