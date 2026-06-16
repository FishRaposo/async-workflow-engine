FROM node:20-alpine AS base
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .

FROM base AS dev
EXPOSE 3000
CMD ["npm", "run", "dev"]

FROM base AS builder
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "start"]
