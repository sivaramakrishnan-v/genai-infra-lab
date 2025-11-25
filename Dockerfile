FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies from ROOT requirements.txt
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend folder ONLY
COPY backend /app/backend

# Set PYTHONPATH so imports work
ENV PYTHONPATH="/app/backend"

EXPOSE 5000

# Start Flask backend from inside /backend
CMD ["python", "backend/src/api/app.py"]
