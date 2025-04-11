import requests
import os
from flask import Flask, request

app = Flask(__name__)

# Variables d'environnement
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Ville par défaut
current_city = "Paris"

# === Envoie un message Telegram ===
def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

# === Convertit degrés en direction cardinal ===
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

# === Recommande la direction pour partir (même que celle du vent) ===
def reco_direction(deg):
    return degrees_to_cardinal(deg)  # On part dans la direction d'où vient le vent

# === Récupère la météo sur 6 heures + conseil cycliste ===
def get_forecast(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    if "list" not in data:
        return f"❌ Impossible de récupérer les prévisions météo pour {city}. Réponse API : {data}"

    forecast_message = f"🌤️ Météo à {city} pour les 6 prochaines heures :\n"
    wind_dir_deg = None

    for item in data["list"][:2]:  # ≈ 6 heures
        time = item["dt_txt"][11:16]
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_dir_deg = item["wind"]["deg"]
        wind_dir = degrees_to_cardinal(wind_dir_deg)

        forecast_message += f"- {time} : 🌡️ {temp}°C, 💨 vent {wind_speed} km/h venant du {wind_dir}\n"

    if wind_dir_deg is not None:
        reco = reco_direction(wind_dir_deg)
        forecast_message += f"\n🚴‍♂️ Conseil cycliste : pars vers le **{reco}** pour rentrer avec le vent dans le dos ! 💪"

    return forecast_message

# === Webhook pour Telegram ===
@app.route("/", methods=["POST"])
def webhook():
    global current_city
    data = request.json

    if "message" in data:
        message_text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]

        if message_text.startswith("/ville "):
            new_city = message_text.split("/ville ")[1]
            current_city = new_city
            send_telegram_message(chat_id, f"📍 Ville mise à jour : {new_city}")

        elif message_text == "/meteo":
            forecast = get_forecast(current_city)
            send_telegram_message(chat_id, forecast)

        elif message_text == "/pluie":
            forecast = get_forecast(current_city)
            if "🌧️" in forecast:
                send_telegram_message(chat_id, forecast)
            else:
                send_telegram_message(chat_id, "✅ Pas de pluie prévue pour le moment.")

        else:
            send_telegram_message(chat_id,
                "🤖 Comment puis-je t'aider ?\n"
                "/pluie pour savoir s’il va pleuvoir\n"
                "/meteo pour connaître les 6 prochaines heures\n"
                "/ville pour changer de localisation"
            )

    return "OK", 200

# === Lancement local (debug uniquement) ===
if __name__ == "__main__":
    app.run()
