# rail-assistant
AI test project to create a UK railways assistant for train times and prices.
Instead of the familiar dropdowns you will be able to use natural language to query train services.

Add the following to .env...

Your anthropic API key:
```ANTHROPIC_API_KEY=<your api key>```
TransportAPI developer keys - go here to signup [https://developer.transportapi.com/]
```TRANSPORTAPI_APP_ID=<your id>```
```TRANSPORTAPI_APP_KEY=<your key>```

Create a venv using 3.12 (as some packages not currently available for latest 3.13)
```python3.12 -m venv venv```

Install the requirements
```pip install -r requirements.txt```

To run locally
```uvicorn main:app --reload --port 8000```
Then in your browser:
[http://127.0.0.1:8000]

# Status
9/6/2025
Created project.
UI takes a query and sends to the backend.
Backend asks claude API to distill into rail journey specific json.
