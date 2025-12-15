# backend/services/resume_service.py
def structure_resume(ocr_result: dict) -> dict:
    text_lines = []
    for page in ocr_result.get("analyzeResult", {}).get("readResults", []):
        for line in page.get("lines", []):
            line_text = " ".join([word["text"] for word in line.get("words", [])])
            text_lines.append(line_text)
    
    full_text = "\n".join(text_lines)
    
    # 這裡你可以之後接 LLM 做更精準的結構化
    return {
        "raw_text": full_text,
        "job_title": "軟體工程師",  # 可改成自動推論
        "name": "未知",
        "email": "unknown@email.com",
        "years_of_experience": 0
    }

# 讓 import 更方便
resume_service = type("ResumeService", (), {"structure_resume": structure_resume})()