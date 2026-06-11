# syntax=docker/dockerfile:1.7
###############################################################################
# LibraryMind Frontend — Multi-stage Next.js 14 image
#
# Targets:
#   deps    — node_modules only (cached layer)
#   dev     — `next dev` with hot reload (used by docker-compose.dev.yml)
#   builder — production `next build` (standalone output)
#   runtime — minimal production server (default target)
###############################################################################

ARG NODE_VERSION=20-alpine

# =============================================================================
# Dependencies
# =============================================================================
FROM node:${NODE_VERSION} AS deps

WORKDIR /app

ENV NEXT_TELEMETRY_DISABLED=1

COPY package.json package-lock.json ./
RUN npm ci

# =============================================================================
# Development target (hot reload; source is bind-mounted by compose)
# =============================================================================
FROM deps AS dev

ENV NODE_ENV=development \
    # File-watch polling is required for bind mounts on Docker Desktop
    # (Windows/macOS) — inotify events do not cross the VM boundary.
    WATCHPACK_POLLING=true \
    CHOKIDAR_USEPOLLING=true

EXPOSE 3000

CMD ["npm", "run", "dev"]

# =============================================================================
# Production build
# =============================================================================
FROM deps AS builder

# NEXT_PUBLIC_* variables are inlined into the client bundle at BUILD time.
# This must be the URL the *browser* uses to reach the backend.
ARG NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL} \
    NODE_ENV=production

COPY . .
RUN npm run build

# =============================================================================
# Production runtime (Next.js standalone output — no node_modules needed)
# =============================================================================
FROM node:${NODE_VERSION} AS runtime

WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

# Non-root user, mirroring the backend image's security posture.
RUN addgroup --system --gid 1001 nodejs \
    && adduser --system --uid 1001 --ingroup nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD wget -qO /dev/null http://localhost:3000/ || exit 1

CMD ["node", "server.js"]
