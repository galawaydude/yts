# --- Stage 1: Build the React App ---
FROM node:18-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci
COPY . .

# We'll provide the production API URL when we build
ARG REACT_APP_API_URL
ENV REACT_APP_API_URL=$REACT_APP_API_URL

RUN npm run build

# --- Stage 2: An empty container to hold the build files ---
FROM alpine:latest
COPY --from=build /app/build /usr/share/nginx/html