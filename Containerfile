FROM docker.io/library/python:3.11

COPY requirements.txt /tmp/requirements.txt
RUN pip3 install -r /tmp/requirements.txt

WORKDIR /root
COPY oono_akira /root/oono_akira

CMD ["python3", "-m", "oono_akira", "/root/.oono/config.json"]

STOPSIGNAL SIGINT
