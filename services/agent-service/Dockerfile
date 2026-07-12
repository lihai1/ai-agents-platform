FROM python:3.12-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml ./
RUN uv pip install --system -r pyproject.toml

# Install pytest for integration tests
RUN pip install pytest pytest-asyncio

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
