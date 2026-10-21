FROM node:24-alpine AS dependencies
WORKDIR /app
RUN npm install --global npm@11.12.1 --ignore-scripts
COPY package.json package-lock.json .npmrc ./
RUN npm ci --ignore-scripts

# Hot-reloading Vite server, used by docker-compose.
FROM dependencies AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM dependencies AS build
COPY . .
# VITE_* vars are inlined at build time.
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
