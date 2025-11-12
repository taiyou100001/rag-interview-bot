# database.py
import os
import uuid
from datetime import datetime
from sqlalchemy import create_engine, Column, String, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID  # 支援PostgreSQL的UUID
from werkzeug.security import generate_password_hash, check_password_hash

# 資料庫配置（環境變數切換）
DB_URL = os.getenv('DATABASE_URL', 'sqlite:///app.db')  # 預設SQLite
engine = create_engine(DB_URL, echo=False)  # echo=True for debug
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    password_hash = Column(String(128), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime)
    
    resumes = relationship('Resume', backref='user', lazy=True)
    sessions = relationship('InterviewSession', backref='user', lazy=True)

class Resume(Base):
    __tablename__ = 'resumes'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    filename = Column(String(255), nullable=False)
    ocr_json = Column(JSON, nullable=True)  # 儲存OCR結果
    structured_data = Column(JSON, nullable=True)  # 儲存結構化結果
    uploaded_at = Column(DateTime, default=datetime.utcnow)

class InterviewSession(Base):
    __tablename__ = 'interview_sessions'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    job_title = Column(String(100), nullable=False)
    resume_id = Column(UUID(as_uuid=True), ForeignKey('resumes.id'), nullable=True)
    history = Column(JSON, nullable=False)  # [{'question': '...', 'answer': '...'}]
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    feedback = Column(String(500), nullable=True)

def init_db():
    """初始化資料庫（建立表格）"""
    Base.metadata.create_all(bind=engine)

# CRUD 操作範例
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

def save_resume(user_id: uuid.UUID, filename: str, ocr_json: dict, structured_data: dict):
    """儲存履歷"""
    resume = Resume(user_id=user_id, filename=filename, ocr_json=ocr_json, structured_data=structured_data)
    with SessionLocal() as db:
        db.add(resume)
        db.commit()
        db.refresh(resume)
    return resume

def save_interview_session(user_id: uuid.UUID, job_title: str, resume_id: uuid.UUID, history: list):
    """儲存面試會話"""
    session = InterviewSession(user_id=user_id, job_title=job_title, resume_id=resume_id, history=history, ended_at=datetime.utcnow())
    with SessionLocal() as db:
        db.add(session)
        db.commit()
        db.refresh(session)
    return session

def get_user_sessions(user_id: uuid.UUID):
    """查詢使用者面試歷史"""
    with SessionLocal() as db:
        return db.query(InterviewSession).filter(InterviewSession.user_id == user_id).all()