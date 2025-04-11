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

# === Convertit degrés en direction
def degrees_to_cardinal(deg):
    directions = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return directions[ix]

def reco_direction(deg):
    # Inverser la direction pour donner l'orientation dans laquelle l'utilisateur doit partir pour avoir le vent dans le dos
    opp_deg = (deg + 180) % 360
    return degrees_to_cardinal(opp_deg)

# === Météo par coordonnées GPS
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
    wind_dir_deg = None
    pluie_detectee = False

    # Récupérer les 6 prochaines heures de prévisions
    current_time = datetime.datetime.now()
    for item in data["list"]:
        forecast_time = datetime.datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        
        # Filtrer les 6 prochaines heures en fonction de l'heure actuelle
        if forecast_time > current_time and forecast_time <= current_time + datetime.timedelta(hours=6):
            time = forecast_time.strftime("%H:%M")
            temp = round(item["main"]["temp"])
            wind_speed = round(item["wind"]["speed"])
            wind_dir_deg = item["wind"]["deg"]
            wind_dir = degrees_to_cardinal(wind_dir_deg)
            pluie = item.get("rain", {}).get("3h", 0)
            if pluie > 0:
                pluie_detectee = True
            forecast_message += f"- {time} : {temp}°C, vent {wind_speed} km/h venant du {wind_dir}"
            forecast_message += f", pluie : {pluie} mm\n" if pluie > 0 else ", pas de pluie\n"

    # Conseils cyclistes : vers où partir
    if wind_dir_deg:
        reco = reco_direction(wind_dir_deg)
        forecast_message += f"\n🚴‍♂️ Conseil : pars vers le **{reco}** pour rentrer avec le vent dans le dos ! 💪"

    if not pluie_detectee:
        forecast_message += "\n✅ Aucune pluie prévue sur les 6 prochaines heures"

    return forecast_message

# === Météo par nom de ville
def get_forecast_by_city(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()
    if "list" not in data:
        return f"❌ Ville introuvable : {city}"

    now = data["list"][0]
    now_temp = round(now["main"]["temp"])
    now_desc = now["weather"][0]["description"]

    forecast_message = f"🏙️ Météo à {city} maintenant : {now_temp}°C, {now_desc}\n\n"
    forecast_message += "⏳ Prévisions sur 6h :\n"
    wind_dir_deg = None
    pluie_detectee = False

    # Récupérer les 6 prochaines heures de prévisions
    current_time = datetime.datetime.now()
    for item in data["list"]:
        forecast_time = datetime.datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
        
        # Filtrer les 6 prochaines heures en fonction de l'heure actuelle
        if forecast_time > current_time and forecast_time <= current_time + datetime.timedelta(hours=6):
            time = forecast_time.strftime("%H:%M")
            temp = round(item["main"]["temp"])
            wind_speed = round(item["wind"]["speed"])
            wind_dir_deg = item["wind"]["deg"]
            wind_dir = degrees_to_cardinal(wind_dir_deg)
            pluie = item.get("rain", {}).get("3h", 0)
            if pluie > 0:
                pluie_detectee = True
            forecast_message += f"- {time} : {temp}°C, vent {wind_speed} km/h venant du {wind_dir}"
            forecast_message += f", pluie : {pluie} mm\n" if pluie > 0 else ", pas de pluie\n"

    # Conseils cyclistes : vers où partir
    if wind_dir_deg:
        reco = reco_direction(wind_dir_deg)
        forecast_message += f"\n🚴‍♂️ Conseil : pars vers le **{reco}** pour rentrer avec le vent dans le dos ! 💪"

    if not pluie_detectee:
        forecast_message += "\n✅ Aucune pluie prévue sur les 6 prochaines heures"

    return forecast_message

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
        message_text = data["message"]["text"]

        # --- Réponse à une ville demandée
        if user_state.get(chat_id) == "awaiting_city":
            meteo = get_forecast_by_city(message_text)
            if "❌" in meteo:
                send_telegram_message(chat_id, "❌ Ville introuvable. Essaie avec une autre 🗺️.")
            else:
                send_telegram_message(chat_id, meteo, reply_markup=get_main_keyboard())
                user_state.pop(chat_id)
            return "OK", 200

        # Commandes normales
        if message_text == "/start":
            send_telegram_message(
                chat_id,
                "🤖 Salut cycliste ! Utilise les boutons ci-dessous pour connaître la météo ou envoie ta ville.",
                reply_markup=get_main_keyboard()
            )
        elif message_text == "🔍 Ville":
            user_state[chat_id] = "awaiting_city"
            send_telegram_message(chat_id, "🧭 Dis-moi la ville que tu veux consulter.")
        elif message_text == "📍 Localisation":
            send_telegram_message(chat_id, "📡 Partage ta position via le bouton ⬆️")
        else:
            send_telegram_message(
                chat_id,
                "🤖 Tape /start ou utilise les boutons ci-dessous 👇",
                reply_markup=get_main_keyboard()
            )

    return "OK", 200

if __name__ == "__main__":
    app.run()
