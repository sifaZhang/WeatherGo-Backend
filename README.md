# WeatherGo Backend

Flask backend service for WeatherGo, running on Port 5000. It handles request routing, external API orchestration, and communicates with the Groq AI microservice.

## Prerequisites

- Python 3.11+
- Docker (optional, for containerised deployment)

## Project Structure
backend/
├── app.py              # Main Flask application
├── test_app.py         # Pytest tests
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker configuration
├── .env.example        # Environment variable template
└── README.md           # This file

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-org/WeatherGo-Backend.git
cd WeatherGo-Backend
```

### 2. Create virtual environment

```bash
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

`.env` content:
WEATHER_API_KEY=your_openweathermap_api_key_here
GROQ_MICROSERVICE_URL=http://localhost:5001/generate

### 5. Run the application

```bash
python app.py
```

The server will start at `http://localhost:5000`.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Check if the service is running |
| POST | `/recommend` | Get activity recommendations |

### POST /recommend

Request body:
```json
{
    "location": "Auckland",
    "activity_type": "cafe"
}
```

Response:
```json
{
    "location": "Auckland",
    "weather": {
        "status": "overcast clouds",
        "temperature": 18.22
    },
    "places": ["Cafe One", "Cafe Two"],
    "recommendation": "AI generated recommendation..."
}
```

## Running Tests

```bash
pytest test_app.py -v
```

## Running with Docker

```bash
docker build -t weathergo-backend .
docker run -p 5000:5000 --env-file .env weathergo-backend
```