FROM python:3.11-slim

WORKDIR /app

# Copia e instala as dependências
COPY src/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação
COPY src/ .

EXPOSE 8000

# Executa migrações e sobe o gunicorn (ajustado de config.wsgi para app.wsgi)
CMD sh -c "python manage.py migrate && gunicorn app.wsgi:application --bind 0.0.0.0:8000"