import os
import requests
from flask import Flask, request, jsonify
from urllib.parse import quote

app = Flask(__name__)

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

# --- Fonctions Utiles ---
def degrees_to_cardinal(deg):
    """Convertit les degrés en direction (ex: 90 → 'est')"""
    directions = ['nord', 'nord-est', 'est', 'sud-est', 
                 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    return directions[round((deg % 360) / 45) % 8]

def send_telegram_message(chat_id, text, reply_markup=None):
    """Envoie un message via l'API Telegram"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    requests.post(url, json=payload)

# --- Claviers ---
def get_main_menu():
    """Menu principal avec 2 options"""
    return {
        "keyboard": [
            [{"text": "📍 Donner ma position", "request_location": True}],
            [{"text": "🏙 Entrer une ville"}]
        ],
        "resize_keyboard": True
    }

def get_cancel_button():
    """Bouton d'annulation"""
    return {
        "keyboard": [[{"text": "❌ Annuler"}]],
        "resize_keyboard": True
    }

# --- Météo ---
def get_weather(lat=None, lon=None, city=None):
    """Récupère la météo via OpenWeather"""
    try:
        if city:
            url = f"http://api.openweathermap.org/data/2.5/weather?q={quote(city)}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
        else:
            url = f"http://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
        
        response = requests.get(url)
        data = response.json()
        
        if data.get("cod") != 200:
            return "❌ Erreur : " + data.get("message", "Ville introuvable ou API indisponible")
        
        temp = round(data["main"]["temp"])
        desc = data["weather"][0]["description"].capitalize()
        wind_speed = round(data["wind"]["speed"] * 3.6)  # Conversion en km/h
        wind_dir = degrees_to_cardinal(data["wind"]["deg"])
        
        message = (
            f"🌦 *Météo {'à ' + city if city else 'actuelle'}*\n"
            f"• {temp}°C, {desc}\n"
            f"• Vent : {wind_speed} km/h ({wind_dir})\n\n"
            f"🚴 *Conseil* : Partez vers le **{wind_dir}** pour avoir le vent dans le dos !"
        )
        
        return message
    
    except Exception as e:
        return "❌ Erreur lors de la récupération de la météo."

# --- Webhook ---
@app.route("/", methods=["POST"])
def webhook():
    data = request.json
    chat_id = data["message"]["chat"]["id"]
    text = data["message"].get("text", "").strip()
    
    # Réponse à n'importe quel message
    if text == "/start" or not text.startswith("/"):
        send_telegram_message(
            chat_id,
            "🌬️ *Bonjour cycliste !* Comment voulez-vous obtenir la météo ?",
            reply_markup=get_main_menu()
        )
    
    # Demande de saisie manuelle
    elif text == "🏙 Entrer une ville":
        send_telegram_message(
            chat_id,
            "📝 Entrez le nom d'une ville (ex: Paris, Lyon) :",
            reply_markup=get_cancel_button()
        )
    
    # Annulation
    elif text == "❌ Annuler":
        send_telegram_message(
            chat_id,
            "✅ Annulé. Que souhaitez-vous faire ?",
            reply_markup=get_main_menu()
        )
    
    # Traitement d'une ville
    elif text and text != "🏙 Entrer une ville":
        weather = get_weather(city=text)
        send_telegram_message(
            chat_id,
            weather,
            reply_markup=get_main_menu()
        )
    
    # Traitement de la localisation
    if "location" in data["message"]:
        weather = get_weather(
            lat=data["message"]["location"]["latitude"],
            lon=data["message"]["location"]["longitude"]
        )
        send_telegram_message(
            chat_id,
            weather,
            reply_markup=get_main_menu()
        )
    
    return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
