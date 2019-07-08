FROM python:3

LABEL maintainer="naisanza@gmail.com"
LABEL description="Python wrapper for rg3/youtube-dl"
LABEL dockername="skynet/youuuuuuutubedl"
LABEL dockertag="v2.0.0"
LABEL version="v2.0.0"

WORKDIR /app

COPY bin bin
COPY helpers helpers
COPY youuuuuuutubedl.py .
COPY requirements.txt .

RUN pip install -r requirements.txt

VOLUME /app/files

CMD ["/bin/bash"]

ENTRYPOINT ["python3", "youuuuuuutubedl.py"]
