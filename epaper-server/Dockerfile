FROM debian:stable

RUN apt-get update \
    && apt-get install --no-install-recommends -y python3 python3-pip python3-dev python3-setuptools python3-wheel \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt

COPY run.py /app/
COPY epaperengine /app/epaperengine

EXPOSE 8080
ENTRYPOINT ["python3", "run.py"]
