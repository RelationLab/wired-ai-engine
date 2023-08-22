import os
import openai
import redis

MILVUS_HOST = os.environ.setdefault('MLIVUS_HOST', '127.0.0.1')
MILVUS_PORT = os.environ.setdefault('MLIVUS_PORT', '19530')
MILVUS_USER = os.environ.setdefault('MLIVUS_USERNAME', 'wired-milvus')
MILVUS_PASS = os.environ.setdefault('MLIVUS_PASSWORD', 'eqS9TjC7YbaviH9VdKTv')
REDIS_HOST = os.environ.setdefault('REDIS_HOST', '10.5.0.2')
REDIS_PORT = os.environ.setdefault('REDIS_PORT', '6379')
REDIS_PASSWORD = os.environ.setdefault('REDIS_PASSWORD', '123456')
openai.api_key = os.environ.setdefault('OPEN_AI_KEY', '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')
OPENAI_EMBED_ENGINE = 'text-embedding-ada-002'
OPENAI_API_BASE = 'https://www.googlex.vip/v1'
openai.api_base = OPENAI_API_BASE
# os.environ["OPENAI_API_KEY"] = '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'
# os.environ["OPENAI_API_KEY"] = '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'
# openai.api_key = os.environ["OPENAI_API_KEY"]

logger_name = "Wired"

redis_pool = redis.ConnectionPool(max_connections=100, host=REDIS_HOST,
                                  port=REDIS_PORT,
                                  db=1,
                                  password=REDIS_PASSWORD,
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
