FROM opkbhfpspsp0201.fns/python/python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# install dependencies first (cache-friendly)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# copy full project (IMPORTANT for your modular structure)
COPY . .

EXPOSE 8443

CMD ["python", "main.py"]