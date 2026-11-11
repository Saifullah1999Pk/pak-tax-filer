# The production web server (docs/deployment.md): build the React app once, then serve the
# static files with Caddy, which also forwards /api to the backend and obtains HTTPS itself.

FROM node:26-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
