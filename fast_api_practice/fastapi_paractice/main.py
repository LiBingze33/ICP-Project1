from fastapi import FastAPI

app = FastAPI()

#homeroute
@app.get("/")

async def home():
    return{"mesasge":"Hello, this is fastapi practice from bing"}