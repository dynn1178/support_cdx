import pytest

from app import ocr


def test_recognize_rejects_empty_image():
    with pytest.raises(ocr.OcrError):
        ocr.recognize_png(b"")


def test_unavailable_reason_is_guidance_text():
    reason = ocr.unavailable_reason()
    if ocr.available():
        assert reason == ""
    else:
        assert reason  # 사용자에게 보여 줄 안내 문구가 반드시 있어야 한다


def test_language_list_shape():
    for tag, display_name in ocr.available_languages():
        assert isinstance(tag, str) and tag
        assert isinstance(display_name, str)


@pytest.mark.skipif(not ocr.available(), reason="Windows OCR 언어팩이 설치되지 않은 환경")
def test_recognize_rejects_broken_image():
    with pytest.raises(ocr.OcrError):
        ocr.recognize_png(b"not-a-png-file")


@pytest.mark.skipif(not ocr.available(), reason="Windows OCR 언어팩이 설치되지 않은 환경")
def test_recognize_reads_rendered_text():
    import io

    pytest.importorskip("PIL")
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("C:/Windows/Fonts/malgun.ttf", 30)
    except OSError:  # pragma: no cover - 글꼴 없는 환경
        pytest.skip("맑은 고딕 글꼴 없음")

    image = Image.new("RGB", (520, 90), "white")
    ImageDraw.Draw(image).text((16, 20), "예약번호 A1234567", font=font, fill="black")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")

    lines = ocr.recognize_png(buffer.getvalue())
    assert any("A1234567" in line for line in lines), lines
