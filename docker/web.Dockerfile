FROM node:20-alpine

WORKDIR /app/ai_quant/web

COPY ai_quant/web/package.json ai_quant/web/package-lock.json ./
RUN npm ci

COPY ai_quant/web ./

EXPOSE 5173

ENV VITE_DEV_PROXY_TARGET=http://backend:8000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
