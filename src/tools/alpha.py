from typing import Any, Dict
import logging
import json
from .base import BaseTool
from ..mcp_client import mcp

# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

class AlphaApiTool(BaseTool):
    PROMPT = """You are a Crypto Analytics Expert using the Alpha API. Follow these guidelines strictly:

1. Search Capabilities
   - Use 'search' with 'search' parameter
   - The response will contain a list of coins with their details
   - ONLY use the data from the actual API response
   - DO NOT make up or hallucinate any additional information
   - For search results, only return the following fields in your response:
     * name
     * symbol
     * address
   - Format the response as a clear list of found coins
   - The response might contain multiple instances of the same token name. just display name,symbol, address for each instance
2. Generate Report
   - 'generate_report' with 'address' parameter
   - Only use addresses that were returned in the search results
   - Do not analyse anything just return the id from the response
   
3. Get Report
   - 'get_report' with 'id' parameter

4. Use the address from 'API-search_coins_api_coin_get' to call 'API-generate_report_api_api_generate_report_get'.

5. Use the id from 'API-generate_report_api_api_generate_report_get' to get the raw report.

6. Parameters format:
   - Search: { "search": "michi" }
   - Generate report: { "address": "5mbK36SZ7J19An8jFochhQS4of8g6BwUjbeCSxBSoWdp" }
   - Get report: { "id": "1234567890" }

IMPORTANT: Never invent or hallucinate information. Only use data that is actually returned by the API.
"""
    GENERATE_REPORT_PROMPT = """generate a detailed investor report for the token attached based on the following structure and the data inside the provided yml file:
Overview. But do not just list numeric data, comment with textual information, on the numbers provided:

    Current Price: (if available)
    Market Capitalization: (if available)
    Total Supply: (if available)
    Circulating Supply: (if available)
    24h Volume: (if available)
    All-Time High (ATH): (price and date, if available)
    Biggest Buyer: (holder with the highest transaction volume/amount)

## Historical Context

Provide a brief history of the token, its launch details, and any major milestones (if available).
Ownership Structure

## Display the top token holders in a table or pie chart, including:

    Address
    Amount held
    Percentage of total supply
    Transaction count
    Whether the address is an exchange or a contract

Comment in textual form on what you think about the listed token holders, what they could do and potential risks involved. 

## Market Sentiment

This section should be the most detailed, covering:

    Social Media Metrics (Twitter, Telegram, Reddit, Discord)
        Followers, engagement rates, daily messages/posts
    Influencer Mentions
        Summarise key mentions on platforms like Telegram, including tone and impact
    Community Sentiment Analysis
        Overall sentiment score: -0.18 (neutral to slightly negative)
        Growth rate and engagement levels

But do not list bullet point, make the section in text format. If some data is missing, also comment on what that could mean.


## Risks and Considerations

Outline potential risks, including:

    Liquidity concerns (if applicable)
    Market volatility
    Regulatory risks
    Security concerns (e.g., contract vulnerabilities)

But do not list bullet point, make the section in text format.

## Conclusion

Summarise key insights from the report, potential investment opportunities, and any critical factors investors should be aware of."""
    # Add operation mappings
    OPERATIONS = {
        "search": "API-search_coins_api_coin_get",
        "generate_report": "API-generate_report_api_api_generate_report_get",
        "get_report": "API-get_yaml_report_api_report_yaml__id__get"
    }

    @property
    def name(self) -> str:
        return "alpha"
    
    @property
    def description(self) -> str:
        return "Access crypto analytics and reporting via Alpha API"

    @property
    def parameters(self) -> Dict:
        return {
            "command": {
                "type": "string",
                "description": "Command to execute (search/generate_report/get_report)"
            },
            "query": {
                "type": "string",
                "description": "Search term, address, or report ID depending on the command"
            }
        }
    
    @property
    def prompt(self) -> str:
        return self.PROMPT
        
    async def execute(self, command: str, query: str) -> Any:
        """Execute Alpha API operations via MCP"""
        # Log the incoming request
        logger.info(f"Alpha API request - Command: {command}, Query: {query}")
        
        # Map the command to operation ID
        operation_id = self._get_operation_id(command)
        if not operation_id:
            return {"error": f"Invalid command: {command}"}
            
        # Prepare parameters based on command
        params = self._prepare_params(command, query)
        
        # Prepare MCP request
        mcp_args = {
            "server": "alpha-api",
            "tool": operation_id,
            "arguments": params
        }
        logger.debug(f"Final MCP arguments: {mcp_args}")
            
        # Call the API through MCP
        try:
            response = await mcp(**mcp_args)
            logger.info(f"Alpha API response received for {operation_id}")

            # Handle string response
            if isinstance(response, str):
                # Check if response matches the expected format
                if "content=[TextContent(type='text', text=" in response:
                    # Extract the text content
                    start = response.find("text='") + 6
                    end = response.rfind("')")
                    if start > 6 and end > 0:  # Found valid markers
                        extracted_text = response[start:end]
                        if command == "get_report":
                            return self.GENERATE_REPORT_PROMPT + "\n\n" + extracted_text
                        else:
                            try:
                                return json.loads(extracted_text)
                            except json.JSONDecodeError:
                                return extracted_text
                
                # If it doesn't match the expected format, try regular JSON parsing
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    return response
            
            # Handle object response with content attribute
            if hasattr(response, 'content'):
                for content in response.content:
                    if content.type == 'text':
                        if command == "get_report":
                            return self.GENERATE_REPORT_PROMPT + "\n\n" + content.text
                        else:
                            return content.text
            
            return response
        except Exception as e:
            error_msg = f"Alpha API error for {operation_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"error": error_msg}

    def _get_operation_id(self, command: str) -> str:
        """Map user-friendly command to operation ID"""
        return self.OPERATIONS.get(command.lower())

    def _prepare_params(self, command: str, query: str) -> Dict:
        """Prepare parameters based on command type"""
        command = command.lower()
        if command == "search":
            return {"search": query}
        elif command == "generate_report":
            return {"address": query}
        elif command == "get_report":
            return {"id": query}
        return {} 