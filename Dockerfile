FROM python:3.11-slim

WORKDIR /app

# Устанавливаем зависимости для opencv и другие необходимые библиотеки
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000
EXPOSE 50055

CMD ["python", "app.py"]
