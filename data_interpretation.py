#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json

import openai
import redis
from base import logger_name, ChatResult, SystemMessage, HumanMessage, FunctionMessage, redis_pool, AIMessage
from base.logger_util import LOG
from label_tools import get_labels_info

logger = LOG.get_logger(logger_name)


def create_functions():
    return [
        {
            "name": "get_labels_info",
            "description": f"Get a detailed description of the labels",
            "parameters": {
                "type": "object",
                "properties": {
                    "label_names": {
                        "type": "string",
                        "description": "label names,Multiple label are separated by ','"
                    }
                },
                "required": ["label_names"]
            }
        }
    ]


def data_explain_chat(messages, using_function=False):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0.5, model="gpt-4", messages=messages)
    if using_function:
        arguments["functions"] = create_functions()
        arguments["function_call"] = "auto"
    response = openai.ChatCompletion.create(**arguments)
    response_message = response["choices"][0]["message"]
    logger.info(json.dumps(response_message))
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    print("chat result：", result)
    return result


def get_label_list_info(label_names: str):
    label_name_list = label_names.split(",")
    results = get_labels_info(label_name_list)
    label_info_map = {result.get("label_name"): result.get("label_desc") for result in results}
    not_found_labels = []
    for label_name in label_name_list:
        if not label_info_map.get(label_name):
            not_found_labels.append(label_name)
    return label_info_map, not_found_labels


def data_interpretation_chat(report_name, report_data, report_desc, question, sessionId):
    messages = [SystemMessage(
        content="You are a data analysis engineer.\n"
                "Based on the digital currency information you know,Make a comprehensive and detailed interpretation of the statistical data provided by users.\n")]
    if sessionId:
        recent_list = get_recent_content(sessionId)
        for recent in recent_list:
            messages.append(json.loads(recent))
    if report_data:
        msg1 = HumanMessage(content=f"The data report name is {report_name}\n"
                                    f"The data report description is {report_desc}\n"
                                    f"The report data is {report_data}\n")
        messages.append(msg1)
        if sessionId:
            add_session_content(sessionId, [json.dumps(msg1)])
    msg2 = HumanMessage(content=question)
    messages.append(msg2)
    if sessionId:
        add_session_content(sessionId, [json.dumps(msg2)])
    result = data_explain_chat(messages, using_function=True)
    times = 0
    while result.function_call:
        '''
        不能让它无限次执行，限定五次
        '''
        times += 1
        if result.function_call.get("name") == "get_labels_info":
            arguments = json.loads(result.function_call.get("arguments"))
            label_names: str = arguments.get("label_names")
            label_info_list, not_found_labels = get_label_list_info(label_names)
            content = json.dumps(label_info_list)
            if not_found_labels:
                content = f"Find the description of the following labels: {content}\n No definitions were found for these labels:[{','.join(not_found_labels)}]"
            messages.append(FunctionMessage(name="get_labels_info", content=content))
            if sessionId:
                add_session_content(sessionId, [json.dumps(FunctionMessage(name="get_labels_info", content=content))])
        if times < 4:
            result = data_explain_chat(messages, using_function=True)
        else:
            result = data_explain_chat(messages)
    if sessionId:
        add_session_content(sessionId, [json.dumps(AIMessage(result.content))])
    return {"success": True, "data": result.content}


def get_recent_content(sessionId, limit=10):
    """
    获取最近的十条会话数据
    :param sessionId: 会话id
    :param limit: 条数，默认为10
    :return:
    """
    conn = redis.Redis(connection_pool=redis_pool)
    result = conn.lrange(f"interpretation::session_context::{sessionId}", 0, limit - 1)
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
        conn.lpush(f"interpretation::session_context::{sessionId}", mes)
    conn.expire(f"interpretation::session_context::{sessionId}", 60 * 60 * 24)
    conn.close()


if __name__ == "__main__":
    # data = data_interpretation_chat(report_name="crowd_portrait_distribution",
    #                                 report_data="[{\"number\":25382.00000000000000000000,\"content\":\"Token whale\"},{\"number\":291002.00000000000000000000,\"content\":\"NFT high demander\"},{\"number\":958791.00000000000000000000,"
    #                                             "\"content\":\"DeFi active users\"},{\"number\":14431143.00000000000000000000,\"content\":\"DeFi high demander\"},{\"number\":259710.00000000000000000000,\"content\":\"Active users\"},"
    #                                             "{\"number\":3622446.00000000000000000000,\"content\":\"Long-term holder\"},{\"number\":1321342.00000000000000000000,\"content\":\"Elite\"},{\"number\":224507.00000000000000000000,"
    #                                             "\"content\":\"NFT whale\"},{\"number\":4976.00000000000000000000,\"content\":\"Web3 active users\"},{\"number\":27525.00000000000000000000,\"content\":\"NFT active users\"}]",
    #                                 report_desc="Based on the special tags held by users, crowd portrait analysis is carried out, so as to label the portraits of addresses.",
    #                                 question="Please help me interpret this data",
    #                                 sessionId="10048")
    # logger.info(json.dumps(data))
    data = data_interpretation_chat(None, None, None, question="请进一步分析", sessionId="10048")
    logger.info(json.dumps(data))
