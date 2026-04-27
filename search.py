from tavily import TavilyClient
client = TavilyClient("tvly-dev-xxxZ")
response = client.search(
    query="北京今天天气怎么样",
    search_depth="advanced"
)
print(response)