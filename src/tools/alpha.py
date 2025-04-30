from typing import Any, Dict, Literal, ClassVar, Type, Optional, List, Union
import logging
import json
from pydantic import BaseModel, Field, ConfigDict
from langchain.tools import StructuredTool
from langchain.schema import AIMessage, HumanMessage, BaseMessage
from langchain_core.output_parsers import StrOutputParser
from ..mcp_client import mcp
from pydantic import field_validator

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

PROMPT = """You are a Crypto Analytics Expert strictly using the Alpha API. Follow these guidelines exactly:

1. SEARCH
   - Use `command: search` with a `search` parameter.
   - The response contains a list of coins and their metadata.
   - Do NOT generate any information beyond what the API returns.
   - Format as a clean list. Do not merge or deduplicate.

2. GENERATE REPORT
   - Use `command: generate_report` with the `address` of a token.
   - the `address` can be in the message or in the context.
   - From the response, extract ONLY the `id`. Do NOT describe, summarize, or analyze the token.
   - Format as a clean list. Do not merge or deduplicate.

3. RUMOUR SUBMISSION
   - Use `command: rumour` with a `message` that includes:
     * Wallet address
     * Message body
     * Token name
     * Token address
   - If any of these are missing, prompt the user to provide the missing fields.
   - Send requests using `message` and `source` as query params.
   - If user provides instructions across multiple messages, merge them into one.
   - `command` should always be `rumour` not `rumor`

4. INTEGRITY RULES
   - Do NOT infer or hallucinate any information.
   - Do NOT estimate token supply, market cap, or risks unless directly provided.
   - Do NOT provide financial advice or sentiment interpretation.
   - Do NOT generate reports or summaries based on retrieved data.
   - Your role is to retrieve data via tools only, not to interpret it.
   - Always respond in the same format as described in the system prompt, even for errors.

5. PARAMETER EXAMPLES
   - Search: `{{ 'search': 'pepe' }}`
   - Generate Report: `{{ 'address': '...' }}`
   - Rumour: `{{ 'message': '...' }}`

6. OUTPUT FORMAT
   - Always respond in the same format as described in the system prompt
   - If the CallToolResult has an error, return the error in the same format as described in the system prompt

REMEMBER: Your job is to call the appropriate Alpha API tools and return the API data only. Never summarize, conclude, or advise based on retrieved data.
"""

class TextOutputParser:
    """Parser for handling various types of text output from the API"""
    
    @staticmethod
    def parse(response: Any) -> Union[str, Dict, List]:
        """Parse response into a usable format"""
        # Extract content from response
        if isinstance(response, BaseMessage):
            content = response.content
        elif hasattr(response, 'content'):
            content = response.content
        else:
            content = response

        # Handle string content
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
                
        return content

class AlphaToolInput(BaseModel):
    """Input schema for Alpha API tool"""
    command: Literal["search", "generate_report", "rumour"] = Field(
        description="Command to execute (search/generate_report/rumour)"
    )
    search: Optional[str] = Field(
        default=None,
        description="Search term for the search command"
    )
    address: Optional[str] = Field(
        default=None,
        description="Token address for the generate_report command"
    )
    message: Optional[str] = Field(
        default=None,
        description="Message for the rumour command"
    )

    class Config:
        extra = "forbid"

    @field_validator("search")
    def validate_search(cls, v, info):
        if info.data.get("command") == "search" and v is None:
            raise ValueError("search parameter is required for search command")
        return v

    @field_validator("address")
    def validate_address(cls, v, info):
        if info.data.get("command") == "generate_report" and v is None:
            raise ValueError("address parameter is required for generate_report command")
        return v

    @field_validator("message")
    def validate_message(cls, v, info):
        if info.data.get("command") == "rumour" and v is None:
            raise ValueError("message parameter is required for rumour command")
        return v

