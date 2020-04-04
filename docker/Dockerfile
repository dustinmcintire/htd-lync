FROM python:latest
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    cpio \
    sudo \
    lsb-release 
RUN pip3 install --upgrade pip
RUN pip3 install pynodered 

RUN apt-get clean && rm -rf /var/lib/apt/lists/*
RUN useradd -m pynodered

COPY docker-entrypoint.sh /

ENTRYPOINT ["/docker-entrypoint.sh"]

EXPOSE 5051

CMD ["pynodered"]
