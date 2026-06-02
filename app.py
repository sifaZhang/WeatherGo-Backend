from flask import Flask, jsonify, request
import requests
import os
import time
from dotenv import load_dotenv
from flask_cors import CORS
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stdout,
    format="%(asctime)s %(levelname)s %(message)s",
    force=True
)

logger = logging.getLogger(__name__)

load_dotenv()

WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY")
GEO_KEY = os.environ.get("GEO_KEY")

app = Flask(__name__)
CORS(app)

logger.info("=== WeatherGo Backend Starting ===")
logger.info(f"WEATHER_API_KEY set: {bool(WEATHER_API_KEY)}")
logger.info(f"GEO_KEY set: {bool(GEO_KEY)}")
logger.info(f"GROQ_MICROSERVICE_URL: {os.environ.get('GROQ_MICROSERVICE_URL', 'not set (default localhost:5001)')}")


def get_coordinates(location):
    """Get coordinates using Geoapify Geocoding API"""
    try:
        logger.info(f"[get_coordinates] Looking up: {location}")
        if not GEO_KEY:
            logger.info("[get_coordinates] ERROR: GEO_KEY is not set")
            return None, None
        url = "https://api.geoapify.com/v1/geocode/search"
        params = {
            "text": location,
            "limit": 1,
            "apiKey": GEO_KEY
        }
        response = requests.get(url, params=params, timeout=10)
        logger.info(f"[get_coordinates] STATUS={response.status_code}")
        logger.info(f"[get_coordinates] BODY={response.text[:500]}")
        data = response.json()
        features = data.get("features", [])
        if not features:
            logger.info("[get_coordinates] ERROR: Empty response, location not found")
            return None, None
        lon = float(features[0]["geometry"]["coordinates"][0])
        lat = float(features[0]["geometry"]["coordinates"][1])
        logger.info(f"[get_coordinates] SUCCESS: lat={lat}, lon={lon}")
        return lat, lon
    except Exception as e:
        logger.exception(f"[get_coordinates] EXCEPTION: {str(e)}")
        return None, None


def get_weather(lat, lon):
    try:
        logger.info(f"[get_weather] Fetching weather for lat={lat}, lon={lon}")
        if not WEATHER_API_KEY:
            logger.info("[get_weather] ERROR: WEATHER_API_KEY is not set")
            return None
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat,
            "lon": lon,
            "appid": WEATHER_API_KEY,
            "units": "metric"
        }
        logger.info(f"[get_weather] Using API key starting with: {WEATHER_API_KEY[:5]}...")
        response = requests.get(url, params=params, timeout=10)
        logger.info(f"[get_weather] OpenWeatherMap status: {response.status_code}")
        logger.info(f"[get_weather] OpenWeatherMap response: {response.text[:200]}")
        data = response.json()
        result = {
            "status": data["weather"][0]["description"],
            "temperature": data["main"]["temp"]
        }
        logger.info(f"[get_weather] SUCCESS: {result}")
        return result
    except Exception as e:
        logger.exception(f"[get_weather] EXCEPTION: {str(e)}")
        return None


def get_places_overpass(lat, lon, activity_type):
    """Try to get places from Overpass API"""
    try:
        logger.info(f"[get_places_overpass] Querying for activity_type={activity_type}")
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
                logger.info(f"[get_places_overpass] {server} status: {response.status_code}")
                if response.status_code == 200 and response.text:
                    data = response.json()
                    places = []
                    for element in data.get("elements", []):
                        tags = element.get("tags", {})
                        name = tags.get("name") or tags.get("addr:street") or "Unknown place"
                        places.append(name)
                    if places:
                        logger.info(f"[get_places_overpass] SUCCESS via {server}: {places}")
                        return places
                    else:
                        logger.info(f"[get_places_overpass] No elements found via {server}")
            except Exception as e:
                logger.exception(f"[get_places_overpass] {server} EXCEPTION: {e}")
                continue
    except Exception as e:
        logger.exception(f"[get_places_overpass] EXCEPTION: {e}")
    return None


GEOAPIFY_CATEGORY_MAP = {
    # 餐饮
    "cafe":           "catering.cafe",
    "restaurant":     "catering.restaurant",
    "bar":            "catering.bar",
    "fast_food":      "catering.fast_food",
    # 休闲
    "park":           "leisure.park",
    "playground":     "leisure.playground",
    "cinema":         "entertainment.cinema",
    "theatre":        "entertainment.theatre",
    # 运动
    "gym":            "sport.fitness",
    "fitness_centre": "sport.fitness",
    "swimming_pool":  "sport.swimming",
    # 购物
    "supermarket":    "commercial.supermarket",
    "shopping_mall":  "commercial.shopping_mall",
    # 教育
    "library":        "education.library",
    "school":         "education.school",
    "university":     "education.university",
    # 医疗
    "hospital":       "healthcare.hospital",
    "pharmacy":       "healthcare.pharmacy",
    "clinic":         "healthcare.clinic",
}


