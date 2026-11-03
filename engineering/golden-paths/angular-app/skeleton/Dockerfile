FROM node:22-alpine AS build
WORKDIR /workspace
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build && mkdir -p /out && cp -a dist/. /out/

FROM nginxinc/nginx-unprivileged:1.27-alpine
COPY --from=build /out/ /usr/share/nginx/html/
EXPOSE 8080
