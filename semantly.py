import spacy

nlp = spacy.load('en_core_web_md')

def similarity(word1, word2):
    doc1 = nlp(word1)
    doc2 = nlp(word2)
    return doc1.similarity(doc2)

def get_feedback(guess, secret_word):
    score = similarity(guess, secret_word)
    return score