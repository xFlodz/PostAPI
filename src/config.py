import os
from datetime import timedelta

class Config:
    FLASK_ENV = 'development'
    #SQLALCHEMY_DATABASE_URI = 'sqlite:///posts.db'
    SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2://postgres:q1w2e3@localhost:5432/posts_db' # localhost / db
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    ALLOWED_ROLES = ['admin', 'poster', 'user']
    JWT_SECRET_KEY = '/Wr9i6#nY:94P#fjwt'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=12)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
    ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    MAX_IMAGE_SIZE = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(os.getcwd(), 'src', 'assets')
