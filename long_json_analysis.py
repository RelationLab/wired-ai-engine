#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json
import os
from threading import Thread
from time import sleep
import openai
import redis
from base import logger_name, ChatResult, SystemMessage, HumanMessage, redis_conn, AIMessage, get_api_key
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)


def Async(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()

    return wrapper


system_msg = SystemMessage(
    content="You are a senior business data analyst, your answer is very important to us, please follow the following rules in your reply:"
            "\n1 According to your understanding of blockchain and digital currency as well as industry information, please conduct descriptive statistics on the input data, and extract data feature information in multiple dimensions; when users ask questions, please analyze and summarize the data according to the user's questions and the above feature information; when analyzing and summarizing the data, please avoid repetitive interpretation of the existing data, and try to summarize the data as much as possible, and make relevant predictions, and output a report for the user's decision-making reference. When analyzing and summarizing, please avoid repeated interpretation of existing data, try to summarize the data and make relevant predictions, and output a report to inform users' decision-making;"
            "\n2 Under the conditions of Rule 1 above, when more than one question is input, you need to determine whether there is a relationship between the next two questions; if there is no relationship, please answer the last question if you are sure there is no relationship; if you are sure there is a relationship, please answer the question in context."
            "\n3 Thank you again, your answer is very important to us, please be sure to answer professionally and carefully!")


def data_explain_chat(messages):
    logger.info("请求OPENAI" + json.dumps(messages))
    arguments = dict(temperature=0.5, model="gpt-4", messages=messages, api_key=get_api_key())
    response = openai.ChatCompletion.create(**arguments)
    logger.info(json.dumps(response))
    response_message = response["choices"][0]["message"]
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=None)
    return result


@Async
def long_json_analysis(json_data, taskId, sessionId):
    logger.info(f"开始分析json数据,taskId:{taskId},sessionId:{sessionId},json data:{json_data}")
    try:
        msg_all = chat_json(json_data)
        logger.info(f"json数据分析结束,taskId:{taskId},sessionId:{sessionId},分析结果:{msg_all}")
        if sessionId:
            set_session_report_data(sessionId, json.dumps(SystemMessage(content="The content of the data analysis report is as follows:\n" + msg_all)))
        set_task_result(taskId, json.dumps({"success": True, "result": msg_all, "finished": True}))
    except Exception as ex:
        logger.error(ex)
        set_task_result(taskId, json.dumps({"success": False, "finished": True}))


def set_task_result(taskId, txt):
    conn = redis_conn()
    conn.set(f"long_json::task::{taskId}", txt)
    conn.expire(f"long_json::task::{taskId}", 60 * 60 * 24)
    conn.close()


def get_task_result(taskId):
    conn = redis_conn()
    txt = conn.get(f"long_json::task::{taskId}")
    result = {"success": False, "finished": False}
    if txt:
        result = json.loads(txt)
    conn.close()
    return result


def write_all_text(file_path, contents):
    with open(file_path, "w", encoding='utf-8') as file:
        file.write(contents)


def read_all_text(file_path):
    with open(file_path, "r", encoding='utf-8') as file:
        txt = file.read()
        return txt


def long_json_chat(question, sessionId):
    logger.info(f"long_json_chat,sessionId:{sessionId},question:{question}")
    messages = [SystemMessage(content="You are a data analytics engineer. Based on your knowledge of digital currency and virtual assets, answer user questions based on the following data analysis report")]
    msg = get_session_report_data(sessionId)
    if not msg:
        raise Exception("The data analysis report has not been completed")
    messages.append(json.loads(msg))
    if sessionId:
        recent_list = get_recent_content(sessionId)
        for recent in recent_list:
            messages.append(json.loads(recent))
    ask = HumanMessage(content=question)
    messages.append(ask)
    result = data_explain_chat(messages)
    if sessionId:
        add_session_content(sessionId, [json.dumps(ask), json.dumps(AIMessage(result.content))])
    return {"success": True, "data": result.content}


