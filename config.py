from azure.cosmos import CosmosClient
import os

COSMOS_ENDPOINT = os.environ.get("COSMOS_ENDPOINT")
COSMOS_KEY = os.environ.get("COSMOS_KEY")

# Cosmos DB に接続してクエリを実行
cosmos_client = CosmosClient(COSMOS_ENDPOINT, COSMOS_KEY)