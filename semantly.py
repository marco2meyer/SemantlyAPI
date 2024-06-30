import openai
import numpy as np
import os

# Load your OpenAI API key from environment variables or replace with your actual key
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_embedding(word):
    response = openai.embeddings.create()(
        model="text-embedding-3-large",
        input=word
    )
    return response['data'][0]['embedding']

def cosine_similarity(embedding1, embedding2):
    # Calculate cosine similarity between two embeddings
    return np.dot(embedding1, embedding2) / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))

def similarity(word1, word2):
    """Calculate similarity between two words using OpenAI embeddings."""
    embedding1 = get_embedding(word1)
    embedding2 = get_embedding(word2)
    return cosine_similarity(embedding1, embedding2)

# Example usage
word1 = "cat"
word2 = "dog"
print(f"Similarity between '{word1}' and '{word2}': {similarity(word1, word2)}")