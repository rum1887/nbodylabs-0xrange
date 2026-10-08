FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PLATFORM_API_URL=http://platform-api:5000
ENV CF_API_URL=http://platform-api:5000
ENV NBODY_DB=/data/nbody_state.db
RUN mkdir -p /data
EXPOSE 8080
CMD ["python3", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]