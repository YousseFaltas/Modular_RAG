
import weaviate
from pprint import pprint

client = weaviate.connect_to_local()
# ==============================
## Get collection informaation
# ==============================

# articles = client.collections.use("DocChunk")
# articles_config = articles.config.get()
# pprint(articles_config)

# ======================================
## Get List of all available collection 
# ======================================

response = client.collections.list_all(simple=False)

pprint(response)

client.close()