"""Windows 내장 OCR(Windows.Media.Ocr) 래퍼.

winrt 바인딩이 없거나 OCR 언어팩이 설치되지 않은 PC에서도 앱이 죽지 않도록,
호출 전에 available() 로 사용 가능 여부를 물어보고 실패 사유는 안내 문구로 돌려준다.
UI 의존성이 없어 어떤 화면에서도 재사용할 수 있다.
"""

from __future__ import annotations

import threading

MAX_IMAGE_DIMENSION = 10000  # OcrEngine.MaxImageDimension 기본값 (조회 실패 시 사용)

LANGUAGE_PACK_GUIDE = (
    "Windows OCR 언어팩이 설치되어 있지 않습니다.\n"
    "설정 > 시간 및 언어 > 언어 및 지역 > 한국어 > 언어 옵션 > 기본 기능에서\n"
    "'광학 문자 인식(OCR)'을 설치한 뒤 다시 시도해 주세요."
)

_IMPORT_ERROR = ""

try:
    from winrt.runtime import init_apartment
    from winrt.windows.globalization import Language
    from winrt.windows.graphics.imaging import BitmapAlphaMode, BitmapDecoder, BitmapPixelFormat
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream
except Exception as error:  # pragma: no cover - 환경 의존
    OcrEngine = None
    _IMPORT_ERROR = str(error)


class OcrError(RuntimeError):
    """사용자에게 그대로 보여 줄 수 있는 한국어 오류 메시지를 담는다."""


_apartment_lock = threading.Lock()
_apartment_threads: set[int] = set()


def _ensure_apartment() -> None:
    """WinRT 호출 전에 현재 스레드의 아파트를 초기화한다 (스레드당 1회)."""
    thread_id = threading.get_ident()
    with _apartment_lock:
        if thread_id in _apartment_threads:
            return
        _apartment_threads.add(thread_id)
    try:
        init_apartment()
    except Exception:
        # 이미 다른 방식으로 초기화된 스레드 — 그대로 사용한다.
        pass


def bindings_available() -> bool:
    return OcrEngine is not None


def available_languages() -> list[tuple[str, str]]:
    """설치된 OCR 인식 언어 목록 [(언어 태그, 표시 이름)]."""
    if not bindings_available():
        return []
    try:
        _ensure_apartment()
        return [(language.language_tag, language.display_name) for language in OcrEngine.available_recognizer_languages]
    except Exception:
        return []


def max_image_dimension() -> int:
    if not bindings_available():
        return MAX_IMAGE_DIMENSION
    try:
        _ensure_apartment()
        return int(OcrEngine.max_image_dimension)
    except Exception:
        return MAX_IMAGE_DIMENSION


def available() -> bool:
    return bool(available_languages())


def unavailable_reason() -> str:
    """사용할 수 없을 때 보여 줄 안내 문구 (사용 가능하면 빈 문자열)."""
    if not bindings_available():
        return (
            "OCR 모듈(winrt)을 불러오지 못했습니다.\n"
            "requirements.txt 를 설치한 뒤 다시 시도해 주세요.\n"
            f"({_IMPORT_ERROR})"
        )
    if not available_languages():
        return LANGUAGE_PACK_GUIDE
    return ""


def _create_engine(language_tag: str = ""):
    tag = str(language_tag or "").strip()
    if tag:
        try:
            engine = OcrEngine.try_create_from_language(Language(tag))
        except Exception:
            engine = None
        if engine is not None:
            return engine
    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is not None:
        return engine
    languages = OcrEngine.available_recognizer_languages
    if languages:
        return OcrEngine.try_create_from_language(languages[0])
    return None


def _software_bitmap_from_png(png_bytes: bytes):
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png_bytes)
    writer.store_async().get()
    writer.flush_async().get()
    writer.detach_stream()
    stream.seek(0)
    decoder = BitmapDecoder.create_async(stream).get()
    return decoder.get_software_bitmap_converted_async(BitmapPixelFormat.BGRA8, BitmapAlphaMode.IGNORE).get()


def recognize_png(png_bytes: bytes, language_tag: str = "") -> list[str]:
    """PNG 바이트에서 글자를 인식해 줄 단위 텍스트 목록을 돌려준다.

    실패하면 사용자에게 보여 줄 문구를 담은 OcrError 를 던진다.
    """
    if not png_bytes:
        raise OcrError("인식할 이미지가 없습니다.")
    reason = unavailable_reason()
    if reason:
        raise OcrError(reason)
    _ensure_apartment()
    try:
        engine = _create_engine(language_tag)
    except Exception as error:
        raise OcrError(f"OCR 엔진을 만들지 못했습니다.\n{error}") from error
    if engine is None:
        raise OcrError(LANGUAGE_PACK_GUIDE)
    try:
        bitmap = _software_bitmap_from_png(png_bytes)
        result = engine.recognize_async(bitmap).get()
    except Exception as error:
        raise OcrError(f"글자를 인식하지 못했습니다.\n{error}") from error
    return [line.text for line in result.lines]
