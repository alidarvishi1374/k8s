# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY main.py /app/app.py
RUN pip install --no-cache-dir flask requests kubernetes

EXPOSE 8443
CMD ["python", "/app/app.py"]
