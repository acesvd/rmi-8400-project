"""A1: Denial Outcomes Analyst module.

Computes appealability scores from two data sources:
  S1: CA DMHC IMR CSV      — case-level overturn rates by denial type × service type (R1 denials)
  S3: CovCA Appeals CSV    — insurer-level internal/external appeal overturn rates (R2 denials)

Routing logic:
  R1 (medical necessity, experimental) → S1 for personalized A-Score by diagnosis + treatment
  R2 (prior auth, admin, OON, etc.)   → S3 for insurer benchmark + internal vs external guidance

Called by:
  - GET /cases/{case_id}/appealability  (main.py)
  - letter.py  (appeal letter enrichment)
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

from ..config import DATA_DIR

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths — data files live under project_root/data/
# ---------------------------------------------------------------------------

S1_CSV_PATH = DATA_DIR / "s1_imr_determinations.csv"
S3_CSV_PATH = DATA_DIR / "s3_appeals.csv"

# ---------------------------------------------------------------------------
# Payer normalization  (covers all Covered CA insurers)
# ---------------------------------------------------------------------------

PAYER_MAP: dict[str, str] = {
    "anthem": "Anthem Blue Cross",
    "blue cross": "Anthem Blue Cross",
    "blue shield": "Blue Shield of California",
    "kaiser": "Kaiser Permanente",
    "health net": "Health Net",
    "la care": "LA Care Health Plan",
    "l.a. care": "LA Care Health Plan",
    "molina": "Molina Healthcare",
    "sharp": "Sharp Health Plan",
    "valley": "Valley Health Plan",
    "western health": "Western Health Advantage",
    "cchp": "CCHP Health Plan",
    "chinese community": "CCHP Health Plan",
    "oscar": "Oscar",
    "aetna": "Aetna CVSHealth",
    "inland empire": "Inland Empire Health Plan",
    "iehp": "Inland Empire Health Plan",
    "humana": "Humana",
}


def normalize_payer(name: str) -> str:
    """Map variant insurer names to a canonical Covered CA name."""
    low = (name or "").lower().strip()
    for fragment, canonical in PAYER_MAP.items():
        if fragment in low:
            return canonical
    return (name or "").strip() or "Unknown"


# ---------------------------------------------------------------------------
# S1: IMR CSV — overturn rate lookup table
# ---------------------------------------------------------------------------

_s1_cache: list[dict[str, str]] | None = None


def _load_s1() -> list[dict[str, str]]:
    """Load the IMR determinations CSV. Auto-detects common column name variants."""
    global _s1_cache
    if _s1_cache is not None:
        return _s1_cache

    if not S1_CSV_PATH.exists():
        logger.warning("S1 CSV not found at %s", S1_CSV_PATH)
        _s1_cache = []
        return _s1_cache

    with open(S1_CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            normed = {k.strip().lower().replace(" ", "_").replace("-", "_"): v.strip()
                      for k, v in row.items() if k}
            rows.append(normed)

    _s1_cache = rows
    logger.info("S1: Loaded %d IMR rows", len(rows))
    return _s1_cache


def _col(row: dict, *candidates: str) -> str:
    """Return the first matching column value from a row."""
    for c in candidates:
        if c in row and row[c]:
            return row[c]
    return ""


def compute_overturn_rate(
    denial_type: str | None = None,
    diagnosis_category: str | None = None,
    diagnosis_subcategory: str | None = None,
    treatment_category: str | None = None,
    year_start: int | None = None,
    year_end: int | None = None,
) -> dict[str, Any]:
    """Query S1 for overturn statistics matching the given filters.

    Returns dict with overturn_rate, sample_size, overturned_count, upheld_count,
    confidence, and year_range.
    """
    rows = _load_s1()
    if not rows:
        return _empty_score("S1 data not loaded")

    filtered = rows

    if denial_type:
        dt_lower = denial_type.lower()
        filtered = [r for r in filtered
                    if dt_lower in _col(r, "type", "imr_type", "denial_type").lower()]

    if diagnosis_category:
        dc_lower = diagnosis_category.lower()
        filtered = [r for r in filtered
                    if dc_lower in _col(r, "diagnosiscategory", "diagnosis_category",
                                        "diagcategory").lower()]

    if diagnosis_subcategory:
        ds_lower = diagnosis_subcategory.lower()
        filtered = [r for r in filtered
                    if ds_lower in _col(r, "diagnosissubcategory", "diagnosis_subcategory",
                                        "diagsubcategory", "diagnosis_sub_category").lower()]

    if treatment_category:
        tc_lower = treatment_category.lower()
        filtered = [r for r in filtered
                    if tc_lower in _col(r, "treatmentcategory", "treatment_category",
                                        "treatcategory").lower()]

    if year_start or year_end:
        def _year(r: dict) -> int | None:
            y = _col(r, "reportyear", "report_year", "year")
            try:
                return int(y)
            except (ValueError, TypeError):
                return None

        if year_start:
            filtered = [r for r in filtered if (_year(r) or 0) >= year_start]
        if year_end:
            filtered = [r for r in filtered if (_year(r) or 9999) <= year_end]

    if not filtered:
        return _empty_score("No matching cases found in S1")

    overturned = 0
    upheld = 0
    other = 0
    for r in filtered:
        det = _col(r, "determination", "imr_determination").lower()
        if "overturn" in det:
            overturned += 1
        elif "upheld" in det or "uphold" in det:
            upheld += 1
        else:
            other += 1

    total = overturned + upheld
    rate = round(overturned / total, 3) if total > 0 else None

    if total >= 100:
        confidence = "high"
    elif total >= 30:
        confidence = "medium"
    elif total >= 5:
        confidence = "low"
    else:
        confidence = "very_low"

    years = []
    for r in filtered:
        y = _col(r, "reportyear", "report_year", "year")
        try:
            years.append(int(y))
        except (ValueError, TypeError):
            pass
    year_range = f"{min(years)}-{max(years)}" if years else "unknown"

    return {
        "overturn_rate": rate,
        "sample_size": total,
        "overturned_count": overturned,
        "upheld_count": upheld,
        "other_count": other,
        "confidence": confidence,
        "year_range": year_range,
        "source": "S1_IMR_CSV",
    }


def get_precedent_cases(
    denial_type: str | None = None,
    diagnosis_category: str | None = None,
    treatment_category: str | None = None,
    query_text: str = "",
    max_results: int = 5,
) -> list[dict[str, Any]]:
    """Return top overturned IMR cases matching the denial type, ranked by TF-IDF
    cosine similarity to the user's denial context.

    Filters by denial type first (hard filter), then uses TF-IDF on the Findings
    text to rank by relevance to the query.
    """
    rows = _load_s1()
    if not rows:
        return []

    _DESC_COLS = (
        "findings", "description", "casedescription", "case_description",
        "narrative", "patientissue", "patient_issue", "imrdecision",
        "imr_decision", "decision", "decision_text", "summary",
    )

    # Hard filter: overturned + denial type
    filtered = [r for r in rows
                if "overturn" in _col(r, "determination", "imr_determination").lower()]

    if denial_type:
        dt_lower = denial_type.lower()
        filtered = [r for r in filtered
                    if dt_lower in _col(r, "type", "imr_type", "denial_type").lower()]

    # Optional: filter by diagnosis/treatment category if provided
    if diagnosis_category:
        dc_lower = diagnosis_category.lower()
        filtered = [r for r in filtered
                    if dc_lower in _col(r, "diagnosiscategory", "diagnosis_category",
                                        "diagcategory").lower()]

    if treatment_category:
        tc_lower = treatment_category.lower()
        filtered = [r for r in filtered
                    if tc_lower in _col(r, "treatmentcategory", "treatment_category",
                                        "treatcategory").lower()]

    if not filtered:
        # If too restrictive, fall back to just denial_type
        filtered = [r for r in rows
                    if "overturn" in _col(r, "determination", "imr_determination").lower()]
        if denial_type:
            dt_lower = denial_type.lower()
            filtered = [r for r in filtered
                        if dt_lower in _col(r, "type", "imr_type", "denial_type").lower()]
        if not filtered:
            return []

    # Build document list for TF-IDF
    docs = []
    doc_rows = []
    for r in filtered:
        diagnosis = _col(r, "diagnosiscategory", "diagnosis_category", "diagcategory")
        diag_sub = _col(r, "diagnosissubcategory", "diagnosis_subcategory",
                        "diagsubcategory", "diagnosis_sub_category")
        treatment = _col(r, "treatmentcategory", "treatment_category", "treatcategory")
        treat_sub = _col(r, "treatmentsubcategory", "treatment_subcategory",
                         "treatsubcategory", "treatment_sub_category")
        description = _col(r, *_DESC_COLS)

        # Combine all text fields for TF-IDF — weight diagnosis/treatment by repeating
        doc_text = f"{diagnosis} {diag_sub} {treatment} {treat_sub} " * 3 + description
        if doc_text.strip():
            docs.append(doc_text)
            doc_rows.append(r)

    if not docs:
        return []

    # Rank using TF-IDF cosine similarity
    if query_text.strip():
        scores = _tfidf_rank(query_text, docs)
    else:
        # No query — fall back to recency
        scores = []
        for r in doc_rows:
            try:
                y = int(_col(r, "reportyear", "report_year", "year"))
                scores.append(y / 10000.0)  # normalize to 0-0.2 range
            except (ValueError, TypeError):
                scores.append(0.0)

    # Pair scores with rows and sort
    paired = list(zip(scores, doc_rows))
    paired.sort(key=lambda x: x[0], reverse=True)

    # Build result
    results = []
    for score, r in paired[:max_results]:
        ref_id = _col(r, "referenceid", "reference_id", "refereceid", "case_id")
        year = _col(r, "reportyear", "report_year", "year")
        diagnosis = _col(r, "diagnosiscategory", "diagnosis_category", "diagcategory")
        diag_sub = _col(r, "diagnosissubcategory", "diagnosis_subcategory",
                        "diagsubcategory", "diagnosis_sub_category")
        treatment = _col(r, "treatmentcategory", "treatment_category", "treatcategory")
        treat_sub = _col(r, "treatmentsubcategory", "treatment_subcategory",
                         "treatsubcategory", "treatment_sub_category")
        determination = _col(r, "determination", "imr_determination")
        description = _col(r, *_DESC_COLS)

        results.append({
            "reference_id": ref_id,
            "year": year,
            "determination": determination,
            "diagnosis": f"{diagnosis} / {diag_sub}" if diag_sub else diagnosis,
            "treatment": f"{treatment} / {treat_sub}" if treat_sub else treatment,
            "description": description,
            "relevance_score": round(score, 4),
            "source": "S1_IMR_CSV",
        })

    return results


# ---------------------------------------------------------------------------
# TF-IDF ranking
# ---------------------------------------------------------------------------

_tfidf_vectorizer = None
_tfidf_matrix = None
_tfidf_doc_hashes: list[int] | None = None


def _tfidf_rank(query: str, documents: list[str]) -> list[float]:
    """Rank documents by TF-IDF cosine similarity to the query.

    Uses sklearn's TfidfVectorizer. Caches the vectorizer across calls
    if the document set hasn't changed.
    """
    global _tfidf_vectorizer, _tfidf_matrix, _tfidf_doc_hashes

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    # Check if we can reuse cached matrix
    doc_hash = hash(tuple(hash(d[:100]) for d in documents[:50]))
    if _tfidf_vectorizer is not None and _tfidf_doc_hashes == doc_hash:
        # Reuse cached — just transform the query
        query_vec = _tfidf_vectorizer.transform([query])
        similarities = cosine_similarity(query_vec, _tfidf_matrix).flatten()
        return similarities.tolist()

    # Build new TF-IDF matrix
    _tfidf_vectorizer = TfidfVectorizer(
        max_features=10000,
        stop_words="english",
        ngram_range=(1, 2),  # unigrams + bigrams for medical phrases
        sublinear_tf=True,
    )
    _tfidf_matrix = _tfidf_vectorizer.fit_transform(documents)
    _tfidf_doc_hashes = doc_hash

    query_vec = _tfidf_vectorizer.transform([query])
    similarities = cosine_similarity(query_vec, _tfidf_matrix).flatten()
    return similarities.tolist()


# ---------------------------------------------------------------------------
# S3: Covered CA Appeals CSV — insurer benchmark (R2 path)
# ---------------------------------------------------------------------------

_s3_cache: list[dict[str, Any]] | None = None


def _load_s3() -> list[dict[str, Any]]:
    global _s3_cache
    if _s3_cache is not None:
        return _s3_cache

    if not S3_CSV_PATH.exists():
        logger.warning("S3 CSV not found at %s", S3_CSV_PATH)
        _s3_cache = []
        return _s3_cache

    with open(S3_CSV_PATH, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        _s3_cache = [dict(r) for r in reader]

    logger.info("S3: Loaded %d appeal rows", len(_s3_cache))
    return _s3_cache


def get_insurer_appeal_benchmark(insurer: str, year: int | None = None) -> dict[str, Any]:
    """Look up insurer's appeal overturn stats from S3.

    Returns internal/external appeal filed & overturned counts, plus computed rates.
    If year is None, returns the most recent year available.
    """
    rows = _load_s3()
    if not rows:
        return {"error": "S3 data not loaded", "source": "S3_CovCA_Appeals"}

    insurer_norm = normalize_payer(insurer)

    matched = [r for r in rows
               if normalize_payer(r.get("insurer", "")) == insurer_norm]

    if not matched:
        low = insurer_norm.lower()
        matched = [r for r in rows if low in r.get("insurer", "").lower()]

    if not matched:
        return {
            "error": f"No S3 data for insurer: {insurer}",
            "source": "S3_CovCA_Appeals",
        }

    if year:
        year_matched = [r for r in matched if str(r.get("year", "")) == str(year)]
        if year_matched:
            matched = year_matched

    try:
        matched.sort(key=lambda r: int(r.get("year", 0)), reverse=True)
    except (ValueError, TypeError):
        pass

    latest = matched[0]

    def _safe_int(v: Any) -> int | None:
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    def _safe_float(v: Any) -> float | None:
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    return {
        "insurer": latest.get("insurer", insurer),
        "year": _safe_int(latest.get("year")),
        "internal_appeals_filed": _safe_int(latest.get("internal_appeals_filed")),
        "internal_appeals_overturned": _safe_int(latest.get("internal_appeals_overturned")),
        "internal_overturn_pct": _safe_float(latest.get("internal_overturn_pct")),
        "external_appeals_filed": _safe_int(latest.get("external_appeals_filed")),
        "external_appeals_overturned": _safe_int(latest.get("external_appeals_overturned")),
        "external_overturn_pct": _safe_float(latest.get("external_overturn_pct")),
        "source": "S3_CovCA_Appeals",
    }


# ---------------------------------------------------------------------------
# Orchestrator — combines S1 and S3 into a single appealability report
# ---------------------------------------------------------------------------

def _empty_score(reason: str = "") -> dict[str, Any]:
    return {
        "overturn_rate": None,
        "sample_size": 0,
        "confidence": "none",
        "year_range": "",
        "source": "",
        "note": reason,
    }


def _map_denial_label_to_imr_type(label: str) -> str | None:
    """Map codebase's REASON_RULES label to S1 IMR 'Type' value."""
    label_low = label.lower()
    if "medical_necessity" in label_low:
        return "Medical Necessity"
    if "experimental" in label_low or "investigational" in label_low:
        return "Experimental/Investigational"
    return None


