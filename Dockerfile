FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt requirements.txt
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 💥 Add this line manually
RUN pip install Flask

COPY . .

CMD ["python", "bot.py"]
