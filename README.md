# wired-ai
### 部署方式
### 参数说明

```{MLIVUS_IP}```: mlivus向量数据库连接地址，默认```127.0.0.1```

```{MLIVUS_PORT}```: mlivus向量数据库端口，默认```19530```

```{MLIVUS_USERNAME}```: mlivus向量数据用户名，默认```''```

```{MLIVUS_PASSWORD}```: mlivus向量数据用户名，默认```''```

```{OPEN_AI_KEY}```: openai的key, <font color="red">(*保存好openai的key)</font>


#### 独立运行
从git 拉取项目后, 进入base文件夹下的```__init__.py```
修改如下参数：
```python
MILVUS_HOST = os.environ.setdefault('MLIVUS_HOST', '{MLIVUS_IP}')
MILVUS_PORT = os.environ.setdefault('MLIVUS_PORT', '{MLIVUS_PORT}')
MILVUS_USER = os.environ.setdefault('MLIVUS_USERNAME', '{MLIVUS_USERNAME}')
MILVUS_PASS = os.environ.setdefault('MLIVUS_PASSWORD', '{MLIVUS_PASSWORD}')
openai.api_key = os.environ.setdefault('OPEN_AI_KEY', '{OPEN_AI_KEY}')
```

服务端口号修改：```web.py```中```uvicorn.run(app, host="0.0.0.0", port=8765)```

### docker-compose部署

启动参数：```docker-compose up -d --build```

```yaml
version: '3'
services:
  app:
    build:
      context: .
      dockerfile: ./Dockerfile
    # 容器名称
    container_name: wired-ai
    # 环境参数（参数说明）
    environment:
      - MLIVUS_HOST=127.0.0.1
      - MLIVUS_PORT=19530
      - OPEN_AI_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
    ports:
      - 8765:8765
    logging:
        driver: "json-file"
        options:
            max-size: "5g"
    volumes:
      # 日志映射目录
      - "/Users/laobinggun/logs:/app/log"
```

environment中参数参考```参数说明```
