import requests
import os
from flask import Flask, request
import datetime

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

user_state = {}

# === Send Telegram message ===
def send_telegram_message(chat_id, message, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# === Keyboards ===
def get_start_button():
    return {"keyboard": [[{"text": "🚴 Démarrer"}]], "resize_keyboard": True, "one_time_keyboard": True}

def get_options_keyboard():
    return {
        "keyboard": [
            [{"text": "📍 Localisation", "request_location": True}],
            [{"text": "🌆 Ville"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

def get_terminate_keyboard():
    return {"keyboard": [[{"text": "✅ Terminer"}]], "resize_keyboard": True, "one_time_keyboard": True}

# === Wind Direction ===
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

def reco_direction(deg):
    opp_deg = (deg + 180) % 360
    return degrees_to_cardinal(opp_deg)

# === Forecast ===
def build_forecast_message(data, label):
    now = data["list"][0]
    now_temp = round(now["main"]["temp"])
    now_desc = now["weather"][0]["description"]

    msg = f"{label} {now_temp}°C, {now_desc}\n\n"
    msg += "⏳ Prévisions sur 6h :\n"

    current_time = datetime.datetime.now()
    wind_dir_deg = None
    pluie_detectee = False

    for item in data["list"]:
        forecast_time = datetime.datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        if current_time < forecast_time <= current_time + datetime.timedelta(hours=6):
            time = forecast_time.strftime("%H:%M")
            temp = round(item["main"]["temp"])
            wind = item["wind"]
            wind_speed = round(wind["speed"])
            wind_gust = round(wind.get("gust", 0))
            wind_dir_deg = wind["deg"]
            wind_dir = degrees_to_cardinal(wind_dir_deg)
            pluie = item.get("rain", {}).get("3h", 0)
            if pluie > 0:
                pluie_detectee = True
            msg += f"- {time} : {temp}°C, vent {wind_speed} km/h (rafales {wind_gust} km/h) venant du {wind_dir}"
            msg += f", pluie : {pluie} mm\n" if pluie > 0 else ", pas de pluie\n"

    if wind_dir_deg is not None:
        reco = reco_direction(wind_dir_deg)
        msg += f"\n🚴 Conseil : pars vers le **{reco}** pour rentrer avec le vent dans le dos ! 💩"

    if not pluie_detectee:
        msg += "\n✅ Aucune pluie prévue sur les 6 prochaines heures"

    return msg

# === Webhook ===
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]
    message = data["message"]

    if "location" in message:
        lat = message["location"]["latitude"]
        lon = message["location"]["longitude"]
        url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
        response = requests.get(url).json()
        if "list" in response:
            msg = build_forecast_message(response, "📍 Météo actuelle :")
            send_telegram_message(chat_id, msg, reply_markup=get_terminate_keyboard())
        else:
            send_telegram_message(chat_id, "❌ Erreur pour obtenir la météo de votre position.", reply_markup=get_terminate_keyboard())
        return "OK", 200

    if "text" in message:
        text = message["text"]

        if user_state.get(chat_id) == "awaiting_city":
            url = f"http://api.openweathermap.org/data/2.5/forecast?q={text}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
            response = requests.get(url).json()
            if "list" in response:
                msg = build_forecast_message(response, f"🌆 Météo à {text} :")
                send_telegram_message(chat_id, msg, reply_markup=get_terminate_keyboard())
            else:
                send_telegram_message(chat_id, "❌ Ville introuvable. Essaie de corriger le nom.")
            user_state.pop(chat_id, None)
            return "OK", 200

        if text == "🚴 Démarrer":
            send_telegram_message(chat_id, "🚀 Choisis une option ci-dessous :", reply_markup=get_options_keyboard())
        elif text == "🌆 Ville":
            user_state[chat_id] = "awaiting_city"
            send_telegram_message(chat_id, "🗺️ Quelle ville veux-tu consulter ?")
        elif text == "✅ Terminer":
            send_telegram_message(chat_id, "🛌 Bot en pause. Envoie un message pour recommencer.", reply_markup=get_start_button())
        else:
            send_telegram_message(chat_id, "📅 Salut cycliste ! Clique sur « Démarrer » pour consulter la météo.", reply_markup=get_start_button())

    return "OK", 200

if __name__ == "__main__":
    app.run()
