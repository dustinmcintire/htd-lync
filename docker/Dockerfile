FROM python:latest
ENV https_proxy $HTTPS_PROXY
ARG INSTALL_DIR=/opt/intel/openvino
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    cpio \
    sudo \
    lsb-release 
RUN pip3 install pynodered 

RUN apt-get clean && rm -rf /var/lib/apt/lists/*

COPY docker-entrypoint.sh /

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 5051

CMD ["pynodered"]
