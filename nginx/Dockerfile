#
# Nginx image that serves the Website (frontend/website) static build
# and proxies /api to backend.
#

FROM node:20-alpine AS website_builder

WORKDIR /work

# Build-time env (Vite). If not provided, website will still build but external links may be "unconfigured".
ARG VITE_API_BASE=/api

ENV VITE_API_BASE=$VITE_API_BASE

COPY frontend/website/package.json frontend/website/package-lock.json ./frontend/website/
RUN cd frontend/website && npm ci

COPY frontend/website/ ./frontend/website/
COPY frontend/shared/ ./frontend/shared/
RUN cd frontend/website && npm run build


FROM nginx:1.27-alpine

# website static
COPY --from=website_builder /work/frontend/website/dist/ /usr/share/nginx/html/

# nginx conf (can still be overridden by docker-compose volume mount if needed)
COPY nginx/conf.d/default.conf /etc/nginx/conf.d/default.conf


