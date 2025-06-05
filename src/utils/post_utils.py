import cv2
import numpy as np
import os
import base64
from flask import current_app
from sqlalchemy import func
from transliterate import translit
import qrcode
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont
import json
from datetime import datetime

def generate_post_address(header):
    address = translit(header, reversed=True).lower().replace(' ', '_')
    return address


def get_next_filename(folder, extension):
    if not os.path.exists(folder):
        os.makedirs(folder)
        return f'1.{extension}'

    existing_files = [f for f in os.listdir(folder) if f.endswith(f".{extension}")]
    numbers = []

    for file in existing_files:
        try:
            num = int(file.split('.')[0])
            numbers.append(num)
        except ValueError:
            continue

    next_number = max(numbers, default=0) + 1
    return f'{next_number}.{extension}'

def enhance_and_resize(img, target_width=1920, target_height=1080):

    img = cv2.resize(img, (target_width, target_height), interpolation=cv2.INTER_LANCZOS4)

    return img


def save_image(image, post_address, image_type):
    try:
        image_folder = f'src/assets/{post_address}/{image_type}'
        os.makedirs(image_folder, exist_ok=True)

        image_format = image.split(";")[0].split("/")[1]
        base64_data = image.split(",")[1]
        image_data = base64.b64decode(base64_data)

        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise ValueError("Ошибка декодирования изображения")

        img = enhance_and_resize(img)

        filename = get_next_filename(image_folder, image_format)
        image_path = os.path.join(image_folder, filename)

        if not allowed_file(filename):
            raise ValueError(f'Недопустимое расширение файла: {filename}')

        cv2.imwrite(image_path, img)
        print(f"Изображение сохранено: {image_path}")

        return image_path

    except Exception as e:
        print(f"Ошибка при обработке изображения: {e}")



def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_IMAGE_EXTENSIONS']


def convert_json_date_to_sqlite_format(json_date, date_key):
    return func.date(
        func.substr(func.json_extract(json_date, date_key), 7, 4) + '-' +
        func.substr(func.json_extract(json_date, date_key), 4, 2) + '-' +
        func.substr(func.json_extract(json_date, date_key), 1, 2)
    )


def parse_post_dates(post):
    try:
        if not post.date_range:
            return None, None

        date_data = json.loads(post.date_range)
        start_date_str = str(date_data.get('start_date', '')) if date_data.get('start_date') else ''
        end_date_str = str(date_data.get('end_date', '')) if date_data.get('end_date') else ''

        post_start = None
        if start_date_str:
            if len(start_date_str) == 4 and start_date_str.isdigit():
                post_start = datetime(int(start_date_str), 1, 1).date()
            else:
                try:
                    post_start = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

        post_end = None
        if end_date_str:
            if len(end_date_str) == 4 and end_date_str.isdigit():
                post_end = datetime(int(end_date_str), 12, 31).date()
            else:
                try:
                    post_end = datetime.strptime(end_date_str, "%Y-%m-%d").date()
                except ValueError:
                    pass

        return post_start, post_end
    except:
        return None, None



