from typing import List, Union, Generator, Iterator
import datetime


class Pipeline:
    def __init__(self):
        self.name = "Simple Timestamp Pipeline"

    async def inlet(self, body: dict, user: dict) -> dict:
        """
        This inlet adds a timestamp to every user message
        """
        messages = body.get("messages", [])
        
        if messages:
            # Get the last message (user's current message)
            user_message = messages[-1].get("content", "")
            
            # Add a timestamp prefix
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Modify the message
            messages[-1]["content"] = f"[Time: {timestamp}]\n\n{user_message}"
            
            # Update the body
            body["messages"] = messages
        
        return body

    def pipe(
        self, user_message: str, model_id: str, messages: List[dict], body: dict
    ) -> Union[str, Generator, Iterator]:
        """
        This is the main function that processes the request
        For a simple passthrough, just return a string response
        """
        return f"You said: {user_message}"
