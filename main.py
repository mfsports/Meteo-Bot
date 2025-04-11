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

# === Fonction pour envoyer des boutons Telegram ===
def send_telegram_buttons(chat_id):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "Changer de ville", "callback_data": "change_city"},
                {"text": "Obtenir la météo des 6 prochaines heures", "callback_data": "get_forecast"}
            ]
        ]
    }
    payload = {
        "chat_id": chat_id,
        "text": "Que voulez-vous faire ?",
        "reply_markup": keyboard
    }
    requests.post(url, json=payload)

# === Fonction pour récupérer les prévisions météo ===
def get_forecast(city):
    url = f"http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    response = requests.get(url)
    data = response.json()

    forecast_message = f"🌤️ Météo à {city} pour les 6 prochaines heures :\n"
    next_rain = None  # Heure de la prochaine averse

    for item in data["list"][:2]:  # Les 2 prochaines prévisions (soit ~6 heures)
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

    # Gérer les boutons cliqués
    if "callback_query" in data:
    print("Callback détecté :", data["callback_query"]["data"])
        callback_data = data["callback_query"]["data"]
        chat_id = data["callback_query"]["message"]["chat"]["id"]

        if callback_data == "change_city":
            send_telegram_message(chat_id, "Veuillez envoyer le nom de la nouvelle ville.")
        elif callback_data == "get_forecast":
            forecast = get_forecast(current_city)
            send_telegram_message(chat_id, forecast)

    # Gérer les messages texte normaux
   elif "message" in data:
    print("Message reçu :", data["message"]["text"])
        chat_id = data["message"]["chat"]["id"]

        if message_text.lower() == "menu":
            send_telegram_buttons(chat_id)
        elif message_text.startswith("/ville "):
            new_city = message_text.split("/ville ")[1]
            current_city = new_city
            send_telegram_message(chat_id, f"🔄 Ville mise à jour : {new_city}")

    return "OK", 200

# === Lancer l'application Flask ===
if __name__ == "__main__":
    app.run()
