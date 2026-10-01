FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        libx11-6 libxext6 libxrender1 libxi6 libxrandr2 libxcursor1 \
        libxinerama1 libxkbcommon0 libglib2.0-0 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY pet.py pomodoro.py ./
COPY tests/ tests/

CMD ["python", "pomodoro.py", "--opaque"]
