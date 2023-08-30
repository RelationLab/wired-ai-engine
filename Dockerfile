FROM python:3.9
MAINTAINER ccc-ju "ccc-ju@outlook.com"

ENV TZ=Asia/Shanghai
RUN set -eux; \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime; \
    echo $TZ > /etc/timezone

WORKDIR /app

# 复制项目文件到镜像中
COPY .. /app

# 安装项目依赖
RUN pip install --no-cache-dir -r requirements.txt

# 暴露应用程序使用的端口, 此处无需修改, 修改docker-compose中映射端口即可
EXPOSE 8765

# 运行应用程序
CMD ["python", "web.py"]
