from flask import Flask, jsonify, request
import requests

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

    return jsonify({
        "location": location,
        "coordinates": {"lat": lat, "lon": lon},
        "weather": None,
        "places": [],
        "recommendation": None
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)