def chat_json_personal(data: dict):
    """
    个人画像分析
    :return:
    """
    try:
        addressInformation: dict = data.get("addressInformation")
        if addressInformation:
            addressInformation.pop("stars")
    except Exception as ex:
        logger.error(ex)

    result1 = ""
    try:
        report1 = data.get("assets")
        report1 = list(filter(lambda item: item.get("name") not in ["ALL", "ALL_TOKEN", "ALL_NFT", "ALL_WEB3"], report1))
        msg1 = [system_msg,
                HumanMessage(content="ReportId:Personal_portrait_analysis.assets\nReportData:" + json.dumps(report1)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result1 = data_explain_chat(msg1).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result2 = ""
    try:
        report2 = data.get("platforms")
        report2 = list(filter(lambda item: item.get("name") not in ["ALL", "ALL_TOKEN", "ALL_NFT", "ALL_WEB3"], report2))
        msg2 = [system_msg,
                HumanMessage(content="ReportId:Personal_portrait_analysis.platforms\nReportData:" + json.dumps(report2)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result2 = data_explain_chat(msg2).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result3 = ""
    try:
        report3 = data.get("actions")
        report3 = list(filter(lambda item: item.get("name") not in ["ALL", "ALL_TOKEN", "ALL_NFT", "ALL_WEB3"], report3))
        msg3 = [system_msg,
                HumanMessage(content="ReportId:Personal_portrait_analysis.actions\nReportData:" + json.dumps(report3)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result3 = data_explain_chat(msg3).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result4 = ""
    try:
        report4 = data.get("basicLabels")
        msg4 = [system_msg,
                HumanMessage(content="ReportId:Personal_portrait_analysis.basicLabels\nReportData:" + json.dumps(report4)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result4 = data_explain_chat(msg4).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result5 = ""
    try:
        report5 = data.get("crowdPortraitLabels")
        msg5 = [system_msg,
                HumanMessage(content="ReportId:Personal_portrait_analysis.crowdPortraitLabels\nReportData:" + json.dumps(report5)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result5 = data_explain_chat(msg5).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result6 = ""
    try:
        if data.get("assets"):
            data.pop("assets")
        if data.get("platforms"):
            data.pop("platforms")
        if data.get("actions"):
            data.pop("actions")
        if data.get("basicLabels"):
            data.pop("basicLabels")
        if data.get("crowdPortraitLabels"):
            data.pop("crowdPortraitLabels")
        msg6 = [system_msg,
                HumanMessage(content="ReportId:Personal_portrait_analysis\nReportData:" + json.dumps(data)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result6 = data_explain_chat(msg6).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result_merger = ""
    try:
        msg_merge = [system_msg,
                     HumanMessage(content=result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6),
                     HumanMessage("Summarize the above conclusions again,Then further interpret the above reports"),
                     SystemMessage(content="Response should not exceed 2000 tokens")]
        result_merger = data_explain_chat(msg_merge).content
    except Exception as ex:
        logger.error(ex)

    return result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6 + "\n" + result_merger


def chat_json(json_data):
    # sleep(30)
    # return "hh"
    data: dict = json.loads(json_data)
    if data.get("assets"):
        return chat_json_personal(data)
    # sleep(10) 防止被限流
    result1 = ""
    try:
        report1 = data.get("level_address_statistics").get("action").get("nft")
        msg1 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.nft\nReportData:" + json.dumps(report1)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result1 = data_explain_chat(msg1).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result2 = ""
    try:
        report2 = data.get("level_address_statistics").get("action").get("token")
        msg2 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.token\nReportData:" + json.dumps(report2)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result2 = data_explain_chat(msg2).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result3 = ""
    try:
        report3 = data.get("level_address_statistics").get("asset").get("nft")
        msg3 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.asset.nft\nReportData:" + json.dumps(report3)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result3 = data_explain_chat(msg3).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result4 = ""
    try:
        report4 = data.get("level_address_statistics").get("asset").get("token")
        msg4 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.asset.token\nReportData:" + json.dumps(report4)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result4 = data_explain_chat(msg4).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result5 = ""
    try:
        report5 = data.get("level_address_statistics").get("platform").get("nft")
        msg5 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.nft\nReportData:" + json.dumps(report5)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result5 = data_explain_chat(msg5).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result6 = ""
    try:
        report6 = data.get("level_address_statistics").get("platform").get("token")
        msg6 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.token\nReportData:" + json.dumps(report6)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result6 = data_explain_chat(msg6).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result7 = ""
    try:
        report7 = data.get("level_address_statistics").get("action").get("web3")
        msg7 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.web3\nReportData:" + json.dumps(report7)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result7 = data_explain_chat(msg7).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result8 = ""
    try:
        report8 = data.get("level_address_statistics").get("platform").get("web3")
        msg8 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.web3\nReportData:" + json.dumps(report8)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result8 = data_explain_chat(msg8).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result9 = ""
    try:
        data.pop("level_address_statistics")
        report9 = data
        msg9 = [system_msg,
                HumanMessage(content="ReportName:crowd_portrait\nReportData:" + json.dumps(report9)),
                SystemMessage(content="Response should not exceed 500 tokens")]
        result9 = data_explain_chat(msg9).content
        sleep(10)
    except Exception as ex:
        logger.error(ex)

    result_merger1 = ""
    result_merger2 = ""
    try:
        msg_merge1 = [system_msg,
                      HumanMessage(content=result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6 + "\n" + result7 + "\n" + result8),
                      HumanMessage("Summarize the above conclusions again,Then further interpret the above reports"),
                      SystemMessage(content="Response should not exceed 500 tokens")]
        result_merger1 = data_explain_chat(msg_merge1).content

        sleep(10)
        msg_merge2 = [system_msg,
                      HumanMessage(content=result9 + "\n" + result_merger1),
                      HumanMessage("Summarize the above conclusions again,Then further interpret the above reports"),
                      SystemMessage(content="Response should not exceed 1000 tokens")]
        result_merger2 = data_explain_chat(msg_merge2).content
    except Exception as ex:
        logger.error(ex)
    logger.info("result1:" + result1)
    logger.info("result2:" + result2)
    logger.info("result3:" + result3)
    logger.info("result4:" + result4)
    logger.info("result5:" + result5)
    logger.info("result6:" + result6)
    logger.info("result7:" + result7)
    logger.info("result8:" + result8)
    logger.info("result9:" + result9)
    logger.info("result_merger1:" + result_merger1)
    logger.info("result_merger2:" + result_merger2)
    msg_all = result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6 + "\n" + result7 + "\n" + result8 + "\n" + result9 + "\n" + result_merger1 + "\n" + result_merger2
    return msg_all


def get_recent_content(sessionId, limit=10):
    """
    获取最近的十条会话数据
    :param sessionId: 会话id
    :param limit: 条数，默认为10
    :return:
    """
    result = redis_conn().lrange(f"long_json::session_context::{sessionId}", 0, limit - 1)
    redis_conn().close()
    result.reverse()
    return result


def add_session_content(sessionId, messages):
    """
    将消息追加到会话，有效期为一天
    :param sessionId: 会话id
    :param messages: 消息
    :return:
    """
    for mes in messages:
        redis_conn().lpush(f"long_json::session_context::{sessionId}", mes)
    redis_conn().expire(f"long_json::session_context::{sessionId}", 60 * 60 * 24)
    redis_conn().close()


def set_session_report_data(sessionId, reportSummary):
    """
    :param sessionId: 会话id
    :param reportSummary: 报表总结
    :return:
    """
    redis_conn().set(f"long_json::session_report::{sessionId}", reportSummary)
    redis_conn().expire(f"long_json::session_report::{sessionId}", 60 * 60 * 24 * 3)
    redis_conn().close()


def get_session_report_data(sessionId):
    """获取会话的总结报告
    :param sessionId: 会话id
    :return:
    """
    msg = redis_conn().get(f"long_json::session_report::{sessionId}")
    redis_conn().close()
    return msg


if __name__ == "__main__":
    test_result = long_json_chat("You have been assigned the task of conducting data mining for a portrait report. Yourgoal is to analyze and extract key information, providing a comprehensive conclusion forthis report.", "e33e")
