"""
OCR may suggest values; it must never decide one.

The failure this guards against is real. On email_512 tesseract returned
"128.544" where the page says "128,544". That parses cleanly as 129 kg, and
without a cap it would be compared as fact and reported as a discrepancy.
"""
from sdoc.core.compare import compare_documents, decide
from sdoc.core.contract import CONFIDENCE_THRESHOLD
from sdoc.core.extract import OCR_CONFIDENCE_CAP, extract_document

SI = """SHIPPING INSTRUCTION
Shipper: APRIL FAR EAST (M) SDN BHD
Consignee: ALGURG STATIONERY LLC
Notify: ALGURG STATIONERY LLC
Port of Loading: NHAVA SHEVA, INDIA
Port of Discharge: TUTICORIN, INDIA
No. of Containers: 6 x 40'HC
Gross Weight 128.544 KG"""
BL = SI.replace("SHIPPING INSTRUCTION", "BILL OF LADING").replace("128.544", "128,544")


def test_cap_is_below_the_trust_threshold():
    assert OCR_CONFIDENCE_CAP < CONFIDENCE_THRESHOLD


def test_ocr_fields_are_never_trusted():
    doc = extract_document(SI, "si.pdf", ingest_method="ocr")
    present = [f for f in doc.fields.values() if f.present]
    assert present, "OCR text should still yield suggestions"
    for f in present:
        assert not f.trusted
        assert f.confidence <= OCR_CONFIDENCE_CAP
        assert f.method == "ocr"


def test_ocr_misread_does_not_become_a_discrepancy():
    si = extract_document(SI, "si.pdf", ingest_method="ocr")
    bl = extract_document(BL, "bl.pdf", ingest_method="ocr")
    comps = compare_documents(si, bl)
    assert not [c for c in comps if c.status == "mismatch"]
    status, _ = decide(comps)
    assert status == "NEEDS_REVIEW"


def test_same_text_from_a_real_text_layer_is_trusted():
    """The cap applies to OCR only, not to ordinary extraction."""
    doc = extract_document(BL, "bl.pdf", ingest_method="pdf")
    assert doc.get("shipper").trusted
