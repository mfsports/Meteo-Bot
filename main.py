import requests
import os
from flask import Flask, request
import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

user_state = {}

# === Fonctions de base ===

def send_telegram_message(chat_id, message, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    requests.post(url, json=payload)

def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

# Pas d’inversion ici ! On part dans le sens du vent pour rentrer avec le vent dans le dos
def reco_direction(deg):
    return degrees_to_cardinal(deg)

def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "📍 Localisation", "request_location": True}],
            [{"text": "🔍 Ville"}],
            [{"text": "❌ Terminé"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# === Prévisions météo (coordonnées ou ville) ===

def build_forecast(data, location_name):
    now = data["list"][0]
    now_temp = round(now["main"]["temp"])
    now_desc = now["weather"][0]["description"]

    forecast_message = f"🌤️ Météo à {location_name} : {now_temp}°C, {now_desc}\n\n"
    forecast_message += "⏳ Prévisions sur 6 prochaines heures :\n"

    pluie_detectee = False
    wind_dir_deg = None
    current_time = datetime.datetime.now()

    for item in data["list"]:
        forecast_time = datetime.datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        if current_time < forecast_time <= current_time + datetime.timedelta(hours=6):
            hour = forecast_time.strftime("%H:%M")
            temp = round(item["main"]["temp"])
            wind_speed = round(item["wind"]["speed"])
            gust = round(item["wind"].get("gust", 0))
            wind_dir_deg = item["wind"]["deg"]
            wind_dir = degrees_to_cardinal(wind_dir_deg)
            pluie = item.get("rain", {}).get("3h", 0)
            if pluie > 0:
                pluie_detectee = True

            forecast_message += (
                f"- {hour} : {temp}°C, vent {wind_speed} km/h "
                f"(rafales {gust} km/h) venant du {wind_dir}"
            )
            forecast_message += f", pluie : {pluie} mm\n" if pluie > 0 else ", pas de pluie\n"

    if wind_dir_deg:
        reco = reco_direction(wind_dir_deg)
        forecast_message += f"\n🚴 Conseil : pars vers le **{reco}** pour rentrer avec le vent dans le dos 💨"

    if not pluie_detectee:
        forecast_message += "\n✅ Aucune pluie prévue sur les 6 prochaines heures"

    return forecast_message

def get_forecast_by_coords(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()
    if "list" not in data:
        return "❌ Erreur météo à cet endroit."
    return build_forecast(data, "ta position")

def get_forecast_by_city(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()
    if "list" not in data:
        return None
    return build_forecast(data, city.capitalize())

# === Webhook principal ===

@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    message = data.get("message")
    if not message:
        return "OK"

    chat_id = message["chat"]["id"]

    # --- Localisation
    if "location" in message:
        lat = message["location"]["latitude"]
        lon = message["location"]["longitude"]
        meteo = get_forecast_by_coords(lat, lon)
        send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
        return "OK"

    # --- Texte
    if "text" in message:
        text = message["text"]

        if user_state.get(chat_id) == "awaiting_city":
            forecast = get_forecast_by_city(text)
            if forecast:
                send_telegram_message(chat_id, forecast, reply_markup=get_main_keyboard())
            else:
                send_telegram_message(chat_id, "❌ Ville introuvable. Vérifie l’orthographe et réessaie 🗺️.")
            user_state.pop(chat_id, None)
            return "OK"

        # Commandes/boutons
        if text == "/start" or text.lower() in ["salut", "bonjour", "yo"]:
            send_telegram_message(chat_id, "🚴 Bienvenue cycliste ! Clique sur Démarrer pour obtenir la météo.",
                                  reply_markup={"keyboard": [[{"text": "▶️ Démarrer"}]], "resize_keyboard": True})
        elif text == "▶️ Démarrer":
            send_telegram_message(chat_id, "📍 Choisis une option ci-dessous 👇", reply_markup=get_main_keyboard())
        elif text == "📍 Localisation":
            send_telegram_message(chat_id, "📡 Partage ta position pour obtenir les prévisions météo.")
        elif text == "🔍 Ville":
            user_state[chat_id] = "awaiting_city"
            send_telegram_message(chat_id, "🧭 Indique-moi la ville dont tu veux connaître la météo.")
        elif text == "❌ Terminé":
            send_telegram_message(chat_id, "✅ Reviens quand tu veux ! Tape /start pour recommencer.")
        else:
            send_telegram_message(chat_id, "👋 Envoie /start pour utiliser le bot météo 🚴")

    return "OK", 200

if __name__ == "__main__":
    app.run()
