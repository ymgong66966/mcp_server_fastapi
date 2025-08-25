from urllib.parse import urlparse
from pymilvus import connections, CollectionSchema, FieldSchema, DataType, Collection
# from langchain_community.vectorstores import Zilliz
from langchain_openai import OpenAIEmbeddings
from langchain.docstore.document import Document
from typing import List, Dict, Optional
import uuid
import pickle
import os
import json
from firecrawl import FirecrawlApp
from pymilvus import MilvusClient
from langchain_community.vectorstores import Zilliz
from langchain_openai import OpenAIEmbeddings
from openai import AsyncOpenAI
import dotenv
from dotenv import load_dotenv
from langsmith import traceable

# Load environment variables from .env file
load_dotenv()

openai_client = AsyncOpenAI()

class TrieNode:
    def __init__(self):
        self.children = {}
        self.urls = []  # All URLs that pass through this node
        self.domain_id = None  # Store domain ID if this is a domain node
        self.already_crawled = False

class URLTrie:
    def __init__(self):
        self.root = TrieNode()
        self.domain_mapping = self.load_or_create_domain_mapping()

    def load_or_create_domain_mapping(self, pickle_path: str = '/Users/xyxg025/langraph_api/src/react_agent/domain_uuid_mapping.pkl') -> Dict[str, str]:
        """Load existing domain-UUID mapping or create a new one."""
        if os.path.exists(pickle_path):
            with open(pickle_path, 'rb') as f:
                print(f"Loading existing domain mappings from {pickle_path}")
                return pickle.load(f)
        print(f"Creating new domain mappings file at {pickle_path}")
        return {}

    def save_domain_mapping(self, pickle_path: str = '/Users/xyxg025/langraph_api/src/react_agent/domain_uuid_mapping.pkl'):
        """Save the current domain-UUID mapping."""
        with open(pickle_path, 'wb') as f:
            pickle.dump(self.domain_mapping, f)
        print(f"Saved domain mappings to {pickle_path}")

    def get_domain_uuid(self, domain: str) -> str:
        """Get or create UUID for a domain."""
        if domain not in self.domain_mapping:
            self.domain_mapping[domain] = str(uuid.uuid4())
            print(f"Created new UUID for domain {domain}: {self.domain_mapping[domain]}")
        return self.domain_mapping[domain]

    async def insert(self, url: str, domain: str, domain_id: str):
        """Insert a URL into the trie and update domain mapping."""
        # Extract domain
        # domain_parts = tldextract.extract(url)
        # domain = f"{domain_parts.subdomain}.{domain_parts.domain}.{domain_parts.suffix}".strip('.')
        # domain_id = self.get_domain_uuid(domain)
        
        # Parse URL path
        parsed_url = urlparse(url)
        path_components = parsed_url.path.strip('/').split('/') if parsed_url.path.strip('/') else []
        
        # Start at root
        current = self.root
        
        # First, create/navigate to domain node
        if domain not in current.children:
            current.children[domain] = TrieNode()
        current = current.children[domain]
        current.domain_id = domain_id
        # No need to add URL to domain node
        # current.urls.append(url)
        
        # Insert path components
        for component in path_components:
            if component not in current.children:
                current.children[component] = TrieNode()
            current = current.children[component]
            current.urls.append(url)
            current.domain_id = domain_id

    async def collect_nodes(self) -> List[Dict]:
        """Collect all nodes with their paths, URLs, and domain IDs."""
        result = []
        await self._collect_nodes_helper(self.root, result, "")
        return result

    async def _collect_nodes_helper(self, node: TrieNode, result: List[Dict], path: str):
        if node.urls:  # Only add nodes that have URLs
            current_node_name = path.split('/')[-1] if path else 'root'
            result.append({
                "path": current_node_name,
                "urls": node.urls,
                "domain_id": node.domain_id,
                "already_crawled": node.already_crawled
            })

        for child_name, child_node in node.children.items():
            new_path = f"{path}/{child_name}".lstrip('/')
            await self._collect_nodes_helper(child_node, result, new_path)

