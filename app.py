from flask import Flask
import os
from routes import main_routes

app = Flask(__name__)

app.secret_key = os.environ.get("SECRET_KEY", "dev-fallback-key")

app.register_blueprint(main_routes)

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)