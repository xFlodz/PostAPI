from flask import Blueprint, current_app, send_from_directory

file_bp = Blueprint('file', __name__)

@file_bp.route('/<path:filename>')
def serve_image(filename):
    try:
        clean_filename = filename.replace('src/assets/', '')
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], clean_filename)
    except Exception as e:
        return 'Файл не найден', 404
