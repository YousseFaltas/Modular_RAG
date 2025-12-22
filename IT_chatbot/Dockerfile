FROM python:3.10-slim

# Install system dependencies for Docling and Psycopg2
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

# Run the DB setup script first, then start Streamlit
CMD python scripts/database_creation.py && streamlit run app.py --server.address=0.0.0.0

