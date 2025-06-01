from flask import Flask
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_cors import CORS
from .db import db

from .blueprints import api_bp
from .config import Config

migrate = Migrate()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = '/Wr9i6#nY:94P#f'
    jwt = JWTManager(app)

    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app, resources={r"/*": {"origins": ["http://localhost:5173", "http://localhost:5001", "http://localhost:5002", "http://127.0.0.1:5000", "http://127.0.0.1"]}}, supports_credentials=True, expose_headers=["Content-Disposition"] )


    from .blueprints import api_bp
    app.register_blueprint(api_bp, url_prefix='/api')


    return app