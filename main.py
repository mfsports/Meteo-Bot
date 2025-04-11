import requests
import os
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# === Envoie un message texte
def send_telegram_message(chat_id, message, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# === Boutons Telegram
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "📍 Localisation", "request_location": True}],
            [{"text": "🌧️ Pluie"}, {"text": "⏳ Prévisions 6h"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# === Direction du vent cardinal
def degrees_to_cardinal(deg):
    dirs = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return dirs[ix]

# === Conseil cycliste : partir face au vent pour revenir avec dans le dos
def reco_direction(deg):
    return degrees_to_cardinal(deg)

# === Récupère la météo via coordonnées
def get_forecast_by_coords(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    if "list" not in data:
        return "❌ Impossible de récupérer la météo à cet endroit."

    forecast_message = f"🌤️ Météo pour les 6 prochaines heures :\n"
    wind_dir_deg = None

    for item in data["list"][:2]:  # ≈ 6h
        time = item["dt_txt"][11:16]
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_dir_deg = item["wind"]["deg"]
        wind_dir = degrees_to_cardinal(wind_dir_deg)
        forecast_message += f"- {time} : 🌡️ {temp}°C, 💨 {wind_speed} km/h venant du {wind_dir}\n"

    if wind_dir_deg:
        reco = reco_direction(wind_dir_deg)
        forecast_message += f"\n🚴‍♂️ Conseil cycliste : pars vers le **{reco}** pour rentrer avec le vent dans le dos ! 💪"

    return forecast_message

# === Route principale webhook
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]

    # --- GPS envoyé
    if "location" in data["message"]:
        lat = data["message"]["location"]["latitude"]
        lon = data["message"]["location"]["longitude"]
        forecast = get_forecast_by_coords(lat, lon)
        send_telegram_message(chat_id, forecast, reply_markup=get_main_keyboard())
        return "OK", 200

    # --- Texte envoyé
    if "text" in data["message"]:
        message_text = data["message"]["text"]

        if message_text == "/start":
            send_telegram_message(
                chat_id,
                "🤖 Salut ! Comment puis-je t'aider ?\n"
                "/pluie pour savoir s’il va pleuvoir\n"
                "/meteo pour les prévisions 6h\n"
                "Ou utilise les boutons ci-dessous 👇",
                reply_markup=get_main_keyboard()
            )

        elif message_text in ["/meteo", "⏳ Prévisions 6h"]:
            send_telegram_message(chat_id, "📍 Envoie ta localisation pour une météo précise !", reply_markup=get_main_keyboard())

        elif message_text in ["/pluie", "🌧️ Pluie"]:
            send_telegram_message(chat_id, "📍 Envoie ta localisation pour voir s’il va pleuvoir !", reply_markup=get_main_keyboard())

        else:
            send_telegram_message(
                chat_id,
                "🤖 Commande inconnue. Utilise les boutons ou tape :\n"
                "/pluie\n/meteo\n/start",
                reply_markup=get_main_keyboard()
            )

    return "OK", 200

if __name__ == "__main__":
    app.run()
