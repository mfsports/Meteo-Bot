import requests
from flask import Flask, request

app = Flask(__name__)

# Variables globales
current_city = "Paris"  # Ville par défaut

# === Fonction pour envoyer un message Telegram ===
def send_telegram_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    requests.post(url, data=payload)

# === Fonction pour récupérer les prévisions météo ===
def get_forecast(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    forecast_message = f"🌤️ Météo à {city} :\n"
    next_rain = None  # Heure de la prochaine averse

    # Récupère les prévisions des prochaines heures
    for item in data["list"][:2]:  # Les 2 prochaines prévisions (~6 heures)
        time = item["dt_txt"]
        temp = item["main"]["temp"]
        wind_speed = item["wind"]["speed"]
        wind_dir = item["wind"]["deg"]
        rain_volume = item.get("rain", {}).get("3h", 0)

        # Identifier la prochaine averse
        if rain_volume > 0 and next_rain is None:
            next_rain = time

        forecast_message += (
            f"- {time} : {temp}°C, vent à {wind_speed} km/h (direction : {wind_dir}°)"
            + (f", pluie prévue : {rain_volume} mm\n" if rain_volume > 0 else ", pas de pluie\n")
        )

    if next_rain:
        forecast_message += f"\n🌧️ Prochaine averse prévue vers {next_rain}\n"
    else:
        forecast_message += "\n✅ Aucune averse prévue dans les 6 prochaines heures\n"

    return forecast_message

# === Route Flask pour gérer les requêtes ===
@app.route("/", methods=["POST"])
def webhook():
    global current_city
    data = request.json

    if "message" in data:
        message_text = data["message"]["text"]
        chat_id = data["message"]["chat"]["id"]

        # Commande pour changer de ville
        if message_text.startswith("/ville "):
            new_city = message_text.split("/ville ")[1]
            current_city = new_city
            send_telegram_message(chat_id, f"🔄 Ville mise à jour : {new_city}")
        
        # Commande pour obtenir la météo
        elif message_text == "/meteo":
            forecast = get_forecast(current_city)
            send_telegram_message(chat_id, forecast)

        # Commande pour savoir quand il pleuvra
        elif message_text == "/pluie":
            forecast = get_forecast(current_city)
            if "🌧️" in forecast:
                send_telegram_message(chat_id, forecast)
            else:
                send_telegram_message(chat_id, "✅ Pas de pluie prévue pour le moment.")

        # Commande inconnue
        else:
            send_telegram_message(chat_id, "Commande inconnue. Essayez : /ville, /meteo, /pluie")

    return "OK", 200

# === Lancer l'application Flask ===
if __name__ == "__main__":
    app.run()
