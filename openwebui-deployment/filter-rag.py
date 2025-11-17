"""
title: RAG Connector
requirements: requests
"""

import requests

class Pipeline:
    def __init__(self):
        self.type = "filter"
        self.rag_url = "http://172.20.0.1:5000"
    
    async def inlet(self, body: dict, user: dict = None) -> dict:
        # Get user's message
        user_message = body["messages"][-1]["content"]
        
        # Only process if message starts with #
        if not user_message.startswith("#"):
            return body
        
        # Extract collection and query
        # Example: "#docs what is the policy?" -> collection="docs", query="what is the policy?"
        parts = user_message.split(" ", 1)
        collection = parts[0][1:]  # Remove #
        query = parts[1] if len(parts) > 1 else ""
        
        if not query:
            return body
        
        # Get context from RAG connector
        try:
            response = requests.post(
                f"{self.rag_url}/retrieve",
                json={"collection": collection, "query": query},
                timeout=30
            )
            context = response.json().get("context", "")
            
            # Add context as system message
            if context:
                body["messages"].insert(-1, {
                    "role": "system",
                    "content": f"Context: {context}"
                })
                
                # Remove #collection from user message
                body["messages"][-1]["content"] = query
        
        except Exception as e:
            print(f"RAG error: {e}")
        
        return body
