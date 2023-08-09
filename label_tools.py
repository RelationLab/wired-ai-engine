import csv
from pymilvus import connections, Collection
from base import MILVUS_HOST, MILVUS_PORT, embed, MILVUS_PASS, MILVUS_USER, logger_name
from base.logger_util import LOG

connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, user=MILVUS_USER, password=MILVUS_PASS)
collection = Collection(name="label_info")

logger = LOG.get_logger(logger_name)


def label_info_search(text):
    search_params = {
        "metric_type": "L2"
    }
    results = collection.search(
        data=[embed(text)],
        anns_field="field_search",
        param=search_params,
        limit=4,
        output_fields=['label_name', 'label_desc']
    )
    ret = []
    for hit in results[0]:
        row = []
        row.extend([hit.id, hit.score, hit.entity])
        ret.append(row)
    return ret


def redefine_label_info(label_name, desc):
    results = collection.query(expr=f"label_name in ['{label_name}']", output_fields=["id"])
    if results:
        pks = ",".join([str(result.get('id')) for result in results])
        collection.delete(expr=f"id in [{pks}]")
    vector = embed(desc)
    ins = [[vector], [desc], [label_name]]
    collection.insert(ins)
    collection.load()


def delete_label_info(label_name):
    results = collection.query(expr=f"label_name in ['{label_name}']", output_fields=["id"])
    if results:
        pks = ",".join([str(result.get('id')) for result in results])
        collection.delete(expr=f"id in [{pks}]")


def get_label_info(label_name):
    results = collection.query(expr=f"label_name in ['{label_name}']", output_fields=["label_name", "label_desc"])
    return results


def get_labels_info(label_names: list):
    exp = ",".join([f"'{label_name}'" for label_name in label_names])
    results = collection.query(expr=f"label_name in [{exp}]", output_fields=["label_name", "label_desc"])
    return results


def convert_label_info_to_vector():
    my_file = f"base/data/标签.csv"
    with open(my_file, "r", encoding='utf-8') as f:
        logger.info(f"正在解析文件 {my_file} 导入Milvus向量库...")
        reader = csv.DictReader(f)
        for row in reader:
            desc = row["desc"]
            label_name = row["label_name"]
            delete_label_info(label_name)
            vector = embed(label_name + " means " + desc)
            ins = [[vector], [desc], [label_name]]
            collection.insert(ins)
            logger.info(f"标签{label_name}向量化完成")
    collection.load()
    logger.info("--------------------")
    logger.info("所有文件向量化存储完成!")


if __name__ == "__main__":
    # label_info = get_label_info("Token Legendary Trader")
    # logger.info(label_info)
    label_info = get_labels_info(["Token Legendary Trader", "Legendary"])
    logger.info(label_info)
    # delete_label_info("Token Legendary Trader")
    # redefine_label_info("Token Legendary Trader", "Top 0.1% of traders on all Platform based on volume of ETH and Erc20 Token trades.")
    # convert_label_info_to_vector()
    # result = label_info_search(
    #     "I would like to know the address of eth balances greater than 10 million and held for more than 1 month")
    # print(result)
