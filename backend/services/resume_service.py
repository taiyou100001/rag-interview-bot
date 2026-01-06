# resume_service.py

import os
import json
import spacy
from typing import Dict, Any, List
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
        
        # 3. 執行結構化解析 (整合了 HEAD 較完整的邏輯)
        structured_data = self._structure_resume_from_ocr_json(ocr_result)

        # 4. (可選) 實體辨識增強
        entities = self._extract_entities(full_text)

        return {
            "full_text": full_text,
            "structured": structured_data,
            "entities": entities,
            "ocr_raw": ocr_result # 視需求保留
        }

    def _extract_full_text(self, ocr_result: Dict) -> str:
        """從 OCR 結果合併所有文字"""
        all_text = []
        for page in ocr_result.get('pages', []):
            page_text = page.get('full_text', '') or page.get('page_text', '')
            if page_text:
                all_text.append(page_text)
        return "\n".join(all_text)

    def _extract_entities(self, text):
        """使用 Spacy 提取實體"""
        if not nlp: return []
        doc = nlp(text)
        return [(ent.text, ent.label_) for ent in doc.ents]

    def _structure_resume_from_ocr_json(self, ocr_json: Dict) -> Dict[str, Any]:
        """
        將 OCR JSON 轉成結構化 dict
        (整合自 HEAD 的 structure_resume_from_ocr_json，邏輯較完整)
        """
        if not ocr_json.get('pages'):
            return {}

        page = ocr_json['pages'][0]
        blocks = page.get('text_blocks', [])
        # 有些 OCR 格式可能不同，這裡做個容錯
        if not blocks and 'pages' in ocr_json:
             # 嘗試從 raw lines 重組，或依賴 OCRProcessor 的輸出格式
             # 假設 OCRProcessor 已經標準化輸出，這裡直接用
             pass
        
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
            for item in block.get('content', []):
                txt = item.get('text', '')
                for field, kw_list in keywords.items():
                    # 若該欄位已存在，跳過 (避免覆蓋)
                    if field in resume:
                        continue

                    for kw in kw_list:
                        if kw in txt:
                            # 取出欄位內容
                            value = txt.replace(kw, '').replace(':', '').strip()
                            
                            # 若內容為空，嘗試取下一個 item
                            if not value:
                                try:
                                    idx = block['content'].index(item)
                                    if idx + 1 < len(block['content']):
                                        next_txt = block['content'][idx+1]['text'].strip()
                                        # 簡單防呆：下一行不能也是關鍵字
                                        if next_txt and not any(k in next_txt for k in kw_list):
                                            value = next_txt
                                except (ValueError, IndexError):
                                    pass
                            
                            if value:
                                resume[field] = value
                            break # 找到關鍵字就跳出內層迴圈

        # --- 2. 技能表格萃取 ---
        skills = []
        for table in tables:
            # 寬鬆判斷 category 或內容
            if table.get('category') == 'skills' or '技能' in str(table.get('data')):
                for row in table.get('data', []):
                    for cell in row:
                        if isinstance(cell, str) and cell.strip():
                            skills.append(cell.strip())
        if skills:
            resume['skills'] = list(set(skills)) # 去重

        # --- 3. 工作經歷 ---
        work_experience = []
        # 定義工作相關關鍵字
        work_keywords = ['公司', '組織', '餐廳', '社', 'organization', '職稱', 'title', '負責', '工作內容']
        
        for block in blocks:
            org, title, period, desc = None, None, None, None
            is_work_block = False
            
            for item in block.get('content', []):
                txt = item.get('text', '')
                
                # 判斷是否為工作區塊的依據
                if any(k in txt for k in work_keywords) or '工作經歷' in txt:
                    is_work_block = True

                if any(kw in txt for kw in ['公司', '組織', '餐廳', '社', 'organization']):
                    org = txt
                if any(kw in txt for kw in ['職稱', 'title', '服務生', '活動長']):
                    title = txt
                if any(kw in txt for kw in ['年', '月', '日', 'period', '時間', '至']):
                    period = txt
                if any(kw in txt for kw in ['負責', '工作內容', '描述', 'desc', 'summary']):
                    desc = txt
            
            # 只有當萃取到足夠資訊時才加入
            if is_work_block and (org or title):
                work_experience.append({
                    'organization': org or "未提及公司",
                    'title': title or "未提及職稱",
                    'period': period or "",
                    'description': desc or ""
                })
        
        if work_experience:
            resume['work_experience'] = work_experience

        # --- 4. 其他欄位 (語言, 電腦, 證照, 時段) ---
        
        # 語言能力
        language_keywords = ['語言能力', '語言', 'language']
        for block in blocks:
            for item in block.get('content', []):
                txt = item.get('text', '')
                if any(kw in txt for kw in language_keywords):
                    # 簡單處理：移除關鍵字後依頓號分割
                    cleaned = txt.replace('語言能力', '').replace('語言', '').replace(':', '')
                    langs = [lang.strip() for lang in cleaned.split('、') if lang.strip()]
                    if langs:
                        resume['languages'] = langs

        # 電腦技能
        computer_keywords = ['電腦能力', '電腦技能', 'computer', 'Excel', 'Word']
        for block in blocks:
            for item in block.get('content', []):
                txt = item.get('text', '')
                if any(kw in txt for kw in computer_keywords):
                    cleaned = txt.replace('擅長', '').replace('電腦能力', '').replace('電腦技能', '').replace(':', '')
                    skills_list = [s.strip() for s in cleaned.split('、') if s.strip()]
                    if skills_list:
                        resume['computer_skills'] = skills_list

        # 證照
        certificate_keywords = ['證照', 'license', 'certificate', '丙級', '蛋糕']
        for block in blocks:
            for item in block.get('content', []):
                txt = item.get('text', '')
                if any(kw in txt for kw in certificate_keywords):
                    cleaned = txt.replace('專業證照', '').replace('證照', '').replace(':', '')
                    certs = [c.strip() for c in cleaned.split('、') if c.strip()]
                    if certs:
                        resume['certificates'] = certs
                if '駕照' in txt:
                    resume['license'] = [txt.replace('駕照', '').strip()]

        # 可配合時段
        available_times = {}
        days = ['週一', '週二', '週三', '週四', '週五', '週六', '週日']
        for block in blocks:
            # 檢查整個 block 是否包含星期
            block_content = block.get('content', [])
            block_text = "".join([i['text'] for i in block_content])
            
            for day in days:
                if day in block_text:
                    # 嘗試在該 block 中找時間格式
                    time_str = None
                    for t_item in block_content:
                        t_txt = t_item['text']
                        if any(h in t_txt for h in ['10:00', '09:00', '18:00', '19:00', ':', '點']):
                            time_str = t_txt
                            break
                    available_times[day] = time_str or '可配合'
        
        if available_times:
            resume['available_times'] = available_times

        return resume