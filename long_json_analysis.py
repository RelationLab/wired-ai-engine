#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json
from time import sleep

import openai
import redis

from base import logger_name, ChatResult, SystemMessage, HumanMessage, redis_pool, AIMessage
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)

system_msg = SystemMessage(
    content="You are a data analysis engineer.\n"
            "Based on the digital currency information you know,Make a comprehensive and detailed interpretation of the statistical data provided by users.\n")


def data_explain_chat(messages):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0.5, model="gpt-4", messages=messages)
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=None)
    print("chat result：", result)
    return result


def long_json_chat(json_data, question, sessionId):
    messages = [system_msg]
    if json_data:
        msg = chat_json(json_data)
        if sessionId:
            clear_content(sessionId)
            add_session_content(sessionId, [json.dumps(AIMessage(content=msg))])
        return {"success": True, "data": msg}
    else:
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
    data: dict = json.loads(json_data)
    report1 = data.get("level_address_statistics").get("action").get("nft")
    msg1 = [system_msg,
            HumanMessage(content="ReportId:level_address_statistics.action.nft\nReportData:" + json.dumps(report1)),
            SystemMessage(content="Response should not exceed 400 tokens")]

    report2 = data.get("level_address_statistics").get("action").get("token")
    msg2 = [system_msg,
            HumanMessage(content="ReportId:level_address_statistics.action.token\nReportData:" + json.dumps(report2)),
            SystemMessage(content="Response should not exceed 400 tokens")]

    report3 = data.get("level_address_statistics").get("asset").get("nft")
    msg3 = [system_msg,
            HumanMessage(content="ReportId:level_address_statistics.asset.nft\nReportData:" + json.dumps(report3)),
            SystemMessage(content="Response should not exceed 400 tokens")]

    report4 = data.get("level_address_statistics").get("asset").get("token")
    msg4 = [system_msg,
            HumanMessage(content="ReportId:level_address_statistics.asset.token\nReportData:" + json.dumps(report4)),
            SystemMessage(content="Response should not exceed 400 tokens")]

    report5 = data.get("level_address_statistics").get("platform").get("nft")
    msg5 = [system_msg,
            HumanMessage(content="ReportId:level_address_statistics.platform.nft\nReportData:" + json.dumps(report5)),
            SystemMessage(content="Response should not exceed 400 tokens")]

    report6 = data.get("level_address_statistics").get("platform").get("token")
    msg6 = [system_msg,
            HumanMessage(content="ReportId:level_address_statistics.platform.token\nReportData:" + json.dumps(report6)),
            SystemMessage(content="Response should not exceed 400 tokens")]

    data.pop("level_address_statistics")
    report7 = data
    msg7 = [system_msg,
            HumanMessage(content="ReportName:crowd_portrait\nReportData:" + json.dumps(report7)),
            SystemMessage(content="Response should not exceed 1000 tokens")]

    # sleep(5) 防止被限流
    result1 = ""
    try:
        result1 = data_explain_chat(msg1).content
        sleep(5)
    except Exception as ex:
        logger.error(ex)

    result2 = ""
    try:
        result2 = data_explain_chat(msg2).content
        sleep(5)
    except Exception as ex:
        logger.error(ex)

    result3 = ""
    try:
        result3 = data_explain_chat(msg3).content
        sleep(5)
    except Exception as ex:
        logger.error(ex)

    result4 = ""
    try:
        result4 = data_explain_chat(msg4).content
        sleep(5)
    except Exception as ex:
        logger.error(ex)

    result5 = ""
    try:
        result5 = data_explain_chat(msg5).content
        sleep(5)
    except Exception as ex:
        logger.error(ex)

    result6 = ""
    try:
        result6 = data_explain_chat(msg6).content
        sleep(5)
    except Exception as ex:
        logger.error(ex)

    result7 = ""
    try:
        result7 = data_explain_chat(msg7).content
        sleep(5)
    except Exception as ex:
        logger.error(ex)
    msg_merge1 = [system_msg,
                  HumanMessage(content=result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6),
                  HumanMessage("Summarize the above conclusions again"),
                  SystemMessage(content="Response should not exceed 1000 tokens")]
    result_merger1 = data_explain_chat(msg_merge1).content
    sleep(5)
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
    logger.info("result7:" + result7)

    logger.info("result_merger1:" + result_merger1)
    logger.info("result_merger2:" + result_merger2)

    return result_merger2


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
    r = open("/Users/guoxinyou/Desktop/data_analysis1.json")
    json_str = r.read()
    s = chat_json(json_str)
    logger.info(s)
