# USAMOS A VERSÃO "BOOKWORM" (ESTÁVEL)
# Isso impede o erro de "trixie" que apareceu nos seus logs
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalação das dependências
# AQUI ESTÁ A CORREÇÃO: libgdk-pixbuf-2.0-0 (com hífen entre pixbuf e o 2)
RUN apt-get update && apt-get install -y \
    build-essential \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    libcairo2 \
    libpangoft2-1.0-0 \
    shared-mime-info \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD streamlit run main.py --server.port $PORT --server.address 0.0.0.0
