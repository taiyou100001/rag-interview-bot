# backend/api/resume_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.ocr_service import ocr_service
from backend.services.resume_service import resume_service
from backend.database import save_resume
import uuid
import os

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
    
    # 建立上傳資料夾
    os.makedirs("uploads", exist_ok=True)
    
    # 儲存檔案
    file_path = f"uploads/{uuid.uuid4()}_{file.filename}"
    
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"檔案儲存失敗: {str(e)}")

    # OCR 辨識
    success, result = ocr_service.process_file(file_path)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))

    # 結構化履歷
    structured = resume_service.structure_resume(result)
    
    # 儲存到資料庫 (user_id 直接用字串)
    try:
        resume = save_resume(
            user_id=user_id,  # 直接傳字串
            filename=file.filename,
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
        "raw_text": structured.get("raw_text", "")[:200],  # 回傳前200字
        "message": "履歷上傳成功"
    }