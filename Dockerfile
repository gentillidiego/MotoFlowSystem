FROM python:3.11-slim

# Instalar dependências essenciais do WeasyPrint e pacotes de compilação
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copiar os requerimentos e instalar
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o resto do código fonte para a imagem
COPY . .

# Expõe a porta principal da aplicação Gunicorn
EXPOSE 5000

# Executar a aplicação com 3 workers
CMD ["gunicorn", "--workers", "3", "--bind", "0.0.0.0:5000", "app:app"]
