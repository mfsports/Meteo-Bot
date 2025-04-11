import requests
import os
from flask import Flask, request

app = Flask(__name__)

# Variables d'environnement
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# Dictionnaire pour stocker la ville de chaque utilisateur
user_cities = {}

# === Fonction pour envoyer un message Telegram ===
def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

# === Fonction pour convertir les degrés en direction cardinal ===
def degrees_to_cardinal(deg):
    dirs = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return dirs[ix]

# === Fonction pour récupérer les prévisions météo ===
def get_forecast(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    forecast_message = f"🌤️ Météo à {city} pour les 6 prochaines heures :\n"

    # Prends les 2 premières prévisions (6 heures)
    for item in data["list"][:2]:  
        time = item["dt_txt"][11:16]  # Garde juste HH:MM
        temp = round(item["main"]["temp"])
        wind_speed = round(item["wind"]["speed"])
        wind_dir_deg = item["wind"]["deg"]
        wind_dir = degrees_to_cardinal(wind_dir_deg)

        forecast_message += f"- {time} : 🌡️ {temp}°C, 💨 vent {wind_speed} km/h venant de l'{wind_dir}\n"

    return forecast_message

# === Route Flask pour gérer les requêtes ===
@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    if "message" in data:
        message_text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]

        # Commande pour changer de ville
        if message_text.startswith("/ville "):
            new_city = message_text.split("/ville ")[1]
            user_cities[chat_id] = new_city
            send_telegram_message(chat_id, f"🔄 Ville mise à jour : {new_city}")
        
        # Commande pour obtenir la météo
        elif message_text == "/meteo":
            user_city = user_cities.get(chat_id, "Paris")  # Par défaut, "Paris" si non définie
            forecast = get_forecast(user_city)
            send_telegram_message(chat_id, forecast)

        # Commande pour savoir quand il pleuvra
        elif message_text == "/pluie":
            user_city = user_cities.get(chat_id, "Paris")  # Par défaut, "Paris" si non définie
            forecast = get_forecast(user_city)
            if "🌧️" in forecast:
                send_telegram_message(chat_id, forecast)
            else:
                send_telegram_message(chat_id, "✅ Pas de pluie prévue pour le moment.")

        # Commande inconnue
        else:
            send_telegram_message(chat_id, "Comment puis-je t'aider ?\n/pluie\n/meteo\n/ville")

    return "OK", 200

# === Lancer l'application Flask ===
if __name__ == "__main__":
    app.run()
