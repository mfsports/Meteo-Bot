import os
import requests
from flask import Flask, request
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# === Mémoire utilisateur
user_state = {}

# === Envoyer un message Telegram ===
def send_telegram_message(chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# === Boutons clavier ===
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "\ud83d\udccd Localisation", "request_location": True}],
            [{"text": "\ud83d\udd0d Ville"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def get_done_keyboard():
    return {
        "keyboard": [[{"text": "\u2705 Terminé"}]],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

# === Utilitaires ===
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

def reco_direction(deg):
    return degrees_to_cardinal(deg + 180)

# === Traitement Météo ===
def format_forecast(data):
    now = datetime.utcnow()
    hourly_data = []
    for item in data["list"]:
        dt = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        if dt > now:
            hourly_data.append(item)
        if len(hourly_data) == 3:
            break

    now_temp = round(data["list"][0]["main"]["temp"])
    now_desc = data["list"][0]["weather"][0]["description"]
    forecast = f"\ud83c\udf24\ufe0f Météo actuelle : {now_temp}°C, {now_desc}\n\n"
    forecast += "\u23f3 Prévisions sur 6h :\n"
    pluie = False
    wind_dir = None

    for item in hourly_data:
        time = item["dt_txt"][11:16]
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_deg = item["wind"]["deg"]
        wind_dir = degrees_to_cardinal(wind_deg)
        rain = item.get("rain", {}).get("3h", 0)
        if rain > 0:
            pluie = True
        forecast += f"- {time} : {temp}°C, vent {wind_speed} km/h venant du {wind_dir}"
        forecast += f", pluie : {rain} mm\n" if rain else ", pas de pluie\n"

    if wind_dir:
        reco = reco_direction(item["wind"]["deg"])
        forecast += f"\n\ud83d\udeb4 Conseil : pars vers le **{reco}** pour rentrer avec le vent dans le dos \ud83d\udca8\n"
    if not pluie:
        forecast += "\n\u2705 Aucune pluie prévue sur les 6 prochaines heures"

    return forecast

# === Requêtes Météo ===
def get_forecast_by_coords(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    r = requests.get(url).json()
    if "list" not in r:
        return "\u274c Erreur lors de la récupération de la météo."
    return format_forecast(r)

def get_forecast_by_city(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    r = requests.get(url).json()
    if "list" not in r:
        return None
    return format_forecast(r)

# === Webhook ===
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]

    if "location" in data["message"]:
        lat = data["message"]["location"]["latitude"]
        lon = data["message"]["location"]["longitude"]
        forecast = get_forecast_by_coords(lat, lon)
        send_telegram_message(chat_id, forecast, reply_markup=get_done_keyboard())
        user_state[chat_id] = "done"
        return "OK"

    if "text" in data["message"]:
        text = data["message"]["text"].strip()
        state = user_state.get(chat_id)

        if text == "/start" or state is None or state == "paused":
            user_state[chat_id] = "awaiting_choice"
            send_telegram_message(chat_id, "\ud83e\udd16 Bonjour ! Choisis une option pour commencer :", reply_markup=get_main_keyboard())
            return "OK"

        if state == "awaiting_city":
            forecast = get_forecast_by_city(text)
            if forecast:
                send_telegram_message(chat_id, forecast, reply_markup=get_done_keyboard())
                user_state[chat_id] = "done"
            else:
                send_telegram_message(chat_id, "\u274c Ville introuvable. Essaie encore.")
            return "OK"

        if text == "\ud83d\udd0d Ville":
            user_state[chat_id] = "awaiting_city"
            send_telegram_message(chat_id, "\ud83c\udf0d Indique une ville :")
            return "OK"

        if text == "\u2705 Terminé":
            user_state[chat_id] = "paused"
            send_telegram_message(chat_id, "\ud83d\udecc Bot en pause. Tape /start pour relancer.")
            return "OK"

        if state == "awaiting_choice":
            send_telegram_message(chat_id, "\u2753 Choisis une option ci-dessous :", reply_markup=get_main_keyboard())
            return "OK"

        # Si rien ne correspond
        send_telegram_message(chat_id, "\ud83d\udecc Dis-moi par où commencer :", reply_markup=get_main_keyboard())

    return "OK"

if __name__ == "__main__":
    app.run()
