from flask import Flask, jsonify, request

app = Flask(__name__)

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

    return jsonify({
        "location": location,
        "activity_type": activity_type,
        "weather": None,
        "places": [],
        "recommendation": None
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)