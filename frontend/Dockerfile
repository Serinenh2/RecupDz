# ── Build stage ──────────────────────────────────────────
FROM node:20-alpine AS builder

ARG VITE_SENTRY_DSN
ENV VITE_SENTRY_DSN=$VITE_SENTRY_DSN

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --legacy-peer-deps && npm cache clean --force

COPY . .
RUN npx vite build

# ── Nginx stage ─────────────────────────────────────────
FROM nginx:1.25-alpine AS runtime

# Copy built assets
COPY --from=builder /app/dist /usr/share/nginx/html

# Security: non-root user
RUN chown -R nginx:nginx /usr/share/nginx/html && \
    chmod -R 755 /usr/share/nginx/html

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:80/ || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
