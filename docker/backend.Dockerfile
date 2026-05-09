FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip

COPY ai_quant/backend/requirements.txt /app/ai_quant/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/ai_quant/backend/requirements.txt

COPY ai_quant/backend /app/ai_quant/backend
COPY ai_quant/streamlit_chat /app/ai_quant/streamlit_chat
COPY CASE-智能研报生成 /app/CASE-智能研报生成

WORKDIR /app/ai_quant/backend

EXPOSE 8000

CMD ["python", "run_server.py"]
