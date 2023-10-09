import csv
import json
from time import sleep

import openai
import redis

from base import logger_name, SystemMessage, HumanMessage, AIMessage, ChatResult, redis_conn, FunctionMessage, get_api_key
from base.logger_util import LOG
from chat_tools_new import master_data
from train_tools_v2 import trained_data_search_v2
from fuzzywuzzy import fuzz

logger = LOG.get_logger(logger_name)

sql_chat_functions = [
    {
        "name": "format_answer",
        "description": """Format ai output.If your answer contains SQL, use the 'sql' parameter. 
 If the user's question is unclear, or there is content that requires user confirmation, or if there is any other non-SQL response, use the 'other' parameter. 
 Please note that the 'sql' parameter and 'other' parameter should not be used together.""",
        "parameters": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "the syntactically correct PostgreSQL query sql.If ai response contains SQL statements,use this parameter"
                },
                "other": {
                    "type": "string",
                    "description": "Other response"
                }
            }
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
        return f"""
Here is an example question and the corresponding SQL query statement for reference.
  question: "{train_data.get('question')}",
  answer: "{train_data.get('answer')}".
If the user's question is the same as the question in the example, use the answer from the example directly. Otherwise, the example answer is for reference only."""


def get_master_data(asset_acronym):
    exact_value_100 = []
    exact_value_90 = []
    exact_value_fuzzy = []
    match = asset_acronym.lower().replace(" ", "")
    for row in master_data:
        if fuzz.ratio(match, row.get("asset").replace(" ", "").lower()) == 100 or fuzz.ratio(match, row.get("symbol").replace(" ", "").lower()) == 100:
            # asset = row.get('asset')
            # b_type = row.get('b_type')
            # statistical_type = row.get('statistical_type')
            # return f"If the user's question contains the asset '{asset_acronym}', please note that the exact value of this asset stored in the database is '{asset}' and the statistical_type is '{statistical_type}',the b_type is '{b_type}'.This " \
            #        f"should be taken into consideration when generating SQL. "
            exact_value_100.append(row)
        elif fuzz.ratio(match, row.get("asset").replace(" ", "").lower()) >= 90 or fuzz.ratio(match, row.get("symbol").replace(" ", "").lower()) >= 90:
            exact_value_90.append(row.get("asset"))
        elif row.get("symbol").lower().replace(" ", "").find(match) >= 0 or row.get("asset").lower().replace(" ", "").find(match) >= 0:
            exact_value_fuzzy.append(row.get("asset"))
    if exact_value_100:
        if len(exact_value_100) == 1:
            row = exact_value_100[0]
            asset = row.get('asset')
            b_type = row.get('b_type')
            statistical_type = row.get('statistical_type')
            return f"If the user's question contains the asset '{asset_acronym}', please note that the exact value of this asset stored in the database is '{asset}' and the statistical_type is '{statistical_type}',the b_type is '{b_type}'.This " \
                   f"should be taken into consideration when generating SQL. "
        else:
            tmp = [{"asset": item.get("asset"), "b_type": item.get("b_type"), "statistical_type": item.get("statistical_type")} for item in exact_value_100]
            tmp_asset = [item.get("asset") for item in exact_value_100]
            tmp_b_type = [item.get("b_type") for item in exact_value_100]
            tmp_statistical_type = [item.get("statistical_type") for item in exact_value_100]
            return f"If the user's query asset name is '{asset_acronym}', tell them that there are multiple asset names in the database with the symbol name '{asset_acronym}'. such as '{tmp_asset}', and then ask which one they " \
                   f"need. (Please note that the corresponding b_type and statistical_type for these assets are: '{tmp}'. Take care when generating SQL.)"
    if exact_value_90:
        return f"If the user's query asset name is '{asset_acronym}', tell them that the asset is not found in the database, but there are similar asset names available, such as '{exact_value_90}', and then ask which one they need."
    if exact_value_fuzzy:
        return f"If the user's query asset name is '{asset_acronym}', tell them that the asset is not found in the database, but there are similar asset names available, such as '{exact_value_fuzzy}', and then ask which one they need."
    return f"If the asset name in the user's question is '{asset_acronym}', inform them that there is no such asset in the database."


