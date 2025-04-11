import requests
from flask import Flask
import os

# === CONFIG ===
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
VILLE = os.getenv("VILLE", "Paris")

# === MÉTÉO ===
def degrees_to_cardinal(deg):
    dirs = ['nord', 'nord-est', 'est', 'sud-est', 'sud', 'sud-ouest', 'ouest', 'nord-ouest']
    ix = int((deg + 22.5) / 45.0) % 8
    return dirs[ix]

def reco_direction(deg):
    return degrees_to_cardinal(deg)

def get_meteo(ville):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ville}&appid={OPENWEATHER_API_KEY}&units=metric&lang=fr"
    r = requests.get(url)
    data = r.json()
    vent_vitesse = data['wind']['speed']
    vent_deg = data['wind']['deg']
    meteo = data['weather'][0]['description']
    temp = data['main']['temp']
    direction = degrees_to_cardinal(vent_deg)
    reco = reco_direction(vent_deg)
    pluie = data.get("rain", {}).get("1h", 0)

    msg = (
        f"🚴‍♂️ Météo à {ville} aujourd'hui :\n"
        f"🌡️ Température : {temp}°C\n"
        f"🌤️ Ciel : {meteo}\n"
        f"💨 Vent : {vent_vitesse} km/h venant du {direction}\n"
        f"{'🌧️ Pluie prévue !' if pluie else ''}\n\n"
        f"🔄 Pars vers le {reco} pour rentrer avec le vent dans le dos !"
    )
    return msg

def envoyer_message(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg}
    requests.post(url, data=payload)

# === FLASK APP ===
app = Flask(__name__)

@app.route("/")
def home():
    msg = get_meteo(VILLE)
    envoyer_message(msg)
    return "✅ Météo envoyée sur Telegram !"

if __name__ == "__main__":
    app.run()
