FROM node:22-slim

WORKDIR /app

COPY package.json package-lock.json tsconfig.json ./
RUN npm ci

COPY src ./src
RUN npm run build && npm prune --omit=dev

ENTRYPOINT ["node", "dist/cli.js"]
