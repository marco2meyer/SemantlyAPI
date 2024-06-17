from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Request, Depends
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
    score: float = None
    timestamp: datetime = None

class Game(BaseModel):
    code: str
    secret_word: str
    preset_guesses: List[Guess] = []
    max_guesses: int
    user_guesses: List[Guess] = []
    players: List[str]
    won: bool = False

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, code: str):
        await websocket.accept()
        if code not in self.active_connections:
            self.active_connections[code] = []
        self.active_connections[code].append(websocket)

    def disconnect(self, websocket: WebSocket, code: str):
        self.active_connections[code].remove(websocket)
        if not self.active_connections[code]:
            del self.active_connections[code]

    async def broadcast(self, code: str, message: str):
        if code in self.active_connections:
            for connection in self.active_connections[code]:
                await connection.send_text(message)

manager = ConnectionManager()

# Verify API key from request headers
def verify_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    if api_key != os.getenv("API_PASSWORD"):
        raise HTTPException(status_code=403, detail="Forbidden")


@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str):
    await manager.connect(websocket, code)
    logger.info(f"WebSocket connection accepted for game: {code}")
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received data: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket, code)
        logger.info(f"WebSocket disconnected for game: {code}")


@app.post("/create_game/", dependencies=[Depends(verify_api_key)])
async def create_game(game: Game):
    try:
        # Calculate similarity scores for preset guesses and add them to preset_guesses
        for guess in game.preset_guesses:
            guess.score = similarity(guess.guess, game.secret_word) * 100
            guess.timestamp = datetime.utcnow()
        
        games_collection.insert_one(game.dict(by_alias=True))
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

@app.post("/game/{code}/guess", dependencies=[Depends(verify_api_key)])
async def add_guess(code: str, guess: Guess):
    try:
        game = games_collection.find_one({"code": code})
        if game:
            guess.timestamp = datetime.utcnow()
            guess.score = similarity(guess.guess, game["secret_word"]) * 100
            game["user_guesses"].append(guess.dict())
            won = guess.score > 95
            if won:
                game["won"] = True
            games_collection.update_one({"code": code}, {"$set": game})
            game["_id"] = str(game["_id"])  # Convert ObjectId to string
            broadcast_message = {
                "new_guess": guess.dict(),
                "won": won
            }
            await manager.broadcast(code, json.dumps(broadcast_message))
            return {"message": "Guess added new", "game": game}
        return {"message": "Game not found"}
    except Exception as e:
        logger.error(f"Error adding guess: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/game/{code}/guesses")
async def get_guesses(code: str):
    try:
        game = games_collection.find_one({"code": code})
        if game:
            game["_id"] = str(game["_id"])  # Convert ObjectId to string
            return {"user_guesses": game["user_guesses"]}
        return {"message": "Game not found"}
    except Exception as e:
        logger.error(f"Error fetching user guesses: {e}")
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