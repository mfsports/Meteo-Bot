import os
import logging
from urllib.parse import quote
import requests
from flask import Flask, request, jsonify

# Configuration initiale
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Variables d'environnement
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Mémoire utilisateur (à remplacer par une DB en production)
user_state = {}

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def send_telegram_message(chat_id: int, text: str, reply_markup: dict = None) -> bool:
    """Envoie un message via l'API Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur d'envoi Telegram: {e}")
        return False

def degrees_to_cardinal(deg: float) -> str:
    """Convertit des degrés en direction cardinale (ex: 90 → 'est')."""
    directions = ['nord', 'nord-est', 'est', 'sud-est', 
                 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    return directions[round((deg % 360) / 45) % 8]

def get_wind_advice(wind_deg: float) -> str:
    """Retourne un conseil cycliste basé sur la direction du vent."""
    return degrees_to_cardinal((wind_deg + 180) % 360)

def get_main_keyboard() -> dict:
    """Génère le clavier Telegram avec bouton de localisation."""
    return {
        "keyboard": [
            [{"text": "📍 Localisation", "request_location": True}],
            [{"text": "🔄 Actualiser"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# -------------------------------------------------------------------
# Météo
# -------------------------------------------------------------------
def fetch_weather_data(url: str) -> dict:
    """Récupère les données météo avec gestion des erreurs."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Erreur API Météo: {e}")
        return None

def format_forecast(data: dict, location_name: str = None) -> str:
    """Formate les données météo en message lisible."""
    if not data or "list" not in data:
        return "❌ Données météo indisponibles."

    current = data["list"][0]
    forecast_msg = [
        f"🌦 **Météo {'à ' + location_name if location_name else 'actuelle'}**",
        f"➡️ {current['weather'][0]['description'].capitalize()}, {round(current['main']['temp'])}°C",
        "\n⏳ **Prévisions 6h** :"
    ]

    rain_detected = False
    wind_dir = None

    for entry in data["list"][:2]:
        time = entry["dt_txt"][11:16]
        temp = round(entry["main"]["temp"])
        wind_speed = round(entry["wind"]["speed"])
        wind_dir = entry["wind"]["deg"]
        rain = entry.get("rain", {}).get("3h", 0)
        
        forecast_msg.append(
            f"- {time} : {temp}°C, vent {wind_speed} km/h ({degrees_to_cardinal(wind_dir)})"
            f"{f', pluie : {rain} mm' if rain > 0 else ''}"
        )
        if rain > 0:
            rain_detected = True

    if wind_dir:
        forecast_msg.append(
            f"\n🚴 **Conseil** : Partez vers le {get_wind_advice(wind_dir)} "
            "pour avoir le vent dans le dos !"
        )

    if not rain_detected:
        forecast_msg.append("\n✅ Pas de pluie prévue dans les 6h")

    return "\n".join(forecast_msg)

def get_forecast_by_coords(lat: float, lon: float) -> str:
    """Récupère la météo par coordonnées GPS."""
    url = (
        f"http://api.openweathermap.org/data/2.5/forecast?"
        f"lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
        f"&units=metric&lang=fr"
    )
    data = fetch_weather_data(url)
    return format_forecast(data)

def get_forecast_by_city(city: str) -> str:
    """Récupère la météo par nom de ville."""
    url = (
        f"http://api.openweathermap.org/data/2.5/forecast?"
        f"q={quote(city)}&appid={OPENWEATHER_API_KEY}"
        f"&units=metric&lang=fr"
    )
    data = fetch_weather_data(url)
    return format_forecast(data, city)

# -------------------------------------------------------------------
# Webhook
# -------------------------------------------------------------------
@app.route("/", methods=["POST"])
def webhook():
    """Endpoint principal pour les webhooks Telegram."""
    if request.headers.get("X-Telegram-Bot-Api-Secret-Token") != os.getenv("WEBHOOK_SECRET"):
        return jsonify({"status": "unauthorized"}), 403

    try:
        data = request.get_json()
        chat_id = data["message"]["chat"]["id"]
        message = data["message"]

        # Gestion localisation
        if "location" in message:
            forecast = get_forecast_by_coords(
                message["location"]["latitude"],
                message["location"]["longitude"]
            )
            send_telegram_message(chat_id, forecast, get_main_keyboard())

        # Gestion texte
        elif "text" in message:
            text = message["text"].strip()
            
            if text == "/start":
                user_state[chat_id] = "ready"
                send_telegram_message(
                    chat_id,
                    "🚴 **Bienvenue !** Envoyez votre position ou un nom de ville.",
                    get_main_keyboard()
                )
            elif text == "🔄 Actualiser":
                send_telegram_message(
                    chat_id,
                    "🔄 Actualisation... Envoyez à nouveau votre position.",
                    get_main_keyboard()
                )
            else:
                forecast = get_forecast_by_city(text)
                send_telegram_message(chat_id, forecast, get_main_keyboard())

    except Exception as e:
        logger.error(f"Erreur webhook: {e}")
        return jsonify({"status": "error"}), 500

    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