async def milvus_emd(nodes):
    milvus_client = MilvusClient(uri="https://in03-d02578f8d924784.serverless.gcp-us-west1.cloud.zilliz.com", token="7fd68eede1a3136bd93d500c83d741f3fcd3405598e19fa2f3631074e5834556ad135bb7c9caf7618eab0063a8e17cd662936d8b")

    connections.connect(
        alias="default",
        uri="https://in03-d02578f8d924784.serverless.gcp-us-west1.cloud.zilliz.com",
        token="7fd68eede1a3136bd93d500c83d741f3fcd3405598e19fa2f3631074e5834556ad135bb7c9caf7618eab0063a8e17cd662936d8b"
    )

    # Create collection
    collection_name = "url_trie_test"
    # milvus_client.drop_collection(collection_name)
    if not milvus_client.has_collection(collection_name):
        # Create schema for the collection
        dim = 1536  # Dimension for OpenAI embeddings
        schema = CollectionSchema(
        fields=[
            FieldSchema(name="id", dtype=DataType.VARCHAR, max_length=100, is_primary=True),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name="path", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="urls", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="domain_id", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="already_crawled", dtype=DataType.BOOL)
        ],
        description="URL Trie collection"
    )
        collection = Collection(name=collection_name, schema=schema)

        # Create index on the vector field
        index_params = {
            "metric_type": "L2",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 1024}
        }
        collection.create_index(field_name="vector", index_params=index_params)
        collection.load()
    else:
        collection = Collection(name=collection_name)

    print(f"Collection '{collection_name}' and index created successfully.")

    # Prepare documents with enhanced metadata
    chunks = [
        Document(
            page_content=f"{node['path']}",
            page_content_type="text",
            metadata={
                "path": node['path'],
                "urls": node['urls'],
                "domain_id": node['domain_id'],
                "already_crawled": node['already_crawled']
            }
        )
        for node in nodes
    ]

    # Define the embedding model
    embeddings = OpenAIEmbeddings()

    # Generate embeddings for the texts
    texts = [doc.page_content for doc in chunks]
    vectors = await embeddings.aembed_documents(texts)
    metadatas = [doc.metadata for doc in chunks]
    ids = [str(uuid.uuid4()) for _ in range(len(chunks))]

    # Insert data
    insert_data = [
        ids,                # id field
        texts,             # text field
        vectors,           # vector field
        [node['path'] for node in nodes],  # path field
        [','.join(node['urls'][:50]) for node in nodes],  # urls field as comma-separated string
        [str(node['domain_id']) for node in nodes],  # domain_id field
        [node['already_crawled'] for node in nodes]  # already_crawled field
    ]

    # Insert the data directly using the collection
    collection.insert(insert_data)
    collection.flush()

async def root_url_2_trie(domain: str):
    trie = URLTrie()
    if domain not in trie.domain_mapping:
        app = FirecrawlApp(api_key='fc-a316f888b79549cfa9bf3e23a8ec6556')
        url_list = await app.map_url(domain)
        domain_id = await trie.get_domain_uuid(domain)
        print("DOMAIN ID_1:", domain_id)
        for url in url_list['links']:
            await trie.insert(url, domain, domain_id)
        await trie.save_domain_mapping()
        nodes = await trie.collect_nodes()
        await milvus_emd(nodes)
        return domain_id
    else:
        domain_id = trie.domain_mapping[domain]
        return  domain_id

async def emb_text(text):
    return (
        await openai_client.embeddings.create(input=text, model="text-embedding-3-small")
        .data[0]
        .embedding
    )

async def generate_related_queries(base_query: list, num_queries: int = 5) -> list:
    client = AsyncOpenAI()
    
    prompt = f"""Given the search query: "{base_query}"
    Generate {num_queries} related database search queries.
    The questions should:
    1. Be concise and friendly for vector database search
    2. Paraphrase the query 
    3. Be relevant to the base query
    4. Do not include the care agency name in the questions
    5. Do not include the care agency domain in the questions
    For example, if the base query is "What areas does BrightStar Care support in Illinois?", the generated sub-queries should be something like "Areas in Illinois", "locations near chicago", etc.
    Format the response as a JSON array of strings.
    """
    
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates related search queries"},
            {"role": "user", "content": prompt}
        ],
        temperature=0,
    )
    
    try:
        queries = json.loads(response.choices[0].message.content)
        print(queries, "queries")
        return queries
    except json.JSONDecodeError:
        content = response.choices[0].message.content
        content = content.replace("```json", "").replace("```", "")
        try:
            return json.loads(content)
        except:
            print("Failed to parse response as JSON. Raw response:")
            print(content)
            return []

