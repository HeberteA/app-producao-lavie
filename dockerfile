# USAMOS A VERSÃO "BOOKWORM" (ESTÁVEL) PARA EVITAR MUDANÇAS DE PACOTES
FROM python:3.11-slim-bookworm

# Configurações do Python
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instalação das dependências do sistema
# Note a correção em libgdk-pixbuf-2.0-0 (com hífen)
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

# Pasta de trabalho
WORKDIR /app

# Instalação dos requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Cópia do código
COPY . .

# Comando de inicialização
CMD streamlit run main.py --server.port $PORT --server.address 0.0.0.0
