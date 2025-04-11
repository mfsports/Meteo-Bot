import requests
import os
from flask import Flask, request
from datetime import datetime, timedelta
import statistics

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# === Envoi de message Telegram
def send_telegram_message(chat_id, message, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# === Bouton principal (uniquement la localisation)
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "📍 Localisation", "request_location": True}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# === Conversion degrés -> points cardinaux
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

# === Conseil cycliste : inverse du vent dominant
def reco_direction(avg_deg):
    reversed_deg = (avg_deg + 180) % 360
    return degrees_to_cardinal(reversed_deg)

# === Météo par coordonnées
def get_forecast_by_coords(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    if "list" not in data:
        return "❌ Erreur météo à cet endroit."

    now = datetime.utcnow()
    end_time = now + timedelta(hours=6)

    hourly_data = []
    for item in data["list"]:
        dt = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        if now < dt <= end_time:
            hourly_data.append(item)
        if len(hourly_data) >= 6:
            break

    if not hourly_data:
        return "❌ Impossible de récupérer les prévisions horaires."

    # Météo actuelle
    current = hourly_data[0]
    temp_now = round(current["main"]["temp"])
    desc_now = current["weather"][0]["description"]
    forecast = f"🌤️ Météo actuelle : {temp_now}°C, {desc_now}\n\n"

    forecast += "⏳ Prévisions sur 6h :\n"
    wind_degrees = []
    pluie_detectee = False

    for item in hourly_data:
        heure = item["dt_txt"][11:16]
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_deg = item["wind"]["deg"]
        pluie = item.get("rain", {}).get("3h", 0)

        wind_degrees.append(wind_deg)
        direction = degrees_to_cardinal(wind_deg)

        line = f"- {heure} : {temp}°C, vent {wind_speed} km/h venant du {direction}"
        if pluie > 0:
            line += f", pluie : {pluie} mm"
            pluie_detectee = True
        else:
            line += ", pas de pluie"
        forecast += line + "\n"

    # Conseil cycliste
    if wind_degrees:
        avg_deg = statistics.mean(wind_degrees)
        conseil = reco_direction(avg_deg)
        forecast += f"\n🚴 Conseil : pars vers le **{conseil}** pour rentrer avec le vent dans le dos 💨"

    if not pluie_detectee:
        forecast += "\n✅ Aucune pluie prévue sur les 6 prochaines heures"

    return forecast

# === Webhook Telegram
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]

    if "location" in data["message"]:
        lat = data["message"]["location"]["latitude"]
        lon = data["message"]["location"]["longitude"]
        meteo = get_forecast_by_coords(lat, lon)
        send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
        return "OK", 200

    # Si l'utilisateur tape quelque chose
    if "text" in data["message"]:
        send_telegram_message(
            chat_id,
            "📍 Pour te donner la météo, j’ai besoin de ta localisation.\nAppuie sur le bouton ci-dessous 👇",
            reply_markup=get_main_keyboard()
        )
        return "OK", 200

    return "OK", 200

if __name__ == "__main__":
    app.run()