def get_places_geoapify(lat, lon, activity_type):
    """Get places from Geoapify (fallback)"""
    try:
        logger.info(f"[get_places_geoapify] Querying for activity_type={activity_type}")
        if not GEO_KEY:
            logger.info("[get_places_geoapify] ERROR: GEO_KEY is not set")
            return []
        category = GEOAPIFY_CATEGORY_MAP.get(activity_type)
        if not category:
            logger.info(f"[get_places_geoapify] Unknown activity_type: {activity_type}")
            return []
        logger.info(f"[get_places_geoapify] Using category: {category}")
        url = "https://api.geoapify.com/v2/places"
        params = {
            "categories": category,
            "filter": f"circle:{lon},{lat},2000",
            "limit": 5,
            "apiKey": GEO_KEY,
        }
        response = requests.get(url, params=params, timeout=15)
        logger.info(f"[get_places_geoapify] Geoapify status: {response.status_code}")
        response.raise_for_status()
        features = response.json().get("features", [])
        places = []
        for f in features:
            name = f.get("properties", {}).get("name")
            if name and name not in places:
                places.append(name)
        if places:
            logger.info(f"[get_places_geoapify] SUCCESS: {places}")
        else:
            logger.info("[get_places_geoapify] No places found")
        return places
    except Exception as e:
        logger.exception(f"[get_places_geoapify] EXCEPTION: {e}")
        return []


def get_places(lat, lon, activity_type):
    """Try Overpass first, fall back to Geoapify"""
    logger.info("[get_places] Trying Overpass...")
    places = get_places_overpass(lat, lon, activity_type)
    if places:
        return places
    logger.info("[get_places] Overpass failed, switching to Geoapify...")
    return get_places_geoapify(lat, lon, activity_type)


def get_recommendation(location, weather, places, activity_type):
    try:
        microservice_url = os.environ.get("GROQ_MICROSERVICE_URL", "http://localhost:5001/generate")
        logger.info(f"[get_recommendation] Calling microservice at: {microservice_url}")
        payload = {
            "location": location,
            "weather": weather["status"],
            "temperature": weather["temperature"],
            "places": places,
            "activity_type": activity_type
        }
        response = requests.post(microservice_url, json=payload, timeout=10)
        logger.info(f"[get_recommendation] Microservice status: {response.status_code}")
        if response.status_code == 200:
            result = response.json().get("recommendation")
            logger.info(f"[get_recommendation] SUCCESS: {str(result)[:100]}")
            return result
        logger.info(f"[get_recommendation] ERROR: non-200 response: {response.text[:200]}")
        return None
    except Exception as e:
        logger.exception(f"[get_recommendation] EXCEPTION: {str(e)}")
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


@app.route('/test_geo')
def test_geo():
    lat, lon = get_coordinates("Unitec, Mt Albert")
    return jsonify({"lat": lat, "lon": lon})


@app.route('/health')
def health():
    return jsonify({"status": "ok"})


@app.route('/recommend', methods=['POST'])
def recommend():
    logger.info("=== /recommend called ===")
    data = request.get_json()
    logger.info(f"[recommend] Request data: {data}")

    location = data.get('location')
    activity_type = data.get('activity_type')
    logger.info(f"[recommend] location={location}, activity_type={activity_type}")

    if not location or not activity_type:
        logger.info("[recommend] ERROR: Missing required fields")
        return jsonify({"error": "location and activity_type are required"}), 400

    logger.info("[recommend] Step 1: Getting coordinates...")
    lat, lon = get_coordinates(location)
    if lat is None:
        logger.info("[recommend] ERROR: Could not get coordinates")
        return jsonify({"error": "Location not recognised, please enter a more specific location"}), 404

    logger.info("[recommend] Step 2: Getting weather...")
    weather = get_weather(lat, lon)
    if weather is None:
        logger.info("[recommend] ERROR: Could not get weather")
        return jsonify({"error": "Weather service is temporarily unavailable, please try again later"}), 503

    logger.info("[recommend] Step 3: Getting places...")
    places = get_places(lat, lon, activity_type)
    if not places:
        logger.info("[recommend] ERROR: No places found")
        return jsonify({"error": "No relevant places found nearby"}), 404

    logger.info("[recommend] Step 4: Getting recommendation...")
    recommendation = get_recommendation(location, weather, places, activity_type)

    logger.info("=== /recommend SUCCESS ===")
    return jsonify({
        "location": location,
        "weather": weather,
        "places": places,
        "recommendation": recommendation
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)