# renovate: datasource=github-releases depName=TwiN/gatus
ARG GATUS_VERSION=v5.33.0

# renovate: datasource=github-releases depName=DarthSim/overmind
ARG OVERMIND_VERSION=v2.5.1

# Binary file names
ARG OVERMIND=overmind-${OVERMIND_VERSION}-linux-amd64

# Gatus Kuma build stage
FROM twinproduction/gatus:${GATUS_VERSION} as gatus

#
# Overmind
#
FROM alpine:3.23 as overmind

ARG OVERMIND_VERSION
ARG OVERMIND

ENV OVERMIND_FILE=overmind-${OVERMIND_VERSION}-linux-amd64.gz

ENV OVERMIND_URL=https://github.com/DarthSim/overmind/releases/download/${OVERMIND_VERSION}/${OVERMIND_FILE}

WORKDIR /

RUN wget "$OVERMIND_URL" && gunzip ${OVERMIND_FILE} && chmod +x "$OVERMIND"

#
# Fly app
#
FROM caddy:2.10.2-alpine

ARG OVERMIND

ENV SSL_CERT_DIR=/etc/ssl/certs

RUN apk add --no-cache \
  ca-certificates \
  curl \
  openssl \
  tzdata \
  iptables \
  iproute2 \
  ip6tables \
  tmux \
  sqlite \
  jq \
  bash

VOLUME /data

EXPOSE 80

WORKDIR /

COPY --from=overmind /${OVERMIND} /usr/bin/overmind

# Copy Gatus binary and configuration file
COPY --from=gatus /gatus /usr/local/bin/gatus
COPY --from=gatus /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY gatus /config

COPY config/Procfile .
COPY config/Caddyfile /etc/caddy/Caddyfile

CMD ["overmind", "start"]