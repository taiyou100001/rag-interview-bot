# backend/api/resume_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.ocr_service import ocr_service
from backend.services.resume_service import resume_service
from backend.database import save_resume
import uuid
import os
import shutil
import time
from pdf2image import convert_from_path
from PIL import Image

def generate_pdf_preview(pdf_path: str, output_folder: str) -> list: # 🌟 改回傳 list
    current_file_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
    poppler_bin = os.path.join(project_root, "bin", "poppler", "Library", "bin")
    
    preview_dir = os.path.join(output_folder, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    
    base_name = os.path.basename(pdf_path)
    file_id = os.path.splitext(base_name)[0]
    ext = os.path.splitext(pdf_path)[1].lower()
    
    urls = [] # 🌟 準備存放多張圖的網址
    try:
        if ext == '.pdf':
            # 🌟 關鍵：將 last_page 改為 2
            pages = convert_from_path(
                pdf_path, 
                first_page=1, 
                last_page=2, 
                poppler_path=poppler_bin
            )
            for i, page in enumerate(pages):
                p_filename = f"prev_{file_id}_{i+1}.jpg"
                p_path = os.path.join(preview_dir, p_filename)
                page.save(p_path, 'JPEG')
                urls.append(f"/static/resumes/previews/{p_filename}")
        else:
            # 圖片維持單張處理
            p_filename = f"prev_{file_id}.jpg"
            p_path = os.path.join(preview_dir, p_filename)
            with Image.open(pdf_path) as img:
                img.convert('RGB').save(p_path, 'JPEG')
            urls.append(f"/static/resumes/previews/{p_filename}")
                
        return urls # 🌟 回傳清單
    except Exception as e:
        print(f"預覽圖生成失敗: {e}")
        return []

router = APIRouter()

# 註：雖然您提到拍照功能已拔掉，但保留此 Endpoint 可相容未來擴充
@router.post("/upload", summary="上傳履歷並進行 OCR 辨識")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Form(...)
):
    SAVE_DIR = "static/resumes"
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(SAVE_DIR, unique_filename)

    # 先存檔
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    # 產預覽圖
    preview_urls = generate_pdf_preview(file_path, SAVE_DIR)

    # 執行 OCR
    success, result = ocr_service.process_file(file_path)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))

    structured = resume_service.structure_resume(result)
    
    resume = save_resume(
        user_id=user_id,
        filename=file.filename,
        file_path=file_path,
        ocr_json=result,
        structured_data=structured
    )
    
    gemini_data = result.get("resume_score", {}).get("gemini_score", {})
    score = gemini_data.get("score", 0)
    reason = "".join(gemini_data.get("reason", [])) if isinstance(gemini_data.get("reason"), list) else gemini_data.get("reason", "無評語")

    return {
        "resume_id": str(resume.id),
        "job_title": structured.get("job_title", "未知職位"),
        "raw_text": structured.get("raw_text", "")[:200],
        "file_urls": preview_urls if preview_urls else f"/static/resumes/{unique_filename}",
        "message": "履歷上傳成功",
        "resume_score": score,
        "resume_reason": reason
    }

@router.post("/upload_local", summary="從伺服器本地資料夾讀取履歷 (Unity 從電腦讀取用)")
async def upload_local_resume(user_id: str = Form(...)):
    """
    讀取伺服器 manual_resume 資料夾內最新的檔案，並產出 Unity 可讀取的預覽圖
    """
    local_dir = "manual_resume"
    os.makedirs(local_dir, exist_ok=True)
    
    # 1. 取得最新檔案
    files = [f for f in os.listdir(local_dir) if os.path.isfile(os.path.join(local_dir, f))]
    if not files:
        raise HTTPException(status_code=404, detail="manual_resume 資料夾內沒有檔案！")
    
    files.sort(key=lambda x: os.path.getmtime(os.path.join(local_dir, x)), reverse=True)
    target_filename = files[0]
    file_path = os.path.join(local_dir, target_filename)
    
    print(f"✅ 正在處理最新本地履歷: {target_filename}")

    # 🌟 重點：生成預覽圖並取得 URL，解決 404 問題
    # 這會將圖片放置於 static 目錄，避開 manual_resume 無法被網頁存取的限制
    preview_urls = generate_pdf_preview(file_path, "static/resumes")

    # 2. 執行 OCR + LLM 評分
    total_start = time.time()
    success, result = ocr_service.process_file(file_path)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))

    # 3. 結構化文字與職位推斷
    structured = resume_service.structure_resume(result)
    
    # 4. 儲存資料庫
    try:
        resume = save_resume(
            user_id=user_id,
            filename=target_filename,
            file_path=file_path,
            ocr_json=result,
            structured_data=structured
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫儲存失敗: {str(e)}")
    
    # 5. 解析 Gemini 分數與評語
    gemini_data = result.get("resume_score", {}).get("gemini_score", {})
    score = gemini_data.get("score", 0)
    raw_reason = gemini_data.get("reason", "無評語")
    reason = "".join(raw_reason) if isinstance(raw_reason, list) else raw_reason

    # 在後端終端機顯示進度
    print(f"🚀 履歷處理總耗時: {time.time() - total_start:.2f} 秒")
    print(f"🎯 推斷職位: {structured.get('job_title', '未知職位')}")
    print("\n" + "="*50)
    print(f"📄 【本地履歷解析完成】")
    print(f"🎯 推斷職位: {structured.get('job_title', '未知職位')}")
    print(f"⭐ AI 評分: {score} / 100")
    print(f"💡 AI 評語: {reason}")
    print("="*50 + "\n")

    # 6. 回傳資料給 Unity (file_urls 指向剛剛產生的預覽圖)
    return {
        "resume_id": str(resume.id),
        "job_title": structured.get("job_title", "未知職位"),
        "raw_text": structured.get("raw_text", "")[:200],
        "file_urls": preview_urls if preview_urls else f"/static/resumes/{target_filename}", 
        "message": "本地履歷讀取成功",
        "resume_score": score,
        "resume_reason": reason
    }