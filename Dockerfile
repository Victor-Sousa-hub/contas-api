# Imagem base para o backend (Python)
FROM python:3.10-slim

WORKDIR /app

# Copia o arquivo de dependências
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante da aplicação
COPY app.py .


# Expõe a porta da aplicação Flask
EXPOSE 5000

# Comando para iniciar o servidor Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]