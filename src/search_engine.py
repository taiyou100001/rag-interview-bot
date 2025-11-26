# search_engine.py (修正版)
import os
import json
from typing import Optional

def read_pdf_resume(file_path: str) -> str:
    """
    使用 Azure OCR 讀取履歷
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"檔案不存在: {file_path}")
    
    # 檢查 Azure 憑證
    if not os.getenv("AZURE_SUBSCRIPTION_KEY"):
        raise ValueError(
            "未設定 Azure OCR 憑證。\n"
            "請在 .env 檔案中設定:\n"
            "AZURE_SUBSCRIPTION_KEY=你的金鑰\n"
            "AZURE_ENDPOINT=你的端點"
        )
    
    try:
        from ocr_processor import OCRProcessor
        from resume_structurer import structure_resume_from_ocr_json
        
        processor = OCRProcessor()
        success, ocr_result = processor.process_file(file_path)
        
        if not success:
            raise ValueError(f"OCR 處理失敗: {ocr_result.get('error', '未知錯誤')}")
        
        # 提取文字
        all_text = []
        for page in ocr_result.get('pages', []):
            page_text = page.get('full_text', '')
            if page_text:
                all_text.append(page_text)
        
        if not all_text:
            raise ValueError("OCR 未能提取任何文字內容")
        
        full_text = "\n".join(all_text)
        
        # 儲存結構化履歷
        try:
            structured = structure_resume_from_ocr_json(ocr_result)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            json_path = f"resume_structured_{base_name}.json"
            
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(structured, f, ensure_ascii=False, indent=2)
            
            print(f"✓ 結構化履歷已儲存: {json_path}")
        except Exception as e:
            print(f"提示: 結構化處理失敗 ({e})")
        
        return full_text
        
    except ImportError as e:
        raise ImportError(
            f"OCR 模組載入失敗: {e}\n"
            "請執行: pip install azure-cognitiveservices-vision-computervision msrest"
        )


def get_structured_resume(file_path: str) -> Optional[dict]:
    """
    取得結構化履歷 (如果存在)
    """
    base_name = os.path.splitext(os.path.basename(file_path))[0]
    json_path = f"resume_structured_{base_name}.json"
    
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None


def load_questions(data_dir="data"):
    """載入題庫 - 使用原生 JSON 讀取"""
    if not os.path.exists(data_dir):
        print(f"提示: 資料夾 '{data_dir}' 不存在,將為您建立範例題庫")
        os.makedirs(data_dir)
        
        sample_data = [
            {"職位": "軟體工程師", "類型": "技術", "題目": "請說明 RESTful API 的設計原則。"},
            {"職位": "後端工程師", "類型": "技術", "題目": "如何設計一個可擴展的微服務架構?"},
            {"職位": "行銷企劃", "類型": "職能", "題目": "你認為一個成功的行銷活動,最重要的三個要素是什麼?"},
            {"職位": "餐飲服務", "類型": "情境", "題目": "遇到客訴時,你會如何處理?"}
        ]
        
        with open(os.path.join(data_dir, "interview_questions.json"), "w", encoding="utf-8") as f:
            json.dump(sample_data, f, ensure_ascii=False, indent=2)
    
    # 直接讀取 JSON 檔案
    all_questions = []
    
    for filename in os.listdir(data_dir):
        if filename.endswith('.json'):
            file_path = os.path.join(data_dir, filename)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    questions = json.load(f)
                    if isinstance(questions, list):
                        all_questions.extend(questions)
                    else:
                        print(f"警告: {filename} 格式錯誤,應為 JSON 陣列")
            except json.JSONDecodeError as e:
                print(f"警告: {filename} JSON 解析失敗: {e}")
            except Exception as e:
                print(f"警告: 讀取 {filename} 時發生錯誤: {e}")
    
    if not all_questions:
        raise ValueError("錯誤: 沒有找到任何有效的面試問題")

    return all_questions


def search_questions_by_keywords(keywords: list, questions: list, top_k=3):
    """關鍵字檢索"""
    if not keywords:
        return []
    
    scored_questions = []
    for q in questions:
        score = 0
        question_text = q.get("題目", "")
        question_type = q.get("類型", "")
        question_job = q.get("職位", "")
        
        for keyword in keywords:
            if keyword in question_text:
                score += 3
            if keyword in question_type:
                score += 2
            if keyword in question_job:
                score += 2
        
        if score > 0:
            scored_questions.append({"question": question_text, "score": score})
    
    sorted_questions = sorted(scored_questions, key=lambda x: x["score"], reverse=True)
    return [item["question"] for item in sorted_questions[:top_k]]