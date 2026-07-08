# syntax=docker/dockerfile:1
# ---------------------------------------------------------------------------
# Versos frontend — Next.js 16 standalone. Multi-stage: build, then a tiny
# runtime image that runs the minimal `node server.js` bundle.
# ---------------------------------------------------------------------------
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV DOCKER_BUILD=1
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
# BACKEND_URL is injected at runtime → the App Runner/Amplify URL of the backend.
# The Next proxy (app/api/[...path]/route.ts) reads it; defaults to localhost:8090.

RUN useradd --create-home --uid 1001 nextjs
# standalone output does NOT include public/ or .next/static — copy them explicitly.
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nextjs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nextjs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
