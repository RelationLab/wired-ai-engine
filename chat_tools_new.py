import csv
import json

import openai
import redis

from base import logger_name, SystemMessage, HumanMessage, AIMessage, ChatResult, redis_conn, FunctionMessage, get_api_key
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
        return f"question : [{train_data.get('question')}],answer : [{train_data.get('answer')}].\nPlease note that this example is for reference only, and should not be overly relied upon."


def get_master_data(asset_acronym):
    if not asset_acronym:
        return f"asset can not be None"
    exact_value = []
    for row in master_data:
        match = asset_acronym.lower().replace(" ", "")
        if row.get("symbol").lower().replace(" ", "").find(match) >= 0 or row.get("asset").lower().replace(" ", "").find(match) >= 0:
            exact_value.append(row.get("asset"))
    if not exact_value:
        return f"There is no asset named '{asset_acronym}'"
    return f"'{asset_acronym}' is '{exact_value}'"


def create_msg(tables, question, history):
    messages = [
        SystemMessage(content="""
        As a PostgreSQL expert, please follow the rules below to provide answers to users:
        1: If a user asks a question that violates laws and common ethics, respond politely.
        2: If the question is praising,complimenting, or derogatory, respond politely.
        3: Based on the above rules, after receiving an input question, determine whether the user needs to generate an SQL statement. If necessary, create a syntactically correct PostgreSQL query statement and use the format_sql function to output the response. If the user's question is ambiguous, you can ask the user for a more accurate description. Please note that some user questions may not match the query conditions of the asset names in the table. For example, if the user's question is "EBTC", but the database stores it as "eBitcoin", you can use the get_master_data function to retrieve the accurate value of the asset stored in the database. When you have multiple accurate values for assets, confirm which one to choose by asking the user. If the user needs to generate an SQL statement,use the get_sql_sample function to retrieve SQL statement examples for similar questions to help you understand the table structure and data characteristics. If the user's question involves the "holder" of assets, add a condition to the returned SQL statement where balance_count is greater than 0. When encountering percentages, such as 0.5%, it corresponds to 0.005, and you should interpret it based on this rule. Finally, handle the generated SQL statement as a whole and group the address field using the group by clause, for example: select address from (select address from table_name) a1 group by address.
        4: Based on the  rules mentioned in 1, 2, and 3, if there are multiple input questions, again determine if there is any connection between these questions. If there is no connection, respond according to the last question. If there is a connection, provide an accurate answer with contextual information. Do not output fields randomly.
        5: When the user's question appears web3 industry such expressions, please ignore such information, because the platform is the default for the digital currency industry services, for the use of the table, please focus on the table to explain the information reference 
        """),
        SystemMessage(content="The structure of the user's data table is as follows:\n" + ";".join(tables))]
    for content in history or []:
        messages.append(json.loads(content))
    messages.append(HumanMessage(content=question))
    messages.append(SystemMessage(content="If your response contains SQL statements, please use the 'format_sql' function to format the output."))
    return messages


def sql_query_chat(messages, using_function=False):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0, model="gpt-4", messages=messages, api_key=get_api_key())
    if using_function:
        arguments["functions"] = sql_chat_functions
        arguments["function_call"] = "auto"
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
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
    tmp_session_content = [json.dumps(HumanMessage(ask))]
    times = 0
    while result.function_call:
        times += 1
        if result.function_call.get("name") == "format_sql":
            arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
            sql: str = arguments.get("sql")
            if sql.endswith(";"):
                sql = sql[0:len(sql) - 1]
            tmp_session_content.append(json.dumps(FunctionMessage(name="format_sql", content=sql)))
            add_session_content(sessionId, tmp_session_content)
            return {"success": True, "data": sql + ";"}
        elif result.function_call.get("name") == "get_sql_sample":
            arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
            sample_question: str = arguments.get("question")
            sample_sql = get_sample_sql(sample_question)
            sample_msg = FunctionMessage(name="get_sql_sample", content=sample_sql)
            tmp_session_content.append(json.dumps(sample_msg))
            messages.append(sample_msg)
        elif result.function_call.get("name") == "get_master_data":
            arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
            asset: str = arguments.get("asset")
            exact_value = get_master_data(asset)
            master_data_msg = FunctionMessage(name="get_master_data", content=exact_value)
            tmp_session_content.append(json.dumps(master_data_msg))
            messages.append(master_data_msg)
        result = sql_query_chat(messages, using_function=times < 4)
    tmp_session_content.append(json.dumps(AIMessage(result.content)))
    add_session_content(sessionId, tmp_session_content)
    return {"success": False, "data": result.content}


def get_recent_content(sessionId, limit=10):
    result = redis_conn().lrange(f"new_query::session_context::{sessionId}", 0, limit - 1)
    redis_conn().close()
    result.reverse()
    return result


def add_session_content(sessionId, messages):
    for mes in messages:
        redis_conn().lpush(f"new_query::session_context::{sessionId}", mes)
    redis_conn().expire(f"new_query::session_context::{sessionId}", 60 * 60)
    redis_conn().close()


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