class AlphaApiTool(StructuredTool):
    """Alpha API tool for crypto analytics"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Tool configuration
    name: str = "alpha"
    description: str = "Access crypto analytics and reporting via Alpha API"
    args_schema: Type[BaseModel] = AlphaToolInput
    parser: StrOutputParser = Field(default_factory=StrOutputParser)
    
    # Add operation mappings
    OPERATIONS: ClassVar[Dict[str, str]] = {
        "search": "API-search_coins_api_coin_get",
        "generate_report": "API-generate_report_api_api_generate_report_get",
        "rumour": "API-evaluate_message_post_api_message_post"
    }

    def _format_coin_data(self, coin: Dict[str, Any]) -> Dict[str, str]:
        """Helper function to format coin data consistently"""
        if not isinstance(coin, dict):
            return None
        return {
            "name": coin.get("name", ""),
            "symbol": coin.get("symbol", ""),
            "address": coin.get("address", "")
        }

    def _parse_response(self, response: Any) -> Union[Dict, List, str]:
        """Parse response using StrOutputParser and convert to appropriate type"""
        print(f"Response type: {type(response)}")
        # Extract content from message types
        if isinstance(response, BaseMessage):
            content = response.content
        elif hasattr(response, 'content'):
            content = response.content
        else:
            content = response

        # Parse to string
        parsed_str = self.parser.parse(str(content))
        
        # Handle streaming response format
        if isinstance(parsed_str, str) and "data:" in parsed_str:
            # Extract the final ID from the stream
            lines = parsed_str.strip().split("\n")
            for line in reversed(lines):
                if line.startswith("data: 100 |"):
                    # Extract the ID after the pipe
                    return json.dumps({"id": line.split("|")[1].strip()})
        
        # Try to parse as JSON
        try:
            return json.loads(parsed_str)
        except json.JSONDecodeError:
            return parsed_str
        
    async def _arun(
        self,
        command: str,
        search: Optional[str] = None,
        address: Optional[str] = None,
        id: Optional[str] = None,
        message: Optional[str] = None
    ) -> str:
        """Execute Alpha API operations via MCP"""
        try:
            # Log the incoming request
            logger.info(f"Alpha API request - Command: {command}, Search: {search}, Address: {address}, ID: {id}, Message: {message}")
            
            # Map the command to operation ID
            operation_id = self._get_operation_id(command)
            if not operation_id:
                return json.dumps({"error": f"Invalid command: {command}"})
            
            # Prepare parameters based on command
            if command == "search":
                params = {"search": search, "verified": False}
            elif command == "generate_report":
                params = {"address": address}
            elif command == "rumour":
                params = {"message": message, "source": "X"}
            else:
                return json.dumps({"error": f"Invalid command: {command}"})
            
            # Prepare MCP request
            mcp_args = {
                "server": "alpha-api",
                "tool": operation_id,
                "arguments": params
            }
            logger.debug(f"Final MCP arguments: {mcp_args}")
            
            # Call the API through MCP
            response = await mcp(**mcp_args)
            logger.info(f"Alpha API response received for {operation_id}")
            print(f"\n\nResponse: {response}")
           
            # Extract text content from response
            text_contents = [c.text for c in response.content if hasattr(c, 'text')]
            if not text_contents:
                return json.dumps({"error": "No text content in response"})
            # Join multiple text contents if present
            content = text_contents[0]
            print(f"\n\nContent: {content}")
            
            # Check for error response in content
            try:
                print(f"\n\nContent type: {type(content)}")
                content_json = json.loads(content) if isinstance(content, str) else content
                print(f"\n\nContent json: {content_json}")
                print(f"\n\nContent json type: {isinstance(content_json, dict)}")
                if isinstance(content_json, dict):
                    if content_json.get("status") == "error" and "detail" in content_json:
                        error_detail = content_json["detail"]
                        return json.dumps({
                            "error": error_detail.get("error", "Unknown error"),
                            "details": error_detail.get("info", {})
                        })
            except json.JSONDecodeError:
                pass  # Continue with normal flow if content is not JSON
                
            # Parse the content based on command
            if command == "search":
                try:
                    search_results = json.loads(content)
                    if isinstance(search_results, list):
                        results = [
                            coin_data for coin in search_results
                            if (coin_data := self._format_coin_data(coin)) is not None
                        ]
                        return json.dumps({"coins": results})
                except json.JSONDecodeError:
                    return json.dumps({"error": "Invalid search results format"})
                
            elif command == "generate_report":
                # Extract the final ID from the stream
                lines = content.strip().split('\\r\\n\\r\\n')
                for line in reversed(lines):

                    if line.startswith("data: 100 |"):
                        # Extract the ID after the pipe
                        return json.dumps({"id": line.split("|")[1].strip()})
                    
        
            # For other commands, try to parse as JSON first
            try:
                parsed_content = json.loads(content)
                return json.dumps(parsed_content)
            except json.JSONDecodeError:
                # If not JSON, return as plain message
                return json.dumps({"message": content})
                
        except Exception as e:
            error_msg = f"Unexpected error in Alpha tool: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return json.dumps({"error": error_msg})

    def _get_operation_id(self, command: str) -> str:
        """Map user-friendly command to operation ID"""
        return self.OPERATIONS.get(command.lower())

    def get_prompt(self) -> str:
        """Return the tool-specific prompt"""
        return PROMPT