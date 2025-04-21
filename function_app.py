import azure.functions as func
from openai import AzureOpenAI
from contextlib import AsyncExitStack
import logging
import json
import os

from mcp import ClientSession
from mcp.client.sse import sse_client
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

# MCPServerの環境変数を取得
MCPSERVER_FUNC_NAME = os.environ.get("MCPSERVER_FUNC_NAME")
MCPSERVER_FUNC_KEY = os.environ.get("MCPSERVER_FUNC_KEY", "")


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
    toolName="judge_langage",
    description="公用語を取得します。",
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

@app.function_name(name="mcp_keep_alive")
@app.timer_trigger(arg_name="myTimer", schedule="*/15 * * * * *", run_on_startup=False, use_monitor=False)
async def mcp_keep_alive(myTimer: func.TimerRequest) -> None:
    logging.info("mcp_keep_alive started.")

    try:
        async with AsyncExitStack() as stack:
            # タイムアウト設定を追加
            stdio, write = await stack.enter_async_context(
                sse_client(f"{MCPSERVER_FUNC_NAME}/runtime/webhooks/mcp/sse", 
                           headers={"x-functions-key": MCPSERVER_FUNC_KEY},
                           timeout=30)
            )
            session = await stack.enter_async_context(ClientSession(stdio, write))
            await session.initialize()

            response = await session.list_tools()
            available_tools = response.tools
            logging.info(f"=====Available Tools: {available_tools}======")

            tool_name = "judge_langage"
            tool_args = {"country": "Japan"}
            logging.info(f"Calling tool {tool_name} with args {tool_args}")
            tool_result = await session.call_tool(tool_name, tool_args)
            logging.info(f"Tool Result: {tool_result}")
    except Exception as e:
        logging.error(f"Error in MCP client: {e}")
        import traceback
        logging.error(traceback.format_exc())