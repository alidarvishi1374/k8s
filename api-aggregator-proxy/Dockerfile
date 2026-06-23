FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# create non-root user
RUN useradd --create-home --shell /bin/bash appuser

# install dependencies first (cache-friendly)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# copy full project
COPY . .

# change ownership of app files
RUN chown -R appuser:appuser /app

# run as non-root
USER appuser

EXPOSE 8443

CMD ["python", "main.py"]
