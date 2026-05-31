from flask import Flask, jsonify, request
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
GEO_KEY = os.environ.get("GEO_KEY")

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

def get_places_overpass(lat, lon, activity_type):
    """尝试从 Overpass API 获取地点"""
    try:
        query = f"[out:json];node[amenity={activity_type}](around:2000,{lat},{lon});out 5;"
        servers = [
            "https://overpass-api.de/api/interpreter",
        ]
        for server in servers:
            try:
                response = requests.get(
                    server,
                    params={"data": query},
                    headers={"User-Agent": "WeatherGo/1.0", "Accept": "*/*"},
                    timeout=10
                )
                if response.status_code == 200 and response.text:
                    data = response.json()
                    places = []
                    for element in data.get("elements", []):
                        tags = element.get("tags", {})
                        name = tags.get("name") or tags.get("addr:street") or "Unknown place"
                        places.append(name)
                    if places:
                        print(f"✅ Overpass success via {server}")
                        return places
            except Exception as e:
                print(f"Overpass {server} error: {e}")
                continue
    except Exception as e:
        print("Overpass error:", e)
    return None

# 映射 amenity 类型到 Geoapify 分类
GEOAPIFY_CATEGORY_MAP = {
    "cafe":        "catering.cafe",
    "restaurant":  "catering.restaurant",
    "park":        "leisure.park",
    "library":     "education.library",
    "supermarket": "commercial.supermarket",
    "gym":         "sport.fitness",
    "fitness_centre": "sport.fitness",
    "hospital":    "healthcare.hospital",
    "pharmacy":    "healthcare.pharmacy",
    "school":      "education.school",
    "cinema":      "entertainment.cinema",
}

def get_places_geoapify(lat, lon, activity_type):
    """从 Geoapify 获取地点（备用）"""
    try:
        category = GEOAPIFY_CATEGORY_MAP.get(activity_type, "catering.restaurant")
        url = "https://api.geoapify.com/v2/places"
        params = {
            "categories": category,
            "filter": f"circle:{lon},{lat},2000",
            "limit": 5,
            "apiKey": GEO_KEY,
        }
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        features = response.json().get("features", [])
        places = []
        for f in features:
            name = f.get("properties", {}).get("name")
            if name and name not in places:
                places.append(name)
        if places:
            print("✅ Geoapify fallback success")
        return places
    except Exception as e:
        print("Geoapify error:", e)
        return []

def get_places(lat, lon, activity_type):
    """先尝试 Overpass，失败则切换到 Geoapify"""
    print("🔍 尝试 Overpass...")
    places = get_places_overpass(lat, lon, activity_type)
    if places:
        return places

    print("⚠️ Overpass 无结果，切换到 Geoapify...")
    return get_places_geoapify(lat, lon, activity_type)

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