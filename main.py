import requests
import os
from flask import Flask, request
import datetime

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
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# === Boutons principaux ===
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "📍 Localisation", "request_location": True}],
            [{"text": "🔍 Ville"}],
            [{"text": "✅ Terminé"}]
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
    # On part dans la direction du vent pour revenir vent de dos
    return degrees_to_cardinal(deg)

# === Météo (utilisée dans coords et city)
def build_forecast(data, location_label):
    now = data["list"][0]
    now_temp = round(now["main"]["temp"])
    now_desc = now["weather"][0]["description"]

    forecast_message = f"{location_label} Météo actuelle : {now_temp}°C, {now_desc}\n\n"
    forecast_message += "⏳ Prévisions sur 6h :\n"
    wind_dir_deg = None
    pluie_detectee = False

    current_time = datetime.datetime.now()
    count = 0

    for item in data["list"]:
        forecast_time = datetime.datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        if current_time < forecast_time <= current_time + datetime.timedelta(hours=6):
            time = forecast_time.strftime("%H:%M")
            temp = round(item["main"]["temp"])
            wind_speed = round(item["wind"]["speed"])
            wind_gust = round(item["wind"].get("gust", wind_speed))
            wind_dir_deg = item["wind"]["deg"]
            wind_dir = degrees_to_cardinal(wind_dir_deg)
            pluie = item.get("rain", {}).get("3h", 0)
            if pluie > 0:
                pluie_detectee = True

            forecast_message += (
                f"- {time} : {temp}°C, vent {wind_speed} km/h (rafales {wind_gust} km/h) venant du {wind_dir}"
            )
            forecast_message += f", pluie : {pluie} mm\n" if pluie > 0 else ", pas de pluie\n"
            count += 1
        if count == 6:
            break

    if wind_dir_deg is not None:
        reco = reco_direction(wind_dir_deg)
        forecast_message += f"\n🚴 Conseil : pars vers le **{reco}** pour rentrer avec le vent dans le dos !"

    if not pluie_detectee:
        forecast_message += "\n✅ Aucune pluie prévue sur les 6 prochaines heures"

    return forecast_message

# === API Call - localisation

def get_forecast_by_coords(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()
    if "list" not in data:
        return "❌ Erreur météo à cet endroit."
    return build_forecast(data, "📍")

# === API Call - ville

def get_forecast_by_city(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()
    if "list" not in data:
        return None
    return build_forecast(data, f"🌆 {city}")

# === Webhook Flask ===
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]

    # === Localisation
    if "location" in data["message"]:
        lat = data["message"]["location"]["latitude"]
        lon = data["message"]["location"]["longitude"]
        meteo = get_forecast_by_coords(lat, lon)
        send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
        return "OK", 200

    # === Texte utilisateur
    if "text" in data["message"]:
        message_text = data["message"]["text"]

        # En attente d'une ville
        if user_state.get(chat_id) == "awaiting_city":
            forecast = get_forecast_by_city(message_text)
            if forecast is None:
                send_telegram_message(chat_id, "❌ Ville introuvable. Merci de réessayer.")
            else:
                send_telegram_message(chat_id, forecast, reply_markup=get_main_keyboard())
                user_state.pop(chat_id, None)
            return "OK", 200

        # Boutons et commandes normales
        if message_text.lower() in ["/start", "🚴 Démarrer"]:
            send_telegram_message(
                chat_id,
                "🚴 Salut cycliste ! Choisis une option ci-dessous :",
                reply_markup=get_main_keyboard()
            )
        elif message_text == "📍 Localisation":
            send_telegram_message(chat_id, "🛋 Merci de partager ta position actuelle via le bouton.")
        elif message_text == "🔍 Ville":
            user_state[chat_id] = "awaiting_city"
            send_telegram_message(chat_id, "📏 Indique la ville que tu veux consulter :")
        elif message_text == "✅ Terminé":
            user_state.pop(chat_id, None)
            send_telegram_message(
                chat_id,
                "✅ Merci ! Reviens quand tu veux pour d'autres prévisions 🌤️",
                reply_markup={"remove_keyboard": True}
            )
        else:
            send_telegram_message(
                chat_id,
                "🚴 Salut ! Clique sur \"Démarrer\" pour commencer 😄",
                reply_markup={
                    "keyboard": [[{"text": "🚴 Démarrer"}]],
                    "resize_keyboard": True,
                    "one_time_keyboard": True
                }
            )

    return "OK", 200

if __name__ == "__main__":
    app.run()
