import spacy
import subprocess
import importlib.util

# Function to check if a spaCy model is installed
def check_and_download_spacy_model(model_name):
    if importlib.util.find_spec(model_name) is None:
        print(f"Model {model_name} not found. Downloading...")
        subprocess.run(["python", "-m", "spacy", "download", model_name])
    else:
        print(f"Model {model_name} is already installed.")

# Model name
model_name = 'en_core_web_md'

# Check and download the model if necessary
check_and_download_spacy_model(model_name)

# Load the spaCy model
nlp = spacy.load(model_name)
