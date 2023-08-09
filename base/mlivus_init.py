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
table_name_schema = FieldSchema(name='table_name', dtype=DataType.VARCHAR, max_length=100)
table_desc_schema = FieldSchema(name='table_desc', dtype=DataType.VARCHAR, max_length=8192)
vector_schema = FieldSchema(name='field_search', dtype=DataType.FLOAT_VECTOR, dim=1536)
id_schema = FieldSchema(name='id', dtype=DataType.INT64, is_primary=True, auto_id=True)

# 创建schema
schema = CollectionSchema(fields=[id_schema, vector_schema, table_name_schema, table_desc_schema])

collection = Collection(name="table_info_new_v2", schema=schema, using='default', consistency_level="Session")

collection.create_index(field_name="field_search", index_params=index_params)

print(collection)
