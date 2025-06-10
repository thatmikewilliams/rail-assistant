import json
import httpx
import asyncio
from typing import Dict, Any, Optional
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

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

class TransportAPIClient:
    def __init__(self, app_id: str, app_key: str):
        self.app_id = app_id
        self.app_key = app_key
        self.base_url = "https://transportapi.com/v3/uk"
    
    async def get_station_code(self, station_name: str) -> Optional[str]:
        """Get 3-letter station code from station name"""
        url = f"{self.base_url}/places.json"
        params = {
            'app_id': self.app_id,
            'app_key': self.app_key,
            'query': station_name,
            'type': 'train_station'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                data = response.json()
                
                if data.get('member') and len(data['member']) > 0:
                    return data['member'][0].get('station_code')
                    
        except Exception as e:
            print(f"Error getting station code for {station_name}: {e}")
        
        return None
    
    async def get_train_times(self, origin_code: str, dest_code: str, 
                            departure_date: str, departure_time: str) -> Optional[Dict]:
        """Get train times from TransportAPI"""
        url = f"{self.base_url}/train/station/{origin_code}/{departure_date}/{departure_time}/timetable.json"
        
        params = {
            'app_id': self.app_id,
            'app_key': self.app_key,
            'destination': dest_code,
            'train_status': 'passenger'
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=15.0)
                
                if response.status_code == 200:
                    return response.json()
                else:
                    print(f"TransportAPI Error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            print(f"Error fetching train times: {e}")
            return None
    
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
- Show platform information when available
- Mention operator and any delays/status updates
- Use 12-hour time format (e.g. 2:30pm not 14:30)
- Keep responses concise but informative
- If multiple options, show the best 2-3 choices
- Use emojis sparingly for better readability (🚂 🕐 🚉)

Example response format:
"🚂 The next train from London to Manchester departs at 2:30pm from Platform 5, arriving at 4:45pm (2h 15m journey). It's operated by Northern Rail and currently running on time."
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

# FastAPI integration
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel as PydanticBaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()
app.mount("/static", StaticFiles(directory="."), name="static")

class RailQueryRequest(PydanticBaseModel):
    query: str

# Initialize integrations
claude_integration = ClaudeRailIntegration(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)

transport_api = TransportAPIClient(
    app_id=os.getenv("TRANSPORTAPI_APP_ID"),
    app_key=os.getenv("TRANSPORTAPI_APP_KEY")
)

@app.get("/")
async def serve_frontend():
    return FileResponse("index.html")

@app.post("/api/rail-query")
async def handle_rail_query(request: RailQueryRequest):
    print(f"Request JSON: {json.dumps(request.dict(), indent=2)}")
    try:
        # Step 1: Parse the query
        parsed_params = await claude_integration.parse_query(request.query)
        print(f"Parsed parameters: {parsed_params}")
        
        # Step 2: Call the real rail API
        rail_data = await fetch_rail_data(parsed_params)
        
        if not rail_data:
            return {"response": f"Sorry, I couldn't find any train information for your journey from {parsed_params.origin} to {parsed_params.destination}. Please check the station names and try again."}
        
        # Step 3: Format the response
        formatted_response = await claude_integration.format_response(
            rail_data, request.query
        )
        
        return {"response": formatted_response, "raw_data": rail_data}
        
    except Exception as e:
        print(f"Error handling query: {e}")
        raise HTTPException(status_code=500, detail=str(e))

async def fetch_rail_data(params: RailQueryParams) -> Optional[Dict[Any, Any]]:
    """
    Integrate with TransportAPI to get real rail data
    """
    try:
        # Get station codes
        origin_code = await transport_api.get_station_code(params.origin)
        dest_code = await transport_api.get_station_code(params.destination)
        
        if not origin_code:
            print(f"Could not find station code for: {params.origin}")
            return None
        if not dest_code:
            print(f"Could not find station code for: {params.destination}")
            return None
        
        print(f"Station codes: {params.origin} -> {origin_code}, {params.destination} -> {dest_code}")
        
        # Format date and time
        departure_date = params.date or "today"
        if departure_date == 'today':
            departure_date = datetime.now().strftime('%Y-%m-%d')
        elif departure_date == 'tomorrow':
            departure_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        departure_time = params.departure_time or "now"
        if departure_time == 'now':
            departure_time = datetime.now().strftime('%H:%M')
        elif departure_time == 'morning':
            departure_time = "09:00"
        elif departure_time == 'afternoon':
            departure_time = "13:00"
        elif departure_time == 'evening':
            departure_time = "17:00"
        
        # Get train data from TransportAPI
        train_data = await transport_api.get_train_times(
            origin_code, dest_code, departure_date, departure_time
        )
        
        if not train_data:
            return None
        
        # Structure the response for Claude to format
        formatted_data = {
            "query_info": {
                "origin": params.origin,
                "destination": params.destination,
                "origin_code": origin_code,
                "destination_code": dest_code,
                "search_date": departure_date,
                "search_time": departure_time
            },
            "services": []
        }
        
        # Extract relevant train information
        departures = train_data.get('departures', {}).get('all', [])[:3]  # Get first 3 trains
        
        for train in departures:
            service = {
                "departure_time": train.get('aimed_departure_time') or train.get('expected_departure_time'),
                "arrival_time": train.get('aimed_arrival_time') or train.get('expected_arrival_time'),
                "expected_departure": train.get('expected_departure_time'),
                "expected_arrival": train.get('expected_arrival_time'),
                "platform": train.get('platform', 'TBC'),
                "operator": train.get('operator_name', ''),
                "service_timetable": train.get('service_timetable', {}),
                "status": train.get('status', 'On time')
            }
            formatted_data["services"].append(service)
        
        return formatted_data
        
    except Exception as e:
        print(f"Error fetching rail data: {e}")
        return None

# Example usage and testing
async def test_integration():
    """Test the complete integration"""
    
    # Test query parsing
    test_query = "when's the next train from Ivybridge to Brookwood"
    parsed = await claude_integration.parse_query(test_query)
    print(f"Parsed: {parsed}")
    
    # Test real API integration
    rail_data = await fetch_rail_data(parsed)
    print(f"Rail data: {json.dumps(rail_data, indent=2)}")
    
    if rail_data:
        # Test response formatting
        formatted = await claude_integration.format_response(rail_data, test_query)
        print(f"Formatted: {formatted}")

if __name__ == "__main__":
    # Run test
    asyncio.run(test_integration())
