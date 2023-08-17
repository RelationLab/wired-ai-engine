import os
import openai
import redis

MILVUS_HOST = os.environ.setdefault('MLIVUS_HOST', '127.0.0.1')
MILVUS_PORT = os.environ.setdefault('MLIVUS_PORT', '19530')
MILVUS_USER = os.environ.setdefault('MLIVUS_USERNAME', '')
MILVUS_PASS = os.environ.setdefault('MLIVUS_PASSWORD', '')
openai.api_key = os.environ.setdefault('OPEN_AI_KEY', '')
OPENAI_EMBED_ENGINE = 'text-embedding-ada-002'
OPENAI_API_BASE = 'https://www.googlex.vip/v1'
openai.api_base = OPENAI_API_BASE
# os.environ["OPENAI_API_KEY"] = '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'
# openai.api_key = os.environ["OPENAI_API_KEY"]

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
