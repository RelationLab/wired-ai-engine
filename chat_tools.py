import json

import openai
import redis

from base import logger_name, SystemMessage, HumanMessage, AIMessage, ChatResult, redis_pool
from base.logger_util import LOG
from table_tools import table_info_search
from table_tools_v2 import table_info_search_v2
from train_tools import trained_data_search
from train_tools_v2 import trained_data_search_v2

logger = LOG.get_logger(logger_name)


# currentSessionTable = {}


def get_session_table(sessionId):
    conn = redis.Redis(connection_pool=redis_pool)
    result = conn.get(f"session_table_{sessionId}")
    conn.close()
    return result


def set_session_table(sessionId, table):
    conn = redis.Redis(connection_pool=redis_pool)
    result = conn.set(f"session_table_{sessionId}", table, ex=60 * 60)
    conn.close()
    return result


def create_msg(tables, example, question, history, isSqlQuestion, sessionId):
    messages = [SystemMessage(
        content="You are a PostgreSQL expert. Please give a polite answer to a question that violates the law and universal morality, or if it is praise, commendation, or denigration, please give a polite answer to that question as well; other "
                "than that, given an input question, determine if the user needs to generate a sql, and if they do, create a syntactically correct PostgreSQL query, if they don't, answer the question as normal.")]
    # messages.append(SystemMessage(content="If you know the answer then reply SQL:[your sql answer here] \n\n Don't write explanations and any other information in your responses \n"))
    # "Otherwise tell the user what additional information you need.\n\n Streamline your answers as much as possible"))
    for content in history or []:
        messages.append(json.loads(content))

    if isSqlQuestion:
        messages.append(HumanMessage(content="The relevant table structure is as follows:" + ";".join(tables) + ".\n"))
        messages.append(HumanMessage(content=f"This is a question and sql example: the question is '{example.get('question')}' and the query SQL is '{example.get('answer')}'.\n"))
    else:
        sessionTableStr = get_session_table(sessionId)
        if sessionId and sessionTableStr:
            sessionTable = json.loads(sessionTableStr)
            sessionExample = sessionTable.get("example")
            sessionTables = sessionTable.get("tables")
            messages.append(HumanMessage(content=f"The relevant table structure is as follows:" + ";".join(sessionTables) + ".\n"))
            messages.append(SystemMessage(content=f"This is a question and sql example: the question is '{sessionExample.get('question')}' and the query SQL is '{sessionExample.get('answer')}'.\n"))

    messages.append(HumanMessage(content=question))
    messages.append(SystemMessage(content="If your reply contains sql, use the exec_sql function whenever possible"))

    return messages