def _compute_agent_score(
    a_score: dict[str, Any],
    precedent: list[dict[str, Any]],
    denial_context: str,
    payer: str,
) -> dict[str, Any]:
    """Use Ollama to generate a case-specific assessment.

    The agent considers: the historical A-score, the top precedent cases,
    and the specific denial context to produce a tailored assessment.
    Falls back to a rule-based assessment if Ollama is unavailable.
    """
    rate = a_score.get("overturn_rate")
    n = a_score.get("sample_size", 0)

    # Build precedent summary for the agent
    prec_summary = ""
    for i, pc in enumerate(precedent[:3], 1):
        desc = pc.get("description", "")[:150]
        prec_summary += (
            f"{i}. {pc.get('reference_id','')} ({pc.get('diagnosis','')}) — "
            f"{pc.get('determination','')}: {desc}\n"
        )

    try:
        from .llm import OllamaClient
        from ..config import OLLAMA_CHAT_MODEL
        client = OllamaClient()
        if client.is_available():
            prompt = (
                "You are an insurance appeal analyst. Based on the data below, assess "
                "this specific case's appeal strength. Return ONLY a JSON object with:\n"
                '{"score": 0-100, "assessment": "1-2 sentence assessment", '
                '"strength": "strong|moderate|limited"}\n\n'
                f"Historical overturn rate: {int(rate*100) if rate else 'unknown'}% "
                f"(n={n})\n"
                f"Denial context: {denial_context[:300]}\n"
                f"Payer: {payer}\n"
                f"Top precedent cases:\n{prec_summary}\n"
                "Return JSON only, no markdown."
            )
            result = client.generate_json(
                prompt=prompt,
                model=OLLAMA_CHAT_MODEL,
                temperature=0.1,
            )
            return {
                "score": result.get("score", int(rate * 100) if rate else 0),
                "assessment": result.get("assessment", ""),
                "strength": result.get("strength", "moderate"),
                "source": "ollama",
            }
    except Exception as exc:
        logger.info("Agent score fallback (Ollama unavailable): %s", exc)

    # Fallback: rule-based assessment
    if rate is not None:
        pct = int(rate * 100)
        if pct >= 60:
            strength = "strong"
            assessment = (
                f"Based on {n} similar IMR cases, {pct}% were overturned — this gives your appeal a strong foundation. "
                f"The precedent cases show that independent reviewers have consistently sided with patients "
                f"in comparable clinical situations, particularly when the treating physician provides "
                f"supporting documentation of medical necessity. "
                f"We recommend filing an internal appeal immediately, and if denied, pursuing Independent "
                f"Medical Review (IMR) through the CA DMHC — it's free and the decision is binding on {payer}."
            )
        elif pct >= 40:
            strength = "moderate"
            assessment = (
                f"Of {n} similar IMR cases, {pct}% were overturned — a moderate basis for appeal. "
                f"Outcomes in this category are mixed, meaning the strength of your specific clinical "
                f"documentation will be the deciding factor. "
                f"Focus on gathering a detailed letter of medical necessity from your treating physician "
                f"that addresses the insurer's specific denial rationale. "
                f"Peer-reviewed literature supporting the treatment's efficacy for your condition will strengthen your case."
            )
        else:
            strength = "limited"
            assessment = (
                f"Only {pct}% of {n} similar IMR cases were overturned, which is below average. "
                f"This doesn't mean your appeal will fail, but it suggests you'll need particularly "
                f"strong evidence to succeed. "
                f"Consult with your treating physician about whether additional diagnostic evidence "
                f"or specialist opinions could strengthen your case. "
                f"Consider whether the denial reason can be reframed with more targeted clinical documentation."
            )
        return {
            "score": pct,
            "assessment": assessment,
            "strength": strength,
            "source": "rule_based",
        }

    return {
        "score": 0,
        "assessment": "Insufficient data to assess appeal strength.",
        "strength": "unknown",
        "source": "rule_based",
    }



