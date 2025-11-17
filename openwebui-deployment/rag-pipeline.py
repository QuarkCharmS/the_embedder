"""
title: My RAG Pipeline
author: Santiago
version: 0.1.0
requirements: requests
"""
import requests

class Pipeline:
    def __init__(self):
        pass
    
    async def inlet(self, body: dict, user: dict = None) -> dict:
        
        json= {
            "Username": "Santiago",
            "Body": body
        }
        response = requests.post("http://172.20.0.1:5000/test", json=json)

        return body

