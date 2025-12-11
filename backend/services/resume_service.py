#resume_service.py

import os
import json
import spacy
from typing import Dict, Any, Tuple
from backend.services.ocr_service import OCRProcessor
from backend.config import settings

# 載入 Spacy 模型 (全域載入一次即可)
try:
    nlp = spacy.load("zh_core_web_sm")
except OSError:
    print("警告: 尚未下載 zh_core_web_sm 模型，實體辨識功能將受限。")
    nlp = None

class ResumeService:
    def __init__(self):
        # 初始化 OCR 處理器
        self.ocr_processor = OCRProcessor()

    def process_resume(self, file_path: str) -> Dict[str, Any]:
        """
        處理履歷的主入口：OCR -> 結構化 -> 回傳完整資料
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"檔案不存在: {file_path}")

        # 1. 執行 OCR
        success, ocr_result = self.ocr_processor.process_file(file_path)
        if not success:
            error_msg = ocr_result.get('error', '未知錯誤')
            raise ValueError(f"OCR 處理失敗: {error_msg}")

        # 2. 提取純文字 (用於 RAG 或 Prompt)
        full_text = self._extract_full_text(ocr_result)
        
        # 3. 執行結構化解析 (用於 Unity 顯示)
        structured_data = self._structure_resume_from_ocr_json(ocr_result)

        return {
            "full_text": full_text,
            "structured": structured_data,
            "ocr_raw": ocr_result # 視需求保留
        }

    def _extract_full_text(self, ocr_result: Dict) -> str:
        """從 OCR 結果合併所有文字"""
        all_text = []
        for page in ocr_result.get('pages', []):
            page_text = page.get('full_text', '')
            if page_text:
                all_text.append(page_text)
        return "\n".join(all_text)

    def _structure_resume_from_ocr_json(self, ocr_json: Dict) -> Dict[str, Any]:
        """
        (原 resume_structurer.py 的邏輯)
        將 OCR JSON 轉成結構化 dict
        """
        if not ocr_json.get('pages'):
            return {}

        page = ocr_json['pages'][0]
        blocks = page.get('text_blocks', [])
        tables = page.get('tables', [])
        resume = {}

        # --- 關鍵字定義 ---
        keywords = {
            'name': ['姓名', '中文姓名', 'name'],
            'phone': ['手機', '電話', 'phone', 'tel'],
            'email': ['Email', 'E-mail', 'email', 'mail'],
            'address': ['通訊地址', '居住地', '地址', 'address'],
            'birth_date': ['出生日期', '生日', 'birth', '出生'],
            'education': ['最高學歷', '學歷', '學校', '科系', 'education', 'degree'],
            'job_title': ['應徵職務', '職稱', 'job', 'title', '申請職位'],
        }

        # --- 1. 基本資料萃取 ---
        for block in blocks:
            for item in block['content']:
                txt = item['text']
                for field, kw_list in keywords.items():
                    # 如果該欄位已經抓到了，就跳過 (避免覆蓋)
                    if field in resume:
                        continue
                    
                    for kw in kw_list:
                        if kw in txt:
                            value = txt.replace(kw, '').replace(':', '').strip()
                            # 若內容為空，嘗試取同一個 block 的下一個 item
                            if not value:
                                try:
                                    idx = block['content'].index(item)
                                    if idx + 1 < len(block['content']):
                                        next_txt = block['content'][idx+1]['text'].strip()
                                        # 簡單防呆：下一行不能也是關鍵字
                                        if next_txt and not any(k in next_txt for k in kw_list):
                                            value = next_txt
                                except ValueError:
                                    pass
                            
                            if value:
                                resume[field] = value

        # --- 2. 技能表格萃取 ---
        skills = []
        for table in tables:
            # 這裡假設 OCR 有正確分類到 skills，或依據內容判斷
            if table.get('category') == 'skills' or '技能' in str(table.get('data')):
                for row in table.get('data', []):
                    for cell in row:
                        if cell.strip():
                            skills.append(cell.strip())
        if skills:
            resume['skills'] = list(set(skills)) # 去重

        # --- 3. 工作經歷簡易萃取 ---
        work_experience = []
        for block in blocks:
            # 簡易判斷：如果 block 裡有公司或職稱的關鍵字
            block_text = "".join([i['text'] for i in block['content']])
            if "公司" in block_text or "任職" in block_text:
                work_experience.append(block_text)
        
        if work_experience:
            resume['work_experience_raw'] = work_experience

        return resume

    # 如果有 extract_entities (spacy) 需求，可以放在這裡
    def _extract_entities(self, text):
        if not nlp: return []
        doc = nlp(text)
        return [(ent.text, ent.label_) for ent in doc.ents]
    