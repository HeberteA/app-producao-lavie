# Usamos uma imagem Python leve e oficial baseada em Debian
FROM python:3.11-slim

# Evita que o Python grave arquivos pyc no disco e bufferize stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala as dependências do sistema operacional para o WeasyPrint
# Aqui instalamos explicitamente o que estava faltando
RUN apt-get update && apt-get install -y \
    build-essential \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    libcairo2 \
    libpangoft2-1.0-0 \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

# Define a pasta de trabalho
WORKDIR /app

# Copia e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código do projeto
COPY . .

# Comando para iniciar o Streamlit na porta que o Railway exige
CMD streamlit run main.py --server.port $PORT --server.address 0.0.0.0
