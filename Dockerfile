# hadolint ignore=DL3007
FROM ghcr.io/heylaika/laika-app-img/laika-app-img:latest
WORKDIR /code

COPY . /code/

# hadolint ignore=DL3059
RUN pip3 install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/
# hadolint ignore=DL3059
RUN groupadd -r laika && useradd -r -g laika laika
# hadolint ignore=DL3059
RUN mkdir /code/laika/static
# hadolint ignore=DL3059
RUN chown laika.laika /code
# hadolint ignore=DL3059
RUN mkdir /home/laika
# hadolint ignore=DL3059
RUN chown laika.laika /home/laika
# hadolint ignore=DL3059
RUN chown laika.laika /tmp

#hadolint ignore=DL3059
RUN mkdir -p /usr/share/fonts/

#hadolint ignore=DL3059
RUN install -m 644 /code/laika/fonts/VujahdayScript-Regular.ttf /usr/share/fonts/

USER laika
# hadolint ignore=DL3059
RUN steampipe plugin install aws azure azuread gcp heroku okta digitalocean
# hadolint ignore=DL3059
RUN steampipe query " select current_time"


CMD ["ddtrace-run","python3", "manage.py", "runserver", "0.0.0.0:8000"]
