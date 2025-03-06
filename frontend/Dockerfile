# Стадія збірки
FROM node:18-alpine as build

WORKDIR /app

# Копіювання package.json та package-lock.json
COPY package*.json ./

# Встановлення залежностей
RUN npm ci

# Копіювання коду
COPY . .

# Збірка проекту
RUN npm run build

# Стадія запуску
FROM nginx:alpine

# Копіювання збудованого проекту
COPY --from=build /app/build /usr/share/nginx/html

# Налаштування Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Відкриття порту
EXPOSE 80

# Запуск Nginx
CMD ["nginx", "-g", "daemon off;"]