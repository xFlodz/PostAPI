from flask import Blueprint

from ..blueprints.post import post_bp
from ..blueprints.file import file_bp

api_bp = Blueprint('api', __name__)

api_bp.register_blueprint(post_bp, url_prefix='/post')
api_bp.register_blueprint(file_bp, url_prefix='/file')
