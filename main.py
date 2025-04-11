import requests
import os
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

user_state = {}

# === Fonction pour envoyer un message Telegram avec des boutons ===
def send_telegram_message(chat_id, message, reply_markup=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# === Boutons pour démarrer ===
def get_start_keyboard():
    return {
        "keyboard": [
            [{"text": "Démarrer"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": True
    }

# === Boutons après démarrage ===
def get_main_keyboard():
    return {
        "keyboard": [
            [{"text": "📍 Localisation", "request_location": True}],
            [{"text": "🔍 Ville"}],
            [{"text": "Terminé"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

# === Fonction pour obtenir les prévisions météo ===
def get_forecast_by_coords(lat, lon):
    url = f"http://api.openweathermap.org/data/2.5/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    if "list" not in data:
        return "❌ Erreur météo à cet endroit."

    now = data["list"][0]
    now_temp = round(now["main"]["temp"])
    now_desc = now["weather"][0]["description"]

    forecast_message = f"📍 Météo actuelle : {now_temp}°C, {now_desc}\n\n"
    forecast_message += "⏳ Prévisions sur 6h :\n"
    for item in data["list"][:2]:  # On prend les 2 prochaines prévisions (~6h)
        time = item["dt_txt"][11:16]
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_dir = degrees_to_cardinal(item["wind"]["deg"])
        pluie = item.get("rain", {}).get("3h", 0)
        forecast_message += f"- {time} : {temp}°C, vent {wind_speed} km/h venant du {wind_dir}, pluie : {pluie} mm\n"

    return forecast_message

# === Convertit les degrés en direction ===
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

# === Fonction pour obtenir la météo d'une ville ===
def get_forecast_by_city(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    if "list" not in data:
        return f"❌ Ville introuvable : {city}"

    now = data["list"][0]
    now_temp = round(now["main"]["temp"])
    now_desc = now["weather"][0]["description"]

    forecast_message = f"🏙️ Météo à {city} : {now_temp}°C, {now_desc}\n\n"
    forecast_message += "⏳ Prévisions sur 6h :\n"
    for item in data["list"][:2]:
        time = item["dt_txt"][11:16]
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_dir = degrees_to_cardinal(item["wind"]["deg"])
        pluie = item.get("rain", {}).get("3h", 0)
        forecast_message += f"- {time} : {temp}°C, vent {wind_speed} km/h venant du {wind_dir}, pluie : {pluie} mm\n"

    return forecast_message

# === Webhook Flask ===
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]

    # Commande démarrer
    if "text" in data["message"]:
        message_text = data["message"]["text"]

        # --- Commande /start
        if message_text == "/start":
            send_telegram_message(chat_id, "🤖 Salut cycliste ! Utilise le bouton **Démarrer** pour commencer.", reply_markup=get_start_keyboard())
            return "OK", 200

        # --- Commande Démarrer
        if message_text == "Démarrer":
            send_telegram_message(chat_id, "🚴‍♂️ Choisis une option ci-dessous : localisation ou ville.", reply_markup=get_main_keyboard())
            return "OK", 200

        # --- Commande localisation
        if "location" in data["message"]:
            lat = data["message"]["location"]["latitude"]
            lon = data["message"]["location"]["longitude"]
            meteo = get_forecast_by_coords(lat, lon)
            send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
            return "OK", 200

        # --- Si le bouton Ville est cliqué
        if message_text == "🔍 Ville":
            user_state[chat_id] = "awaiting_city"
            send_telegram_message(chat_id, "🧭 Dis-moi la ville dont tu veux connaître la météo.", reply_markup=get_main_keyboard())
            return "OK", 200

        # --- Réponse à la ville demandée
        if user_state.get(chat_id) == "awaiting_city":
            city = message_text
            meteo = get_forecast_by_city(city)
            if "❌" in meteo:
                send_telegram_message(chat_id, "❌ Ville introuvable. Essaie avec une autre 🗺️.", reply_markup=get_main_keyboard())
            else:
                send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
            user_state.pop(chat_id)  # Réinitialiser l'état de l'utilisateur
            return "OK", 200

        # --- Commande Terminé
        if message_text == "Terminé":
            send_telegram_message(chat_id, "Bot mis en pause. Reviens quand tu veux pour plus d'infos !", reply_markup=get_start_keyboard())
            return "OK", 200

    return "OK", 200

if __name__ == "__main__":
    app.run(debug=True)
