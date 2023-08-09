#!/usr/bin/python
# -*- coding: UTF-8 -*-
import base64
import json
import os
import uuid

import matplotlib
import matplotlib.pyplot as plt
import openai
import pandas as pd

from base import logger_name, ChatResult, SystemMessage, HumanMessage, FunctionMessage
from base.logger_util import LOG

matplotlib.use('Agg')
logger = LOG.get_logger(logger_name)

currentSessionTable = {}

data_explain_functions = [
    {
        "name": "data_analysis",
        "description": "According to the user's data file,Perform data analysis and statistics based on the provided label name. return the statistics result and generate statistical charts",
        "parameters": {
            "type": "object",
            "properties": {
                "label_name": {
                    "type": "string",
                    "description": "The specified label name."
                },
                "chart_type": {
                    "type": "string",
                    "description": "chart type Currently only supports bar,pie,line"
                },
                "top_k": {
                    "type": "integer",
                    "description": "number of labels to analyze"
                }
            },
            "required": ["label_name", "chart_type"]
        }
    }
]


def data_analysis(csv_file_path, label_name: str, chart_type, top_k: int = None):
    if chart_type not in ["bar", "pie", "line"]:
        raise RuntimeError("不支持的类型")
    if not top_k:
        top_k = 10
    data = pd.read_csv(csv_file_path)
    first_five_line = data.sample(5).to_csv(index=False)
    eth_df = data[data['content'].str.contains(label_name, case=False)]
    content_counts = eth_df['content'].value_counts().nlargest(top_k)
    # content_counts.to_json(json_file_path)
    plt.figure(figsize=(10, 6))
    plt.rcParams["font.sans-serif"] = ["SimHei"]
    plt.rcParams["axes.unicode_minus"] = False
    content_counts.plot(kind=chart_type)
    plt.title(f'Distribution of {label_name} related content')
    plt.xlabel('Content')
    plt.ylabel('Frequency')
    plt.tight_layout()
    plt.savefig('./tmp/tmp.png')
    with open('./tmp/tmp.png', 'rb') as image_file:
        encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
    json_result = content_counts.to_json()
    return encoded_image, json_result, first_five_line


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
    return result


def convert_data_to_csv(json_data, csv_path):
    rows = []
    dataLoads = json.loads(json_data)
    addresses = dataLoads.get("data").get("query_by_labels_action").get("data")
    for addr in addresses:
        address = addr.get("address").get("value")
        labels = addr.get("labels")
        for label in labels:
            content = label.get("content")
            name = label.get("name")
            source = label.get("source")
            wiredType = label.get("wiredType")
            if source == "SYSTEM":
                rows.append({"address": address, "content": content, "name": name, "wiredType": wiredType, "source": source})
    dataframe = pd.DataFrame(rows)
    dataframe.to_csv(csv_path, index=False, sep=',')


def explain_data(json_data, question):
    csv_file_name = f"./tmp/{uuid.uuid4()}.csv"
    os.makedirs("./tmp/", exist_ok=True)
    convert_data_to_csv(json_data, csv_file_name)
    messages = [SystemMessage(content="You are a data analysis engineer.\n According to the user's question and functions execute result explain the statistical data"),
                HumanMessage(content=question)]
    result = data_explain_chat(messages, using_function=True)
    if result.function_call and result.function_call.get("name") == "data_analysis":
        arguments = json.loads(result.function_call.get("arguments"))
        label_name: str = arguments.get("label_name")
        chart_type: str = arguments.get("chart_type")
        encoded_image, json_result, first_five_line = data_analysis(csv_file_name, label_name, chart_type)
        messages.append(FunctionMessage(name="data_analysis", content=f"the statistics data result is {json_result}, and  part of the file is as follows: \n{first_five_line}"))
        result = data_explain_chat(messages)
        return {"success": False, "data": result.content, "image": encoded_image}
    else:
        return {"success": False, "data": result.content}


if __name__ == "__main__":
    pass
    # with open("/Users/guoxinyou/Desktop/labels.json", "r", encoding='utf-8') as f:
    #     json_str = f.read()
    #     result = explain_data(json_str, "统计下eth相关的标签分布")
    #     logger.info(result)
