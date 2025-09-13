from langchain_community.vectorstores import Zilliz
from langchain_openai import OpenAIEmbeddings
import os

collection_name = "url_trie_test"
embeddings = OpenAIEmbeddings()
vectorstore = Zilliz(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args={
            "uri": os.getenv("ZILLIZ_URI", "https://in03-d02578f8d924784.serverless.gcp-us-west1.cloud.zilliz.com"),
            "token": os.getenv("ZILLIZ_TOKEN", "7fd68eede1a3136bd93d500c83d741f3fcd3405598e19fa2f3631074e5834556ad135bb7c9caf7618eab0063a8e17cd662936d8b"),
        }
    )