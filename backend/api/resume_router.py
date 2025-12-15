# backend/api/resume_router.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Form
from backend.services.ocr_service import ocr_service
from backend.services.resume_service import resume_service
from backend.database import SessionLocal, Resume, save_resume
import uuid
import os

router = APIRouter()

@router.post("/upload_resume")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: str = Form(...)
):
    os.makedirs("uploads", exist_ok=True)
    file_path = f"uploads/{uuid.uuid4()}_{file.filename}"
    
    with open(file_path, "wb") as f:
        content = await file.read()
        f.write(content)

    success, result = ocr_service.process_file(file_path)
    if not success:
        raise HTTPException(status_code=400, detail=result.get("error"))

    structured = resume_service.structure_resume(result)
    
    resume = save_resume(
        user_id=uuid.UUID(user_id),
        filename=file.filename,
        ocr_json=result,
        structured_data=structured
    )

    return {
        "resume_id": str(resume.id),
        "job_title": structured.get("job_title", "未知職位"),
        "message": "履歷上傳成功"
    }