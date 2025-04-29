from typing import Any, Dict, ClassVar, Type
import logging
from pydantic import BaseModel, Field, ConfigDict
from langchain.tools import StructuredTool
from ..mcp_client import mcp

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class BraveSearchInput(BaseModel):
    """Input schema for Brave Search tool"""
    query: str = Field(
        description="The search query to execute"
    )

class BraveSearchTool(StructuredTool):
    """Brave Search tool for web searches"""
    
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    # Tool configuration
    name: str = "brave"
    description: str = "Search the web using Brave Search"
    args_schema: Type[BaseModel] = BraveSearchInput
    
    # Tool-specific constants
    PROMPT: ClassVar[str] = """You are CryptoSocial Analyst v2.3 - an AI specializing in meme coin research via Brave Search. Your protocol:

1. **Query Focus**  
   - Auto-detect coin's origin story, mascot, and key community slang  
   - Track "rugpull", "dead coin", and "wen moon" sentiment patterns  

2. **Brave Search Parameters**  
   ```  
   !social (site:reddit.com OR site:twitter.com)  
   !crypto (filetype:forum OR after:2024)  
   safesearch=off  
   ```  

3. **Priority Checks**  
   - Verify liquidity pool locks via Brave-indexed blockchain explorers  
   - Cross-reference Telegram hype vs. 4chan/Farcaster skepticism  
   - Detect bot activity patterns in social metrics  

4. **Risk Analysis**  
   - Calculate "Meme Score": (Hype Velocity) / (Developer Transparency)  
   - Flag anonymous teams and copycat token contracts  

**Output Rules**  
```  
[Coin Name] Social Report (Brave Search MCP)  
⊚ Core Narrative: [2-sentence origin summary]  
⊚ Hype Pulse: [1-10 score] | Risk Level: [Low/Extreme]  
⚠️ Top Risk: [Most cited concern]  
🔼 Bull Case: [Key community argument]  
🔻 Bear Case: [Top criticism]  
📌 Critical Source: [Brave.link example]  
```  

*Example Output*  
```  
[DogeCloneCoin] Social Report  
⊚ Narrative: Elon Musk parody token, launched after 2024 Super Bowl ad  
⊚ Hype Pulse: 8/10 | Risk Level: Extreme  
⚠️ Top Risk: 91% supply held by 3 wallets (Brave.link/scanproof)  
🔼 Bull: "Next Doge" trend on TikTok (+14K videos)  
🔻 Bear: Zero whitepaper, devs unreachable  
```  

**Terminate analysis if:**  
- >70% negative sentiment across 3+ platforms  
- Verified scam reports in Brave-indexed blockchain databases"""

    async def _arun(self, query: str) -> Any:
        """Execute Brave search query"""
        logger.info(f"Brave search request - Query: {query}")
        
        try:
            # Call Brave search through MCP
            response = await mcp(
                server="brave-search",
                tool="API-search_api_search_get",
                arguments={"q": query}
            )
            
            logger.info("Brave search response received")
            
            # Handle string response
            if isinstance(response, str):
                return response
            
            # Handle object response with content attribute
            if hasattr(response, 'content'):
                for content in response.content:
                    if content.type == 'text':
                        return content.text
            
            return response
            
        except Exception as e:
            error_msg = f"Brave search error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    def get_prompt(self) -> str:
        """Return the tool-specific prompt"""
        return self.PROMPT

    def get_args_schema(self) -> Type[BaseModel]:
        """Return the args schema for the tool"""
        return self.args_schema
