from flask import Flask, jsonify, request
import requests
import os
import time
from dotenv import load_dotenv
from flask_cors import CORS

load_dotenv()

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
GEO_KEY = os.environ.get("GEO_KEY")

app = Flask(__name__)
CORS(app)

print("=== WeatherGo Backend Starting ===")
print(f"WEATHER_API_KEY set: {bool(WEATHER_API_KEY)}")
print(f"GEO_KEY set: {bool(GEO_KEY)}")
print(f"GROQ_MICROSERVICE_URL: {os.environ.get('GROQ_MICROSERVICE_URL', 'not set (default localhost:5001)')}")


def get_coordinates(location):
    try:
        print(f"[get_coordinates] Looking up: {location}")
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            "q": location,
            "format": "json",
            "limit": 1
        }
        headers = {"User-Agent": "WeatherGo/1.0 (Sifazhang.nzl@gmail.com)"}
        response = requests.get(url, params=params, headers=headers, timeout=10)
        print(f"[get_coordinates] Nominatim status: {response.status_code}")
        print(f"[get_coordinates] Nominatim response: {response.text[:200]}")
        data = response.json()
        if not data:
            print("[get_coordinates] ERROR: Empty response from Nominatim")
            return None, None
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
        print(f"[get_coordinates] SUCCESS: lat={lat}, lon={lon}")
        return lat, lon
    except Exception as e:
        print(f"[get_coordinates] EXCEPTION: {str(e)}")
        return None, None


def get_weather(lat, lon):
    try:
        print(f"[get_weather] Fetching weather for lat={lat}, lon={lon}")
        if not WEATHER_API_KEY:
            print("[get_weather] ERROR: WEATHER_API_KEY is not set")
            return None
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }
        print(f"[get_weather] Using API key starting with: {WEATHER_API_KEY[:5]}...")
        response = requests.get(url, params=params, timeout=10)
        print(f"[get_weather] OpenWeatherMap status: {response.status_code}")
        print(f"[get_weather] OpenWeatherMap response: {response.text[:200]}")
        data = response.json()
        result = {
            "status": data["weather"][0]["description"],
            "temperature": data["main"]["temp"]
        }
        print(f"[get_weather] SUCCESS: {result}")
        return result
    except Exception as e:
        print(f"[get_weather] EXCEPTION: {str(e)}")
        return None


def get_places_overpass(lat, lon, activity_type):
    """Try to get places from Overpass API"""
    try:
        print(f"[get_places_overpass] Querying for activity_type={activity_type}")
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
                print(f"[get_places_overpass] {server} status: {response.status_code}")
                if response.status_code == 200 and response.text:
                    data = response.json()
                    places = []
                    for element in data.get("elements", []):
                        tags = element.get("tags", {})
                        name = tags.get("name") or tags.get("addr:street") or "Unknown place"
                        places.append(name)
                    if places:
                        print(f"[get_places_overpass] SUCCESS via {server}: {places}")
                        return places
                    else:
                        print(f"[get_places_overpass] No elements found via {server}")
            except Exception as e:
                print(f"[get_places_overpass] {server} EXCEPTION: {e}")
                continue
    except Exception as e:
        print(f"[get_places_overpass] EXCEPTION: {e}")
    return None


GEOAPIFY_CATEGORY_MAP = {
    "cafe":           "catering.cafe",
    "restaurant":     "catering.restaurant",
    "park":           "leisure.park",
    "library":        "education.library",
    "supermarket":    "commercial.supermarket",
    "gym":            "sport.fitness",
    "fitness_centre": "sport.fitness",
    "hospital":       "healthcare.hospital",
    "pharmacy":       "healthcare.pharmacy",
    "school":         "education.school",
    "cinema":         "entertainment.cinema",
}


