# backend/database.py
import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, JSON, Integer, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from werkzeug.security import generate_password_hash, check_password_hash

# 資料庫配置
DB_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')
engine = create_engine(DB_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    """使用者資料表"""
    __tablename__ = 'users'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    resumes = relationship('Resume', back_populates='user', lazy='dynamic')
    sessions = relationship('InterviewSession', back_populates='user', lazy='dynamic')

class Resume(Base):
    """履歷資料表"""
    __tablename__ = 'resumes'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    
    filename = Column(String(255), nullable=False)
    # 新增：儲存檔案的實體路徑 (設定長度 512 以防路徑過長)
    file_path = Column(String(512), nullable=True)

    ocr_json = Column(JSON, nullable=True)
    structured_data = Column(JSON, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship('User', back_populates='resumes')

class InterviewSession(Base):
    """面試會話資料表"""
    __tablename__ = 'interview_sessions'
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey('users.id'), nullable=False)
    job_title = Column(String(100), nullable=False)
    resume_id = Column(String(36), ForeignKey('resumes.id'), nullable=True)
    
    # Phase 1 欄位
    resume_text = Column(Text, nullable=True)  # 改用 Text 避免長度限制
    current_question = Column(Text, nullable=True)
    question_count = Column(Integer, default=0)
    
    history = Column(JSON, nullable=False, default=list)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    feedback = Column(JSON, nullable=True)
    
    user = relationship('User', back_populates='sessions')

def init_db():
    """初始化資料庫 (建立所有表格)"""
    Base.metadata.create_all(bind=engine)
    print("[Database] 資料表建立完成")

# ========== CRUD 操作函數 ==========

def create_user(username: str, email: str, password: str):
    """註冊使用者"""
    hashed = generate_password_hash(password)
    user = User(username=username, email=email, password_hash=hashed)
    
    with SessionLocal() as db:
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

def authenticate_user(email: str, password: str):
    """登入驗證"""
    with SessionLocal() as db:
        user = db.query(User).filter(User.email == email).first()
        
        if user and check_password_hash(user.password_hash, password):
            user.last_login = datetime.utcnow()
            db.commit()
            return user
    
    return None

def save_resume(user_id, filename: str, ocr_json: dict, structured_data: dict):
    """
    儲存履歷
    
    Args:
        user_id: 可以是 str 或 uuid.UUID
    """
    # 統一轉為字串
    if isinstance(user_id, uuid.UUID):
        user_id = str(user_id)
    
    resume = Resume(
        user_id=user_id,
        filename=filename,
        file_path=file_path,  # 這裡將路徑存入資料庫
        ocr_json=ocr_json,
        structured_data=structured_data
    )
    
    with SessionLocal() as db:
        db.add(resume)
        db.commit()
        db.refresh(resume)
    
    return resume

def get_user_sessions(user_id):
    """
    查詢使用者面試歷史
    
    Args:
        user_id: 可以是 str 或 uuid.UUID
    """
    # 統一轉為字串
    if isinstance(user_id, uuid.UUID):
        user_id = str(user_id)
    
    with SessionLocal() as db:
        sessions = db.query(InterviewSession).filter(
            InterviewSession.user_id == user_id
        ).all()
        return sessions