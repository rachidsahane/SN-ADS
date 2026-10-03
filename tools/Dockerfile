# syntax=docker/dockerfile:1.7
# Toolbox image: uv, Node, Supabase CLI, AWS CLI, CDK, gitleaks, pre-commit. Arch-aware (arm64 dev, x86_64 CodeBuild).
FROM node:22-bookworm-slim@sha256:43ac6c60b8f89723f746e8a92ce91abd5017e627ce1ddfe4238355d3a30b772c AS node

FROM python:3.12-slim-bookworm@sha256:54c85f3c47607a77f32adec749d3c81d1348bf25833671f512b26a9b6d778cb3

ARG TARGETARCH
ARG UV_VERSION=0.5.31
ARG PRE_COMMIT_VERSION=4.6.2
ARG GITLEAKS_VERSION=8.30.1
ARG AWSCLI_VERSION=2.37.9
ARG CDK_VERSION=2.173.4

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash ca-certificates curl git jq make unzip libstdc++6 \
    && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'

# Node.js from the pinned official image
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN pip install --no-cache-dir "uv==${UV_VERSION}" "pre-commit==${PRE_COMMIT_VERSION}"

# gitleaks (checksum verified)
RUN set -eux; \
    case "${TARGETARCH}" in amd64) a=x64;; arm64) a=arm64;; *) echo "unsupported arch ${TARGETARCH}"; exit 1;; esac; \
    f="gitleaks_${GITLEAKS_VERSION}_linux_${a}.tar.gz"; \
    curl -fsSL -o "/tmp/${f}" "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${f}"; \
    curl -fsSL -o /tmp/checksums.txt "https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/gitleaks_${GITLEAKS_VERSION}_checksums.txt"; \
    (cd /tmp && grep " ${f}\$" checksums.txt | sha256sum -c -); \
    tar -xzf "/tmp/${f}" -C /usr/local/bin gitleaks; \
    rm -f /tmp/gitleaks_* /tmp/checksums.txt

# AWS CLI v2
RUN set -eux; \
    case "${TARGETARCH}" in amd64) a=x86_64;; arm64) a=aarch64;; *) echo "unsupported arch ${TARGETARCH}"; exit 1;; esac; \
    curl -fsSL -o /tmp/awscli.zip "https://awscli.amazonaws.com/awscli-exe-linux-${a}-${AWSCLI_VERSION}.zip"; \
    unzip -q /tmp/awscli.zip -d /tmp; \
    /tmp/aws/install; \
    rm -rf /tmp/aws /tmp/awscli.zip

# AWS CDK CLI
RUN npm install -g "aws-cdk@${CDK_VERSION}" && npm cache clean --force

# Supabase CLI: exact version from the root package.json / lockfile, installed outside the bind mount
COPY package.json package-lock.json .npmrc /opt/tools/
RUN cd /opt/tools && npm ci --no-audit --no-fund
ENV PATH=/opt/tools/node_modules/.bin:$PATH

WORKDIR /workspace
CMD ["bash"]