def sql_query_chat(messages, using_function=False):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0, model="gpt-4", messages=messages, api_key=get_api_key())
    if using_function:
        arguments["functions"] = sql_chat_functions
        arguments["function_call"] = {"name": "format_answer"}
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    return result


def read_all_text(file_path):
    with open(file_path, "r", encoding='utf-8') as file:
        txt = file.read()
        return txt


def create_msg(tableInfo, question, history, check_result, sessionId):
    sys_msg = get_prompt_info()
    sys_msg = f"{sys_msg} \n {tableInfo}"
    if check_result.get("success"):
        if check_result.get("need_sql"):
            sample_sql = get_sample_sql(question)
            if sample_sql:
                set_session_sample_sql(sessionId, sample_sql)
                sys_msg = f"{sys_msg} \n {sample_sql}"
        else:
            sample_sql = get_session_sample_sql(sessionId)
            if sample_sql:
                sys_msg = f"{sys_msg} \n {sample_sql}"
        assets = check_result.get("assets")
        master_data_msg = ""
        if assets:
            asset_list = assets.split(";")
            if len(asset_list) == 1:
                asset = asset_list[0]
                if asset == 'ETH':
                    pass
                elif asset == 'ALL':
                    master_data_msg = "When querying 'all ERC20 and ETH' use asset='ALL'."
                else:
                    master_data_msg = get_master_data(asset)
            else:
                for asset in asset_list:
                    asset_master_data = get_master_data(asset)
                    master_data_msg = f"{master_data_msg} \n {asset_master_data} \n"
            sys_msg = f"{sys_msg} \n {master_data_msg}"
            set_session_master_data(sessionId, master_data_msg)
        else:
            master_data_msg = get_session_master_data(sessionId)
            if master_data_msg:
                sys_msg = f"{sys_msg} \n {master_data_msg}"
    else:
        sample_sql = get_session_sample_sql(sessionId)
        if sample_sql:
            sys_msg = f"{sys_msg} \n {sample_sql}"
        master_data_msg = get_session_master_data(sessionId)
        if master_data_msg:
            sys_msg = f"{sys_msg} \n {master_data_msg}"
    messages = [SystemMessage(content=sys_msg)]
    for content in history or []:
        messages.append(json.loads(content))
    messages.append(HumanMessage(content=question))
    return messages


def set_session_sample_sql(sessionId, sample):
    redis_conn().set(f"new_query_v4::sample_sql::{sessionId}", sample)
    redis_conn().expire(f"new_query_v4::sample_sql::{sessionId}", 60 * 60)
    redis_conn().close()


def get_session_sample_sql(sessionId):
    conn = redis_conn()
    data = conn.get(f"new_query_v4::sample_sql::{sessionId}")
    conn.close()
    if data:
        return str(data)
    return data


def set_session_master_data(sessionId, data):
    redis_conn().set(f"new_query_v4::master_data::{sessionId}", data)
    redis_conn().expire(f"new_query_v4::master_data::{sessionId}", 60 * 60)
    redis_conn().close()


def get_session_master_data(sessionId):
    conn = redis_conn()
    data = conn.get(f"new_query_v4::master_data::{sessionId}")
    conn.close()
    if data:
        return str(data)
    return data


