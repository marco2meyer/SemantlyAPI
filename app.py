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
from fastapi.encoders import jsonable_encoder

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

# Verify API key from request headers
def verify_api_key(request: Request):
    api_key = request.headers.get("x-api-key")
    if api_key != os.getenv("API_PASSWORD"):
        raise HTTPException(status_code=403, detail="Forbidden")

@app.websocket("/ws/{code}")
async def websocket_endpoint(websocket: WebSocket, code: str):
    await websocket.accept()
    logger.info(f"WebSocket connection accepted for game: {code}")
    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received data: {data}")
            await websocket.send_text(f"Echo: {data}")
    except WebSocketDisconnect:
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
            game["user_guesses"].append({
                "player": guess.player,
                "guess": guess.guess,
                "score": guess.score,
                "timestamp": guess.timestamp.isoformat()
            })
            
            # Remove the '_id' field from the game object to avoid the immutable field error
            game_without_id = {k: v for k, v in game.items() if k != "_id"}
            
            if guess.score > 95:
                game_without_id["won"] = True
            
            games_collection.update_one({"code": code}, {"$set": game_without_id})
            
            guess_data = {"guess": guess.dict(), "won": game_without_id["won"]}
            message = json.dumps(guess_data, default=str)
            await manager.broadcast(message)
            
            # Convert ObjectId to string for the response
            game["_id"] = str(game["_id"])
            
            return {"message": "Guess added", "game": game}
        
        return {"message": "Game not found"}
    except Exception as e:
        logger.error(f"Error adding guess: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {e}")
            
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