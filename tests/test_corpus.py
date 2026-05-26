import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code'))
from corpus import Corpus

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')

def test_corpus_loads_chunks():
    c = Corpus(data_dir=os.path.join(REPO_ROOT, 'data'))
    assert c.num_chunks > 791

def test_search_multi_returns_real_paths():
    c = Corpus(data_dir=os.path.join(REPO_ROOT, 'data'))
    results = c.search_multi(["lost stolen visa card", "card fraud"], k=5)
    assert len(results) == 5
    for path, text, score in results:
        assert os.path.exists(os.path.join(REPO_ROOT, path)), f"Missing: {path}"
        assert path.startswith('data/')
        assert 0.0 <= score <= 1.0

def test_search_multi_relevant_domain():
    c = Corpus(data_dir=os.path.join(REPO_ROOT, 'data'))
    results = c.search_multi(["delete HackerRank account", "account close devplatform"], k=5)
    paths = [r[0] for r in results]
    assert any('devplatform' in p for p in paths)

def test_domain_boost_biases_results():
    c = Corpus(data_dir=os.path.join(REPO_ROOT, 'data'))
    results_visa = c.search_multi(["lost card"], k=5, domain_boost="visa")
    paths_visa = [r[0] for r in results_visa]
    assert any('visa' in p for p in paths_visa)

def test_all_returned_paths_exist():
    c = Corpus(data_dir=os.path.join(REPO_ROOT, 'data'))
    results = c.search_multi(["billing invoice payment", "refund charge"], k=10)
    for path, _, _ in results:
        assert os.path.exists(os.path.join(REPO_ROOT, path))

def test_single_query_still_works():
    c = Corpus(data_dir=os.path.join(REPO_ROOT, 'data'))
    results = c.search_multi(["password reset"], k=3)
    assert len(results) == 3
