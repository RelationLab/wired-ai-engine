import os
import openai
import redis

MILVUS_HOST = '127.0.0.1'
# MILVUS_PORT = 19530
# MILVUS_USER = "wired-milvus"
# MILVUS_PASS = "eqS9TjC7YbaviH9VdKTv"
# MILVUS_HOST = '192.168.0.102'
# MILVUS_HOST = '10.5.0.2'
MILVUS_PORT = 19530
MILVUS_USER = ""
MILVUS_PASS = ""
OPENAI_EMBED_ENGINE = 'text-embedding-ada-002'
OPENAI_API_BASE = 'https://www.googlex.vip/v1'
openai.api_base = OPENAI_API_BASE
os.environ["OPENAI_API_KEY"] = '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'
openai.api_key = os.environ["OPENAI_API_KEY"]

logger_name = "Wired"

redis_pool = redis.ConnectionPool(max_connections=100, host='10.5.0.2',
                                  port=6379,
                                  db=1,
                                  password='123456',
                                  decode_responses=True)


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
        engine=OPENAI_EMBED_ENGINE)["data"][0]["embedding"]
