from pymilvus import connections, Collection
import csv
from base import MILVUS_HOST, MILVUS_PORT, embed, MILVUS_USER, MILVUS_PASS, logger_name
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)

connections.connect(host=MILVUS_HOST, port=MILVUS_PORT, user=MILVUS_USER, password=MILVUS_PASS)
collection = Collection(name="trained_sql_data_v2")


def train_v2(ask, answer, cover_similar=False, cover_similar_score=0.9):
    """
    将常见的问题向量化，作为本地知识库
    :param ask: 问题
    :param answer: 答案
    :param cover_similar 相似性的问题是否覆盖
    :param cover_similar_score 覆盖相似度阈值
    :return:
    """
    if cover_similar:
        results = find_similar_question_v2(ask, score=cover_similar_score, limit=100)
        ids = [str(result[0]) for result in results or []]
        pks = ",".join(ids)
        collection.delete(expr=f"id in [{pks}]")
    search_vector = embed(ask)
    ins = [[search_vector], [ask], [answer]]
    collection.insert(ins)
    collection.load()


def find_similar_question_v2(question, score=0.8, limit=10):
    """
    相似性问题搜索
    :param question: 问题
    :param score: 相似度
    :param limit: 限制条数
    :return:
    """
    search_params = {
        "metric_type": "L2"
    }
    results = collection.search(
        data=[embed(question)],
        anns_field="field_search",
        param=search_params,
        limit=limit,
        output_fields=['question', 'answer']
    )
    ret = []
    for hit in results[0]:
        if hit.score <= 1 - score:
            row = []
            row.extend([hit.id, hit.score, hit.entity])
            ret.append(row)
    return ret


def trained_data_search_v2(ask):
    search_params = {
        "metric_type": "L2"
    }
    results = collection.search(
        data=[embed(ask)],
        anns_field="field_search",
        param=search_params,
        limit=1,
        output_fields=['question', 'answer', 'id']
    )
    ret = []
    for hit in results[0]:
        row = []
        row.extend([hit.id, hit.score, hit.entity])
        ret.append(row)
    return ret

def convert_train_data_to_vector():
    my_file = f"base/data/sql样例v.1.1.csv"
    with open(my_file, "r", encoding='utf-8') as f:
        logger.info(f"正在解析文件 {my_file} 导入Milvus向量库...")
        # delete exist data
        delete_all_data()
        reader = csv.DictReader(f)
        for row in reader:
            question = row["question"]
            answer = row["answer"]
            vector = embed(question)
            ins = [[vector], [question], [answer]]
            collection.insert(ins)
    collection.load()
    logger.info("--------------------")
    logger.info("所有文件向量化存储完成!")


def get_all_data():
    results = collection.query(expr="id>0", output_fields=["id"])
    print(results)
    return results
    # if results:
    #     pks = ",".join([str(result.get('id')) for result in results])
    #     collection.delete(expr=f"id in [{pks}]")

def delete_all_data():
    results = get_all_data()
    if results:
        pks = ",".join([str(result.get('id')) for result in results])
        collection.delete(expr=f"id in [{pks}]")

if __name__ == "__main__":
    # collection.load()
    # train_v2(
    #     ask="Can you recommend me some addresses with a balance of more than $1 million ETH",
    #     answer="select \
    #              distinct address \
    #             from \
    #              token_balance_volume_usd \
    #             where \
    #              token = 'eth' \
    #              and balance_usd >= 1000000;",
    #     cover_similar=True)
    convert_train_data_to_vector()
    # result = find_similar_question(question="find a transactions on the Uniswap platform with a transaction count of 10?")
    # logger.info(result[0][2].get("question"), result[0][2].get("answer"))
    # trained_data_search_v2("Is there any user who has $100-$1,000 volume of trades on all Decentralized Exchanges?");
