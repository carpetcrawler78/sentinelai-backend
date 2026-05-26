import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from vigilex.coding.reranker import CrossEncoderReranker, RerankedResult
from tests.helpers import make_search_result, mock_search_results


# ---------------------------------------------------------------------------
# Fixture: CrossEncoderReranker mit gemocktem CrossEncoder
#
# patch('vigilex.coding.reranker.CrossEncoder') -- patcht den Namen im
# reranker-Modul, wo er gebunden ist. Kein Modell-Download, kein HuggingFace.
# ---------------------------------------------------------------------------

@pytest.fixture
def reranker():
    with patch("vigilex.coding.reranker.CrossEncoder") as MockCE:
        mock_instance = MagicMock()
        MockCE.return_value = mock_instance
        yield CrossEncoderReranker(), mock_instance


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_rerank_empty_candidates(reranker):
    ranker, mock_ce = reranker
    result = ranker.rerank("some query", [], top_k=5)
    assert result == []
    mock_ce.predict.assert_not_called()


def test_rerank_returns_top_k(reranker):
    ranker, mock_ce = reranker
    candidates = mock_search_results(10)
    mock_ce.predict.return_value = np.arange(10, dtype=float)
    result = ranker.rerank("query", candidates, top_k=5)
    assert len(result) == 5


def test_rerank_order(reranker):
    ranker, mock_ce = reranker
    candidates = mock_search_results(3)
    mock_ce.predict.return_value = np.array([0.1, 0.9, 0.5])
    result = ranker.rerank("query", candidates, top_k=3)
    scores = [r.crossencoder_score for r in result]
    assert scores == sorted(scores, reverse=True)
    assert result[0].crossencoder_score == pytest.approx(0.9)


def test_rerank_preserves_fields(reranker):
    ranker, mock_ce = reranker
    sr = make_search_result(pt_code=10020635, pt_name="Hyperglycaemia",
                            rrf_score=0.011, trgm_sim=0.6, cosine_sim=0.77)
    mock_ce.predict.return_value = np.array([0.8])
    result = ranker.rerank("query", [sr], top_k=1)
    r = result[0]
    assert isinstance(r, RerankedResult)
    assert r.pt_code == 10020635
    assert r.pt_name == "Hyperglycaemia"
    assert r.soc_name == sr.soc_name
    assert r.rrf_score == pytest.approx(0.011)
    assert r.trgm_sim == pytest.approx(0.6)
    assert r.cosine_sim == pytest.approx(0.77)
    assert r.crossencoder_score == pytest.approx(0.8)


def test_rerank_assigns_rank_by_score_position(reranker):
    ranker, mock_ce = reranker
    candidates = mock_search_results(3)
    mock_ce.predict.return_value = np.array([0.9, 0.8, 0.7])
    result = ranker.rerank("query", candidates, top_k=3)
    by_score = {round(r.crossencoder_score, 9): r.rrf_rank for r in result}
    assert by_score[0.9] == 1
    assert by_score[0.8] == 2
    assert by_score[0.7] == 3


def test_rerank_top_k_gt_candidates(reranker):
    ranker, mock_ce = reranker
    candidates = mock_search_results(3)
    mock_ce.predict.return_value = np.array([0.1, 0.2, 0.3])
    result = ranker.rerank("query", candidates, top_k=10)
    assert len(result) == 3


def test_rerank_negative_scores(reranker):
    ranker, mock_ce = reranker
    candidates = mock_search_results(3)
    mock_ce.predict.return_value = np.array([-5.0, -1.0, -3.0])
    result = ranker.rerank("query", candidates, top_k=3)
    assert result[0].crossencoder_score == pytest.approx(-1.0)
    assert result[1].crossencoder_score == pytest.approx(-3.0)
    assert result[2].crossencoder_score == pytest.approx(-5.0)


def test_rerank_calls_predict_with_query_candidate_pairs(reranker):
    ranker, mock_ce = reranker
    candidates = [
        make_search_result(pt_code=1, pt_name="Hyperglycaemia"),
        make_search_result(pt_code=2, pt_name="Hypoglycaemia"),
    ]
    mock_ce.predict.return_value = np.array([0.2, 0.8])

    ranker.rerank("patient had high blood sugar", candidates, top_k=2)

    mock_ce.predict.assert_called_once()
    pairs = mock_ce.predict.call_args.args[0]
    assert pairs == [
        ("patient had high blood sugar", "Hyperglycaemia"),
        ("patient had high blood sugar", "Hypoglycaemia"),
    ]
