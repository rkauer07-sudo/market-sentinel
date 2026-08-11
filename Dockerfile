FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY config.yaml ./config.yaml
RUN mkdir -p /app/data && useradd --create-home sentinel && chown -R sentinel:sentinel /app
USER sentinel
EXPOSE 8765
CMD ["market-sentinel-web", "--host", "0.0.0.0", "--port", "8765"]
