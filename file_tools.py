import uuid

from fastapi import UploadFile


def get_uuid():
    return str(uuid.uuid4()).replace("-", "")


def save_file(file: UploadFile):
    uid: str = get_uuid()
    file_bytes = file.file.read()
    file_name = file.filename
    ext_name = file_name[file_name.rfind("."):]
    output = open("./tmp/" + uid + ext_name, "wb")
    output.write(file_bytes)
    return uid + ext_name
