import uuid

import requests

from fastapi import UploadFile


def get_uuid():
    return str(uuid.uuid4()).replace("-", "")


def save_file(file: UploadFile):
    uid: str = get_uuid()
    file_bytes = file.file.read()
    file_name = file.filename
    ext_name = file_name[file_name.rfind("."):]
    output = open("/tmp/" + uid + ext_name, "wb")
    output.write(file_bytes)
    return uid + ext_name


def save_file_url(url: str):
    urlFile = requests.get(url, stream=True)
    if urlFile.status_code == 200:
        uid: str = get_uuid()
        ext_name = url[url.rfind("."):]
        output = open("/tmp/" + uid + ext_name, "wb")
        for chunk in urlFile.iter_content(chunk_size=512):
            if chunk:
                output.write(chunk)
        output.close()
        return uid + ext_name
    else:
        raise Exception("文件下载失败")
