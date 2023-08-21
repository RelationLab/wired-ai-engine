#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json
import os
from threading import Thread
from time import sleep
import openai
import redis
from base import logger_name, ChatResult, SystemMessage, HumanMessage, redis_pool, AIMessage
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)


def Async(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()

    return wrapper


system_msg = SystemMessage(
    content="You are a senior business data analyst, please according to your knowledge of blockchain and digital currency and industry information; according to the user's problem, analyze and summarize the input data, draw conclusions, "
            "output the corresponding analysis report, to provide reference for the user's decision-making; please avoid repetitive reading out of the existing data when analyzing and summarizing, try to carry out the interpretation and summary of "
            "the data, and there are also relevant predictions")


def data_explain_chat(messages):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0.5, model="gpt-4", messages=messages)
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=None)
    print("chat result：", result)
    return result


@Async
def long_json_analysis(json_data, taskId, sessionId):
    msg_all, msg_session = chat_json(json_data)
    if sessionId:
        clear_content(sessionId)
        add_session_content(sessionId, [json.dumps(AIMessage(content=msg_session))])
    os.makedirs("./data", exist_ok=True)
    write_all_text(f"./data/{taskId}", msg_all)


def get_task_result(taskId):
    if os.path.isfile(f"./data/{taskId}"):
        result = read_all_text(f"./data/{taskId}")
        return {"success": True, "data": result}
    else:
        return {"success": False, "data": None}


def write_all_text(file_path, contents):
    with open(file_path, "w", encoding='utf-8') as file:
        file.write(contents)


def read_all_text(file_path):
    with open(file_path, "r", encoding='utf-8') as file:
        txt = file.read()
        return txt


def long_json_chat(question, sessionId):
    messages = [SystemMessage(content="You are a senior business data analyst, please according to your knowledge of blockchain and digital currency and industry information; according to the user's problem, analyze and summarize the input data, "
                                      "draw conclusions, output the corresponding analysis report, to provide reference for the user's decision-making; please avoid repetitive reading out of the existing data when analyzing and summarizing, "
                                      "try to carry out the interpretation and summary of the data, and there are also relevant predictions")]
    ask = HumanMessage(content=question)
    if sessionId:
        recent_list = get_recent_content(sessionId)
        for recent in recent_list:
            messages.append(json.loads(recent))
    messages.append(ask)
    result = data_explain_chat(messages)
    if sessionId:
        add_session_content(sessionId, [json.dumps(ask), json.dumps(AIMessage(result.content))])
    return {"success": True, "data": result.content}


def chat_json(json_data):
    # sleep(30)
    # return "hh"
    data: dict = json.loads(json_data)

    # sleep(10) 防止被限流
    result1 = ""
    try:
        report1 = data.get("level_address_statistics").get("action").get("nft")
        msg1 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.nft\nReportData:" + json.dumps(report1)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result1 = data_explain_chat(msg1).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result2 = ""
    try:
        report2 = data.get("level_address_statistics").get("action").get("token")
        msg2 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.token\nReportData:" + json.dumps(report2)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result2 = data_explain_chat(msg2).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result3 = ""
    try:
        report3 = data.get("level_address_statistics").get("asset").get("nft")
        msg3 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.asset.nft\nReportData:" + json.dumps(report3)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result3 = data_explain_chat(msg3).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result4 = ""
    try:
        report4 = data.get("level_address_statistics").get("asset").get("token")
        msg4 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.asset.token\nReportData:" + json.dumps(report4)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result4 = data_explain_chat(msg4).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result5 = ""
    try:
        report5 = data.get("level_address_statistics").get("platform").get("nft")
        msg5 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.nft\nReportData:" + json.dumps(report5)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result5 = data_explain_chat(msg5).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result6 = ""
    try:
        report6 = data.get("level_address_statistics").get("platform").get("token")
        msg6 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.token\nReportData:" + json.dumps(report6)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result6 = data_explain_chat(msg6).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result8 = ""
    try:
        report8 = data.get("level_address_statistics").get("action").get("web3")
        msg8 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.web3\nReportData:" + json.dumps(report8)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result8 = data_explain_chat(msg8).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result9 = ""
    try:
        report9 = data.get("level_address_statistics").get("platform").get("web3")
        msg9 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.web3\nReportData:" + json.dumps(report9)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result9 = data_explain_chat(msg9).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result7 = ""
    try:
        data.pop("level_address_statistics")
        report7 = data
        msg7 = [system_msg,
                HumanMessage(content="ReportName:crowd_portrait\nReportData:" + json.dumps(report7)),
                SystemMessage(content="Response should not exceed 1000 tokens")]
        result7 = data_explain_chat(msg7).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)
    msg_merge1 = [system_msg,
                  HumanMessage(content=result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6 + "\n" + result8 + "\n" + result9),
                  HumanMessage("Summarize the above conclusions again"),
                  SystemMessage(content="Response should not exceed 1000 tokens")]
    result_merger1 = data_explain_chat(msg_merge1).content
    sleep(10)
    msg_merge2 = [system_msg,
                  HumanMessage(content=result7 + "\n" + result_merger1),
                  HumanMessage("Summarize the above conclusions again"),
                  SystemMessage(content="Response should not exceed 2000 tokens")]
    result_merger2 = data_explain_chat(msg_merge2).content
    logger.info("result1:" + result1)
    logger.info("result2:" + result2)
    logger.info("result3:" + result3)
    logger.info("result4:" + result4)
    logger.info("result5:" + result5)
    logger.info("result6:" + result6)
    logger.info("result8:" + result8)
    logger.info("result9:" + result9)

    logger.info("result7:" + result7)
    logger.info("result_merger1:" + result_merger1)
    logger.info("result_merger2:" + result_merger2)
    msg_all = result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6 + "\n" + result8 + "\n" + result9 + "\n" + result7 + "\n" + result_merger1 + "\n" + result_merger2
    msg_session = result7 + "\n" + result_merger1 + "\n" + result_merger2
    return msg_all, msg_session


def clear_content(sessionId):
    """
    清空session
    :param sessionId: 会话id
    :return:
    """
    conn = redis.Redis(connection_pool=redis_pool)
    conn.delete(f"long_json::session_context::{sessionId}")
    conn.close()


def get_recent_content(sessionId, limit=10):
    """
    获取最近的十条会话数据
    :param sessionId: 会话id
    :param limit: 条数，默认为10
    :return:
    """
    conn = redis.Redis(connection_pool=redis_pool)
    result = conn.lrange(f"long_json::session_context::{sessionId}", 0, limit - 1)
    conn.close()
    result.reverse()
    return result


def add_session_content(sessionId, messages):
    """
    将消息追加到会话，有效期为一天
    :param sessionId: 会话id
    :param messages: 消息
    :return:
    """
    conn = redis.Redis(connection_pool=redis_pool)
    for mes in messages:
        conn.lpush(f"long_json::session_context::{sessionId}", mes)
    conn.expire(f"long_json::session_context::{sessionId}", 60 * 60 * 24)
    conn.close()


if __name__ == "__main__":
    pass
