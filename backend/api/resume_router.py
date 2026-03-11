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

def generate_pdf_preview(pdf_path: str, output_folder: str) -> list:
    """
    將 PDF 前三頁或圖片轉為 JPG 預覽圖，並回傳前端可存取的網址清單
    """
    current_file_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
    poppler_bin = os.path.join(project_root, "bin", "poppler-25.12.0", "Library", "bin")

    print(f"🔍 [DEBUG] 正在尋找 Poppler 路徑: {poppler_bin}")
    if not os.path.exists(poppler_bin):
        print(f"⚠️ [警告] 找不到 Poppler 資料夾，PDF 預覽可能會失敗！")
    
    preview_dir = os.path.join(output_folder, "previews")
    os.makedirs(preview_dir, exist_ok=True)
    
    base_name = os.path.basename(pdf_path)
    file_id = os.path.splitext(base_name)[0]
    ext = os.path.splitext(pdf_path)[1].lower()
    
    urls = []
    try:
        if ext == '.pdf':
            # 🌟 支援最多 3 頁預覽
            pages = convert_from_path(
                pdf_path, 
                first_page=1, 
                last_page=3, 
                poppler_path=poppler_bin
            )
            for i, page in enumerate(pages):
                p_filename = f"prev_{file_id}_{i+1}.jpg"
                p_path = os.path.join(preview_dir, p_filename)
                page.save(p_path, 'JPEG')
                urls.append(f"/static/resumes/previews/{p_filename}")
        elif ext in ['.jpg', '.jpeg', '.png', '.bmp']:
            p_filename = f"prev_{file_id}.jpg"
            p_path = os.path.join(preview_dir, p_filename)
            with Image.open(pdf_path) as img:
                img.convert('RGB').save(p_path, 'JPEG')
            urls.append(f"/static/resumes/previews/{p_filename}")
                
        return urls
    except Exception as e:
        print(f"❌ 預覽圖生成失敗: {e}")
        return []

router = APIRouter()

@router.post("/upload", summary="上傳履歷並進行 OCR 辨識")
async def upload_resume(file: UploadFile = File(...), user_id: str = Form(...)):
    SAVE_DIR = "static/resumes"
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(SAVE_DIR, unique_filename)

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    preview_urls = generate_pdf_preview(file_path, SAVE_DIR)

    success, result = ocr_service.process_file(file_path)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))

    structured = resume_service.structure_resume(result)
    resume = save_resume(user_id=user_id, filename=file.filename, file_path=file_path, ocr_json=result, structured_data=structured)
    
    gemini_data = result.get("resume_score", {}).get("gemini_score", {})
    score = gemini_data.get("score", 0)
    reason = "".join(gemini_data.get("reason", [])) if isinstance(gemini_data.get("reason"), list) else gemini_data.get("reason", "無評語")

    return {
        "resume_id": str(resume.id),
        "job_title": structured.get("job_title", "未知職位"),
        "raw_text": structured.get("raw_text", "")[:200],
        "file_urls": preview_urls, # 🌟 統一回傳陣列
        "message": "履歷上傳成功",
        "resume_score": score,
        "resume_reason": reason
    }

@router.post("/upload_local", summary="從伺服器本地資料夾讀取履歷")
async def upload_local_resume(user_id: str = Form(...)):
    local_dir = "manual_resume"
    os.makedirs(local_dir, exist_ok=True)
    
    # 🌟 修正 1：過濾檔案，只讀取支援的格式，避免 Azure 報 400 錯誤
    supported_exts = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    files = [f for f in os.listdir(local_dir) 
             if os.path.isfile(os.path.join(local_dir, f)) and os.path.splitext(f)[1].lower() in supported_exts]
    
    if not files:
        raise HTTPException(status_code=404, detail="資料夾內無有效履歷檔案！")
    
    files.sort(key=lambda x: os.path.getmtime(os.path.join(local_dir, x)), reverse=True)
    target_filename = files[0]
    file_path = os.path.join(local_dir, target_filename)
    
    # 🌟 修正 2：優先產預覽圖到 static 資料夾，解決 404 問題
    preview_urls = generate_pdf_preview(file_path, "static/resumes")

    total_start = time.time()

    t0 = time.time()
    success, result = ocr_service.process_file(file_path)
    t1 = time.time()
    print(f"⏱️ [計時] 1. Azure OCR + Gemini 評分耗時: {t1 - t0:.2f} 秒")

    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    structured = resume_service.structure_resume(result)
    t2 = time.time()
    print(f"⏱️ [計時] 2. 結構化與 Ollama 猜職位耗時: {t2 - t1:.2f} 秒")
    
    try:
        resume = save_resume(user_id=user_id, filename=target_filename, file_path=file_path, ocr_json=result, structured_data=structured)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"資料庫儲存失敗: {str(e)}")
    
    t3 = time.time()
    print(f"⏱️ [計時] 3. 資料庫儲存耗時: {t3 - t2:.2f} 秒")
    print(f"🚀 [計時總結] 履歷處理總耗時: {t3 - total_start:.2f} 秒")
    
    gemini_data = result.get("resume_score", {}).get("gemini_score", {})
    score = gemini_data.get("score", 0)
    reason = "".join(gemini_data.get("reason", [])) if isinstance(gemini_data.get("reason"), list) else gemini_data.get("reason", "無評語")

    print("\n" + "="*50 + f"\n📄 【本地履歷解析完成】\n🎯 推斷職位: {structured.get('job_title', '未知職位')}\n⭐ AI 評分: {score} / 100\n💡 AI 評語: {reason}\n" + "="*50 + "\n")

    return {
        "resume_id": str(resume.id),
        "job_title": structured.get("job_title", "未知職位"),
        "raw_text": structured.get("raw_text", "")[:200],
        "file_urls": preview_urls if preview_urls else [], # 🌟 確保一定是陣列
        "message": "本地履歷讀取成功",
        "resume_score": score,
        "resume_reason": reason
    }
