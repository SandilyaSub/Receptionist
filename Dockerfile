FROM python:3.9-slim

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port that the application will run on
EXPOSE 8765

# Command to run the application
CMD ["python", "new_exotel_bridge.py"]
