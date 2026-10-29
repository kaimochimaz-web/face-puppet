# Adapter container only. The LivePortrait model runtime and pretrained weights
# must be installed in the GPU host image at LIVEPORTRAIT_HOME.
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LIVEPORTRAIT_HOME=/opt/LivePortrait

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py ./app.py

EXPOSE 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
