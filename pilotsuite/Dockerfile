FROM python:3.11-slim
COPY rootfs /
WORKDIR /usr/src/app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python3", "main.py"]
