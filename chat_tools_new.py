import csv
import json

import openai
import redis

from base import logger_name, SystemMessage, HumanMessage, AIMessage, ChatResult, redis_pool, FunctionMessage
from base.logger_util import LOG
from table_tools_v2 import table_info_search_v2
from train_tools_v2 import trained_data_search_v2

logger = LOG.get_logger(logger_name)

my_file = "master-data.csv"


def init_master_data():
    master_data_tmp = []
    with open(my_file, "r", encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            symbol = row["symbol"]
            asset = row["asset"]
            statistical_type = row["statistical_type"]
            lable = row["lable"]
            master_data_tmp.append({"symbol": symbol, "asset": asset, "statistical_type": statistical_type, "lable": lable})
    return master_data_tmp


master_data = init_master_data()

sql_chat_functions = [
    {
        "name": "format_sql",
        "description": "format query sql.",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "the syntactically correct PostgreSQL query sql."
                }
            },
            "required": ["sql"]
        }
    },
    {
        "name": "get_sql_sample",
        "description": "get SQL statements for similar question",
        "parameters": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "user's question"
                }
            },
            "required": ["question"]
        }
    },
    {
        "name": "get_master_data",
        "description": "get the exact value of the asset stored in the database",
        "parameters": {
            "type": "object",
            "properties": {
                "asset": {
                    "type": "string",
                    "description": "Asset acronym"
                }
            },
            "required": ["asset"]
        }
    }
]


def get_sample_sql(ask):
    logger.info(f"获取相似性问题的答案:{ask}")
    train_search_data = trained_data_search_v2(ask)
    if train_search_data:
        train_data = train_search_data[0][2]
        return f"question : {train_data.get('question')},answer : {train_data.get('answer')}"


def get_master_data(asset_acronym):
    exact_value = []
    for row in master_data:
        if asset_acronym.lower() == row.get("symbol").lower():
            exact_value.append(row.get("asset"))
    if not exact_value:
        return f"'There is no asset named '{asset_acronym}''"
    return f"'{asset_acronym}' is '{exact_value}'"


def create_msg(tables, question, history):
    messages = [SystemMessage(
        content="You are a PostgreSQL expert. Determine whether the user needs to generate a query sql based on the user's input question. If so, create a syntactically correct PostgreSQL query statement and output the response using the "
                "format_sql function. If the user's question is vague, you can ask the user back to get a more precise description.\nPlease note that some of the user's questions may not match the query criteria for the asset name in the table. "
                "For example, if the user's question is 'eBitcoin' and the database stores 'EBTC', you can use the get_master_data function to get the exact value of the asset stored in the database.\nIf the user needs to generate SQL you should "
                "first use the get_sql_sample function to get the SQL statement for a similar problem to help you understand the user's table structure and data characteristics.\nThe structure of the user's data table is as follows."),
        SystemMessage(content=";".join(tables))]
    for content in history or []:
        messages.append(json.loads(content))
    messages.append(HumanMessage(content=question))
    # messages.append(SystemMessage(content="If your reply contains sql, use the exec_sql function whenever possible"))
    return messages


def sql_query_chat(messages, using_function=False):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0, model="gpt-4", messages=messages)
    if using_function:
        arguments["functions"] = sql_chat_functions
        arguments["function_call"] = "auto"
    response = openai.ChatCompletion.create(**arguments)
    response_message = response["choices"][0]["message"]
    logger.info(json.dumps(response_message))
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    return result


def get_answer_v3(sessionId, ask):
    if not sessionId:
        raise Exception("sessionId不能为空")
    tables_result = table_info_search_v2(ask)
    tables = [table[2] for table in tables_result]
    context = get_recent_content(sessionId)
    messages = create_msg(tables, ask, context)
    logger.info(f"发送给OpenAI的提示词：{messages}")
    result = sql_query_chat(messages, using_function=True)
    logger.info("result:" + str(result))
    question = json.dumps(HumanMessage(ask))
    add_session_content(sessionId, [question])
    times = 0
    while result.function_call:
        times += 1
        if result.function_call.get("name") == "format_sql":
            arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
            sql: str = arguments.get("sql")
            if sql.endswith(";"):
                sql = sql[0:len(sql) - 1]
            add_session_content(sessionId, [json.dumps(FunctionMessage(name="format_sql", content=sql))])
            return {"success": True, "data": sql + ";"}
        elif result.function_call.get("name") == "get_sql_sample":
            arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
            sample_question: str = arguments.get("question")
            sample_sql = get_sample_sql(sample_question)
            sample_msg = FunctionMessage(name="get_sql_sample", content=sample_sql)
            add_session_content(sessionId, [json.dumps(sample_msg)])
            messages.append(sample_msg)
        elif result.function_call.get("name") == "get_master_data":
            arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
            asset: str = arguments.get("asset")
            exact_value = get_master_data(asset)
            master_data_msg = FunctionMessage(name="get_master_data", content=exact_value)
            add_session_content(sessionId, [json.dumps(master_data_msg)])
            messages.append(master_data_msg)
        result = sql_query_chat(messages, using_function=times < 4)
    add_session_content(sessionId, [json.dumps(AIMessage(result.content))])
    return {"success": False, "data": result.content}


def get_recent_content(sessionId, limit=10):
    conn = redis.Redis(connection_pool=redis_pool)
    result = conn.lrange(f"new_query::session_context::{sessionId}", 0, limit - 1)
    conn.close()
    result.reverse()
    return result


def add_session_content(sessionId, messages):
    conn = redis.Redis(connection_pool=redis_pool)
    for mes in messages:
        conn.lpush(f"new_query::session_context::{sessionId}", mes)
    conn.expire(f"new_query::session_context::{sessionId}", 60 * 60)
    conn.close()


if __name__ == "__main__":
    # 有上下文
    # test1 = get_answer_v3('12345', "hello")
    # logger.info(test1)
    # test2 = get_answer_v3('23456', "Can you help me find some transactions on the Uniswap platform with a transaction count of 600?")
    # logger.info(test2)
    # test3 = get_answer_v3('12345', "max_value_of_system is 500")
    # logger.info(test3)
    # test1 = get_answer_v3('12345', "good")
    # logger.info(test1)
    test4 = get_answer_v3('34567', "Can you recommend me some addresses with a balance of more than 100 ShareToken	")
    logger.info(test4)
    # test1 = get_answer('10087', 'hello,how old are you')
    # test1 = get_answer('10087', 'max_value_of_system means 600')
    # test1 = get_answer('10087', 'Can you help me find some transactions on the Uniswap platform with a transaction count of max_value_of_system?')
