import os

import openai
from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    String,
    insert,
)
from llama_index import SQLDatabase
from llama_index.indices.struct_store import (
    NLSQLTableQueryEngine
)

OPENAI_API_BASE = 'https://www.googlex.vip/v1'
openai.api_base = OPENAI_API_BASE
os.environ["OPENAI_API_KEY"] = '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'
openai.api_key = os.environ["OPENAI_API_KEY"]

engine = create_engine("duckdb:///:memory:")
# uncomment to make this work with MotherDuck
# engine = create_engine("duckdb:///md:llama-index")
metadata_obj = MetaData()

# create city SQL table
table_name = "address_label"
address_label_table = Table(
    table_name,
    metadata_obj,
    Column("address", String(50)),
    Column("content", String(100), nullable=False),
    Column("name", String(200), nullable=False),
    Column("wiredType", String(200), nullable=False),
    Column("source", String(200), nullable=False)
)
metadata_obj.create_all(engine)

import json

rows = []
with open('/Users/guoxinyou/Desktop/labels.json', 'r') as f:
    dataLoads = json.load(f)
    addresses = dataLoads.get("data").get("query_by_labels_action").get("data")
    for addr in addresses:
        address = addr.get("address").get("value")
        labels = addr.get("labels")
        for label in labels:
            content = label.get("content")
            name = label.get("name")
            source = label.get("source")
            wiredType = label.get("wiredType")
            rows.append({"address": address, "content": content, "name": name, "wiredType": wiredType, "source": source})
print(rows)

for row in rows:
    # print(row["address"] + "," + row["content"] + "," + row["name"] + "," + row["wiredType"] + "," + row["source"])
    stmt = insert(address_label_table).values(**row)
    with engine.connect() as connection:
        cursor = connection.execute(stmt)
        connection.commit()

sql_database = SQLDatabase(engine, include_tables=["address_label"])
query_engine = NLSQLTableQueryEngine(sql_database)
# response = query_engine.query("Which address has the most labels?")
response = query_engine.query("统计标签数量最多的前十个地址，给出结构化的数据")
print(response)

# with engine.connect() as connection:
#     cursor = connection.exec_driver_sql("SELECT * FROM address_label")
#     print(cursor.fetchall())
