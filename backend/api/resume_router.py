# backend/api/resume_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.ocr_service import ocr_service
from backend.services.resume_service import resume_service
from backend.database import save_resume
import uuid
import os
import shutil  # Imported for efficient file saving

router = APIRouter()

@router.post("/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Form(...)
):
    """
    上傳履歷並進行 OCR 辨識
    
    Args:
        file: 上傳的履歷檔案 (PDF/圖片)
        user_id: 使用者 ID (字串格式)
        
    Returns:
        {
            "resume_id": str,
            "job_title": str,
            "raw_text": str,
            "message": str
        }
    """
    # 驗證 user_id 格式
    try:
        # 如果是 UUID 格式，轉為字串
        if len(user_id) == 36 and '-' in user_id:
            uuid.UUID(user_id)  # 驗證格式
    except ValueError:
        # 不是標準 UUID，但接受任意字串作為 user_id
        pass
    
    # 2. 建立永久儲存資料夾 (建議放在 static 下，方便前端存取)
    SAVE_DIR = "static/resumes"
    os.makedirs(SAVE_DIR, exist_ok=True)
    
    # 3. 產生唯一檔名並定義完整路徑
    # 保留原始副檔名 (例如 .jpg, .png, .pdf)
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(SAVE_DIR, unique_filename)
    
    # 4. 儲存檔案 (使用 shutil，效率較高)
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    # 5. OCR 辨識
    success, result = ocr_service.process_file(file_path)
    if not success:
        # 如果辨識失敗，視情況決定是否要刪除檔案，這裡先保留
        raise HTTPException(status_code=400, detail=result.get("error"))

    # 6. 結構化履歷
    structured = resume_service.structure_resume(result)
    
    # 7. 儲存到資料庫
    try:
        resume = save_resume(
            user_id=user_id,
            filename=file.filename,
            file_path=file_path,  # ✅ 重點：將儲存的路徑傳入資料庫
            ocr_json=result,
            structured_data=structured
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"資料庫儲存失敗: {str(e)}")

    return {
        "resume_id": str(resume.id),
        "job_title": structured.get("job_title", "未知職位"),
        "raw_text": structured.get("raw_text", "")[:200],
        "file_url": f"/static/resumes/{unique_filename}", # ✅ 回傳網址給前端
        "message": "履歷上傳成功"
    }
