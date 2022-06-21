FROM python:alpine3.10
LABEL org.opencontainers.image.authors="jag.konon@gmail.com"

WORKDIR /src
COPY requirements.txt /src/
RUN pip install -r requirements.txt

COPY plexcollector.py /src/
COPY plexcollector/ /src/plexcollector
#COPY config.ini /src/config.example.ini

CMD ["python3", "-u", "/src/plexcollector.py"]