def _get_s1_categories() -> tuple[list[str], list[str]]:
    """Return the unique DiagnosisCategory and TreatmentCategory values from S1."""
    rows = _load_s1()
    diags: set[str] = set()
    treats: set[str] = set()
    for r in rows:
        d = _col(r, "diagnosiscategory", "diagnosis_category", "diagcategory")
        t = _col(r, "treatmentcategory", "treatment_category", "treatcategory")
        if d:
            diags.add(d)
        if t:
            treats.add(t)
    return sorted(diags), sorted(treats)


# Keyword map: common medical terms → S1 DiagnosisCategory
_DIAG_KEYWORDS: dict[str, list[str]] = {
    "Cancer": ["cancer", "tumor", "oncolog", "carcinoma", "melanoma", "lymphoma",
               "leukemia", "sarcoma", "metasta", "nsclc", "malignant", "neoplasm",
               "chemo", "pembrolizumab", "keytruda", "nivolumab", "opdivo",
               "immunotherapy", "radiation"],
    "Mental Disorder": ["mental", "depression", "anxiety", "bipolar", "schizophren",
                        "psychiatric", "ptsd", "adhd", "eating disorder", "substance",
                        "behavioral", "residential treatment"],
    "Endocrine/Metabolic": ["diabetes", "thyroid", "endocrin", "metabolic", "obesity",
                            "mounjaro", "ozempic", "wegovy", "zepbound", "insulin",
                            "tirzepatide", "semaglutide", "growth hormone"],
    "CNS/ Neuromusc Dis": ["neuro", "brain", "seizure", "epilepsy", "multiple sclerosis",
                           "parkinson", "alzheimer", "migraine", "neuropath", "spinal cord",
                           "cerebral", "apnea", "sleep"],
    "Orth/Musculoskeletal": ["orthoped", "spine", "joint", "knee", "hip", "shoulder",
                             "musculoskeletal", "fracture", "disc", "lumbar", "cervical",
                             "physical therapy", "back pain", "arthroplasty"],
    "Cardiac/Circ Problem": ["cardiac", "heart", "cardiovasc", "coronary", "arrhythmia",
                             "stent", "bypass", "hypertension"],
    "Skin Disorders": ["dermat", "skin", "psoriasis", "eczema", "atopic",
                       "dupixent", "humira"],
    "Respiratory System": ["pulmonary", "lung", "asthma", "copd", "respiratory",
                           "bronch"],
    "GU/ Kidney Disorder": ["kidney", "renal", "urology", "bladder", "prostate",
                            "dialysis", "hysterectomy", "uterine"],
    "Autism Spectrum": ["autism", "asd", "aba therapy", "applied behavior"],
    "Immuno Disorders": ["autoimmune", "lupus", "rheumatoid", "immune deficiency",
                         "immunoglobulin", "ivig"],
    "Digestive System/ GI": ["gastro", "intestin", "colon", "liver", "hepat",
                             "crohn", "celiac", "ibs"],
    "Pregnancy/Childbirth": ["pregnan", "prenatal", "obstetric", "labor", "delivery",
                             "cesarean", "maternity"],
    "Vision": ["vision", "eye", "ophthalmol", "cataract", "retina", "lasik"],
    "Ears/Nose/Throat": ["ear", "nose", "throat", "ent", "sinus", "hearing",
                         "cochlear", "tonsil"],
    "Infectious Disease": ["infection", "hiv", "hepatitis", "antibiotic", "antiviral"],
    "Trauma/ Injuries": ["trauma", "injury", "fracture", "burn", "wound"],
    "Genetic Diseases": ["genetic", "gene therapy", "hereditary", "cystic fibrosis"],
}

