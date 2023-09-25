#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json
from threading import Thread
from time import sleep
import openai
from base import logger_name, ChatResult, SystemMessage, HumanMessage, redis_conn, AIMessage, get_api_key
from base.logger_util import LOG

logger = LOG.get_logger(logger_name)


def Async(f):
    def wrapper(*args, **kwargs):
        thr = Thread(target=f, args=args, kwargs=kwargs)
        thr.start()

    return wrapper


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
    print(f"开始分析json数据,taskId:{taskId},sessionId:{sessionId},json data:{json_data}")
    try:
        msg_all = chat_json(json_data)
        logger.info(f"json数据分析结束,taskId:{taskId},sessionId:{sessionId},分析结果:{msg_all}")
        if sessionId:
            set_session_report_data(sessionId, json.dumps(SystemMessage(content=f"The content of the data analysis report is as follows(Content between square brackets):\n[{msg_all}]")))
        set_task_result(taskId, json.dumps({"success": True, "result": msg_all, "finished": True}))
    except Exception as ex:
        logger.error(f"taskId:{taskId},sessionId:{sessionId},json data:{json_data},执行失败")
        logger.exception(ex)
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
    print(f"long_json_chat,sessionId:{sessionId},question:{question}")
    # messages = [SystemMessage(content="You are a data analytics engineer. Based on your knowledge of digital currency and virtual assets, answer user questions based on the following data analysis report\r\n")]
    msg = get_session_report_data(sessionId)
    if not msg:
        raise Exception("The data analysis report has not been completed")
    # messages.append(json.loads(msg))
    report = json.loads(msg).get("content")
    messages = [SystemMessage(content=f"""You are a senior business data analyst at the "Wired" platform. Wired is a platform dedicated to professional on-chain address analysis for Web3. It marks and filters billions of addresses, categorizes and labels them based on a large amount of real-time on-chain behavior data. Please describe, understand, and analyze the input report based on the user's input; If you determine that the user wants you to assist him in data analysis and summarization, please output and summarize the report based on advanced data analysis methods (including but not limited to multidimensional comparative analysis methods or correlation analysis methods); Be sure to include the key figures from the input report in the output content.\r\n{report}Please make sure the logic and structure of the output content are clear.""")]
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
    address = data.get("addressInformation").get("address")
    system_msg_personal_analyse = SystemMessage(f"""
You are a senior business data analyst at the "Wired" platform. Wired is a platform dedicated to professional on-chain address analysis for Web3. It tags and filters billions of addresses, categorizing and labeling them based on a large amount of real-time on-chain behavior data. Please follow the steps below to extract the information of the input data: 1. Describe, understand, and parse the data in the user input report. 2. The output content must include the relevant input data.
""")

    system_msg_personal_analyse_merge = SystemMessage(f"""
You are a senior business data analyst at Wired, specializing in the analysis of commercial application data in the field of web3 cryptocurrencies and digital assets. Please use advanced data analysis methods including but not limited to multi-dimensional comparison and distribution analysis to analyze blockchain transaction address data provided by the user ({address}). While preserving the original data, perform comprehensive multi-dimensional data comparison analysis, descriptive statistics, and data feature extraction on all user portraits and tag data. Then, based on your understanding of the field of web3 cryptocurrencies and virtual assets, further explore this address. Finally, generate corresponding reports, ensuring the preservation of the original data for validation of the analysis results to assist users in decision-making. In your data analysis and summary, please present your analysis conclusion clearly and logically.
""")

    system_msg_personal_analyse_platform = SystemMessage(f"""
The details of the on-chain platforms where the address set conducts transactions, such as Uniswap, Balancer, OpenSea, Mirror, Gitcoin, etc., include asset balances, transaction volume, and trading count (activity) (DeFi, NFT, and Web3 platforms have separate statistics for balance/transaction volume/activity).
""")

    system_msg_personal_analyse_action = SystemMessage(f"""
The current set of this address includes detailed information on types of on-chain interaction behaviors, such as Swap, LP (Liquidity Provision), Mint, Burn, Buy, etc. These indicators include transaction volume and count (activity). (Separate statistics for transaction volume/activity are kept for DeFi, NFT, and Web3 behaviors.)
""")

    system_msg_personal_analyse_asset = SystemMessage(f"""
The details of the on-chain assets currently held by this address or set of addresses, including asset balance, transaction volume, and trading count (activity), cover a variety of on-chain assets like UNI, CryptoPunks, ENS, etc. (The balance/transaction volume/activity of DeFi, NFT, and Web3 assets are calculated separately).
""")
    system_msg_personal_analyse_basic = SystemMessage(f"""
The basic information of all addresses in this address set, including the percentage of personal addresses,and the overall distribution of labels focusing on which category.
""")

    try:
        addressInformation: dict = data.get("addressInformation")
        if addressInformation:
            addressInformation.pop("stars")
    except Exception as ex:
        logger.exception(ex)

    result1 = ""
    try:
        report1 = data.get("assets")
        report1 = list(filter(lambda item: item.get("name") not in ["ALL", "ALL_TOKEN", "ALL_NFT", "ALL_WEB3"], report1))
        msg1 = [system_msg_personal_analyse,
                system_msg_personal_analyse_asset,
                HumanMessage(content="Below are all the 'asset information' held by this address\nReportData:" + json.dumps(report1)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result1 = data_explain_chat(msg1).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result2 = ""
    try:
        report2 = data.get("platforms")
        report2 = list(filter(lambda item: item.get("name") not in ["ALL", "ALL_TOKEN", "ALL_NFT", "ALL_WEB3"], report2))
        msg2 = [system_msg_personal_analyse,
                system_msg_personal_analyse_platform,
                HumanMessage(content="The following is the data portrait of this address on various 'platforms'\nReportData:" + json.dumps(report2)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result2 = data_explain_chat(msg2).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result3 = ""
    try:
        report3 = data.get("actions")
        report3 = list(filter(lambda item: item.get("name") not in ["ALL", "ALL_TOKEN", "ALL_NFT", "ALL_WEB3"], report3))
        msg3 = [system_msg_personal_analyse,
                system_msg_personal_analyse_action,
                HumanMessage(content="The following data is all the 'actions' of this address\nReportData:" + json.dumps(report3)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result3 = data_explain_chat(msg3).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result4 = ""
    try:
        report4 = data.get("basicLabels")
        msg4 = [system_msg_personal_analyse,
                HumanMessage(content="The following data is the 'basic labels' of the address\nReportData:" + json.dumps(report4)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result4 = data_explain_chat(msg4).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result5 = ""
    try:
        report5 = data.get("crowdPortraitLabels")
        msg5 = [system_msg_personal_analyse,
                HumanMessage(content="The following data is the 'crowd portrait labels' of the address\nReportData:" + json.dumps(report5)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result5 = data_explain_chat(msg5).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

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
        msg6 = [system_msg_personal_analyse,
                system_msg_personal_analyse_basic,
                HumanMessage(content="The following data is some basic information about the address\nReportData:" + json.dumps(data)),
                SystemMessage(content="Response should not exceed 400 tokens")]
        result6 = data_explain_chat(msg6).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result_merger = ""

    try:
        msg_merge = [system_msg_personal_analyse_merge,
                     HumanMessage(content=result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6),
                     HumanMessage("Summarize the above conclusions again,Then further interpret the above reports"),
                     SystemMessage(content="Response should not exceed 2000 tokens")]
        result_merger = data_explain_chat(msg_merge).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    return result6 + "\n" + result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result_merger


def chat_json(json_data):
    data: dict = json.loads(json_data)
    if data.get("addressInformation"):
        return chat_json_personal(data)

    system_msg_global_analyse = f"""
Wired specializes in professional on-chain address analysis for Web3. It marks and filters billions of addresses, categorizing and labeling them based on a massive amount of real-time on-chain behavioral data. You are a seasoned data analyst at the Wired platform. Please perform multidimensional data analysis, statistics, and feature extraction from all user profiles and tag data using methods not limited to distribution analysis and comparative analysis, while preserving as much raw data as possible. Then, with your understanding of the cryptocurrency and virtual asset domains, delve deeper into the data. Ultimately, generate a corresponding report, which must retain raw data to substantiate the analysis results, for users to reference in making decisions. When analyzing and summarizing data, avoid duplicating existing information. The generated result should be consistent with the style of professional data organizations."""
    system_msg = SystemMessage(system_msg_global_analyse)

    result1 = ""
    try:
        report1 = data.get("level_address_statistics").get("action").get("nft")
        msg1 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.nft\nReportData:" + json.dumps(report1)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result1 = data_explain_chat(msg1).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result2 = ""
    try:
        report2 = data.get("level_address_statistics").get("action").get("token")
        msg2 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.token\nReportData:" + json.dumps(report2)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result2 = data_explain_chat(msg2).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result3 = ""
    try:
        report3 = data.get("level_address_statistics").get("asset").get("nft")
        msg3 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.asset.nft\nReportData:" + json.dumps(report3)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result3 = data_explain_chat(msg3).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result4 = ""
    try:
        report4 = data.get("level_address_statistics").get("asset").get("token")
        msg4 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.asset.token\nReportData:" + json.dumps(report4)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result4 = data_explain_chat(msg4).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result5 = ""
    try:
        report5 = data.get("level_address_statistics").get("platform").get("nft")
        msg5 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.nft\nReportData:" + json.dumps(report5)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result5 = data_explain_chat(msg5).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result6 = ""
    try:
        report6 = data.get("level_address_statistics").get("platform").get("token")
        msg6 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.token\nReportData:" + json.dumps(report6)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result6 = data_explain_chat(msg6).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result7 = ""
    try:
        report7 = data.get("level_address_statistics").get("action").get("web3")
        msg7 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.action.web3\nReportData:" + json.dumps(report7)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result7 = data_explain_chat(msg7).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result8 = ""
    try:
        report8 = data.get("level_address_statistics").get("platform").get("web3")
        msg8 = [system_msg,
                HumanMessage(content="ReportId:level_address_statistics.platform.web3\nReportData:" + json.dumps(report8)),
                SystemMessage(content="Response should not exceed 200 tokens")]
        result8 = data_explain_chat(msg8).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result9 = ""
    try:
        data.pop("level_address_statistics")
        report9 = data
        msg9 = [system_msg,
                HumanMessage(content="ReportName:crowd_portrait\nReportData:" + json.dumps(report9)),
                SystemMessage(content="Response should not exceed 500 tokens")]
        result9 = data_explain_chat(msg9).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)

    result_merger1 = ""
    result_merger2 = ""
    try:
        msg_merge1 = [system_msg,
                      HumanMessage(content=result1 + "\n" + result2 + "\n" + result3 + "\n" + result4 + "\n" + result5 + "\n" + result6 + "\n" + result7 + "\n" + result8),
                      HumanMessage("Summarize the above conclusions again,Then further interpret the above reports"),
                      SystemMessage(content="Response should not exceed 500 tokens")]
        result_merger1 = data_explain_chat(msg_merge1).content

        sleep(20)
        msg_merge2 = [system_msg,
                      HumanMessage(content=result9 + "\n" + result_merger1),
                      HumanMessage("Summarize the above conclusions again,Then further interpret the above reports"),
                      SystemMessage(content="Response should not exceed 1000 tokens")]
        result_merger2 = data_explain_chat(msg_merge2).content
    except Exception as ex:
        logger.exception(ex)
    sleep(20)
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
