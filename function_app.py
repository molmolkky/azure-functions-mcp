import azure.functions as func
from openai import AzureOpenAI
import logging
import json
import os

from config import cosmos_client
from utils import simplify_cosmos_item

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

# CosmosDBのログ出力レベルをWARNINGに設定（ターミナルの表示が減る）
logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel('WARNING')

COSMOS_DATABASE_NAME = os.environ.get("COSMOS_DATABASE_NAME")
COSMOS_CONTAINER_NAME = os.environ.get("COSMOS_CONTAINER_NAME")

# OpenAI API キー（必要に応じて設定）
AZURE_OPENAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.environ.get("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_DEPLOYMENT_NAME = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION")

aoai_client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION
)

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="query_cosmosdb",
    description="自然言語でデータを取得します。",
    toolProperties='[{"propertyName": "query", "propertyType": "string", "description": "取得したい情報を自然言語で入力してください。"}]',
)
def query_cosmosdb(context) -> str:
    try:
        logging.info("MCPToll Called! query_cosmosdb")
        # 自然言語クエリを取得
        content = json.loads(context)
        natural_language_query = content["arguments"]["query"]

        logging.info(f"自然言語クエリ: {natural_language_query}")

        # サンプルアイテムを取得
        database = cosmos_client.get_database_client(COSMOS_DATABASE_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)
        sample_items = list(container.query_items(query="SELECT TOP 1 * FROM c", enable_cross_partition_query=True))

        sample_item = simplify_cosmos_item(sample_items[0])

        # 自然言語を SQL に変換（OpenAI API を使用する例）
        system_prompt = """あなたは、ユーザーの意図を汲んで欲しいデータを提示するための、CosmosDBのSQL生成のスペシャリストです。ユーザーの質問をCosmosDBのSQLに変換してください。'
        コンテナーのデータは以下のようなアイテムが格納されています: 
        
        ## アイテム例
        <<sample_item>>

        ## 出力形式
        以下JSON形式に従って出力すること:

        {
            "sql": "ここにSQLを出力"
        }

        ## 注意事項
        - 安易に SELECT * FROM c を使用しないこと。
        """
        messages = [{"role": "system", "content": system_prompt.replace("<<sample_item>>", str(sample_item))},
                    {"role": "user", "content": natural_language_query}]
        logging.info("AOAI Calling...")
        response = aoai_client.chat.completions.create(
            messages=messages,
            model=AZURE_OPENAI_DEPLOYMENT_NAME,
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        response_json = json.loads(response.choices[0].message.content)
        sql_query = response_json.get("sql")
        logging.info("AOAI Reponse completed!"
                     f"SQL: {sql_query}")

        # Cosmos DB に接続してクエリを実行
        database = cosmos_client.get_database_client(COSMOS_DATABASE_NAME)
        container = database.get_container_client(COSMOS_CONTAINER_NAME)
        items = []
        for item in container.query_items(query=sql_query, enable_cross_partition_query=True):
            simple_item = simplify_cosmos_item(item)
            items.append(simple_item)
        logging.info(f"GET items from CosmosDB: {len(items)} items.")
        return json.dumps(items, ensure_ascii=False)

    except Exception as e:
        logging.error(f"エラーが発生しました: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)

@app.generic_trigger(
    arg_name="context",
    type="mcpToolTrigger",
    toolName="hello_mcp",
    description="国で使用している言語を取得します。",
    toolProperties='[{"propertyName": "country", "propertyType": "string", "description": "国名を英語で入れてください"}]',
)
def judge_langage(context) -> str:
    logging.info("MCPTool called! judge_langage")
    content = json.loads(context)
    country_name = content["arguments"]["country"]
    logging.info(f"content: {content}")

    if country_name.lower() == "japan":
        return f"{country_name}は日本語です"
    elif country_name.lower() == "china":
        return f"{country_name}は中国語です"
    else:
        return f"{country_name}は日本語でも中国語でもない別の言語です"
