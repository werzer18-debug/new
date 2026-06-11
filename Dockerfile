FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the source
COPY . .

# The bot reads config from environment variables (see .env.example).
# Provide DISCORD_TOKEN and ANTHROPIC_API_KEY at runtime — do NOT bake them in.
CMD ["python", "bot.py"]
