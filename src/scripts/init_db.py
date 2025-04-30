import sys
import os
from pathlib import Path

# Add the src directory to the Python path
src_dir = Path(__file__).parent.parent
sys.path.append(str(src_dir.parent))

from src.database import Base
from src.config.database import engine

def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)

if __name__ == '__main__':
    init_db()
    print("Database tables created successfully")