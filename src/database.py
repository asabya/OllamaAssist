from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import os


Base = declarative_base()

# Get database URL from environment variable or use default
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/ollamaassist')

# Create engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    poolclass=QueuePool,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@contextmanager
def get_db() -> Session:
    """Get database session with context management"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class Conversation(Base):
    """SQLAlchemy model for conversations"""
    __tablename__ = 'conversations'
    
    id = Column(String, primary_key=True)
    current_user = Column(String, nullable=True)
    conversation_metadata = Column(JSON, default={})
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship to messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base):
    """SQLAlchemy model for messages"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String, ForeignKey('conversations.id'), nullable=False)
    type = Column(String, nullable=False)  # HumanMessage, AIMessage, SystemMessage
    content = Column(Text, nullable=False)
    additional_kwargs = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationship to conversation
    conversation = relationship("Conversation", back_populates="messages") 