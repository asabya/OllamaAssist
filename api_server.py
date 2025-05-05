import traceback
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import os
from datetime import datetime
import json
import re
import uuid

from langchain_anthropic import ChatAnthropic
from langchain.agents import AgentExecutor
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory
from langchain.prompts import MessagesPlaceholder, ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from langchain.agents.agent import AgentOutputParser
from langchain_core.agents import AgentAction, AgentFinish
from langchain.schema import SystemMessage

from cli_chat import setup_agent
from src.database import Base, engine
from src.prompts.system_prompt import SystemPrompt
from src.llm_factory import LLMFactory
from src.memory_manager import MemoryManager

# Configure logging
log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, f"api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for database initialization"""
    try:
        Base.metadata.create_all(bind=engine)
        logging.info("Database tables dropped and recreated successfully")
        yield
    except Exception as e:
        logging.error(f"Failed to initialize database: {str(e)}\n{traceback.format_exc()}")
        raise
    finally:
        # Cleanup (if needed) when the app shuts down
        pass

app = FastAPI(
    title="Chat API",
    description="API for chat interactions with Claude and tools using LangChain",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    input: str
    conversation_id: Optional[str] = None
    user_id: Optional[str] = None
    title: Optional[str] = None

class ChatResponse(BaseModel):
    output: str
    conversation_id: str
    
# Store conversation agents in memory
# In production, you'd want to use a proper database
conversation_agents: Dict[str, tuple[AgentExecutor, Any]] = {}

# Configuration
CONTEXT_WINDOW_SIZE = 10  # Number of messages to keep in context

memory_manager = MemoryManager()

@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "Chat API",
        "version": "1.0.0",
        "description": "API for chat interactions with Claude and tools using LangChain"
    }

@app.get("/tools")
async def list_tools():
    """List available tools and their descriptions"""
    tool_info = []
    
    for tool in tools:
        schema = tool.args_schema.schema() if tool.args_schema else {}
        tool_info.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": schema
        })
    
    return {"tools": tool_info}

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that processes messages using LangChain agent
    
    Request body:
    - input: User's message
    - conversation_id: Optional ID to continue a conversation
    - user_id: Optional user identifier
    - title: Optional conversation title
    
    Returns:
    - output: Assistant's response
    - conversation_id: ID for the conversation
    """
    try:
        # Get or create conversation agent
        conversation_id = request.conversation_id or str(uuid.uuid4())
        
        # Create new agent executor if it doesn't exist
        if not conversation_id in conversation_agents:
            agent_executor, client = await setup_agent(memory_manager, conversation_id, context_window=CONTEXT_WINDOW_SIZE)
            conversation_agents[conversation_id] = (agent_executor, client)
        else:
            agent_executor, client = conversation_agents[conversation_id]
        
        # Add user message to memory
        await memory_manager.add_user_message(
            conversation_id=conversation_id,
            content=request.input,
            user_id=request.user_id,
            title=request.title
        )
        print("Processing message...")
        
        response = await agent_executor.ainvoke(
            {"input": request.input}
        )
        
        # Add AI response to memory with metadata
        await memory_manager.add_ai_message(
            conversation_id=conversation_id,
            content=response["output"].rstrip() if isinstance(response["output"], str) else str(response["output"]).rstrip(),
            title=request.title
        )
        
        return ChatResponse(
            output=response["output"],
            conversation_id=conversation_id
        )
        
    except Exception as e:
        logging.error(f"Error in chat endpoint: {str(e)}", exc_info=True)
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 