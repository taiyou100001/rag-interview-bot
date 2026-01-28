# backend/api/resume_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.ocr_service import ocr_service
from backend.services.resume_service import resume_service
from backend.database import save_resume
import uuid
import os

router = APIRouter()

@router.post("/upload_resume", summary="上傳履歷並進行 OCR 辨識")
async def upload_resume(
    file: UploadFile = File(..., description="上傳的履歷檔案 (PDF/圖片)"),
    user_id: str = Form(..., description="使用者 ID (字串格式)")
):
    """
    上傳履歷並進行 OCR 辨識
    
    處理流程：
    1. 接收並儲存上傳的履歷檔案
    2. 使用 Azure OCR 進行文字辨識
    3. 透過 LLM 結構化履歷內容
    4. 推斷應徵職位
    5. 儲存至資料庫
    
    回傳資料：
    - **resume_id**: 履歷的唯一識別碼
    - **job_title**: 系統推斷的應徵職位
    - **raw_text**: 履歷原始文字（前 200 字預覽）
    - **message**: 處理狀態訊息
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