async def url_vector_search(base_query: list, domain_id: str):
    related_queries = await generate_related_queries(base_query)
    # all_results, related_queries = ["test"], ["test"]
    collection_name = "url_trie_test"
    embeddings = OpenAIEmbeddings()

    vectorstore = Zilliz(
        embedding_function=embeddings,
        collection_name=collection_name,
        connection_args={
            "uri": "https://in03-d02578f8d924784.serverless.gcp-us-west1.cloud.zilliz.com",
            "token": "7fd68eede1a3136bd93d500c83d741f3fcd3405598e19fa2f3631074e5834556ad135bb7c9caf7618eab0063a8e17cd662936d8b",
        }
    )

    # print(f"\nBase Query: {base_query}")
    # print("\nRelated Queries:")
    # for i, query in enumerate(related_queries, 1):
    #     print(f"{i}. {query}")

    all_results = []
    for query in related_queries:
        results = vectorstore.similarity_search(query, k=2, expr=f"domain_id == '{domain_id}'&& already_crawled == false")

        all_results.extend(results)
        for i, doc in enumerate(results, 1):
            print(f"\nResult {i}:")
            print(f"Content: {doc.page_content}")
            print(f"Path: {doc.metadata['path']}")
            urls = doc.metadata['urls'].split(',') if doc.metadata['urls'] else []
            print(f"Number of URLs: {len(urls)}")
            if urls:
                print(f"Sample URL: {urls[0]}")
            print(f"Domain ID: {doc.metadata['domain_id']}")

    return all_results, related_queries

@traceable
async def pick_relevant(all_results, related_queries):
    all_urls = []
    for doc in all_results:
        urls = doc.metadata['urls'].split(',') if doc.metadata['urls'] else []
        all_urls.extend(urls)
    
    unique_urls = list(dict.fromkeys(all_urls))
    
    context = {
        "queries": related_queries,
        "urls": unique_urls[:50]  # Limit to first 50 URLs to avoid token limits
    }
    print(context)
    prompt = f"""Given these search queries about insurance and healthcare services:
    {json.dumps(related_queries, indent=2)}
    
    And these URLs:
    {json.dumps(context['urls'], indent=2)}
    
    Select the most relevant URLs that would answer these queries.
    Return ONLY a JSON array of URLs, nothing else.
    """
    
    @traceable
    async def openai_call(prompt):
        response = await openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that selects relevant URLs based on search queries. Make sure to look at all the search queries, not just the first one. Pick the relevant urls for each one of these search queries. Make sure you at least pick one url!! Make sure you at least pick one url!! IMPORTANT: Return ONLY a JSON format dictionary, the key should be called relevant_urls and the value should be a list of URLs, nothing else. DO not include any thest like json or output or JSON in your response."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        return response

    response = await openai_call(prompt)
    
    try:
        relevant_urls = json.loads(response.choices[0].message.content)['relevant_urls']
        # print("\nSelected relevant URLs:")
        # for url in relevant_urls:
        #     print(f"- {url}")
        return relevant_urls
    except json.JSONDecodeError:
        content = response.choices[0].message.content.strip()
        content = content.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(content)
        except:
            print("Failed to parse response as JSON. Raw response:")
            print(content)
            return []

async def zilliz_url_trie(domain, base_query):
    domain_id = await root_url_2_trie(domain)
    
    all_results, related_queries = await url_vector_search(base_query, domain_id)
    print(all_results, related_queries, "all_results, related_queries")
    relevant_urls = await pick_relevant(all_results,related_queries)
    return relevant_urls

# import asyncio
# async def main():
#     relevant_urls = await zilliz_url_trie("brightstarcare.com", ["insurance they accept?", "what services do they offer?"])
#     print(relevant_urls)

# asyncio.run(main())