# frontend/Dockerfile
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./
RUN npm ci --only=production

# Copy app files
COPY . .

# Build the app
RUN npm run build

# Production stage
FROM node:18-alpine

WORKDIR /app

# Copy from builder
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

# Set port
ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
```

### Option 3: Use Nixpacks (Recommended)
Just remove any Dockerfile references and let Railway handle it:

1. In Railway Dashboard for frontend service:
   - **Root Directory**: `/frontend`
   - **Build Command**: Leave empty
   - **Start Command**: Leave empty
   - **Environment Variables**:
```
     NEXT_PUBLIC_API_URL=https://seo-manager-production.up.railway.app
