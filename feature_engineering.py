import json, pickle, os
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy import sparse
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from sentence_transformers import SentenceTransformer, util
'''
Construct features for learning-to-rank
The main function is the construct_features(q) which receives input of a query (which in our case a requirement)
then it is computed for each pattern in privacypatterns.org
'''

class PrivacyPatternFeatures(object):
    def __init__(self):
        self.patterns, self.pattern_titles, self.pattern_excerpts = self.get_corpus_pattern()
        self.initiate_tf_idf()
        self.initiate_bm25(0.75, 1.6)
        
        print("Loading LTR Embeddings...")
        self.model_sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
        self.model_sentence_transformer_overflow = SentenceTransformer('flax-sentence-embeddings/stackoverflow_mpnet-base')
        
        self.emb_pattern_file = 'LTR_resources/emb_pattern.pkl'
        if os.path.isfile(self.emb_pattern_file):
            self.load_pattern_embeddings()
        else:
            self.precompute_pattern_embeddings()
            
    
    def load_pattern_embeddings(self):
        # Load the embeddings from the saved files
        with open('LTR_resources/emb_pattern.pkl', 'rb') as f:
            self.emb_pattern = pickle.load(f)
            
        with open('LTR_resources/emb_pattern_title.pkl', 'rb') as f:
            self.emb_pattern_title = pickle.load(f)
            
        with open('LTR_resources/emb_pattern_excerpt.pkl', 'rb') as f:
            self.emb_pattern_excerpt = pickle.load(f)
            
        with open('LTR_resources/emb_pattern_overflow.pkl', 'rb') as f:
            self.emb_pattern_overflow = pickle.load(f)
            
        with open('LTR_resources/emb_pattern_title_overflow.pkl', 'rb') as f:
            self.emb_pattern_title_overflow = pickle.load(f)
            
        with open('LTR_resources/emb_pattern_excerpt_overflow.pkl', 'rb') as f:
            self.emb_pattern_excerpt_overflow = pickle.load(f)
        
    def precompute_pattern_embeddings(self):
        # Compute embeddings for patterns
        self.emb_pattern = self.model_sentence_transformer.encode(self.patterns, convert_to_tensor=True)
        self.emb_pattern_title = self.model_sentence_transformer.encode(self.pattern_titles, convert_to_tensor=True)
        self.emb_pattern_excerpt = self.model_sentence_transformer.encode(self.pattern_excerpts, convert_to_tensor=True)
        
        self.emb_pattern_overflow = self.model_sentence_transformer_overflow.encode(self.patterns, convert_to_tensor=True)
        self.emb_pattern_title_overflow = self.model_sentence_transformer_overflow.encode(self.pattern_titles, convert_to_tensor=True)
        self.emb_pattern_excerpt_overflow = self.model_sentence_transformer_overflow.encode(self.pattern_excerpts, convert_to_tensor=True)

        # Save the embeddings for later use
        with open('LTR_resources/emb_pattern.pkl', 'wb') as f:
            pickle.dump(self.emb_pattern, f)
            
        with open('LTR_resources/emb_pattern_title.pkl', 'wb') as f:
            pickle.dump(self.emb_pattern_title, f)
            
        with open('LTR_resources/emb_pattern_excerpt.pkl', 'wb') as f:
            pickle.dump(self.emb_pattern_excerpt, f)
            
        with open('LTR_resources/emb_pattern_overflow.pkl', 'wb') as f:
            pickle.dump(self.emb_pattern_overflow, f)
            
        with open('LTR_resources/emb_pattern_title_overflow.pkl', 'wb') as f:
            pickle.dump(self.emb_pattern_title_overflow, f)
            
        with open('LTR_resources/emb_pattern_excerpt_overflow.pkl', 'wb') as f:
            pickle.dump(self.emb_pattern_excerpt_overflow, f)


    def construct_story_embeddings(self, all_story):
        self.story_emb = self.model_sentence_transformer.encode(all_story, convert_to_tensor=True)
        self.story_emb_overflow  = self.model_sentence_transformer_overflow.encode(all_story, convert_to_tensor=True)
        
        self.precompute_semantic_similarity_features()
        
    def construct_features(self, q, story_key):
        q_words = word_tokenize(self.remove_stopwords(q))

        # we adapt the representation from MSLR-WEB dataset
        # q is query that represents the requirements
        # pattern is the document
        # each query have the pattern features
        # query level feature = when the parameter only contain q

        len_q = len(self.remove_stopwords(q))
        idf_q = self.get_idf(q_words)
        tf_idf_q = self.tf_idf_features(q)
        bm25 = self.bm25(q)

        features_all = []
        for i, pattern in enumerate(self.patterns):
            features = []
            features.extend(self.number_of_covered_words(q_words, pattern)) # 1, 2
            features.append(len_q) # 3
            features.append(idf_q) # 4
            features.extend(self.tf_features(q_words, pattern)) # 5 - 14
            features.extend(tf_idf_q) # 15 - 19
            features.append(bm25[i]) # 20
            features.append(float(self.cosine_scores_pattern[story_key][i])) # 21
            features.append(float(self.cosine_scores_title[story_key][i])) # 22
            features.append(float(self.cosine_scores_excerpt[story_key][i])) # 23
            features.append(float(self.cosine_scores_pattern_overflow[story_key][i])) # 24
            features.append(float(self.cosine_scores_title_overflow[story_key][i])) # 25
            features.append(float(self.cosine_scores_excerpt_overflow[story_key][i])) # 26

            # add information about category (unlinkability, transparency, etc) based on automatic classification

            features_all.append(features)

        return features_all
            

    def get_corpus_pattern(self):
        pattern_file= "LTR_resources/patterns.json"
        X = []
        title = []
        excerpt = []
        with open(pattern_file, 'r') as p:
            patterns = json.loads(p.read())

        for pattern in patterns:
            text = ""

            filename = pattern["filename"].replace(".md","").replace("-"," ")

            title.append(filename)
            excerpt.append(pattern["excerpt"].strip())

            text += filename
            if not text.endswith("."):
                text += ". "

            text += pattern["excerpt"].strip()
            if not text.endswith("."):
                text += ". "

            for heading in pattern["heading"]:
                text += heading["content"].strip()
                if not text.endswith("."):
                    text += ". "

            X.append(text)

        return X, title, excerpt
    
    def get_lookup_patterns(self):
        pattern_file= "LTR_resources/patterns.json"
        pattern_dict = {}
        
        with open(pattern_file, 'r') as p:
            patterns = json.loads(p.read())

        for pattern in patterns:
            title = pattern["filename"].replace(".md","")
            pattern_dict[title] = pattern
            
        return pattern_dict

    def remove_stopwords(self, q):
        stop_words = set(stopwords.words('english'))
        word_tokens = word_tokenize(q)
        filtered_sentence = " ".join([w for w in word_tokens if not w.lower() in stop_words])

        return filtered_sentence


    def initiate_tf_idf(self):
        self.tf_idf_vectorizer = TfidfVectorizer(norm=None, smooth_idf=False)
        self.tf_idf_vectorizer.fit(self.patterns)
        self.tf_idf_feature_names = self.tf_idf_vectorizer.get_feature_names_out()


    def initiate_bm25(self, b, k1):
        self.b = b
        self.k1 = k1

        y = super(TfidfVectorizer, self.tf_idf_vectorizer).transform(self.patterns)
        self.avdl = y.sum(1).mean()


    def bm25(self, q):
        X = self.patterns
        """ Calculate BM25 between query q and documents X """
        b, k1, avdl = self.b, self.k1, self.avdl

        # apply CountVectorizer
        X = super(TfidfVectorizer, self.tf_idf_vectorizer).transform(X)
        len_X = X.sum(1).A1
        q, = super(TfidfVectorizer, self.tf_idf_vectorizer).transform([q])
        assert sparse.isspmatrix_csr(q)

        # convert to csc for better column slicing
        X = X.tocsc()[:, q.indices]
        denom = X + (k1 * (1 - b + b * len_X / avdl))[:, None]
        # idf(t) = log [ n / df(t) ] + 1 in sklearn, so it need to be coneverted
        # to idf(t) = log [ n / df(t) ] with minus 1
        idf = self.tf_idf_vectorizer._tfidf.idf_[None, q.indices] - 1.
        numer = X.multiply(np.broadcast_to(idf, X.shape)) * (k1 + 1)                                                          
        return (numer / denom).sum(1).A1

    def number_of_covered_words(self, q_words, pattern):
        # How many terms in the user query are covered by the text.
        # ration = Covered query term number divided by the number of query terms.
        
        n = 0
        for word in q_words:
            if word.lower() in pattern.lower():
                n += 1

        ratio = n/len(q_words)
        return [n, ratio]

    def get_idf(self, q_words):
        # 1 divided by the number of documents containing the query terms.

        n = 0
        word_in_patterns = set()
        for pattern in self.patterns:
            for word in q_words:
                if word.lower() in pattern.lower():
                    word_in_patterns.add(word.lower())

        idf = 1/len(list(word_in_patterns))

        return idf

    def tf_features(self, q_words, pattern):
        # Sum, Min, Max, Average, Variance of counts of each query term in the document.
        # Normalized version : term counts divided by text length
        
        pattern_words = word_tokenize(pattern)
        total_len = len(pattern_words)
        n_count_all = [pattern_words.count(word) for word in q_words]

        tf_sum, tf_min, tf_max, tf_avg, tf_var = sum(n_count_all), min(n_count_all), max(n_count_all), np.average(n_count_all), np.var(n_count_all)

        norm_tf_sum, norm_tf_min, norm_tf_max, norm_tf_avg, norm_tf_var = sum(n_count_all)/total_len, min(n_count_all)/total_len, max(n_count_all)/total_len, np.average(n_count_all)/total_len, np.var(n_count_all)/float(total_len)

        return [tf_sum, tf_min, tf_max, tf_avg, tf_var, norm_tf_sum, norm_tf_min, norm_tf_max, norm_tf_avg, norm_tf_var]


    def tf_idf_features(self, q):
        tfidf_matrix= self.tf_idf_vectorizer.transform([q]).todense()
        feature_index = tfidf_matrix[0,:].nonzero()[1]
        tfidf_scores = zip([self.tf_idf_feature_names[i] for i in feature_index], [tfidf_matrix[0, x] for x in feature_index])

        word_scores = [score for score in dict(tfidf_scores).values()]

        tfidf_sum, tfidf_min, tfidf_max, tfidf_avg, tfidf_var = sum(word_scores), min(word_scores), max(word_scores), np.average(word_scores), np.var(word_scores)

        return [tfidf_sum, tfidf_min, tfidf_max, tfidf_avg, tfidf_var]

    def precompute_semantic_similarity_features(self):
        self.cosine_scores_pattern = util.cos_sim(self.story_emb, self.emb_pattern)
        self.cosine_scores_title = util.cos_sim(self.story_emb, self.emb_pattern_title)
        self.cosine_scores_excerpt = util.cos_sim(self.story_emb, self.emb_pattern_excerpt)

        self.cosine_scores_pattern_overflow = util.cos_sim(self.story_emb_overflow, self.emb_pattern_overflow)
        self.cosine_scores_title_overflow = util.cos_sim(self.story_emb_overflow, self.emb_pattern_title_overflow)
        self.cosine_scores_excerpt_overflow = util.cos_sim(self.story_emb_overflow, self.emb_pattern_excerpt_overflow)

# pp = PrivacyPatternFeatures()
# features = pp.construct_features("Location personal data")
# print(features)

'''
patterns = pp.get_corpus_pattern()

score_bm25 = pp.bm25("Location personal data")

indices = (-score_bm25).argsort()[:5]

for index in indices:
    print(patterns[index][:50])
'''