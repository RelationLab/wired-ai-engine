#!/usr/bin/python
# -*- coding: UTF-8 -*-
import json
import os
import queue
import re
import subprocess
from time import sleep
import openai
import pandas as pd
import redis
from jupyter_client import KernelManager
from base import logger_name, ChatResult, SystemMessage, HumanMessage, FunctionMessage, redis_conn, AIMessage
from base.logger_util import LOG
from label_tools import get_labels_info

logger = LOG.get_logger(logger_name)

km = KernelManager(kernel_name='python3')
km.start_kernel()


def get_csv_data_sample(file_path: str):
    if not os.path.isfile(file_path):
        return f"Error: No such file or directory: '{file_path}'"
    data_frame = pd.read_csv(file_path)
    first_five_line = data_frame.sample(3).to_csv(index=False)
    describe = data_frame.describe()
    return first_five_line, describe


def create_functions():
    return [
        {
            "name": "exec_python_script",
            "description": f"Execute python script",
            # "description": f"execute python script,you can store the statistical json data in the {json_file_path},If you want to generate an image, you can save image file to {image_save_path}",
            "parameters": {
                "type": "object",
                "properties": {
                    "script": {
                        "type": "string",
                        "description": "the syntactically correct python script.Pay attention to the format when converting to json,The python script does not have permission to write to local file"
                    },
                    "packages": {
                        "type": "string",
                        "description": "Packages that python scripts depend on"
                    }
                },
                "required": ["script"]
            }
        },
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


def write_all_text(file_path, contents):
    with open(file_path, "w", encoding='utf-8') as file:
        file.write(contents)


def data_analyses(fileId, question, sessionId):
    csv_file_name = f"./tmp/{fileId}"
    if not os.path.isfile(csv_file_name):
        return {"success": False, "data": "数据文件不存在"}
    # image_file = f"./tmp/{get_uuid()}.png"
    # json_file_path = f"./tmp/{get_uuid()}.json"
    messages = [SystemMessage(
        content="You are a data analysis engineer.\n"
                "You can use python scripts to analyze user files and get statistical data.\n"
                "Please consider the execution performance of the code according to the characteristics of the data.\n"
                "And according to the user's question explain the statistical data.\n"
                "Don't use dangerous code like delete data etc.\n"
                "Do not generate code that writes to file.\n"
                "Don't let the user know the process executed by python and the path where the file is stored.\n"
                f"The user's data file is '{csv_file_name}'\n")]
    csv_sample, describe = get_csv_data_sample(csv_file_name)
    messages.append(SystemMessage(content=f"the csv data sample is {csv_sample} \n The data describe is {describe}"))
    if sessionId:
        recent_list = get_recent_content(sessionId, fileId)
        for recent in recent_list:
            messages.append(json.loads(recent))
    messages.append(HumanMessage(content=question))
    if sessionId:
        add_session_content(sessionId, fileId, [json.dumps(HumanMessage(question))])
    result = data_explain_chat(messages, using_function=True)
    times = 0
    image_data = None
    while result.function_call:
        '''
        不能让它无限次执行，限定五次
        '''
        times += 1
        if result.function_call.get("name") == "exec_python_script":
            arguments = json.loads(result.function_call.get("arguments"))
            python_code: str = arguments.get("script")
            packages = arguments.get("packages")
            logger.info(f"安装python依赖包：\n{packages}")
            logger.info(f"执行python脚本\n{python_code}")
            exec_result = exec_python_code(packages, python_code)

            content = f"Python code ```python\n {python_code} \n``` execution finished,"
            if exec_result.get("std_error"):
                content = content + f"The error message is as follows :{exec_result.get('std_error')}"
            if exec_result.get("std_output"):
                content = content + f"The standard output is as follows:{exec_result.get('std_output')}"
            if exec_result.get("exec_result"):
                content = content + f"The execute result is as follows:{exec_result.get('exec_result')}"
            if exec_result.get("image"):
                image_data = exec_result.get("image")
            messages.append(FunctionMessage(name="exec_python_script", content=content))
            if sessionId:
                add_session_content(sessionId, fileId, [json.dumps(FunctionMessage(name="exec_python_script", content=content))])
        if result.function_call.get("name") == "get_labels_info":
            arguments = json.loads(result.function_call.get("arguments"))
            label_names: str = arguments.get("label_names")
            label_info_list, not_found_labels = get_label_list_info(label_names)
            content = json.dumps(label_info_list)
            if not_found_labels:
                content = f"Find the description of the following labels: {content}\n No definitions were found for these labels:[{','.join(not_found_labels)}]"
            messages.append(FunctionMessage(name="get_labels_info", content=content))
            if sessionId:
                add_session_content(sessionId, fileId, [json.dumps(FunctionMessage(name="get_labels_info", content=content))])
        if times < 4:
            result = data_explain_chat(messages, using_function=True)
        else:
            result = data_explain_chat(messages)
    if sessionId:
        add_session_content(sessionId, fileId, [json.dumps(AIMessage(result.content))])
    return {"success": True, "data": result.content, "image": image_data}


def get_recent_content(sessionId, fileId, limit=10):
    """
    获取最近的十条会话数据
    :param sessionId: 会话id
    :param fileId 文件id
    :param limit: 条数，默认为10
    :return:
    """
    result = redis_conn().lrange(f"session_context::{sessionId}::{fileId}", 0, limit - 1)
    redis_conn().close()
    result.reverse()
    return result


def add_session_content(sessionId, fileId, messages):
    """
    将消息追加到会话，有效期为一天
    :param sessionId: 会话id
    :param fileId 文件id
    :param messages: 消息
    :return:
    """
    for mes in messages:
        redis_conn().lpush(f"session_context::{sessionId}::{fileId}", mes)
    redis_conn().expire(f"session_context::{sessionId}::{fileId}", 60 * 60 * 24)
    redis_conn().close()


def exec_python_code(packages: str, code):
    print(packages)
    # package_list = packages.split(",")
    # for package in package_list:
    #     shell_exec(f"pip3 install {package}")
    client = km.client()
    client.start_channels()
    client.wait_for_ready()
    client.execute(code)
    result = flush_kernel_msgs(client, tries=5, timeout=1)
    client.stop_channels()
    if client.is_alive():
        try:
            client.shutdown()
        except Exception as ex:
            logger.error(ex)
    return result


def shell_exec(command):
    errors = []
    sub_pro = subprocess.Popen([command], shell=True,
                               cwd=os.path.dirname(__file__),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    for line in sub_pro.stdout.readlines():
        logger.info(line.decode('utf-8'))
    for error in sub_pro.stderr.readlines():
        logger.error(error.decode('utf-8'))
        errors.append(error)
    sub_pro.wait()
    return errors


def flush_kernel_msgs(kc, tries=1, timeout=0.2):
    result = {}
    try:
        hit_empty = 0
        sleep(1)
        while True:
            try:
                msg = kc.get_iopub_msg(timeout=timeout)
                if msg["msg_type"] == "execute_result":
                    if "text/plain" in msg["content"]["data"]:
                        execute_result = result.get("exec_result") or ''
                        execute_result = execute_result + "\n" + msg["content"]["data"]["text/plain"]
                        result["exec_result"] = execute_result
                if msg["msg_type"] == "display_data":
                    if "image/png" in msg["content"]["data"]:
                        result["image"] = msg["content"]["data"]["image/png"]
                    elif "text/plain" in msg["content"]["data"]:
                        execute_result = result.get("exec_result") or ''
                        execute_result = execute_result + "\n" + msg["content"]["data"]["text/plain"]
                        result["exec_result"] = execute_result
                elif msg["msg_type"] == "stream":
                    std_output = result.get("std_output") or ''
                    std_output = std_output + "\n" + msg["content"]["text"]
                    result["std_output"] = std_output
                    logger.debug("Received stream output %s" % msg["content"]["text"])
                elif msg["msg_type"] == "error":
                    std_error = result.get("std_error") or ''
                    std_error = std_error + "\n" + escape_ansi("\n".join(msg["content"]["traceback"]))
                    result["std_error"] = std_error
            except queue.Empty:
                hit_empty += 1
                if hit_empty == tries:
                    break
            except Exception as e:
                logger.debug(f"{e} [{type(e)}")
                break
        return result
    except Exception as e:
        logger.debug(f"{e} [{type(e)}")


def read_all_text(file_path):
    with open(file_path, "r", encoding='utf-8') as file:
        txt = file.read()
        return txt


def escape_ansi(line):
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


if __name__ == "__main__":
    # data = data_analyses("eed44e67440c452ea424543d13b76b76.csv", "Do you known these labels meaning :Token Legendary Trader,Token Billion Trader", sessionId="10048")
    # logger.info(json.dumps(data))
    data = data_analyses("eed44e67440c452ea424543d13b76b76.csv", "统计出现频率最高的前十条标签", sessionId="12345")
    logger.info(json.dumps(data))
    data = data_analyses("eed44e67440c452ea424543d13b76b76.csv", "用柱状图展示一下", sessionId="12345")
    logger.info(json.dumps(data))
    data = data_analyses("eed44e67440c452ea424543d13b76b76.csv", "尝试用你了解的知识去分析这几条数据的意义", sessionId="12345")
    logger.info(json.dumps(data))
    while True:
        sleep(10)
        print(111)
