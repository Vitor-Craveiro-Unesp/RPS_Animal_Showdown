FROM node:20-alpine

WORKDIR /app

COPY --chown=node:node package.json package-lock.json ./
COPY --chown=node:node apps/frontend/package.json ./apps/frontend/package.json
USER node
RUN npm ci

COPY --chown=node:node apps/frontend ./apps/frontend

WORKDIR /app/apps/frontend
EXPOSE 3000
CMD ["npm", "run", "dev"]
