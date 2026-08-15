FROM node:20.20.1-alpine3.22@sha256:c0a3cda003a229d51f0f118c12a706842f43450ae505ed6825d66b5acdef127f AS base
WORKDIR /app

FROM base AS dependencies
COPY package.json package-lock.json ./
RUN npm ci

FROM dependencies AS dev
COPY . .
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM dependencies AS builder
COPY . .
RUN npm run build

FROM base AS production-dependencies
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=production-dependencies /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
EXPOSE 3000
CMD ["npm", "start"]
