"""Each thread gets its own OCR engine, so documents can be read in parallel."""
import sys
import threading
import types

from medai import ocr


def test_each_thread_has_its_own_engine(monkeypatch):
    created = []

    class FakeRapid:
        def __init__(self):
            created.append(self)

    monkeypatch.setitem(sys.modules, "rapidocr_onnxruntime", types.SimpleNamespace(RapidOCR=FakeRapid))
    monkeypatch.setattr(ocr, "_local", threading.local())

    seen = []

    def work():
        first = ocr._rapidocr()
        assert ocr._rapidocr() is first   # same thread, same engine
        seen.append(first)

    threads = [threading.Thread(target=work) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(seen) == 3
    assert len({id(e) for e in seen}) == 3
    assert len(created) == 3
