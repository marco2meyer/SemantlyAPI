from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import pymongo
from pydantic import BaseModel
from typing import List
from datetime import datetime
import json
import os
from semantly import similarity



app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo_uri = "mongodb+srv://marco:wisket-kebKyc-6zybco@semantly.kblpbvn.mongodb.net/"


client = pymongo.MongoClient(mongo_uri)
db = client["app"]
games_collection = db["games"]


# Define Pydantic models
class Guess(BaseModel):
    player: str
    guess: str
    timestamp: datetime = None

class Game(BaseModel):
    code: str
    secret_word: str
    preset_guesses: List[str]
    max_guesses: int
    user_guesses: List[Guess]
    players: List[str]
    won: bool

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

# WebSocket endpoint for real-time updates
@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# Endpoint to create a new game
@app.post("/create_game/")
async def create_game(game: Game):
    games_collection.insert_one(game.dict())
    return {"message": "Game created"}

# Endpoint to get the game state by code
@app.get("/game/{code}")
async def get_game(code: str):
    game = games_collection.find_one({"code": code})
    if game:
        game["_id"] = str(game["_id"])
        return game
    return {"message": "Game not found"}

# Endpoint to add a guess to a game
@app.post("/game/{code}/guess")
async def add_guess(code: str, guess: Guess):
    game = games_collection.find_one({"code": code})
    if game:
        # Generate a timestamp for the guess
        guess.timestamp = datetime.utcnow()
        score = similarity(guess.guess, game["secret_word"])
        # Append the guess with timestamp to the user_guesses list
        game["user_guesses"].append({"player": guess.player, "guess": guess.guess, "score": score, "timestamp": guess.timestamp})
        if score > 0.95:
            game["won"] = True
        games_collection.update_one({"code": code}, {"$set": game})
        await manager.broadcast(json.dumps(game))
        return {"message": "Guess added", "game": game}
    return {"message": "Game not found"}

# Endpoint to get all games (for debugging purposes)
@app.get("/games")
async def get_all_games():
    games = list(games_collection.find())
    for game in games:
        game["_id"] = str(game["_id"])
    return games

# Run the FastAPI application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))