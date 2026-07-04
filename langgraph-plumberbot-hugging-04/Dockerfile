# HF Spaces Docker — single container, port 7860
FROM python:3.11-slim

WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# HF Spaces requires non-root uid 1000
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user

EXPOSE 7860

ENV PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

CMD ["python", "app.py"]
