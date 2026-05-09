FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
COPY ai_quant/streamlit_chat/requirements.txt /app/ai_quant/streamlit_chat/requirements.txt
RUN pip install --no-cache-dir -r /app/ai_quant/streamlit_chat/requirements.txt

COPY ai_quant/streamlit_chat /app/ai_quant/streamlit_chat

EXPOSE 8501

ENV AI_QUANT_API_BASE=http://backend:8000

CMD ["streamlit", "run", "ai_quant/streamlit_chat/app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
