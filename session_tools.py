import time

from pymilvus import connections, Collection

from base import MILVUS_HOST, MILVUS_PORT, MILVUS_PASS, MILVUS_USER, logger_name
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)

connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, user=MILVUS_USER, password=MILVUS_PASS)
collection = Collection(name="session_context")


def get_recent_content(session_id, limit=10):
    search_params = {
        "metric_type": "L2"
    }
    now = time.time() * 10
    v1, v2 = convert_vector(now)
    results = collection.search(
        data=[[v1, v2]],
        anns_field="time",
        param=search_params,
        expr=f"session_id in ['{session_id}']",
        limit=limit,
        output_fields=['session_id', 'content']
    )
    result = results[0]
    length = len(result)
    ret = []
    for index in range(length):
        hit = results[0][length - 1 - index]
        row = []
        row.extend([hit.id, hit.score, hit.entity])
        ret.append(row)
    return ret


def add_session_content(session_id, content):
    now = time.time() * 10
    v1, v2 = convert_vector(now)
    data = [[[v1, v2]], [session_id], [content]]
    print(data)
    collection.insert(data)


def convert_vector(data):
    v1, v2 = int(int(data) / 1000000), (int(data) % 1000000) / 1000000,
    return v1, v2


if __name__ == "__main__":
    collection.delete(expr="id in [442509030495100194,442509030495100218]")

    # collection.delete(expr="id in ['442509030495100176','442509030495100178','442509030495100180','442509030495100182','442509030495100184','442509030495100186','442509030495100188','442509030495100190','442509030495100192']")
    # for i in range(10):
    #     add_session_content('hello-world', f"你好呀,你好呀啊啊啊{i}")
    #     time.sleep(3)
    # result = get_recent_content('hello-world', limit=5)
    # print(result)
