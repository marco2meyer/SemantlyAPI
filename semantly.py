import openai
import os
import numpy as np

# Load your OpenAI API key from environment variables
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_embedding(text, model="text-embedding-ada-002"):
    response = openai.Embedding.create(input=[text], model=model)
    return response['data'][0]['embedding']

def cosine_similarity(vec1, vec2):
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def similarity(word1, word2):
    """Calculate similarity between two words using OpenAI's embeddings."""
    embedding1 = get_embedding(word1)
    embedding2 = get_embedding(word2)
    return cosine_similarity(embedding1, embedding2)

# Example usage
if __name__ == "__main__":
    word1 = "apple"
    word2 = "orange"
    print(f"Similarity between '{word1}' and '{word2}': {similarity(word1, word2)}")