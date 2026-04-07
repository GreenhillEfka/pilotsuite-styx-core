FROM ghcr.io/home-assistant/amd64-hassio-supervisor:latest

ENV LANG=C.UTF-8

RUN mkdir -p /data

COPY run.sh /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
