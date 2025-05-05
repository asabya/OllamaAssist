from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
from pydantic import BaseModel, Field
from langgraph.graph import Graph, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage

from src.database import Message, Conversation, get_db

class ConversationState(BaseModel):
    """State model for conversation memory"""
    messages: List[BaseMessage] = Field(default_factory=list)
    current_user: Optional[str] = None
    conversation_id: Optional[str] = None
    title: Optional[str] = None
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
        
        workflow = StateGraph(Dict)
        workflow.add_node("add_message", add_message_node)
        workflow.set_entry_point("add_message")
        
        return workflow.compile()
    
    def _message_to_db(self, message: BaseMessage) -> Dict:
        """Convert BaseMessage to database format"""
        return {
            "type": type(message).__name__,
            "content": message.content
        }
    
    def _db_to_message(self, db_message: Message) -> BaseMessage:
        """Convert database message to BaseMessage"""
        message_types = {
            "HumanMessage": HumanMessage,
            "AIMessage": AIMessage,
            "SystemMessage": SystemMessage
        }
        message_class = message_types[db_message.type]
        
        # Extract usage metadata if it exists
        additional_kwargs = {}
        if db_message.input_tokens is not None:
            additional_kwargs['usage_metadata'] = {
                'input_tokens': db_message.input_tokens,
                'output_tokens': db_message.output_tokens,
                'total_tokens': db_message.total_tokens,
                'input_token_details': {
                    'cache_read': db_message.cache_read,
                    'cache_creation': db_message.cache_creation
                }
            }
        if db_message.tool_calls:
            additional_kwargs['tool_calls'] = db_message.tool_calls
            
        return message_class(
            content=db_message.content,
            additional_kwargs=additional_kwargs
        )
    
    def get_or_create_state(self, conversation_id: str, user_id: Optional[str] = None, title: Optional[str] = None) -> ConversationState:
        """Get an existing conversation state or create a new one from the database"""
        with get_db() as db:
            # Get or create conversation
            conversation = Conversation.get_or_create(db, conversation_id, title=title, user_id=user_id)
            
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at).all()
            
            return ConversationState(
                messages=[self._db_to_message(msg) for msg in messages],
                current_user=user_id,
                conversation_id=conversation_id,
                title=conversation.title,
                last_updated=conversation.updated_at
            )
    
    async def add_user_message(self, conversation_id: str, content: str, user_id: Optional[str] = None, title: Optional[str] = None) -> None:
        """Add a user message to the conversation"""
        message = HumanMessage(content=content)
        
        with get_db() as db:
            # Ensure conversation exists and update title if provided
            conversation = Conversation.get_or_create(db, conversation_id, title=title, user_id=user_id)
            if title and conversation.title != title:
                conversation.title = title
            db.flush()
            
            db_message = Message(
                conversation_id=conversation_id,
                **self._message_to_db(message)
            )
            db.add(db_message)
            db.commit()
    
    async def add_ai_message(self, conversation_id: str, content: str, message_id: Optional[str] = None, title: Optional[str] = None) -> None:
        """Add an AI message to the conversation
        
        Args:
            conversation_id: ID of the conversation
            content: The message content
            message_id: Optional external message ID
            title: Optional conversation title to update
        """
        message = AIMessage(content=content)
        
        with get_db() as db:
            # Get existing conversation (don't create new one for AI messages)
            conversation = db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).first()
            
            if conversation and title and conversation.title != title:
                conversation.title = title
                db.commit()
            
            message_data = {
                **self._message_to_db(message),
                'conversation_id': conversation_id,
                'message_id': message_id
            }
            
            # Use the upsert_message method to handle updates
            Message.upsert_message(db, message_data)
    
    def update_conversation(self, conversation_id: str, title: Optional[str] = None, user_id: Optional[str] = None) -> None:
        """Update conversation attributes
        
        Args:
            conversation_id: ID of the conversation
            title: New title for the conversation
            user_id: New user ID for the conversation
        """
        with get_db() as db:
            updates = {}
            if title is not None:
                updates['title'] = title
            if user_id is not None:
                updates['user_id'] = user_id
            
            if updates:
                Conversation.update_conversation(db, conversation_id, **updates)

    def get_all_conversations(self) -> List[Dict[str, Any]]:
        """Get all conversations with their basic information"""
        with get_db() as db:
            conversations = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
            return [{
                'conversation_id': conv.conversation_id,
                'user_id': conv.user_id,
                'title': conv.title,
                'created_at': conv.created_at,
                'updated_at': conv.updated_at
            } for conv in conversations]

    def get_user_conversations(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all conversations for a specific user"""
        with get_db() as db:
            conversations = db.query(Conversation).filter(
                Conversation.user_id == user_id
            ).order_by(Conversation.updated_at.desc()).all()
            return [{
                'conversation_id': conv.conversation_id,
                'title': conv.title,
                'created_at': conv.created_at,
                'updated_at': conv.updated_at
            } for conv in conversations]

    def get_conversation_history(self, conversation_id: str, limit: Optional[int] = None) -> List[BaseMessage]:
        """Get the conversation history for a specific conversation
        
        Args:
            conversation_id: ID of the conversation
            limit: Optional limit on number of messages to return (most recent)
            
        Returns:
            List of BaseMessage objects representing the conversation history
        """
        with get_db() as db:
            query = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(Message.created_at)
            
            if limit:
                query = query.limit(limit)
                
            messages = query.all()
            return [self._db_to_message(msg) for msg in messages]

    def delete_conversation(self, conversation_id: str) -> None:
        """Delete a conversation and all its messages"""
        with get_db() as db:
            # Delete all messages first
            db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).delete()
            
            # Delete the conversation
            db.query(Conversation).filter(
                Conversation.conversation_id == conversation_id
            ).delete()
            
            db.commit()

    def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation's messages but keep the conversation record"""
        with get_db() as db:
            db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).delete()
            db.commit()
    
    def save_state(self, file_path: str) -> None:
        """Export conversation states to a file"""
        with get_db() as db:
            # Get all conversations
            conversations = db.query(Conversation).all()
            serialized_states = {}
            
            for conv in conversations:
                messages = db.query(Message).filter(
                    Message.conversation_id == conv.conversation_id
                ).order_by(Message.created_at).all()
                
                serialized_states[conv.conversation_id] = {
                    "title": conv.title,
                    "user_id": conv.user_id,
                    "created_at": conv.created_at.isoformat(),
                    "updated_at": conv.updated_at.isoformat(),
                    "messages": []
                }
                
                for msg in messages:
                    message_data = {
                        "type": msg.type,
                        "content": msg.content,
                        "message_id": msg.message_id,
                        "input_tokens": msg.input_tokens,
                        "output_tokens": msg.output_tokens,
                        "total_tokens": msg.total_tokens,
                        "cache_read": msg.cache_read,
                        "cache_creation": msg.cache_creation,
                        "tool_calls": msg.tool_calls
                    }
                    serialized_states[conv.conversation_id]["messages"].append(message_data)
            
            with open(file_path, 'w') as f:
                json.dump(serialized_states, f, indent=2)
    
    def load_state(self, file_path: str) -> None:
        """Import conversation states from a file"""
        with open(file_path, 'r') as f:
            serialized_states = json.load(f)
        
        with get_db() as db:
            for conv_id, state_data in serialized_states.items():
                # Create or update conversation
                conversation = Conversation.get_or_create(
                    db, 
                    conv_id,
                    title=state_data.get("title"),
                    user_id=state_data.get("user_id")
                )
                
                # Add messages
                for msg_data in state_data["messages"]:
                    message_data = {
                        "conversation_id": conv_id,
                        "type": msg_data["type"],
                        "content": msg_data["content"],
                        "message_id": msg_data.get("message_id"),
                        "input_tokens": msg_data.get("input_tokens"),
                        "output_tokens": msg_data.get("output_tokens"),
                        "total_tokens": msg_data.get("total_tokens"),
                        "cache_read": msg_data.get("cache_read"),
                        "cache_creation": msg_data.get("cache_creation"),
                        "tool_calls": msg_data.get("tool_calls", [])
                    }
                    Message.upsert_message(db, message_data)