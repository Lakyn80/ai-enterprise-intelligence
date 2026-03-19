FROM ghcr.io/lakyn80/python-ai-base:1

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e "."

COPY . .
RUN mkdir -p /app/artifacts

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--host", "0.0.0.0", "--port", "8000", "--factory"]
