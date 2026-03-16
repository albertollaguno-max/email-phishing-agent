from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text, Enum
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
import enum
import os
from dotenv import load_dotenv

load_dotenv()

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "secret")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "email_phishing_agent")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class SenderType(str, enum.Enum):
    DOMAIN = "domain"
    EMAIL = "email"

class AllowedSender(Base):
    __tablename__ = "allowed_senders"

    id = Column(Integer, primary_key=True, index=True)
    type = Column(Enum(SenderType), nullable=False)
    value = Column(String(255), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True)
    description = Column(String(512), nullable=True)

class EmailAnalysisLog(Base):
    __tablename__ = "email_analysis_logs"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(512), unique=True, index=True, nullable=False)
    from_address = Column(String(255), nullable=True)
    forwarded_by = Column(String(255), nullable=False, index=True)
    subject = Column(String(512), nullable=True)
    date_received = Column(DateTime, default=datetime.utcnow)

    is_fraudulent = Column(Boolean, nullable=True)
    ai_explanation = Column(Text, nullable=True)
    ai_provider_used = Column(String(50), nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)

    # Email body storage for review and debugging
    body_text = Column(Text, nullable=True)  # Plain text version of the email body
    body_html = Column(Text, nullable=True)  # HTML version of the email body

    response_sent_at = Column(DateTime, nullable=True)

    # Human feedback for few-shot learning
    # 'correct' = AI was right | 'incorrect' = AI was wrong (false positive/negative)
    user_feedback = Column(String(20), nullable=True)  # 'correct' | 'incorrect'
    user_notes = Column(Text, nullable=True)  # Optional comment from user

class SystemLog(Base):
    __tablename__ = "system_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    level = Column(String(50), nullable=False) # INFO, ERROR, WARNING
    message = Column(Text, nullable=False)

def init_db():
    Base.metadata.create_all(bind=engine)
