import json
import httpx
import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Data models
class RailQueryParams(BaseModel):
    origin: str
    destination: str
    departure_time: Optional[str] = None
    arrival_time: Optional[str] = None
    date: Optional[str] = None
    journey_type: str = "single"  # single, return, next_available
    passengers: int = 1
    railcard: Optional[str] = None
    
class ClaudeRailIntegration:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.anthropic.com/v1/messages"
        self.headers = {
            "Content-Type": "application/json",
            "X-API-Key": api_key,
            "anthropic-version": "2023-06-01"
        }
    
    async def parse_query(self, user_query: str) -> RailQueryParams:
        """
        Parse natural language query into structured parameters
        """
        system_prompt = """You are a UK rail query parser. Convert natural language queries into structured JSON parameters.

Return ONLY a JSON object with these fields:
- origin: string (station name)
- destination: string (station name)  
- departure_time: string or null (e.g. "09:30", "morning", "now")
- arrival_time: string or null (e.g. "17:00", "before 6pm")
- date: string or null (e.g. "today", "tomorrow", "2024-12-25", "Friday")
- journey_type: "single" | "return" | "next_available"
- passengers: number (default 1)
- railcard: string or null (e.g. "16-25", "Senior", "Two Together")

Examples:
"next train from London to Manchester" → {"origin": "London", "destination": "Manchester", "departure_time": "now", "date": "today", "journey_type": "next_available", "passengers": 1, "railcard": null}
"return ticket from Leeds to York tomorrow morning" → {"origin": "Leeds", "destination": "York", "departure_time": "morning", "date": "tomorrow", "journey_type": "return", "passengers": 1, "railcard": null}
"""
        
        user_prompt = f"Parse this query: {user_query}"
        
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Claude API error: {response.status_code} - {response.text}")
            
            result = response.json()
            content = result["content"][0]["text"]
            
            # Parse JSON response
            try:
                parsed_data = json.loads(content)
                return RailQueryParams(**parsed_data)
            except (json.JSONDecodeError, ValueError) as e:
                raise Exception(f"Failed to parse Claude response: {content}")
    
    async def format_response(self, rail_data: Dict[Any, Any], original_query: str) -> str:
        """
        Format raw rail API data into natural language response
        """
        system_prompt = """You are a helpful UK rail assistant. Format raw train data into clear, conversational responses.

Guidelines:
- Be conversational and friendly
- Include key details: departure/arrival times, journey duration, changes required
- Mention prices if available
- Highlight any important notes (delays, platform changes, etc.)
- Use 12-hour time format (e.g. 2:30pm not 14:30)
- Keep responses concise but informative
- If multiple options, show the best 2-3 choices

Example response format:
"The next train from London to Manchester departs at 2:30pm, arriving at 4:45pm (2h 15m journey). It's direct with no changes required. Advance single tickets from £25.50, or off-peak return from £89.40."
"""
        
        user_prompt = f"""Original query: "{original_query}"

Raw rail data:
{json.dumps(rail_data, indent=2)}

Please format this into a helpful response for the user."""
        
        payload = {
            "model": "claude-3-5-sonnet-20241022",
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt}
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                headers=self.headers,
                json=payload,
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"Claude API error: {response.status_code} - {response.text}")
            
            result = response.json()
            return result["content"][0]["text"]

# FastAPI integration example
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as PydanticBaseModel
# for serving static directly as a test:
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
#


app = FastAPI()
# for serving static directly as a test:
app.mount("/static", StaticFiles(directory="."), name="static")
#

class RailQueryRequest(PydanticBaseModel):
    query: str

# Initialize Claude integration
claude_integration = ClaudeRailIntegration(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

# for serving static directly as a test:
@app.get("/")
async def serve_frontend():
    print("server frontend")
    return FileResponse("index.html")
#

@app.post("/api/rail-query")
async def handle_rail_query(request: RailQueryRequest):
    print(f"Request JSON: {json.dumps(request.dict(), indent=2)}")
    try:
        # Step 1: Parse the query
        parsed_params = await claude_integration.parse_query(request.query)
        print(f"Parsed parameters: {parsed_params}")
        
        # Step 2: Call your rail API (placeholder)
        rail_data = await fetch_rail_data(parsed_params)
        
        # Step 3: Format the response
        formatted_response = await claude_integration.format_response(
            rail_data, request.query
        )
        
        return {"response": formatted_response}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Placeholder for your rail API integration
async def fetch_rail_data(params: RailQueryParams) -> Dict[Any, Any]:
    """
    This is where you'll integrate with the actual UK rail API
    Replace this with your chosen rail data provider
    """
    # Mock response for testing
    mock_data = {
        "services": [
            {
                "departure_time": "14:32",
                "arrival_time": "17:45", 
                "duration": "3h 13m",
                "changes": 1,
                "change_stations": ["London Waterloo"],
                "operator": "South Western Railway",
                "price": {
                    "advance_single": 23.50,
                    "off_peak_return": 45.20
                }
            }
        ],
        "origin": params.origin,
        "destination": params.destination
    }
    
    # Simulate API delay
    await asyncio.sleep(0.5)
    return mock_data

# Example usage and testing
async def test_integration():
    """Test the Claude integration"""
    claude = ClaudeRailIntegration(api_key="your-api-key-here")
    
    # Test query parsing
    test_query = "when's the next train from Ivybridge to Brookwood"
    parsed = await claude.parse_query(test_query)
    print(f"Parsed: {parsed}")
    
    # Test response formatting
    mock_rail_data = {
        "services": [
            {
                "departure_time": "14:32",
                "arrival_time": "17:45",
                "duration": "3h 13m",
                "changes": 1,
                "operator": "South Western Railway"
            }
        ]
    }
    
    formatted = await claude.format_response(mock_rail_data, test_query)
    print(f"Formatted: {formatted}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_integration())