_TREAT_KEYWORDS: dict[str, list[str]] = {
    "Pharmacy": ["medication", "drug", "prescription", "pharmacy", "formulary",
                 "generic", "brand", "injectable", "infusion", "biologic",
                 "pembrolizumab", "keytruda", "nivolumab", "mounjaro", "ozempic",
                 "dupixent", "humira", "zepbound", "tirzepatide", "semaglutide"],
    "Cancer Care": ["chemotherapy", "radiation", "oncolog", "immunotherapy",
                    "proton beam", "targeted therapy", "cancer treatment"],
    "Mental Health": ["psychiatric", "counseling", "therapy sessions", "residential",
                      "behavioral health", "inpatient psych"],
    "Orthopedic Proc": ["surgery", "arthroplasty", "replacement", "arthroscopy",
                        "spinal fusion", "orthopedic surgery"],
    "Rehab/ Svc - Outpt": ["physical therapy", "occupational therapy", "speech therapy",
                           "rehabilitation", "outpatient rehab"],
    "Diag Imag & Screen": ["mri", "ct scan", "pet scan", "x-ray", "imaging",
                           "mammogram", "ultrasound", "screening"],
    "DME": ["wheelchair", "prosthetic", "durable medical", "cpap", "brace", "orthotic"],
    "Pain Management": ["pain management", "nerve block", "epidural", "pain clinic"],
    "Neurosurgery Proc": ["neurosurgery", "brain surgery", "spinal surgery",
                          "deep brain stimulation"],
    "Acute Med Svc Inpt": ["inpatient", "hospital admission", "acute care",
                           "hospitalization"],
    "Autism Related Tx": ["aba", "applied behavior", "autism therapy"],
}


