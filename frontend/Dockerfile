# 阶段一：node 构建 dist（API 走 nginx 同源反代，无需 VITE_ 构建期变量）
FROM node:20 AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm config set registry https://registry.npmmirror.com && npm ci
COPY . .
RUN npm run build

# 阶段二：nginx 托管静态产物 + 反代后端
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