def get_places_geoapify(lat, lon, activity_type):
    """Get places from Geoapify (fallback)"""
    try:
        print(f"[get_places_geoapify] Querying for activity_type={activity_type}")
        if not GEO_KEY:
            print("[get_places_geoapify] ERROR: GEO_KEY is not set")
            return []
        category = GEOAPIFY_CATEGORY_MAP.get(activity_type, "catering.restaurant")
        print(f"[get_places_geoapify] Using category: {category}")
        url = "https://api.geoapify.com/v2/places"
        params = {
            "categories": category,
            "filter": f"circle:{lon},{lat},2000",
            "limit": 5,
            "apiKey": GEO_KEY,
        }
        response = requests.get(url, params=params, timeout=15)
        print(f"[get_places_geoapify] Geoapify status: {response.status_code}")
        response.raise_for_status()
        features = response.json().get("features", [])
        places = []
        for f in features:
            name = f.get("properties", {}).get("name")
            if name and name not in places:
                places.append(name)
        if places:
            print(f"[get_places_geoapify] SUCCESS: {places}")
        else:
            print("[get_places_geoapify] No places found")
        return places
    except Exception as e:
        print(f"[get_places_geoapify] EXCEPTION: {e}")
        return []


def get_places(lat, lon, activity_type):
    """Try Overpass first, fall back to Geoapify"""
    print("[get_places] Trying Overpass...")
    places = get_places_overpass(lat, lon, activity_type)
    if places:
        return places
    print("[get_places] Overpass failed, switching to Geoapify...")
    return get_places_geoapify(lat, lon, activity_type)


def get_recommendation(location, weather, places, activity_type):
    try:
        microservice_url = os.environ.get("GROQ_MICROSERVICE_URL", "http://localhost:5001/generate")
        print(f"[get_recommendation] Calling microservice at: {microservice_url}")
        payload = {
            "location": location,
            "weather": weather["status"],
            "temperature": weather["temperature"],
            "places": places,
            "activity_type": activity_type
        }
        response = requests.post(microservice_url, json=payload, timeout=10)
        print(f"[get_recommendation] Microservice status: {response.status_code}")
        if response.status_code == 200:
            result = response.json().get("recommendation")
            print(f"[get_recommendation] SUCCESS: {str(result)[:100]}")
            return result
        print(f"[get_recommendation] ERROR: non-200 response: {response.text[:200]}")
        return None
    except Exception as e:
        print(f"[get_recommendation] EXCEPTION: {str(e)}")
        return None



@app.route('/')
def index():
    return jsonify({"status": "WeatherGo API is running"})

@app.route('/routes')
def list_routes():
    routes = []
    for rule in app.url_map.iter_rules():
        routes.append({
            "endpoint": rule.endpoint,
            "methods": list(rule.methods),
            "path": rule.rule
        })
    return jsonify(routes)


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/recommend', methods=['POST'])
def recommend():
    print("=== /recommend called ===")
    data = request.get_json()
    print(f"[recommend] Request data: {data}")

    location = data.get('location')
    activity_type = data.get('activity_type')
    print(f"[recommend] location={location}, activity_type={activity_type}")

    if not location or not activity_type:
        print("[recommend] ERROR: Missing required fields")
        return jsonify({"error": "location and activity_type are required"}), 400

    print("[recommend] Step 1: Getting coordinates...")
    lat, lon = get_coordinates(location)
    if lat is None:
        print("[recommend] ERROR: Could not get coordinates")
        return jsonify({"error": "Location not recognised, please enter a more specific location"}), 404

    print("[recommend] Step 2: Getting weather...")
    weather = get_weather(lat, lon)
    if weather is None:
        print("[recommend] ERROR: Could not get weather")
        return jsonify({"error": "Weather service is temporarily unavailable, please try again later"}), 503

    print("[recommend] Step 3: Getting places...")
    places = get_places(lat, lon, activity_type)
    if not places:
        print("[recommend] ERROR: No places found")
        return jsonify({"error": "No relevant places found nearby"}), 404

    print("[recommend] Step 4: Getting recommendation...")
    recommendation = get_recommendation(location, weather, places, activity_type)

    print("=== /recommend SUCCESS ===")
    return jsonify({
        "location": location,
        "weather": weather,
        "places": places,
        "recommendation": recommendation
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)