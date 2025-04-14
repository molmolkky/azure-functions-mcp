# Azure FunctionsのMCPサーバーの実装例(Python)

Azure FunctionsでMCPサーバーをローカルとリモートの両方で実装できるようになりました。
そこで、[記事](https://techcommunity.microsoft.com/blog/appsonazureblog/build-ai-agent-tools-using-remote-mcp-with-azure-functions/4401059)と[GitHub](https://github.com/Azure-Samples/remote-mcp-functions-python/tree/main)を参考にして、CosmosDBに自然言語でデータを取得するMCPサーバーを作成しました。

## MCP Inspectorを使用した動作確認手順
### ローカルで実行する場合
1. 本リポジトリをクローンして、ルートディレクトリでazuriteとfunc startをターミナルで実行します。
  ```bash
  azurite
  ```
  ```bash
  func start
  ```
2. MCP Inspectorをターミナルで起動します
   ```bash
   npx @modelcontextprotocol/inspector
   ```
   インストールは不要になっています。
3. ターミナルに表示されるURLをブラウザで開きます（以下はURLの例）
   ```bash
   🔍 MCP Inspector is up and running at http://127.0.0.1:6274 🚀
   ```
4. 画面左上の「Transport Type」を`SSE`に設定します。
5. 「URL」に以下を貼り付けます
  ```
  http://0.0.0.0:7071/runtime/webhooks/mcp/sse
  ```
6. あとはToolを選択して実行します。