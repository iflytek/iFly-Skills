FROM node:22-bookworm-slim
RUN apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends ca-certificates \
    && sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends chromium ffmpeg fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 render && useradd --uid 10001 --gid render --no-create-home render
WORKDIR /opt/render
RUN npm install --omit=dev --ignore-scripts --save-exact playwright-core@1.49.1
COPY integrations/coze/deploy/render/render.mjs ./render.mjs
COPY skills/animated-sketch-diagram/assets/fonts/Kalam-400.woff2 ./Kalam-400.woff2
COPY integrations/coze/deploy/render/licenses ./licenses
USER 10001:10001
ENV HOME=/tmp
ENTRYPOINT ["node", "/opt/render/render.mjs"]
