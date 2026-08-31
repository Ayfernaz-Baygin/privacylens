# Build context is frontend/ (see compose.yaml) -- self-contained,
# no repo-root import-path concerns like the backend has.

FROM node:22-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Vite embeds this at BUILD time into the static JS bundle -- it must
# be a URL the browser (running on the host, not inside a container)
# can reach, e.g. http://localhost:8000, never a Compose service
# hostname like http://backend:8000.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

RUN npm run build

# Stock nginx image/config: this is a single-page app with no
# client-side routing, so the default "serve dist/index.html and
# static assets" behavior needs no custom nginx.conf.
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
