"""
测试工具
"""
import logging

from pymilvus import connections, Collection
from base import MILVUS_HOST, MILVUS_PORT, MILVUS_USER, MILVUS_PASS, logger_name
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)

connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, user=MILVUS_USER, password=MILVUS_PASS)
collection = Collection(name="trained_sql_data_v2")


def get_all_data():
    results = collection.query(expr="id>0", output_fields=["id"])
    logging.info(results)
    print(results)
    return results

if __name__ == "__main__":
    get_all_data()
