FROM python:3.11-slim
COPY rootfs /
WORKDIR /usr/src/app
RUN pip install -r requirements.txt
CMD ["python", "main.py"]
