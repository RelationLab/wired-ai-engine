import csv
from pymilvus import connections, Collection
from base import MILVUS_HOST, MILVUS_PORT, embed, MILVUS_PASS, MILVUS_USER, logger_name
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)

connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, user=MILVUS_USER, password=MILVUS_PASS)
collection = Collection(name="table_info_new")


def table_info_search(text):
    search_params = {
        "metric_type": "L2"
    }
    results = collection.search(
        data=[embed(text)],
        anns_field="field_search",
        param=search_params,
        limit=4,
        output_fields=['table_desc']
    )
    ret = []
    for hit in results[0]:
        row = []
        row.extend([hit.id, hit.score, hit.entity.get('table_desc')])
        ret.append(row)
    return ret


def redefine_table_info(table_name, desc):
    results = collection.query(expr=f"table_name in ['{table_name}']", output_fields=["id"])
    if results:
        pks = ",".join([str(result.get('id')) for result in results])
        collection.delete(expr=f"id in [{pks}]")
    vector = embed(desc)
    ins = [[vector], [desc], [table_name]]
    collection.insert(ins)
    collection.load()


def delete_table_info(table_name):
    results = collection.query(expr=f"table_name in ['{table_name}']", output_fields=["id"])
    if results:
        pks = ",".join([str(result.get('id')) for result in results])
        collection.delete(expr=f"id in [{pks}]")


def get_table_info(table_name):
    results = collection.query(expr=f"table_name in ['{table_name}']", output_fields=["table_name", "table_desc"])
    return results


def convert_table_info_to_vector():
    my_file = f"base/data/表结构-1.9.csv"
    with open(my_file, "r", encoding='utf-8') as f:
        logger.info(f"正在解析文件 {my_file} 导入Milvus向量库...")
        reader = csv.DictReader(f)
        for row in reader:
            desc = row["desc"]
            table_name = row["table_name"]
            delete_table_info(table_name)
            vector = embed(desc)
            ins = [[vector], [desc], [table_name]]
            collection.insert(ins)
    collection.load()
    logger.info("--------------------")
    logger.info("所有文件向量化存储完成!")


if __name__ == "__main__":
    table_info = get_table_info("dex_tx_count_summary")
    logger.info(table_info)
    # delete_table_info("dds")
    # redefine_table_info("dds", "你好呀，，，地球人")
    # convert_table_info_to_vector()
    # result = table_info_search(
    #     "I would like to know the address of eth balances greater than 10 million and held for more than 1 month")
    # print(result)
