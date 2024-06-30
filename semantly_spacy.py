import spacy
from spacy.lang.en import English

# Load the spaCy model
try:
    nlp = spacy.load('en_core_web_md')
except OSError:
    from spacy.cli import download
    download('en_core_web_md')
    nlp = spacy.load('en_core_web_md')

def similarity(word1, word2):
    """Calculate similarity between two words using spaCy."""
    doc1 = nlp(word1)
    doc2 = nlp(word2)
    return doc1.similarity(doc2)