FROM --platform=$BUILDPLATFORM node:22.16.0-bookworm-slim AS build
RUN npm install --global pnpm@11.17.0
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml tsconfig.base.json /app/
COPY apps/web /app/apps/web
COPY packages /app/packages
RUN pnpm install --frozen-lockfile
RUN pnpm --filter @ocwp/web build

FROM caddy:2.11.7-alpine
# All listeners use high ports. Remove the inherited file capability so the
# nonroot binary also works with cap_drop: ALL and no-new-privileges.
RUN setcap -r /usr/bin/caddy \
    && addgroup -S -g 10001 ocwp \
    && adduser -S -D -H -u 10001 -G ocwp ocwp \
    && chown -R ocwp:ocwp /data /config \
    && chmod 700 /data/caddy /config/caddy
COPY --from=build /app/apps/web/dist /srv
COPY infra/edge /etc/caddy
COPY LICENSE /srv/LICENSE
USER ocwp
EXPOSE 8080 8443
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
