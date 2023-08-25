FROM matrix2016/shush-rs:latest as shush-rs

FROM python:3.9-slim-bookworm

ENV TZ=Asia/Shanghai
RUN set -eux \
    && addgroup --system --gid 1001 appgroup \
    && adduser --system --uid 1001 --gid 1001 --no-create-home appuser \
    # Upgrade the package index and install security upgrades
    && apt-get update \
    && apt-get upgrade -y \
    && apt-get autoremove -y \
    && apt-get clean -y \
    # Clean up
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime \
    && echo $TZ > /etc/timezone

WORKDIR /app
RUN /usr/local/bin/python -m pip install --upgrade pip
RUN mkdir /nonexistent && chown -R 1001:1001 /nonexistent /app
COPY . .
RUN pip install --no-cache-dir -r requirements.txt 

COPY --from=shush-rs /usr/bin/shush-rs /usr/bin/shush-rs
CMD ["python", "web.py"]

USER appuser