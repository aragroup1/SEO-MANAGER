# frontend/Dockerfile
FROM node:18-alpine

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci

# Copy application
COPY . .

# Build application
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