def _classify_claim(
    denial_text: str,
    chunk_texts: list[str] | None = None,
) -> dict[str, Any]:
    """Classify a claim into S1's DiagnosisCategory and TreatmentCategory.

    Strategy:
      1. Try Ollama — give it the exact category lists and the denial text
      2. Fall back to keyword matching against _DIAG_KEYWORDS / _TREAT_KEYWORDS

    Also extracts medically relevant keywords from the denial text.

    Returns:
        {"diagnosis_category": str|None, "treatment_category": str|None,
         "medical_keywords": list[str], "source": "ollama"|"keywords"}
    """
    all_text = denial_text
    if chunk_texts:
        all_text = denial_text + " " + " ".join(chunk_texts)
    all_text_lower = all_text.lower()

    diag_cats, treat_cats = _get_s1_categories()

    # --- Try Ollama first ---
    try:
        from .llm import OllamaClient
        from ..config import OLLAMA_CHAT_MODEL
        client = OllamaClient()
        if client.is_available():
            prompt = (
                "You are a medical claim classifier. Given denial letter text, pick the BEST matching "
                "DiagnosisCategory and TreatmentCategory from the lists below. "
                "Also extract 5-10 medically relevant keywords (drug names, conditions, procedures). "
                "Return ONLY a JSON object, no markdown.\n\n"
                f"DiagnosisCategory options: {diag_cats}\n"
                f"TreatmentCategory options: {treat_cats}\n\n"
                f"Denial text: {all_text[:600]}\n\n"
                'Return: {"diagnosis_category": "...", "treatment_category": "...", '
                '"medical_keywords": ["...", "..."]}'
            )
            result = client.generate_json(
                prompt=prompt,
                model=OLLAMA_CHAT_MODEL,
                temperature=0.0,
            )
            diag = result.get("diagnosis_category")
            treat = result.get("treatment_category")
            keywords = result.get("medical_keywords", [])
            # Validate against actual categories
            if diag and diag not in diag_cats:
                diag = None
            if treat and treat not in treat_cats:
                treat = None
            if diag or treat:
                return {
                    "diagnosis_category": diag,
                    "treatment_category": treat,
                    "medical_keywords": keywords[:10] if isinstance(keywords, list) else [],
                    "source": "ollama",
                }
    except Exception as exc:
        logger.info("Claim classification Ollama failed: %s", exc)

    # --- Keyword fallback ---
    best_diag = None
    best_diag_score = 0
    for cat, keywords in _DIAG_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in all_text_lower)
        if score > best_diag_score:
            best_diag_score = score
            best_diag = cat

    best_treat = None
    best_treat_score = 0
    for cat, keywords in _TREAT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in all_text_lower)
        if score > best_treat_score:
            best_treat_score = score
            best_treat = cat

    # Extract medical keywords (simple: words 6+ chars not in common English)
    import re
    _COMMON = {"patient", "treatment", "medical", "request", "authorization", "coverage",
               "denied", "denial", "necessary", "review", "health", "service", "insurer",
               "insurance", "appeal", "letter", "document", "reason", "clinical",
               "provide", "following", "standard", "adjuvant", "requested", "criteria",
               "determination", "information", "received", "records", "recommend"}
    med_keywords = []
    for word in re.findall(r"[a-zA-Z]{5,}", all_text):
        w = word.lower()
        if w not in _COMMON and w not in med_keywords:
            med_keywords.append(w)
        if len(med_keywords) >= 15:
            break

    return {
        "diagnosis_category": best_diag if best_diag_score >= 2 else None,
        "treatment_category": best_treat if best_treat_score >= 1 else None,
        "medical_keywords": med_keywords[:10],
        "source": "keywords",
    }


