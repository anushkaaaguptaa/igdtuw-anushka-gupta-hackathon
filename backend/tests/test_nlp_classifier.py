import pytest
from app.services.nlp.classifier import (
    KeywordTaxonomyClassifier,
    EventCategory,
    EventClassificationResult,
    CATEGORY_SEVERITY_WEIGHTS
)


def test_taxonomy_geopolitical_classification():
    classifier = KeywordTaxonomyClassifier()
    headline = "US imposes sweeping semiconductor export controls and sanctions amid Taiwan Strait tensions"
    content = "The Department of Commerce expanded foreign policy trade war restrictions."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.GEOPOLITICAL
    assert res.confidence > 0.50
    assert res.confidence <= 0.88  # Calibrated: never uncalibrated 1.0


def test_taxonomy_regulatory_action_classification():
    classifier = KeywordTaxonomyClassifier()
    headline = "FTC opens formal antitrust probe into tech acquisitions"
    content = "Regulators issued a subpoena seeking internal emails regarding monopoly power."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.REGULATORY_ACTION
    assert res.confidence > 0.50
    assert "antitrust" in res.evidence or "probe" in res.evidence


def test_taxonomy_credit_event_classification():
    classifier = KeywordTaxonomyClassifier()
    headline = "Ratings agency issues credit rating downgrade to junk bond status"
    content = "The firm faces imminent debt restructuring following insolvency rumors."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.CREDIT_EVENT
    assert res.confidence > 0.50


def test_taxonomy_product_operational_classification():
    classifier = KeywordTaxonomyClassifier()
    headline = "Global IT outage strikes airlines and hospitals after faulty sensor update"
    content = "A massive system halt and cyberattack scare grounded thousands of flights."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.PRODUCT_OPERATIONAL
    assert res.confidence > 0.50


def test_taxonomy_macroeconomic_classification():
    classifier = KeywordTaxonomyClassifier()
    headline = "Federal Reserve signals another interest rate hike to combat persistent inflation"
    content = "Chairman warned that monetary policy must remain restrictive as CPI remains elevated."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.MACROECONOMIC
    assert res.confidence > 0.50


def test_taxonomy_earnings_classification():
    classifier = KeywordTaxonomyClassifier()
    headline = "Company reports Q3 quarterly results with unexpected profit warning"
    content = "Operating margin collapsed and guidance was lowered for the fiscal year."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.EARNINGS_FINANCIAL_RESULTS
    assert res.confidence > 0.50


def test_taxonomy_mergers_and_acquisitions():
    classifier = KeywordTaxonomyClassifier()
    headline = "Software giant agrees to $20B buyout and tender offer in cash"
    content = "The board accepted the acquisition proposal, completing the merger agreement."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.MERGERS_AND_ACQUISITIONS
    assert res.confidence > 0.50


def test_taxonomy_irrelevant_and_ambiguous_text():
    classifier = KeywordTaxonomyClassifier()
    headline = "Sunny weekend forecast brings large crowds to regional park"
    content = "Families enjoyed picnics and outdoor sports throughout the pleasant afternoon."
    res = classifier.predict(content, headline=headline)

    assert res.category == EventCategory.OTHER_UNCERTAIN
    assert res.confidence == 0.20  # Low confidence reflecting lack of markers


def test_all_categories_have_defined_severity_weights():
    for cat in EventCategory:
        assert cat in CATEGORY_SEVERITY_WEIGHTS
        assert 1.0 <= CATEGORY_SEVERITY_WEIGHTS[cat] <= 5.0
