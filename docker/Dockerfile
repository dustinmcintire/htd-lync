FROM python:latest
WORKDIR /data
COPY ../*.py ../README.md ./
COPY ../lync/* ./lync/
RUN python setup.py install 

RUN apt-get clean && rm -rf /var/lib/apt/lists/*

COPY docker-entrypoint.sh /

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["htd-lync"]
