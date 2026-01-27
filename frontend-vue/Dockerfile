# Build stage
FROM node:20-alpine AS build
WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build argument for API URL (must be set at build time for Vite)
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL

# Build the application
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy nginx configuration template
COPY nginx.conf /etc/nginx/templates/default.conf.template

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Railway uses dynamic PORT - nginx:alpine supports envsubst automatically
# when using /etc/nginx/templates/*.template files
ENV PORT=80

# Expose the port
EXPOSE ${PORT}

# Use shell to substitute PORT and start nginx
CMD ["/bin/sh", "-c", "envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf && nginx -g 'daemon off;'"]
