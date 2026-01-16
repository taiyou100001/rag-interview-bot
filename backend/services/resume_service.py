# backend/services/resume_service.py
from typing import Dict, Tuple, List

class ResumeService:
    """
    ResumeService 負責從 Azure OCR 結果中抽取文字，並進行簡單的職稱推論。
    - 同時支援 snake_case 與 camelCase 的鍵名
    - 兼容 Azure Read API 3.0/3.1 (readResults) 與 3.2+ (pages) 結構
    - 提供結構化錯誤回傳與詳細 debug log
    """

    def structure_resume(self, ocr_result: Dict) -> Dict:
        """
        主入口：結合抽取與職稱推論，並加強錯誤處理。
        返回結構：
        {
            "raw_text": str,
            "job_title": str,
            "structure_used": str,  # "read_3_2_pages" 或 "read_3_0_results" 或 ""
            "error": Optional[dict] # 結構化錯誤
        }
        """
        # 顶层 debug：列出所有鍵名
        top_keys = list(ocr_result.keys()) if isinstance(ocr_result, dict) else []
        print(f"[DEBUG] OCR top-level keys: {top_keys}")

        text, structure_used, error = self._extract_text_multi_version(ocr_result)

        # 若抽取出錯或文字過短，回傳錯誤 dict
        if error or len(text.strip()) < 10:
            available_keys = top_keys
            structured_error = error or {
                "code": "StructureNotSupported",
                "message": "未找到 pages 或 readResults 結構，無法提取文字",
                "available_keys": available_keys,
            }
            print(f"[ERROR] 結構化抽取失敗: {structured_error}")
            return {
                "raw_text": "",
                "job_title": "未指定職位",
                "structure_used": structure_used or "",
                "error": structured_error,
            }

        job_title = self._infer_job_title(text)

        return {
            "raw_text": text,
            "job_title": job_title,
            "structure_used": structure_used,
            "error": None,
        }

    def _extract_text_multi_version(self, ocr_result: Dict) -> Tuple[str, str, Dict]:
        """
        支援多種結構命名，優先嘗試 Read 3.2+ 的 pages，再回退到 Read 3.0/3.1 的 readResults。
        返回 (text, structure_used, error)
        - text: 擷取出的全文字串
        - structure_used: "read_3_2_pages" 或 "read_3_0_results" 或 ""
        - error: 若失敗則為結構化錯誤 dict
        """
        if not isinstance(ocr_result, dict):
            err = {
                "code": "InvalidInput",
                "message": "OCR 結果不是字典結構",
                "available_keys": [],
            }
            print(f"[ERROR] {err}")
            return "", "", err

        # 支援 analyzeResult / analyze_result
        analyze_result = (
            ocr_result.get("analyzeResult")
            or ocr_result.get("analyze_result")
            or {}
        )

        print(f"[DEBUG] Has 'analyzeResult': {bool(ocr_result.get('analyzeResult'))}")
        print(f"[DEBUG] Has 'analyze_result': {bool(ocr_result.get('analyze_result'))}")

        # Debug 顯示 analyze_result 可用鍵名
        analyze_keys = list(analyze_result.keys()) if isinstance(analyze_result, dict) else []
        print(f"[DEBUG] analyze_result keys: {analyze_keys}")

        # 1) 嘗試 Read 3.2+：pages 結構
        pages = analyze_result.get("pages")
        if isinstance(pages, list) and pages:
            print("[DEBUG] Detected Read 3.2+ 'pages' structure.")
            lines_text: List[str] = []
            for p_idx, page in enumerate(pages):
                page_lines = page.get("lines") or []
                print(f"[DEBUG] Page {p_idx} lines count: {len(page_lines)}")
                for l_idx, line in enumerate(page_lines):
                    # 支援 line 的 text 欄位
                    line_text = line.get("text")
                    if line_text:
                        lines_text.append(line_text)
                    else:
                        # 若沒有 line.text，嘗試從 words 拼接
                        words = line.get("words") or []
                        if words:
                            joined = " ".join(
                                [w.get("text", "") for w in words if isinstance(w, dict)]
                            ).strip()
                            if joined:
                                lines_text.append(joined)
                        # 若依舊沒有，忽略此行
                    if l_idx % 50 == 0 and l_idx > 0:
                        print(f"[DEBUG] Processed {l_idx} lines on page {p_idx}...")
            text = "\n".join(lines_text).strip()
            print(f"[DEBUG] Extracted text length (pages): {len(text)}")
            return text, "read_3_2_pages", None

        print("[DEBUG] Read 3.2+ 'pages' not found or empty. Will try 3.0/3.1 structure.")

        # 2) 回退至 Read 3.0/3.1：readResults / read_results
        read_results = (
            analyze_result.get("readResults")
            or analyze_result.get("read_results")
            or []
        )

        if isinstance(read_results, list) and read_results:
            print("[DEBUG] Detected Read 3.0/3.1 'readResults' structure.")
            lines_text: List[str] = []
            for r_idx, read in enumerate(read_results):
                # 3.0/3.1 結構通常在 readResults[n].lines
                read_lines = read.get("lines") or []
                print(f"[DEBUG] ReadResult {r_idx} lines count: {len(read_lines)}")
                for l_idx, line in enumerate(read_lines):
                    # 優先 line.text
                    line_text = line.get("text")
                    if line_text:
                        lines_text.append(line_text)
                    else:
                        # 回退：words
                        words = line.get("words") or []
                        if words:
                            joined = " ".join(
                                [w.get("text", "") for w in words if isinstance(w, dict)]
                            ).strip()
                            if joined:
                                lines_text.append(joined)
                    if l_idx % 50 == 0 and l_idx > 0:
                        print(f"[DEBUG] Processed {l_idx} lines in readResult {r_idx}...")
            text = "\n".join(lines_text).strip()
            print(f"[DEBUG] Extracted text length (readResults): {len(text)}")
            return text, "read_3_0_results", None

        # 3) 若兩種結構都沒找到，結構化錯誤
        err = {
            "code": "StructureNotSupported",
            "message": "未找到 pages 或 readResults 結構，無法提取文字",
            "available_keys": analyze_keys,
        }
        print(f"[ERROR] {err}")
        return "", "", err

    def _infer_job_title(self, text: str) -> str:
        """
        職稱推論：
        - 優先檢查前 5 行是否包含明確職稱語句
        - 擴大中英文關鍵字集合（設計/行銷/PM/工程/資料等）
        - 若無法推論則回傳「未指定職位」
        """
        if not text or not text.strip():
            return "未指定職位"

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        top_lines = lines[:5]

        # 明確標籤提示
        explicit_markers = [
            "職稱", "Title", "Job Title", "Position", "Role", "Title:",
            "職位", "任職", "目前職稱", "求職目標", "目標職位"
        ]

        # 常見職稱關鍵字（中英混合）
        keywords_map = {
            "設計": ["設計師", "UI", "UX", "產品設計", "介面設計", "視覺設計", "industrial design", "designer", "design"],
            "行銷": ["行銷", "市場", "marketing", "growth", "digital marketing", "content marketing", "brand"],
            "產品經理": ["產品經理", "產品管理", "product manager", "PM", "product owner"],
            "工程": ["工程師", "developer", "software engineer", "frontend", "backend", "fullstack", "mobile", "android", "ios"],
            "資料": ["資料科學", "data scientist", "data engineer", "ml engineer", "machine learning", "ai", "人工智慧"],
            "營運": ["operations", "ops", "營運", "business operations"],
            "業務": ["sales", "account manager", "業務", "商務", "bd", "business development"],
            "人資": ["hr", "human resources", "人才招募", "recruiter", "人資"],
            "財務": ["finance", "financial analyst", "會計", "稅務", "審計"],
            "客服": ["customer service", "support", "客服", "cs"],
            "專案": ["project manager", "專案經理", "專案管理", "pmo"],
            "資料分析": ["data analyst", "商業分析", "bi analyst", "分析師"],
        }

        # 優先從前幾行尋找顯式表述
        for line in top_lines:
            lower = line.lower()
            for marker in explicit_markers:
                if marker.lower().rstrip(":") in lower:
                    # 嘗試提取冒號後內容
                    if ":" in line:
                        after = line.split(":", 1)[1].strip()
                        if after:
                            inferred = self._normalize_title(after)
                            print(f"[DEBUG] Explicit title inferred: {inferred}")
                            return inferred
                    # 若無冒號，整行嘗試當職稱
                    inferred = self._normalize_title(line)
                    print(f"[DEBUG] Explicit marker matched, using line as title: {inferred}")
                    return inferred

        # 關鍵字匹配（先看前 5 行，再全局）
        def match_keywords(search_lines: List[str]) -> str:
            joined = "\n".join(search_lines).lower()
            for group, kws in keywords_map.items():
                for kw in kws:
                    if kw.lower() in joined:
                        # 回傳群組名或關鍵字更自然的標籤
                        title = self._group_to_title(group)
                        print(f"[DEBUG] Keyword matched '{kw}' -> {title}")
                        return title
            return ""

        title = match_keywords(top_lines)
        if title:
            return title

        title = match_keywords(lines)
        if title:
            return title

        # 兜底：尋找常見職稱模式（例如以「工程師」「設計師」結尾）
        tail_titles = ["工程師", "設計師", "經理", "分析師", "專員", "顧問"]
        for line in top_lines:
            for t in tail_titles:
                if t in line:
                    inferred = self._normalize_title(line)
                    print(f"[DEBUG] Tail title matched: {inferred}")
                    return inferred

        return "未指定職位"

    # -------------- helpers ----------------

    def _normalize_title(self, title: str) -> str:
        """
        簡單清洗職稱字串：去除多餘空白與冗餘標記。
        """
        cleaned = title.strip()
        # 移除可能的前綴標籤
        prefixes = ["Title", "Job Title", "Position", "Role", "職稱", "職位", "任職", "目前職稱", "求職目標", "目標職位"]
        for p in prefixes:
            p_lower = p.lower()
            if cleaned.lower().startswith(p_lower):
                cleaned = cleaned[len(p):].strip().lstrip(":").strip()
        return cleaned if cleaned else "未指定職位"

    def _group_to_title(self, group: str) -> str:
        """
        將關鍵字群組映射到更自然的職稱展示。
        """
        mapping = {
            "設計": "UI/UX 設計師",
            "行銷": "行銷/Marketing",
            "產品經理": "產品經理 (PM)",
            "工程": "軟體工程師",
            "資料": "AI/ML/資料工程",
            "營運": "營運管理",
            "業務": "商務開發/業務",
            "人資": "人力資源 HR",
            "財務": "財務/會計",
            "客服": "客服/Technical Support",
            "專案": "專案經理",
            "資料分析": "資料分析師",
        }
        return mapping.get(group, group)


# 提供全域實例，便於現有代碼直接導入使用
resume_service = ResumeService()