sql_exec_functions = [
    {
        "name": "exec_sql",
        "description": "execute query sql.",
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


def sql_query_chat(messages, using_function=False):
    logger.info("请求OPENAI" + json.dumps(messages))

    arguments = dict(temperature=0, model="gpt-4", messages=messages)
    if using_function:
        arguments["functions"] = sql_exec_functions
        arguments["function_call"] = "auto"
    response = openai.ChatCompletion.create(**arguments)
    response_message = response["choices"][0]["message"]
    logger.info(json.dumps(response_message))
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    return result


def get_answer(sessionId, ask):
    example = {}
    tables = []
    isSqlQuestion = check_sql_question(ask)
    if isSqlQuestion:
        train_data = trained_data_search(ask)[0][2]
        example = {"question": train_data.get("question"), "answer": train_data.get("answer")}

        tables_result = table_info_search(ask)
        tables = [table[2] for table in tables_result]
        if sessionId:
            set_session_table(sessionId, json.dumps({"tables": tables, "example": example}))
    context = []
    if sessionId:
        context = get_recent_content(sessionId)
    msg = create_msg(tables, example, ask, context, isSqlQuestion, sessionId)
    logger.info(f"发送给OpenAI的提示词：{msg}")
    result = sql_query_chat(msg, using_function=True)
    logger.info("result:" + str(result))
    if result.function_call and result.function_call.get("name") == "exec_sql":
        arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
        sql: str = arguments.get("sql")
        if sql.endswith(";"):
            sql = sql[0:len(sql) - 1]
        if sessionId:
            question = json.dumps(HumanMessage(ask))
            answer = json.dumps(AIMessage(sql))
            add_session_content(sessionId, [question, answer])
        return {"success": True, "data": sql + ";"}
    else:
        if sessionId:
            question = json.dumps(HumanMessage(ask))
            answer = json.dumps(AIMessage(result.content))
            add_session_content(sessionId, [question, answer])
        return {"success": False, "data": result.content}


def get_answer_v2(sessionId, ask):
    example = {}
    tables = []
    isSqlQuestion = check_sql_question(ask)
    if isSqlQuestion:
        train_search_data = trained_data_search_v2(ask)
        if train_search_data:
            train_data = train_search_data[0][2]
            example = {"question": train_data.get("question"), "answer": train_data.get("answer")}
        # train_data = trained_data_search_v2(ask)[0][2]
        # example = {"question": train_data.get("question"), "answer": train_data.get("answer")}

        tables_result = table_info_search_v2(ask)
        tables = [table[2] for table in tables_result]
        if sessionId:
            set_session_table(sessionId, json.dumps({"tables": tables, "example": example}))
    context = []
    if sessionId:
        context = get_recent_content(sessionId)
    msg = create_msg(tables, example, ask, context, isSqlQuestion, sessionId)
    logger.info(f"发送给OpenAI的提示词：{msg}")
    result = sql_query_chat(msg, using_function=True)
    logger.info("result:" + str(result))
    if result.function_call and result.function_call.get("name") == "exec_sql":
        # args = result.function_call.get("arguments")
        arguments = json.loads(result.function_call.get("arguments").replace('\n', ' '))
        sql: str = arguments.get("sql")
        if sql.endswith(";"):
            sql = sql[0:len(sql) - 1]
        if sessionId:
            question = json.dumps(HumanMessage(ask))
            answer = json.dumps(AIMessage(sql))
            add_session_content(sessionId, [question, answer])
        return {"success": True, "data": sql + ";"}
    else:
        if sessionId:
            question = json.dumps(HumanMessage(ask))
            answer = json.dumps(AIMessage(result.content))
            add_session_content(sessionId, [question, answer])
        return {"success": False, "data": result.content}


def get_recent_content(sessionId, limit=10):
    conn = redis.Redis(connection_pool=redis_pool)
    result = conn.lrange(f"session_context_{sessionId}", 0, limit - 1)
    conn.close()
    result.reverse()
    return result


def add_session_content(sessionId, messages):
    conn = redis.Redis(connection_pool=redis_pool)
    for mes in messages:
        conn.lpush(f"session_context_{sessionId}", mes)
    conn.expire(f"session_context_{sessionId}", 60 * 60)
    conn.close()


def check_sql_question(content):
    messages = [SystemMessage(content="You are a PostgreSQL expert. Given an input question, Determine if the user needs to generate a query sql,if so then return 'YES' else return 'NO'\n"), HumanMessage(content=content)]
    result = sql_query_chat(messages)
    return result.content == 'YES'


if __name__ == "__main__":
    # 无上下文普通对话
    test1 = get_answer(None, "hello")
    logger.info(test1)

    # 无上下文有训练的sql对话
    # test2 = get_answer(None, "Can you help me find some transactions on the Uniswap platform with a transaction count of 500")
    # logger.info(test2)

    # 无上下文，没训练的sql对话
    # test3 = get_answer(None, "Can you help me find some users with more than 1 million ETH transaction volume?")
    # logger.info(test3)

    # print(check_sql_question("Can you help me find some transactions on the Uniswap platform with a transaction count of max_value_of_system?"))
    # Can you help me find some transactions on the Uniswap platform with a transaction count of 200?
    # logger.info(get_answer('123456', 'hello'))
    # logger.info(get_answer('123456', 'Can you help me find some transactions on the Uniswap platform with a transaction count of max_value_of_system?'))

    # 有上下文
    # test1 = get_answer('asdfg1', "hello")
    # logger.info(test1)
    # test1 = get_answer('asdfg1', "吃饭了嘛")
    # logger.info(test1)
    # test2 = get_answer('asdfg1', "Can you help me find some transactions on the Uniswap platform with a transaction count of max_value_of_system?")
    # logger.info(test2)
    test3 = get_answer('asdfg1', "max_value_of_system is 500")
    logger.info(test3)
    # test4 = get_answer('asdfg1', "Can you recommend me some addresses with a balance of more than max_value_of_system ETH	")
    # logger.info(test4)

    # test1 = get_answer('10087', 'hello,how old are you')
    # test1 = get_answer('10087', 'max_value_of_system means 600')
    # test1 = get_answer('10087', 'Can you help me find some transactions on the Uniswap platform with a transaction count of max_value_of_system?')
