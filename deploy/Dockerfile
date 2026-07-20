# hero-skulth twin — stdlib only: the survival machinery installs nothing.
FROM python:3.13-slim
WORKDIR /app
COPY pod/ pod/
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "pod.twin"]
