from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import pymongo
from pydantic import BaseModel
from typing import List
from datetime import datetime
import json
import os
from semantly import similarity
import ssl
import logging
from bson import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

mongo_uri = os.getenv("MONGODB_URI")
client = pymongo.MongoClient(mongo_uri, ssl_cert_reqs=ssl.CERT_NONE)
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

@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/create_game/")
async def create_game(game: Game):
    try:
        games_collection.insert_one(game.dict())
        return {"message": "Game created"}
    except Exception as e:
        logger.error(f"Error creating game: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/game/{code}")
async def get_game(code: str):
    try:
        game = games_collection.find_one({"code": code})
        if game:
            game["_id"] = str(game["_id"])  # Convert ObjectId to string
            return game
        return {"message": "Game not found"}
    except Exception as e:
        logger.error(f"Error fetching game: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/game/{code}/guess")
async def add_guess(code: str, guess: Guess):
    try:
        game = games_collection.find_one({"code": code})
        if game:
            guess.timestamp = datetime.utcnow()
            score = similarity(guess.guess, game["secret_word"])
            game["user_guesses"].append({"player": guess.player, "guess": guess.guess, "score": score, "timestamp": guess.timestamp})
            if score > 0.95:
                game["won"] = True
            games_collection.update_one({"code": code}, {"$set": game})
            game["_id"] = str(game["_id"])  # Convert ObjectId to string
            await manager.broadcast(json.dumps(game, default=str))
            return {"message": "Guess added", "game": game}
        return {"message": "Game not found"}
    except Exception as e:
        logger.error(f"Error adding guess: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/games")
async def get_all_games():
    try:
        games = list(games_collection.find())
        for game in games:
            game["_id"] = str(game["_id"])  # Convert ObjectId to string
        return games
    except Exception as e:
        logger.error(f"Error fetching all games: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Run the FastAPI application
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))