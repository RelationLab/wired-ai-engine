from typing import Optional

import uvicorn as uvicorn
from fastapi import FastAPI, UploadFile, Form
from pydantic import BaseModel

from base import logger_name
from base.logger_util import LOG
from chat_tools import get_answer, get_answer_v2
from data_analyses import data_analyses
from data_interpretation import data_interpretation_chat
from file_tools import save_file, save_file_url, get_uuid
from label_tools import redefine_label_info, get_label_info, delete_label_info
from long_json_analysis import long_json_chat, long_json_analysis, get_task_result
from table_tools import redefine_table_info, get_table_info, delete_table_info
from train_tools import train, find_similar_question
from train_tools_v2 import train_v2, find_similar_question_v2

logger = LOG.get_logger(logger_name)


def success(data: object = "执行成功"):
    return {"success": True,
            "data": data}


def fail(msg="执行失败"):
    return {"success": False,
            "data": msg}


class Ask(BaseModel):
    question: str
    sessionId: Optional[str] = None


class TrainSql(BaseModel):
    question: str
    answer: str


class GetSql(BaseModel):
    question: str


class TrainTable(BaseModel):
    tableName: str
    description: str


class TrainLabel(BaseModel):
    labelName: str
    description: str


class DataAnalyses(BaseModel):
    fileId: str
    sessionId: Optional[str] = None
    question: str


class DataInterpretation(BaseModel):
    reportName: Optional[str] = None
    reportData: Optional[str] = None
    reportDesc: Optional[str] = None
    question: str
    sessionId: Optional[str] = None


class LongJsonChat(BaseModel):
    sessionId: Optional[str] = None
    jsonData: Optional[str] = None
    question: Optional[str] = None


app = FastAPI()


@app.post("/sql/ask")
def ask(question: Ask):
    try:
        result = get_answer(question.sessionId, question.question)
        if result:
            return success(result.get('data'))
        else:
            return fail()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/sql/ask_v2")
def ask_v2(question: Ask):
    try:
        result = get_answer_v2(question.sessionId, question.question)
        if result:
            return success(result.get('data'))
        else:
            return fail()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/sql/train")
def train_data(qa: TrainSql):
    try:
        train(qa.question, qa.answer, cover_similar=True)
        return success()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/sql/train_v2")
def train_data_v2(qa: TrainSql):
    try:
        train_v2(qa.question, qa.answer, cover_similar=True)
        return success()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/sql/find_similar")
def find_similar(data: GetSql):
    try:
        results = find_similar_question(data.question, limit=5)
        similar_data = [{"question": result[2].get("question"), "answer": result[2].get("answer")} for result in results or []]
        return success(similar_data)
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/sql/find_similar_v2")
def find_similar(data: GetSql):
    try:
        results = find_similar_question_v2(data.question, limit=5)
        similar_data = [{"question": result[2].get("question"), "answer": result[2].get("answer")} for result in results or []]
        return success(similar_data)
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/table/redefine")
def redefineTableInfo(tableInfo: TrainTable):
    try:
        redefine_table_info(tableInfo.tableName, tableInfo.description)
        return success()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.get("/table/get")
def getTableInfo(tableName: str):
    try:
        return success(get_table_info(tableName))
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.delete("/table/delete")
def deleteTableInfo(tableName: str):
    try:
        delete_table_info(tableName)
        return success()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/label/redefine")
def redefineLabelInfo(labelInfo: TrainLabel):
    try:
        redefine_label_info(labelInfo.labelName, labelInfo.description)
        return success()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.get("/label/get")
def getLabelInfo(labelName: str):
    try:
        return success(get_label_info(labelName))
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.delete("/label/delete")
def deleteLabelInfo(labelName: str):
    try:
        delete_label_info(labelName)
        return success()
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/data/analyses")
def analyses(dataAnalyses: DataAnalyses):
    try:
        result = data_analyses(dataAnalyses.fileId, dataAnalyses.question, dataAnalyses.sessionId)
        return result
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/file/upload")
def file_upload(file: UploadFile):
    try:
        return success(save_file(file))
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/file/upload_by_url")
def file_upload_url(url: str = Form()):
    try:
        return success(save_file_url(url))
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/data/interpretation")
def data_interpretation(data: DataInterpretation):
    try:
        result = data_interpretation_chat(report_name=data.reportName,
                                          report_data=data.reportData,
                                          report_desc=data.reportDesc,
                                          question=data.question,
                                          sessionId=data.sessionId)
        return success(result)
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/report/json_analyses")
def long_json_analyses(data: LongJsonChat):
    try:
        if not data.jsonData:
            raise Exception("json_data can't be None")
        taskId = get_uuid()
        long_json_analysis(json_data=data.jsonData, taskId=taskId, sessionId=data.sessionId)
        return success({"taskId": taskId})
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.get("/report/get_task_info")
def get_task_info(taskId: str):
    try:
        return get_task_result(taskId=taskId)
    except Exception as ex:
        logger.error(ex)
        return fail()


@app.post("/report/json_chat")
def json_chat(data: LongJsonChat):
    try:
        return long_json_chat(question=data.question, sessionId=data.sessionId)
    except Exception as ex:
        logger.error(ex)
        return fail()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8765)
