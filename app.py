from flask import Flask, jsonify, request
import requests
import os
from dotenv import load_dotenv

load_dotenv()

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")

app = Flask(__name__)

def get_coordinates(location):
    try:
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "WeatherGo/1.0"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        data = response.json()
        if not data:
            return None, None
        return float(data[0]["lat"]), float(data[0]["lon"])
    except Exception as e:
        print("Nominatim error:", e)
        return None, None

def get_weather(lat, lon):
    try:
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        return {
            "status": data["weather"][0]["description"],
            "temperature": data["main"]["temp"]
        }
    except Exception as e:
        print("OpenWeatherMap error:", e)
        return None

def get_places(lat, lon, activity_type):
    try:
        query = f"[out:json];node[amenity={activity_type}](around:2000,{lat},{lon});out 5;"
        url = "https://overpass-api.de/api/interpreter"
        response = requests.get(
            url,
            params={"data": query},
            headers={
                "User-Agent": "WeatherGo/1.0",
                "Accept": "*/*"
            },
            timeout=10
        )
        if response.status_code != 200 or not response.text:
            return []
        data = response.json()
        places = []
        for element in data.get("elements", []):
            tags = element.get("tags", {})
            name = tags.get("name") or tags.get("addr:street") or "Unknown place"
            places.append(name)
        return places
    except Exception as e:
        print("Overpass error:", e)
        return []

def get_recommendation(location, weather, places, activity_type):
    try:
        microservice_url = os.environ.get("GROQ_MICROSERVICE_URL", "http://localhost:5001/generate")
        payload = {
            "location": location,
            "weather": weather["status"],
            "temperature": weather["temperature"],
            "places": places,
            "activity_type": activity_type
        }
        response = requests.post(microservice_url, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("recommendation")
        return None
    except Exception as e:
        print("Groq microservice error:", e)
        return None

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
    if weather is None:
        return jsonify({"error": "Weather service is temporarily unavailable, please try again later"}), 503

    places = get_places(lat, lon, activity_type)
    if not places:
        return jsonify({"error": "No relevant places found nearby"}), 404

    recommendation = get_recommendation(location, weather, places, activity_type)

    return jsonify({
        "location": location,
        "weather": weather,
        "places": places,
        "recommendation": recommendation
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)