#!/usr/bin/python
# -*- coding: UTF-8 -*-
import base64
import json
import os
import subprocess
import uuid

import openai
import pandas as pd

from base import logger_name, ChatResult, SystemMessage, HumanMessage, FunctionMessage
from base.logger_util import LOG
from file_tools import get_uuid

logger = LOG.get_logger(logger_name)

currentSessionTable = {}

data_explain_functions = [
    {
        "name": "exec_python_script",
        "description": "execute python script and return nothing,If you want to get the result,The result can only be saved through code, and then read the file",
        "parameters": {
            "type": "object",
            "properties": {
                "script": {
                    "type": "string",
                    "description": "the syntactically correct python script.Pay attention to the format when converting to json"
                }
            },
            "required": ["script"]
        }
    },
    {
        "name": "get_csv_data_sample",
        "description": "Get a sample of the five lines of data in the given file,the file type should be csv",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "the data file path"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "read_all_file_content",
        "description": "Read all file content,Due to permission restrictions,only files in the ./tmp directory can be read",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "the data file path"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "format_answer",
        "description": "Format the AI's answer",
        "parameters": {
            "type": "object",
            "properties": {
                "image_path": {
                    "type": "string",
                    "description": "the image file path,Due to permission restrictions, only files in the ./tmp directory can be read"
                },
                "content": {
                    "type": "string",
                    "description": "AI's answer content,Results of data analysis"
                }
            },
            "required": ["content"]
        }
    }
]


def read_all_file_content(file_path: str):
    if not os.path.isfile(file_path):
        return f"Error: No such file or directory: '{file_path}'"
    if not file_path.startswith("./tmp"):
        return "Error：no permission to read"
    if file_path.endswith(".png") or file_path.endswith(".jpg"):
        with open(file_path, 'rb') as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            return encoded_image
    with open(file_path, "r", encoding='utf-8') as file:
        txt = file.read()
        return txt


def format_answer(image_path, content):
    if image_path and not os.path.isfile(image_path):
        return {"success": False, "msg": "Error: No such file or directory"}
    tmp = {"success": True, "data": content}
    if image_path:
        with open(image_path, 'rb') as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        tmp["image"] = encoded_image
    return tmp


def get_csv_data_sample(file_path: str):
    if not os.path.isfile(file_path):
        return f"Error: No such file or directory: '{file_path}'"
    data = pd.read_csv(file_path)
    first_five_line = data.sample(5).to_csv(index=False)
    return first_five_line


def data_explain_chat(messages, using_function=False):
    logger.info("请求OPENAI" + json.dumps(messages))
    response = openai.ChatCompletion.create(
        temperature=0,
        model="gpt-4",
        messages=messages,
        functions=data_explain_functions,
        function_call="auto",
    ) if using_function else openai.ChatCompletion.create(
        temperature=0,
        model="gpt-4",
        messages=messages
    )
    response_message = response["choices"][0]["message"]
    logger.info(json.dumps(response_message))
    result = ChatResult(role=response_message.get("role"), content=response_message.get("content"), function_call=response_message.get("function_call"))
    print("chat result：", result)
    return result


def convert_data_to_csv(json_data, csv_path):
    rows = []
    data_loads = json.loads(json_data)
    addresses = data_loads.get("data").get("query_by_labels_action").get("data")
    for addr in addresses:
        address = addr.get("address").get("value")
        labels = addr.get("labels")
        for label in labels:
            content = label.get("content")
            name = label.get("name")
            source = label.get("source")
            wired_type = label.get("wiredType")
            if source == "SYSTEM":
                rows.append({"address": address, "content": content, "name": name, "wiredType": wired_type, "source": source})
    dataframe = pd.DataFrame(rows)
    dataframe.to_csv(csv_path, index=False, sep=',')


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


def read_all_text(file_path):
    with open(file_path, "r", encoding='utf-8') as file:
        txt = file.read()
        return txt


def write_all_text(file_path, contents):
    with open(file_path, "w", encoding='utf-8') as file:
        file.write(contents)


def explain_data1(json_data, question):
    csv_file_name = f"./tmp/{get_uuid()}.csv"
    os.makedirs("./tmp/", exist_ok=True)
    convert_data_to_csv(json_data, csv_file_name)
    python_file_data = f"./tmp/{get_uuid()}.py"
    messages = [SystemMessage(
        content="You are a data analysis engineer.\n According to the user's question explain the statistical data,"
                "And return the formatted data,You can use python scripts for auxiliary analysis"
                f"The user's data file is '{csv_file_name}'\n"
                f"If user wants to generate an image, you can return the image file path"), HumanMessage(content=question)]
    csv_sample = get_csv_data_sample(csv_file_name)
    messages.append(FunctionMessage(name="get_csv_data_sample", content=csv_sample))
    result = data_explain_chat(messages, using_function=True)
    times = 1
    while result.function_call and times < 5:
        '''
        不能让它无限次执行，限定五次
        '''
        times += 1
        if result.function_call.get("name") == "exec_python_script":
            arguments = json.loads(result.function_call.get("arguments"))
            python_code: str = arguments.get("script")
            logger.info(python_code)
            write_all_text(python_file_data, python_code)
            errors = shell_exec("python3 " + python_file_data)
            content = f"Python code ```python\n {python_code} \n``` execution success"
            if errors:
                content = f"Python code ```python\n {python_code} \n``` execution fail,the errors is :{errors}"
            messages.append(FunctionMessage(name="exec_python_script", content=content))
            result = data_explain_chat(messages, using_function=True)
        elif result.function_call.get("name") == "get_csv_data_sample":
            arguments = json.loads(result.function_call.get("arguments"))
            file_path: str = arguments.get("file_path")
            file_sample = get_csv_data_sample(file_path)
            messages.append(FunctionMessage(name="get_csv_data_sample", content=file_sample))
            result = data_explain_chat(messages, using_function=True)
        elif result.function_call.get("name") == "read_all_file_content":
            arguments = json.loads(result.function_call.get("arguments"))
            file_path: str = arguments.get("file_path")
            file_content = read_all_file_content(file_path)
            messages.append(FunctionMessage(name="read_all_file_content", content=file_content))
            result = data_explain_chat(messages, using_function=True)
        elif result.function_call.get("name") == "format_answer":
            arguments = json.loads(result.function_call.get("arguments"))
            image_path = arguments.get("image_path")
            content = arguments.get("content")
            format_result = format_answer(image_path=image_path, content=content)
            if format_result.get("success"):
                return {"success": True, "data": format_result.get("data"), "image": format_result.get("image")}
            else:
                msg = format_result.get("msg")
                messages.append(FunctionMessage(name="format_answer", content=msg))
                result = data_explain_chat(messages, using_function=True)
    return {"success": False, "data": result.content}


if __name__ == "__main__":
    with open("/Users/guoxinyou/Desktop/labels.json", "r", encoding='utf-8') as f:
        json_str = f.read()
        an_result = explain_data1(json_str, "统计地址0x000077151fc27e13b09b508e0258762d06a4a8cc下所有的标签")
        logger.info(an_result)