def get_appealability(case_json: dict[str, Any]) -> dict[str, Any]:
    """Main entry point. Takes a case_json from case_extraction and returns
    a full appealability report.

    Routing:
      R1 (medical necessity / experimental) → S1 for A-Score
      R2 (prior auth / admin / OON / other) → S3 for insurer benchmark

    Args:
        case_json: The extraction output with payer, denial_reasons, etc.

    Returns:
        dict with: denial_classification, a_score (R1) or insurer_benchmark (R2),
        and recommendations.
    """
    payer = case_json.get("payer", "unknown")
    reasons = case_json.get("denial_reasons", [])

    if not reasons:
        return {
            "denial_classification": "unknown",
            "a_score": _empty_score("No denial reasons extracted"),
            "insurer_benchmark": {},
            "recommendations": ["Upload a denial letter so we can extract the denial reason."],
        }

    primary_reason = reasons[0]
    label = primary_reason.get("label", "")
    imr_type = _map_denial_label_to_imr_type(label)

    if imr_type:
        classification = "R1"
    elif label in ("prior_authorization", "administrative", "coding_billing", "out_of_network"):
        classification = "R2"
    else:
        classification = "technical"

    result: dict[str, Any] = {
        "denial_classification": classification,
        "denial_label": label,
        "payer": normalize_payer(payer),
    }

    # --- R1 path: S1 for personalized A-Score + precedent ---
    if classification == "R1":
        a_score = compute_overturn_rate(denial_type=imr_type)
        result["a_score"] = a_score
        result["insurer_benchmark"] = {}

        # Build query text from denial letter context
        query_parts = []
        for r in reasons:
            quote = r.get("supporting_quote", "")
            if quote:
                query_parts.append(quote)
            kw = r.get("keyword", "")
            if kw:
                query_parts.append(kw)
        query_text = " ".join(query_parts)

        # Classify our claim into S1's DiagnosisCategory + TreatmentCategory
        claim_class = _classify_claim(query_text)
        inferred_diag = claim_class.get("diagnosis_category")
        inferred_treat = claim_class.get("treatment_category")
        medical_keywords = claim_class.get("medical_keywords", [])

        # Filter S1 by matched categories, then TF-IDF within
        precedent = get_precedent_cases(
            denial_type=imr_type,
            diagnosis_category=inferred_diag,
            treatment_category=inferred_treat,
            query_text=query_text,
            max_results=5,
        )

        # If diag+treat was too strict (< 3 results), relax treatment filter
        if len(precedent) < 3 and inferred_treat:
            precedent = get_precedent_cases(
                denial_type=imr_type,
                diagnosis_category=inferred_diag,
                query_text=query_text,
                max_results=5,
            )

        # If still too few, relax all category filters
        if len(precedent) < 3 and inferred_diag:
            precedent = get_precedent_cases(
                denial_type=imr_type,
                query_text=query_text,
                max_results=5,
            )

        result["precedent_cases"] = precedent
        result["inferred_diagnosis"] = inferred_diag or "Not identified"
        result["inferred_treatment"] = inferred_treat or "Not identified"
        result["medical_keywords"] = medical_keywords
        result["classification_source"] = claim_class.get("source", "unknown")

        # Agent-based score
        agent_score = _compute_agent_score(a_score, precedent, query_text, payer)
        result["agent_score"] = agent_score

        recs = []
        if a_score.get("overturn_rate") is not None:
            rate_pct = int(a_score["overturn_rate"] * 100)
            n = a_score.get("sample_size", 0)
            recs.append(
                f"Based on {n} similar IMR cases, {rate_pct}% of {imr_type.lower()} "
                f"denials were overturned. This is a "
                f"{'strong' if rate_pct >= 60 else 'moderate' if rate_pct >= 40 else 'limited'} "
                f"basis for appeal."
            )
            if rate_pct >= 50:
                recs.append(
                    "We recommend filing an appeal. If your internal appeal is denied, "
                    "pursue Independent Medical Review (IMR) through the CA DMHC — it's free "
                    "and the decision is binding on the insurer."
                )
            else:
                recs.append(
                    "Overturn rates are below average for this denial type. An appeal is still "
                    "possible, but gather strong supporting documentation from your physician."
                )
        else:
            recs.append("We recommend filing an appeal with supporting medical documentation.")

        # Add precedent-based recommendations
        for pc in precedent[:2]:
            desc = pc.get("description", "")
            if desc:
                recs.append(
                    f"Precedent case {pc['reference_id']} ({pc['year']}): {desc[:300]}"
                )

        result["recommendations"] = recs

    # --- R2 path: S3 for insurer benchmark + routing ---
    elif classification == "R2":
        result["a_score"] = _empty_score("Not an IMR-eligible denial type — using insurer benchmark")
        benchmark = get_insurer_appeal_benchmark(payer)
        result["insurer_benchmark"] = benchmark

        recs = [
            f"This denial ({label.replace('_', ' ')}) is procedural, not clinical.",
        ]

        int_pct = benchmark.get("internal_overturn_pct")
        ext_pct = benchmark.get("external_overturn_pct")

        if int_pct is not None and ext_pct is not None:
            if int_pct >= 50:
                recs.append(
                    f"At {normalize_payer(payer)}, {int_pct}% of internal appeals were overturned. "
                    f"An internal appeal is likely your fastest path to resolution."
                )
            elif ext_pct > int_pct:
                recs.append(
                    f"At {normalize_payer(payer)}, internal appeals have a {int_pct}% overturn rate "
                    f"but external reviews reach {ext_pct}%. Consider escalating to the CA DMHC "
                    f"if your internal appeal is denied."
                )
            else:
                recs.append(
                    f"At {normalize_payer(payer)}, {int_pct}% of internal appeals were overturned. "
                    f"Start with an internal appeal and resubmit with correct documentation."
                )
        elif int_pct is not None:
            recs.append(
                f"At {normalize_payer(payer)}, {int_pct}% of internal appeals were overturned."
            )
        else:
            recs.append(
                "Resubmit with correct documentation or contact member services to resolve."
            )

        result["recommendations"] = recs

    # --- Technical/certain denial ---
    else:
        result["a_score"] = _empty_score("Technical denial — not appealable via clinical argument")
        result["insurer_benchmark"] = {}
        result["recommendations"] = [
            "This appears to be a technical or administrative denial.",
            "Contact your insurer's member services to resolve the specific issue.",
        ]

    return result