from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from pydantic import BaseModel, Field
from langgraph.graph import Graph, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage

from src.database import Conversation, Message, get_db

class ConversationState(BaseModel):
    """State model for conversation memory"""
    messages: List[BaseMessage] = Field(default_factory=list)
    current_user: Optional[str] = None
    conversation_id: Optional[str] = None
    conversation_metadata: Dict[str, Any] = Field(default_factory=dict)
    last_updated: datetime = Field(default_factory=datetime.now)
    
    def add_message(self, message: BaseMessage) -> None:
        """Add a message to the conversation history"""
        self.messages.append(message)
        self.last_updated = datetime.now()
    
    def clear_messages(self) -> None:
        """Clear all messages from the conversation history"""
        self.messages = []
        self.last_updated = datetime.now()
    
    def get_recent_messages(self, limit: int = 10) -> List[BaseMessage]:
        """Get the most recent messages"""
        return self.messages[-limit:] if limit > 0 else self.messages

class MemoryManager:
    """Memory manager using PostgreSQL for conversation state management"""
    
    def __init__(self):
        self.graph = self._create_memory_graph()
    
    def _create_memory_graph(self) -> StateGraph:
        """Create the LangGraph state management graph"""
        
        def add_message_node(state: Dict) -> Dict:
            """Node for adding messages to state"""
            if "new_message" in state:
                state["messages"].append(state["new_message"])
                state["last_updated"] = datetime.now()
            return state
        
        def update_metadata_node(state: Dict) -> Dict:
            """Node for updating metadata"""
            if "metadata_update" in state:
                state["conversation_metadata"].update(state["metadata_update"])
                state["last_updated"] = datetime.now()
            return state
        
        workflow = StateGraph(Dict)
        workflow.add_node("add_message", add_message_node)
        workflow.add_node("update_metadata", update_metadata_node)
        workflow.add_edge("add_message", "update_metadata")
        workflow.set_entry_point("add_message")
        
        return workflow.compile()
    
    def _message_to_db(self, message: BaseMessage) -> Dict:
        """Convert BaseMessage to database format"""
        return {
            "type": type(message).__name__,
            "content": message.content,
            "additional_kwargs": message.additional_kwargs
        }
    
    def _db_to_message(self, db_message: Message) -> BaseMessage:
        """Convert database message to BaseMessage"""
        message_types = {
            "HumanMessage": HumanMessage,
            "AIMessage": AIMessage,
            "SystemMessage": SystemMessage
        }
        message_class = message_types[db_message.type]
        return message_class(
            content=db_message.content,
            additional_kwargs=db_message.additional_kwargs
        )
    
    def get_or_create_state(self, conversation_id: str, user_id: Optional[str] = None) -> ConversationState:
        """Get an existing conversation state or create a new one from the database"""
        with get_db() as db:
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                conversation = Conversation(
                    id=conversation_id,
                    current_user=user_id,
                    conversation_metadata={},
                    last_updated=datetime.now()
                )
                db.add(conversation)
                db.commit()
                db.refresh(conversation)
            
            messages = [self._db_to_message(msg) for msg in conversation.messages]
            
            return ConversationState(
                messages=messages,
                current_user=conversation.current_user,
                conversation_id=conversation.id,
                conversation_metadata=conversation.conversation_metadata,
                last_updated=conversation.last_updated
            )
    
    async def add_user_message(self, conversation_id: str, content: str, user_id: Optional[str] = None) -> None:
        """Add a user message to the conversation"""
        message = HumanMessage(content=content)
        
        with get_db() as db:
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()
            
            if not conversation:
                conversation = Conversation(
                    id=conversation_id,
                    current_user=user_id
                )
                db.add(conversation)
            
            db_message = Message(
                conversation_id=conversation_id,
                **self._message_to_db(message)
            )
            db.add(db_message)
            db.commit()
    
    async def add_ai_message(self, conversation_id: str, content: str) -> None:
        """Add an AI message to the conversation"""
        message = AIMessage(content=content)
        
        with get_db() as db:
            db_message = Message(
                conversation_id=conversation_id,
                **self._message_to_db(message)
            )
            db.add(db_message)
            db.commit()
    
    def get_conversation_history(self, conversation_id: str, limit: Optional[int] = None) -> List[BaseMessage]:
        """Get the conversation history from the database
        
        Args:
            conversation_id: ID of the conversation
            limit: Maximum number of most recent messages to return
            
        Returns:
            List of messages in the conversation, ordered by creation time
        """
        with get_db() as db:
            if limit:
                # Get the most recent messages when limit is specified
                messages = db.query(Message).filter(
                    Message.conversation_id == conversation_id
                ).order_by(Message.created_at.desc()).limit(limit).all()
                # Reverse the messages to get chronological order
                messages = messages[::-1]
            else:
                # Get all messages in chronological order
                messages = db.query(Message).filter(
                    Message.conversation_id == conversation_id
                ).order_by(Message.created_at).all()
            
            return [self._db_to_message(msg) for msg in messages]
    
    def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation's history from the database"""
        with get_db() as db:
            db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).delete()
            db.commit()
    
    def save_state(self, file_path: str) -> None:
        """Export conversation states to a file"""
        with get_db() as db:
            conversations = db.query(Conversation).all()
            serialized_states = {}
            
            for conv in conversations:
                messages = []
                for msg in conv.messages:
                    messages.append({
                        "type": msg.type,
                        "content": msg.content,
                        "additional_kwargs": msg.additional_kwargs
                    })
                
                serialized_states[conv.id] = {
                    "messages": messages,
                    "current_user": conv.current_user,
                    "conversation_id": conv.id,
                    "conversation_metadata": conv.conversation_metadata,
                    "last_updated": conv.last_updated.isoformat()
                }
            
            with open(file_path, 'w') as f:
                json.dump(serialized_states, f, indent=2)
    
    def load_state(self, file_path: str) -> None:
        """Import conversation states from a file"""
        with open(file_path, 'r') as f:
            serialized_states = json.load(f)
        
        with get_db() as db:
            for conv_id, state_data in serialized_states.items():
                conversation = Conversation(
                    id=conv_id,
                    current_user=state_data["current_user"],
                    conversation_metadata=state_data.get("conversation_metadata", {}),
                    last_updated=datetime.fromisoformat(state_data["last_updated"])
                )
                db.add(conversation)
                
                for msg_data in state_data["messages"]:
                    message = Message(
                        conversation_id=conv_id,
                        type=msg_data["type"],
                        content=msg_data["content"],
                        additional_kwargs=msg_data["additional_kwargs"]
                    )
                    db.add(message)
            
            db.commit()