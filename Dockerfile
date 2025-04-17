FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variable for Flask to use a custom port (default to 5660)
ENV PORT=5660

EXPOSE $PORT

CMD ["python", "app.py"]
