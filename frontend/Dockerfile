FROM docker.1ms.run/node:20-alpine

WORKDIR /app

# 复制package文件
COPY package*.json ./

# 安装依赖
RUN npm config set registry https://registry.npmmirror.com && npm install

# 复制源代码
COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
