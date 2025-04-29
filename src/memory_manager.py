from typing import Dict, List, Optional, Any
from datetime import datetime
import json
from pydantic import BaseModel, Field
from langgraph.graph import Graph, StateGraph
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, BaseMessage

class ConversationState(BaseModel):
    """State model for conversation memory"""
    messages: List[BaseMessage] = Field(default_factory=list)
    current_user: Optional[str] = None
    conversation_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
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
    """Memory manager using LangGraph for conversation state management"""
    
    def __init__(self):
        self.states: Dict[str, ConversationState] = {}
        self.graph = self._create_memory_graph()
    
    def _create_memory_graph(self) -> StateGraph:
        """Create the LangGraph state management graph"""
        
        def add_message_node(state: Dict) -> Dict:
            """Node for adding messages to state"""
            # The message is included in the state dict
            if "new_message" in state:
                state["messages"].append(state["new_message"])
                state["last_updated"] = datetime.now()
            return state
        
        def update_metadata_node(state: Dict) -> Dict:
            """Node for updating metadata"""
            if "metadata_update" in state:
                state["metadata"].update(state["metadata_update"])
                state["last_updated"] = datetime.now()
            return state
        
        # Create the graph
        workflow = StateGraph(Dict)
        
        # Add nodes
        workflow.add_node("add_message", add_message_node)
        workflow.add_node("update_metadata", update_metadata_node)
        
        # Add edges
        workflow.add_edge("add_message", "update_metadata")
        
        # Set entry points
        workflow.set_entry_point("add_message")
        
        return workflow.compile()
    
    def get_or_create_state(self, conversation_id: str, user_id: Optional[str] = None) -> ConversationState:
        """Get an existing conversation state or create a new one"""
        if conversation_id not in self.states:
            self.states[conversation_id] = ConversationState(
                conversation_id=conversation_id,
                current_user=user_id
            )
        return self.states[conversation_id]
    
    async def add_user_message(self, conversation_id: str, content: str, user_id: Optional[str] = None) -> None:
        """Add a user message to the conversation"""
        state = self.get_or_create_state(conversation_id, user_id)
        message = HumanMessage(content=content)
        
        # Create state dict with the new message
        state_dict = {
            "messages": state.messages.copy(),
            "current_user": user_id,
            "conversation_id": conversation_id,
            "metadata": state.metadata,
            "last_updated": state.last_updated,
            "new_message": message
        }
        
        # Use the graph to update state
        updated_state = await self.graph.ainvoke(state_dict)
        
        # Update the stored state
        state.messages = updated_state["messages"]
        state.last_updated = updated_state["last_updated"]
    
    async def add_ai_message(self, conversation_id: str, content: str) -> None:
        """Add an AI message to the conversation"""
        state = self.get_or_create_state(conversation_id)
        message = AIMessage(content=content)
        
        # Create state dict with the new message
        state_dict = {
            "messages": state.messages.copy(),
            "current_user": state.current_user,
            "conversation_id": conversation_id,
            "metadata": state.metadata,
            "last_updated": state.last_updated,
            "new_message": message
        }
        
        # Use the graph to update state
        updated_state = await self.graph.ainvoke(state_dict)
        
        # Update the stored state
        state.messages = updated_state["messages"]
        state.last_updated = updated_state["last_updated"]
    
    def get_conversation_history(self, conversation_id: str, limit: Optional[int] = None) -> List[BaseMessage]:
        """Get the conversation history"""
        state = self.get_or_create_state(conversation_id)
        if limit is not None:
            return state.get_recent_messages(limit)
        return state.messages
    
    def clear_conversation(self, conversation_id: str) -> None:
        """Clear a conversation's history"""
        if conversation_id in self.states:
            self.states[conversation_id].clear_messages()
    
    def save_state(self, file_path: str) -> None:
        """Save all conversation states to a file"""
        serialized_states = {}
        for conv_id, state in self.states.items():
            serialized_states[conv_id] = {
                "messages": [
                    {
                        "type": type(msg).__name__,
                        "content": msg.content,
                        "additional_kwargs": msg.additional_kwargs
                    }
                    for msg in state.messages
                ],
                "current_user": state.current_user,
                "conversation_id": state.conversation_id,
                "metadata": state.metadata,
                "last_updated": state.last_updated.isoformat()
            }
        
        with open(file_path, 'w') as f:
            json.dump(serialized_states, f, indent=2)
    
    def load_state(self, file_path: str) -> None:
        """Load conversation states from a file"""
        with open(file_path, 'r') as f:
            serialized_states = json.load(f)
        
        for conv_id, state_data in serialized_states.items():
            messages = []
            for msg_data in state_data["messages"]:
                msg_type = msg_data["type"]
                if msg_type == "HumanMessage":
                    msg = HumanMessage(
                        content=msg_data["content"],
                        additional_kwargs=msg_data["additional_kwargs"]
                    )
                elif msg_type == "AIMessage":
                    msg = AIMessage(
                        content=msg_data["content"],
                        additional_kwargs=msg_data["additional_kwargs"]
                    )
                elif msg_type == "SystemMessage":
                    msg = SystemMessage(
                        content=msg_data["content"],
                        additional_kwargs=msg_data["additional_kwargs"]
                    )
                messages.append(msg)
            
            self.states[conv_id] = ConversationState(
                messages=messages,
                current_user=state_data["current_user"],
                conversation_id=state_data["conversation_id"],
                metadata=state_data["metadata"],
                last_updated=datetime.fromisoformat(state_data["last_updated"])
            ) 