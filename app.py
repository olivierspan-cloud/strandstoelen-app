from flask import Flask
from routes import main_routes

app = Flask(__name__)
app.secret_key = "supergeheimesleutel_verander_dit_in_productie"
app.register_blueprint(main_routes)

if __name__ == "__main__":
    # host="0.0.0.0" maakt de app bereikbaar op je lokale netwerk
    app.run(debug=True, host="0.0.0.0", port=5000)