def get_answer_v4(sessionId, ask):
    if not sessionId:
        raise Exception("sessionId不能为空")
    tables = get_table_info()
    context = get_recent_content(sessionId)
    check_result = check_sql_question(ask)
    # 暂停几秒，防止限流
    sleep(3)
    messages = create_msg(tables, ask, context, check_result, sessionId)
    logger.info(f"发送给OpenAI的提示词：{messages}")
    result = sql_query_chat(messages, using_function=True)
    logger.info("result:" + str(result))
    tmp_session_content = [json.dumps(HumanMessage(ask))]
    times = 0
    if result.function_call:
        times += 1
        if result.function_call.get("name") == "format_answer":
            arguments = json.loads(result.function_call.get("arguments"))
            sql: str = arguments.get("sql")
            content: str = arguments.get("other")
            if sql:
                if sql.endswith(";"):
                    sql = sql[0:len(sql) - 1]
                tmp_session_content.append(json.dumps(AIMessage(content=sql)))
                add_session_content(sessionId, tmp_session_content)
                return {"success": True, "data": sql + ";"}
            else:
                tmp_session_content.append(json.dumps(AIMessage(content=content)))
                add_session_content(sessionId, tmp_session_content)
                return {"success": False, "data": content}
    tmp_session_content.append(json.dumps(AIMessage(result.content)))
    add_session_content(sessionId, tmp_session_content)
    return {"success": False, "data": result.content}


def check_sql_question(content):
    result = {"success": False}
    match = content.replace(" ", "").lower()
    for row in master_data:
        if fuzz.ratio(match, row.get("asset").replace(" ", "").lower()) == 100 or fuzz.ratio(match, row.get("symbol").replace(" ", "").lower()) == 100:
            result["success"] = True
            result["asset"] = row.get('asset')
            return result
    messages = [SystemMessage(content="""
     You are a PostgreSQL expert. Given an input question,
  First determine if the user needs to generate a query SQL. 
  Then check if the user's question contains assett((traded pair and Includes transaction rates) or nft asset  or Digital Currency Industry Assets) /platform information, and if so, extract the name of the assett((traded pair and Includes transaction rates)  or nft asset  or Digital Currency Industry Assets) /platform(If the user needs 'ETH and ERC20' assets, the asset is 'ALL').  
     """), HumanMessage(content=content)]
    function = [
        {
            "name": "format_answer",
            "description": "Format ai output",
            "parameters": {
                "type": "object",
                "properties": {
                    "need_sql": {
                        "type": "string",
                        "description": "Whether the user needs to generate SQL,'YES' or 'NO' or 'UNKNOWN'.",
                        "enum": ["YES", "NO", "UNKNOWN"]
                    },
                    "assets": {
                        "type": "string",
                        "description": "The asset names contained in the extracted user's question.Multiple asset names are separated by ';'"
                    },
                    "platforms": {
                        "type": "string",
                        "description": "The platform names contained in the extracted user's question.Multiple platform names are separated by ';'"
                    }
                },
                "required": ["need_sql"]
            }
        }
    ]

    logger.info("判断用户输入是否需要生成SQL，请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0, model="gpt-4", messages=messages,
                     functions=function,
                     function_call={"name": "format_answer"}, api_key=get_api_key())
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
    response_result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    result = {"success": False}
    if response_result.function_call:
        arguments = json.loads(response_result.function_call.get("arguments").replace('\n', ' '))
        assets: str = arguments.get("assets")
        needs_sql: bool = "YES" == arguments.get("need_sql")
        result["success"] = True
        result["need_sql"] = needs_sql
        result["assets"] = assets
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
    # test1 = check_sql_question("Which addresses have an ETH token volume ranging from $100 to $1,000?")
    # print(test1)
    print(get_master_data("TNT"))
    # test1 = get_answer_v4('12345', "hello")
    # logger.info(test1)
    # test2 = get_answer_v4('23456', "Can you help me find some transactions on the Uniswap platform with a transaction count of 600?")
    # logger.info(test2)
    # test1 = get_answer_v4('12345', "good")
    # logger.info(test1)
    # test4 = get_answer_v4('34567', "Can you recommend me some addresses with a balance of more than 100 ShareToken")
    # logger.info(test4)
    # test1 = get_answer_v4('10087', 'hello,how old are you')
    # logger.info(test1)
    # test1 = get_answer_v4('10087', 'Can you help me find some transactions on the Uniswap platform with a transaction count of max_value_of_system?')
    # logger.info(test1)
    # test1 = get_answer_v4('10087', 'max_value_of_system means 600')
