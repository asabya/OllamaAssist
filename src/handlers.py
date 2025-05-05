from langchain_core.callbacks import AsyncCallbackHandler
from src.database import Message, get_db
import json

class UsageTrackingHandler(AsyncCallbackHandler):
    def __init__(self, conversation_id: str):
        self.conversation_id = conversation_id
        self.usage = {}

    async def on_llm_end(self, response, run_id, **kwargs):
        print("================================================")
        # Convert generations to a serializable format and print as JSON
        generations_data = []
        for gen_list in response.generations:
            gen_list_data = []
            for gen in gen_list:
                gen_data = {
                    'text': gen.text if hasattr(gen, 'text') else None,
                    'message_content': gen.message.content if hasattr(gen, 'message') else None,
                    'usage_metadata': gen.message.usage_metadata if hasattr(gen.message, 'usage_metadata') else None
                }
                gen_list_data.append(gen_data)
            generations_data.append(gen_list_data)
        
        print(json.dumps({
            'generations': generations_data,
            'run_id': str(run_id)
        }, indent=2))
        print("================================================")
        
        # Extract token usage from the response
        if response.generations:
            for generation_list in response.generations:
                for generation in generation_list:
                    if hasattr(generation.message, 'usage_metadata'):
                        usage_metadata = generation.message.usage_metadata
                        try:
                            with get_db() as db:
                                Message.upsert_message(db, {
                                    'conversation_id': self.conversation_id,
                                    'type': 'AIMessage',
                                    'content': generation.message.content.strip(),
                                    'message_id': str(run_id),
                                    'input_tokens': usage_metadata.get('input_tokens', 0),
                                    'output_tokens': usage_metadata.get('output_tokens', 0),
                                    'total_tokens': usage_metadata.get('total_tokens', 0),
                                    'cache_read': usage_metadata.get('input_token_details', {}).get('cache_read', 0),
                                    'cache_creation': usage_metadata.get('input_token_details', {}).get('cache_creation', 0),
                                })
                        except Exception as e:
                            print(f"Error upserting message to database: {str(e)}")
                            print(f"Message data: conversation_id={self.conversation_id}, run_id={run_id}")
                            # You might want to raise the exception here depending on your error handling strategy
                            # raise e
