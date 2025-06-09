import asyncio
from main import ClaudeRailIntegration
import os
from dotenv import load_dotenv

load_dotenv()

async def test():
    claude = ClaudeRailIntegration(os.getenv("ANTHROPIC_API_KEY"))
    
    # Test query parsing
    result = await claude.parse_query("next train from London to Manchester")
    print("✅ Parsed query:", result)
    
    # Test response formatting  
    mock_data = {
        "services": [{
            "departure_time": "14:30",
            "arrival_time": "16:45", 
            "duration": "2h 15m",
            "operator": "Avanti West Coast"
        }]
    }
    
    response = await claude.format_response(mock_data, "next train from London to Manchester")
    print("✅ Formatted response:", response)

if __name__ == "__main__":
    asyncio.run(test())
