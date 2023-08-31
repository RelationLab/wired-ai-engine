import csv
import json
from time import sleep

import openai
import redis

from base import logger_name, SystemMessage, HumanMessage, AIMessage, ChatResult, redis_conn, FunctionMessage
from base.logger_util import LOG
from chat_tools_new import master_data
from train_tools_v2 import trained_data_search_v2

logger = LOG.get_logger(logger_name)

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
    }
]


def get_table_info():
    return read_all_text("table_info.txt")


def get_prompt_info():
    return read_all_text("prompt.txt")


def get_sample_sql(ask):
    logger.info(f"获取相似性问题的答案:{ask}")
    train_search_data = trained_data_search_v2(ask)
    if train_search_data:
        train_data = train_search_data[0][2]
        return f"""Here is an example question and the corresponding SQL query statement for reference.
        question : [{train_data.get('question')}],
        answer : [{train_data.get('answer')}].
        Please note that this example is for reference only, and should not be overly relied upon."""


def get_master_data(asset_acronym):
    exact_value = []
    for row in master_data:
        match = asset_acronym.lower().replace(" ", "")
        if row.get("symbol").lower().replace(" ", "").find(match) >= 0 or row.get("asset").lower().replace(" ", "").find(match) >= 0:
            exact_value.append(row.get("asset"))
    if not exact_value:
        return f"If the asset name in the user's question is '{asset_acronym}', inform them that there is no such asset in the database."
    return f"If the user's query asset name is '{asset_acronym}', tell them that there are many similar assets in the database, such as '{exact_value}', and then ask which one they need."


def sql_query_chat(messages, using_function=False):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0, model="gpt-4", messages=messages)
    if using_function:
        arguments["functions"] = sql_chat_functions
        arguments["function_call"] = "auto"
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    return result


def read_all_text(file_path):
    with open(file_path, "r", encoding='utf-8') as file:
        txt = file.read()
        return txt


def create_msg(tableInfo, question, history, check_result):
    sys_msg = get_prompt_info()
    sys_msg = sys_msg + tableInfo
    if check_result.get("success") and check_result.get("need_sql"):
        sample_sql = get_sample_sql(question)
        sys_msg = sys_msg + sample_sql
        if check_result.get("asset"):
            asset = check_result.get("asset")
            asset_master_data = get_master_data(asset)
            sys_msg = sys_msg + asset_master_data
    messages = [SystemMessage(content=sys_msg)]
    for content in history or []:
        messages.append(json.loads(content))
    messages.append(HumanMessage(content=question))
    return messages


def get_answer_v4(sessionId, ask):
    if not sessionId:
        raise Exception("sessionId不能为空")
    tables = get_table_info()
    context = get_recent_content(sessionId)
    check_result = check_sql_question(ask)
    # 暂停几秒，防止限流
    sleep(3)
    messages = create_msg(tables, ask, context, check_result)
    logger.info(f"发送给OpenAI的提示词：{messages}")
    result = sql_query_chat(messages, using_function=True)
    logger.info("result:" + str(result))
    tmp_session_content = [json.dumps(HumanMessage(ask))]
    times = 0
    if result.function_call:
        times += 1
        if result.function_call.get("name") == "format_sql":
            arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
            sql: str = arguments.get("sql")
            if sql.endswith(";"):
                sql = sql[0:len(sql) - 1]
            tmp_session_content.append(json.dumps(FunctionMessage(name="format_sql", content=sql)))
            add_session_content(sessionId, tmp_session_content)
            return {"success": True, "data": sql + ";"}
    tmp_session_content.append(json.dumps(AIMessage(result.content)))
    add_session_content(sessionId, tmp_session_content)
    return {"success": False, "data": result.content}


def check_sql_question(content):
    messages = [SystemMessage(content="""
     You are a PostgreSQL expert.
     Based on your knowledge of digital currencies or virtual assets, determine whether the user needs to generate SQL based on their question.
     If the user's question includes asset information, extract the name of the asset.
     Then call the format_answer function for output."""), HumanMessage(content=content)]
    function = [
        {
            "name": "format_answer",
            "description": "Format ai output",
            "parameters": {
                "type": "object",
                "properties": {
                    "need_sql": {
                        "type": "string",
                        "description": "Whether the user needs to generate SQL,'YES' or 'NO'.",
                        "enum": ["YES", "NO"]
                    },
                    "asset": {
                        "type": "string",
                        "description": "The asset name contained in the extracted user's question."
                    }
                },
                "required": ["need_sql"]
            }
        }
    ]

    logger.info("判断用户输入是否需要生成SQL，请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0, model="gpt-4", messages=messages, functions=function, function_call="auto")
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
    response_result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    result = {"success": False}
    if response_result.function_call:
        arguments = json.loads(response_result.function_call.get("arguments").replace('\n', ' '))
        asset: str = arguments.get("asset")
        needs_sql: bool = "YES" == arguments.get("need_sql")
        result["success"] = True
        result["need_sql"] = needs_sql
        result["asset"] = asset
    return result


def get_recent_content(sessionId, limit=10):
    result = redis_conn().lrange(f"new_query_v4::session_context::{sessionId}", 0, limit - 1)
    redis_conn().close()
    result.reverse()
    return result


def add_session_content(sessionId, messages):
    for mes in messages:
        redis_conn().lpush(f"new_query_v4::session_context::{sessionId}", mes)
    redis_conn().expire(f"new_query_v4::session_context::{sessionId}", 60 * 60)
    redis_conn().close()


if __name__ == "__main__":
    # 有上下文
    test1 = get_answer_v4('12345', "hello")
    logger.info(test1)
    test2 = get_answer_v4('23456', "Can you help me find some transactions on the Uniswap platform with a transaction count of 600?")
    logger.info(test2)
    test1 = get_answer_v4('12345', "good")
    logger.info(test1)
    test4 = get_answer_v4('34567', "Can you recommend me some addresses with a balance of more than 100 ShareToken")
    logger.info(test4)
    test1 = get_answer_v4('10087', 'hello,how old are you')
    logger.info(test1)
    test1 = get_answer_v4('10087', 'Can you help me find some transactions on the Uniswap platform with a transaction count of max_value_of_system?')
    logger.info(test1)
    test1 = get_answer_v4('10087', 'max_value_of_system means 600')
