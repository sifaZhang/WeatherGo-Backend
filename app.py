from flask import Flask, jsonify, request
import requests
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def get_coordinates(location):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": location,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "WeatherGo/1.0"
    }
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    if not data:
        return None, None
    return float(data[0]["lat"]), float(data[0]["lon"])

def get_weather(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": os.environ.get("WEATHER_API_KEY"),
        "units": "metric"
    }
    response = requests.get(url, params=params)
    data = response.json()
    return {
        "status": data["weather"][0]["description"],
        "temperature": data["main"]["temp"]
    }

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()
    location = data.get('location')
    activity_type = data.get('activity_type')

    if not location or not activity_type:
        return jsonify({"error": "location and activity_type are required"}), 400

    lat, lon = get_coordinates(location)
    if lat is None:
        return jsonify({"error": "Location not recognised, please enter a more specific location"}), 404

    weather = get_weather(lat, lon)

    return jsonify({
        "location": location,
        "coordinates": {"lat": lat, "lon": lon},
        "weather": weather,
        "places": [],
        "recommendation": None
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)