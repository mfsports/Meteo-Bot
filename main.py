import os
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

# Configurations
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# --- Fonctions Utiles ---
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 
                  'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    return directions[round((deg % 360) / 45) % 8]

def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# --- Clavier
def get_location_keyboard():
    return {
        "keyboard": [[{"text": "📍 Envoyer ma position", "request_location": True}]],
        "resize_keyboard": True
    }

# --- Météo ---
def get_weather(lat, lon):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
        response = requests.get(url)
        data = response.json()

        if data.get("cod") != 200:
            return "❌ Erreur : " + data.get("message", "Impossible d'obtenir la météo.")

        temp = round(data["main"]["temp"])
        desc = data["weather"][0]["description"].capitalize()
        wind_speed = round(data["wind"]["speed"] * 3.6)
        wind_dir = degrees_to_cardinal(data["wind"]["deg"])

        message = (
            f"🌤️ *Météo actuelle à ta position*\n"
            f"• {temp}°C, {desc}\n"
            f"• Vent : {wind_speed} km/h ({wind_dir})\n\n"
            f"🚴 *Conseil* : Pars vers le **{wind_dir}** pour revenir avec le vent dans le dos ! 💨"
        )
        return message

    except:
        return "❌ Erreur lors de la récupération des données météo."

# --- Webhook ---
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]

    # Si l'utilisateur envoie sa position
    if "location" in data["message"]:
        lat = data["message"]["location"]["latitude"]
        lon = data["message"]["location"]["longitude"]
        weather = get_weather(lat, lon)
        send_telegram_message(chat_id, weather, reply_markup=get_location_keyboard())
        return jsonify({"status": "ok"}), 200

    # Si l'utilisateur envoie un message texte
    send_telegram_message(
        chat_id,
        "👋 Bonjour cycliste ! Pour obtenir la météo, envoie-moi simplement ta *localisation* via le bouton ci-dessous 👇",
        reply_markup=get_location_keyboard()
    )
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
