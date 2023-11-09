from base import MILVUS_HOST, MILVUS_PORT, MILVUS_USER, MILVUS_PASS
from pymilvus import DataType, CollectionSchema, FieldSchema, Collection, connections

connect = connections.connect(alias='default'
                              , host=MILVUS_HOST
                              , port=MILVUS_PORT
                              , user=MILVUS_USER
                              , password=MILVUS_PASS)

# 索引
index_params = {
    "metric_type": "L2",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 1024}
}

# 创建collection的表字段
question_schema = FieldSchema(name='question', dtype=DataType.VARCHAR, max_length=4096)
answer_schema = FieldSchema(name='answer', dtype=DataType.VARCHAR, max_length=8192)
vector_schema = FieldSchema(name='field_search', dtype=DataType.FLOAT_VECTOR, dim=1536)
id_schema = FieldSchema(name='id', dtype=DataType.INT64, is_primary=True, auto_id=True)

# 创建schema
schema = CollectionSchema(fields=[id_schema, vector_schema, question_schema, answer_schema])

collection = Collection(name="trained_sql_data", schema=schema, using='default', consistency_level="Session")

collection.create_index(field_name="field_search", index_params=index_params)

collection.load()
print(collection)
