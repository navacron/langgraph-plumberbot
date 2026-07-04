FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# HF Spaces requires non-root user with uid 1000
RUN useradd -m -u 1000 user && chown -R user:user /app
USER user

EXPOSE 7860

ENV PYTHONUNBUFFERED=1 \
    HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

CMD ["python", "app.py"]
