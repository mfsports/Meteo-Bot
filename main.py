import requests
import os
from flask import Flask, request
from datetime import datetime, timedelta

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Mémoire temporaire
user_state = {}

# === Telegram : envoi de message
def send_telegram_message(chat_id, message, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "reply_markup": reply_markup,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

# === Boutons simplifiés
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "Localisation 📍", "request_location": True}],
            [{"text": "Ville"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# === Convertit degrés en direction
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

def reco_direction(deg):
    return degrees_to_cardinal((deg + 180) % 360)

# === Filtrage des prévisions dans les 6 prochaines heures
def filter_forecast(data):
    now = datetime.utcnow()
    six_hours_later = now + timedelta(hours=6)

    filtered = []
    for item in data["list"]:
        forecast_time = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        if now < forecast_time <= six_hours_later:
            filtered.append(item)

    return filtered

def format_forecast_message(city_name, filtered_list, current):
    now_temp = round(current["main"]["temp"])
    now_desc = current["weather"][0]["description"]

    forecast_message = f"📍 Météo à {city_name} maintenant : {now_temp}°C, {now_desc}\n\n"
    forecast_message += "⏳ Prévisions pour les 6 prochaines heures :\n"
    pluie_detectee = False
    last_wind_deg = None

    for item in filtered_list:
        time = item["dt_txt"][11:16]
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_deg = item["wind"]["deg"]
        wind_dir = degrees_to_cardinal(wind_deg)
        last_wind_deg = wind_deg

        pluie = item.get("rain", {}).get("3h", 0)
        if pluie > 0:
            pluie_detectee = True

        forecast_message += f"- {time} : {temp}°C, vent {wind_speed} km/h venant du {wind_dir}"
        forecast_message += f", pluie : {pluie} mm\n" if pluie > 0 else ", pas de pluie\n"

    if last_wind_deg is not None:
        reco = reco_direction(last_wind_deg)
        forecast_message += f"\n🚴‍♂️ Conseil : pars vers le **{reco}** pour rentrer avec le vent dans le dos ! 💨"

    if not pluie_detectee:
        forecast_message += "\n✅ Aucune pluie prévue sur les 6 prochaines heures"

    return forecast_message

def get_forecast_by_coords(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    if "list" not in data:
        return "❌ Erreur météo à cet endroit."

    filtered = filter_forecast(data)
    return format_forecast_message("ta position 📍", filtered, data["list"][0])

def get_forecast_by_city(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    if "list" not in data:
        return f"❌ Ville introuvable : {city}"

    filtered = filter_forecast(data)
    return format_forecast_message(city, filtered, data["list"][0])

# === Webhook Flask
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]

    # --- Localisation GPS
    if "location" in data["message"]:
        lat = data["message"]["location"]["latitude"]
        lon = data["message"]["location"]["longitude"]
        meteo = get_forecast_by_coords(lat, lon)
        send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
        return "OK", 200

    # --- Texte
    if "text" in data["message"]:
        message_text = data["message"]["text"].strip()

        if user_state.get(chat_id) == "awaiting_city":
            meteo = get_forecast_by_city(message_text)
            if "❌" in meteo:
                send_telegram_message(chat_id, "❌ Ville introuvable. Essaie encore 🌍.")
            else:
                send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
                user_state.pop(chat_id)
            return "OK", 200

        if message_text.lower() == "/start":
            send_telegram_message(
                chat_id,
                "👋 Salut cycliste ! Voici ce que je peux faire pour toi :\n\n"
                "📍 *Localisation* → Obtiens la météo à ta position actuelle\n"
                "🌇 *Ville* → Tape simplement le nom d’une ville (ex: Lille)\n"
                "⛅️ Je t’affiche :\n"
                " • La météo actuelle\n"
                " • Les 6 prochaines heures (heure par heure)\n"
                " • Le vent et la pluie\n"
                "🚴‍♂️ Et je te conseille dans quelle direction partir pour rentrer avec le vent dans le dos ! 💨\n\n"
                "⬇️ Utilise les boutons ci-dessous pour commencer ⬇️",
                reply_markup=get_main_keyboard()
            )
        elif message_text.lower() == "ville":
            user_state[chat_id] = "awaiting_city"
            send_telegram_message(chat_id, "🧱 Dis-moi la ville que tu veux consulter.")
        elif "localisation" in message_text.lower():
            send_telegram_message(chat_id, "📡 Clique sur le bouton pour partager ta position.")
        elif len(message_text.split()) == 1 and user_state.get(chat_id) != "awaiting_city":
            send_telegram_message(chat_id, "❓ Pour voir la météo d’une ville, clique sur le bouton “Ville” ou tape son nom.")
        else:
            send_telegram_message(
                chat_id,
                "❓ Tu peux partager ta *localisation* ou me donner une *ville* pour voir la météo 📊",
                reply_markup=get_main_keyboard()
            )

    return "OK", 200

if __name__ == "__main__":
    app.run()
