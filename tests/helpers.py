"""
helpers.py -- Plain test helper functions (no pytest dependency).

Importable from test modules and conftest.py alike:
    from tests.helpers import make_search_result, mock_search_results
"""

from vigilex.coding.hybrid_search import SearchResult


def make_search_result(
    pt_code: int = 10020635,
    pt_name: str = "Hyperglycaemia",
    soc_name: str = "Metabolism and nutrition disorders",
    rrf_score: float = 0.012,
    bm25_rank: int = 1,
    vector_rank: int = 2,
    trgm_sim: float = 0.45,
    cosine_sim: float = 0.82,
) -> SearchResult:
    return SearchResult(
        pt_code=pt_code,
        pt_name=pt_name,
        soc_name=soc_name,
        rrf_score=rrf_score,
        bm25_rank=bm25_rank,
        vector_rank=vector_rank,
        trgm_sim=trgm_sim,
        cosine_sim=cosine_sim,
    )


def mock_search_results(n: int) -> list:
    """Return n distinct SearchResult objects with predictable pt_codes.

    Note: pt_code = base_code + i may collide with real MedDRA codes.
    Acceptable for unit tests -- we test reranker logic, not DB integrity.
    """
    _base = [
        (10020635, "Hyperglycaemia"),
        (10021081, "Hypoglycaemia"),
        (10012671, "Diabetic ketoacidosis"),
        (10003036, "Application site dermatitis"),
        (10002855, "Anxiety"),
        (10040880, "Skin irritation"),
        (10023379, "Ketoacidosis"),
        (10049803, "Blood glucose fluctuation"),
        (10005553, "Blood glucose"),
        (10040914, "Skin reaction"),
    ]
    results = []
    for i in range(n):
        code, name = _base[i % len(_base)]
        results.append(make_search_result(
            pt_code=code + i,
            pt_name=name,
            rrf_score=round(0.015 - i * 0.001, 6),
            bm25_rank=i + 1,
            vector_rank=i + 1,
        ))
    return results
