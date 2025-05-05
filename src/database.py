from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Index, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, relationship
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
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    conversation_id = Column(String(255), unique=True, nullable=False)
    user_id = Column(String(255), nullable=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relationship with messages
    messages = relationship("Message", back_populates="conversation")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_conversation_id', conversation_id),
        Index('idx_user_id', user_id),
        Index('idx_updated_at', updated_at.desc()),
        Index('idx_user_updated', user_id, updated_at.desc()),
    )
    
    @classmethod
    def get_or_create(cls, db: Session, conversation_id: str, title: Optional[str] = None, user_id: Optional[str] = None) -> 'Conversation':
        """Get existing conversation or create new one"""
        conversation = db.query(cls).filter(cls.conversation_id == conversation_id).first()
        if not conversation:
            conversation = cls(conversation_id=conversation_id, title=title, user_id=user_id)
            db.add(conversation)
            db.commit()
        return conversation

    @classmethod
    def update_conversation(cls, db: Session, conversation_id: str, **kwargs) -> 'Conversation':
        """Update conversation attributes"""
        conversation = db.query(cls).filter(cls.conversation_id == conversation_id).first()
        if conversation:
            for key, value in kwargs.items():
                if hasattr(conversation, key):
                    setattr(conversation, key, value)
            db.commit()
        return conversation

class Message(Base):
    """SQLAlchemy model for messages with integrated metadata"""
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True, nullable=True)  # For storing external message IDs
    conversation_id = Column(String(255), ForeignKey('conversations.conversation_id'), nullable=False)
    type = Column(String(50), nullable=False)  # HumanMessage, AIMessage, SystemMessage
    content = Column(Text, nullable=False)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    cache_read = Column(Integer, nullable=True)
    cache_creation = Column(Integer, nullable=True)
    tool_calls = Column(JSON, default=[])
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationship with conversation
    conversation = relationship("Conversation", back_populates="messages")
    
    # Indexes for efficient querying
    __table_args__ = (
        Index('idx_conversation_message', conversation_id, message_id),
        Index('idx_message_id', message_id),
    )

    @classmethod
    def upsert_message(cls, db: Session, message_data: Dict[str, Any]) -> 'Message':
        """Upsert a message - update if message_id exists, otherwise insert new"""
        # Ensure conversation exists
        conversation_id = message_data.get('conversation_id')
        if conversation_id:
            Conversation.get_or_create(db, conversation_id)
            
        existing_message = None
        if message_data.get('message_id'):
            existing_message = db.query(cls).filter(cls.message_id == message_data['message_id']).first()
        
        if existing_message:
            for key, value in message_data.items():
                setattr(existing_message, key, value)
            message = existing_message
        else:
            message = cls(**message_data)
            db.add(message)
        
        db.commit()
        return message 