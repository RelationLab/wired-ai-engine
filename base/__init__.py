import os
import openai
import redis
from rediscluster import RedisCluster
from rediscluster.connection import *

MILVUS_HOST = os.environ.setdefault('MILVUS_HOST', '127.0.0.1')
MILVUS_PORT = os.environ.setdefault('MILVUS_PORT', '19530')
MILVUS_USER = os.environ.setdefault('MILVUS_USERNAME', 'wired-milvus')
MILVUS_PASS = os.environ.setdefault('MILVUS_PASSWORD', 'eqS9TjC7YbaviH9VdKTv')
REDIS_MODE = os.environ.setdefault('REDIS_IS_CLUSTER', 'false')
REDIS_HOST = os.environ.setdefault('REDIS_HOST', '10.5.0.2')
REDIS_PORT = os.environ.setdefault('REDIS_PORT', '6379')
REDIS_PASSWORD = os.environ.setdefault('REDIS_PASSWORD', '123456')
openai.api_key = os.environ.setdefault('OPEN_AI_KEY', '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;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')
OPENAI_EMBED_ENGINE = 'text-embedding-ada-002'
OPENAI_API_BASE = 'https://www.googlex.vip/v1'
openai.api_base = OPENAI_API_BASE
# os.environ["OPENAI_API_KEY"] = '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'
# os.environ["OPENAI_API_KEY"] = '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'
# openai.api_key = os.environ["OPENAI_API_KEY"]


logger_name = "Wired"

startup_nodes = [
    {"host": REDIS_HOST, "port": REDIS_PORT},
]

index = 0


def get_api_key():
    keys = openai.api_key.split(";")
    global index
    index = index + 1
    return keys[index % len(keys)]


def redis_conn():
    if REDIS_MODE == 'true':
        conn = RedisCluster(connection_class=SSLClusterConnection, password=REDIS_PASSWORD,
                            startup_nodes=startup_nodes, skip_full_coverage_check=True)
        return conn
    else:
        redis_pool = redis.ConnectionPool(max_connections=100,
                                          host=REDIS_HOST,
                                          port=REDIS_PORT,
                                          db=1,
                                          password=REDIS_PASSWORD,
                                          decode_responses=True)
        conn = redis.Redis(connection_pool=redis_pool)
        return conn


def SystemMessage(content):
    return {"role": "system", "content": content}


def HumanMessage(content):
    return {"role": "user", "content": content}


def FunctionMessage(name, content):
    return {"role": "function", "content": content, "name": name}


def AIMessage(content):
    return {"role": "assistant", "content": content}


class ChatResult:

    def __init__(self, role, content, function_call):
        self.role = role
        self.content = content
        self.function_call = function_call


def embed(txt):
    return openai.Embedding.create(
        input=txt,
        engine=OPENAI_EMBED_ENGINE, api_key=get_api_key())["data"][0]["embedding"]
