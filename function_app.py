import azure.functions as func
from azure.cosmos import CosmosClient
from openai import AzureOpenAI
import logging
import json
import os

from config import cosmos_client

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
        # 自然言語クエリを取得
        content = json.loads(context)
        natural_language_query = content["arguments"]["query"]

        logging.info(f"自然言語クエリ: {natural_language_query}")

        # 自然言語を SQL に変換（OpenAI API を使用する例）
        system_prompt = """あなたは、ユーザーの意図を汲んで欲しいデータを提示するための、CosmosDBのSQL生成のスペシャリストです。ユーザーの質問をCosmosDBのSQLに変換してください。'
        コンテナーのデータは以下のようなフィールドを持っています: 

        ## フィールド説明
            - id (str): 一意キー
            - city (str): 都道府県＋市区町村（パーティションキー）
            - types (List[str]): 飲食店のカテゴリリスト
            - nationalPhoneNumber (str): 電話番号
            - formattedAddress (str): 住所
            - rating (float): 評価
            - displayName: 表示名 
                - text (str): 店名
                - languageCode (str): 言語を示すISO2桁コード  
        
        ## アイテム例
        {{
            "id": ,
            "city": "東京都渋谷区",
            "types": [
                "italian_restaurant",
                "bar_and_grill",
                "vegetarian_restaurant",
                "steak_house",
                "meal_takeaway",
                "restaurant",
                "food",
                "bar",
                "point_of_interest",
                "establishment"
            ],
            "nationalPhoneNumber": "03-6434-7155",
            "formattedAddress": "日本、〒107-0061 東京都港区北青山３丁目５−４３ 表参道LAB 1F",
            "rating": 4.4,
            "displayName": {
                "text": "TRATTORIA 庭",
                "languageCode": "ja"
            }
        }}

        ## 出力形式
        以下JSON形式に従って出力すること:

        {
            "sql": "ここにSQLを出力"
        }

        ## 注意事項
        - 安易に SELECT * FROM c を使用しないこと。
        """
        messages = [{"role": "system", "content": system_prompt},
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
        items = list(container.query_items(query=sql_query, enable_cross_partition_query=True))
        logging.info(f"GET items from CosmosDB: {len(items)} items.")
        return json.dumps(items, ensure_ascii=False)

    except Exception as e:
        logging.error(f"エラーが発生しました: {e}")
        return json.dumps({"error": str(e)}, ensure_ascii=False)
