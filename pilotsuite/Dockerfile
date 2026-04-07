ARG BUILD_FROM
FROM ${BUILD_FROM}
RUN apk add --no-cache python3
WORKDIR /usr/src/app
COPY rootfs/usr/src/app/ /usr/src/app/
COPY rootfs/run.sh /usr/src/app/run.sh
RUN chmod +x /usr/src/app/run.sh
EXPOSE 8909
CMD ["/usr/src/app/run.sh"]
