# rail-assistant
AI test project to create a UK railways assistant for train times and prices

add the following to .env
ANTHROPIC_API_KEY=<your api key>

Create a venv using 3.12 (as some packages not available for 3.13)
python3.12 -m venv venv

Install the requirements
pip install -r requirements.txt

Run locally
uvicorn main:app --reload --port 8000

Browse to http://127.0.0.1:8000
