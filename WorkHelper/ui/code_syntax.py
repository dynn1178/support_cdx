"""스니펫 코드 강조 — 언어 정의, 자동 감지, QSyntaxHighlighter, 언어 선택 콤보."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from PyQt6.QtCore import QEvent, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PyQt6.QtWidgets import QComboBox, QCompleter, QTextEdit

AUTO_LANGUAGE = "auto"
PLAIN_LANGUAGE = "text"

# ---------------------------------------------------------------------------
# 언어 정의
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LanguageSpec:
    id: str
    label: str
    extension: str
    keywords: str = ""
    types: str = ""
    line_comments: tuple[str, ...] = ()
    # (시작 토큰, 끝 토큰, 색상 키) — 여러 줄에 걸치는 주석/문자열
    regions: tuple[tuple[str, str, str], ...] = ()
    strings: tuple[str, ...] = ()
    escape: bool = True
    case_insensitive: bool = False
    functions: bool = True
    # (정규식, 색상 키, 캡처 그룹)
    extra: tuple[tuple[str, str, int], ...] = ()


C_BLOCK = (("/*", "*/", "comment"),)
QUOTES = ("'", '"')

_SPEC_LIST: list[LanguageSpec] = [
    LanguageSpec("text", "텍스트 (Plain Text)", "txt", functions=False),
    LanguageSpec(
        "sql",
        "SQL",
        "sql",
        keywords=(
            "select from where group by order having join inner left right outer full cross apply on as and or not in "
            "exists between like is null case when then else end insert into values update set delete create table "
            "temporary temp view materialized index sequence trigger procedure function drop alter add column rename "
            "union all any some distinct with limit offset fetch next rows only top over partition range preceding "
            "following unbounded current row desc asc primary key foreign references unique check default constraint "
            "cast declare begin commit rollback grant revoke truncate merge using natural pivot unpivot connect prior "
            "start exec execute call returning if elsif loop while for each statement before after instead of"
        ),
        types=(
            "int integer smallint bigint decimal numeric float real double precision char varchar varchar2 nchar "
            "nvarchar text clob blob date datetime timestamp time boolean bit binary uuid json xml "
            "count sum avg min max coalesce nvl nvl2 ifnull isnull to_char to_date to_number to_timestamp substr "
            "substring trim ltrim rtrim upper lower length len replace round trunc floor ceil abs mod power sqrt "
            "sysdate current_date current_timestamp extract datediff dateadd rank dense_rank row_number ntile lag "
            "lead first_value last_value listagg string_agg group_concat concat nullif greatest least decode convert"
        ),
        line_comments=("--",),
        regions=C_BLOCK,
        strings=QUOTES,
        escape=False,
        case_insensitive=True,
    ),
    LanguageSpec(
        "python",
        "Python",
        "py",
        keywords=(
            "False None True and as assert async await break class continue def del elif else except finally for from "
            "global if import in is lambda nonlocal not or pass raise return try while with yield match case"
        ),
        types=(
            "abs all any bool bytes callable chr dict dir divmod enumerate eval exec filter float format frozenset "
            "getattr hasattr hash hex id input int isinstance issubclass iter len list map max min next object oct "
            "open ord pow print range repr reversed round set setattr slice sorted staticmethod str sum super tuple "
            "type vars zip self cls Exception ValueError TypeError KeyError IndexError RuntimeError"
        ),
        line_comments=("#",),
        regions=(('"""', '"""', "string"), ("'''", "'''", "string")),
        strings=QUOTES,
        extra=((r"@\w[\w.]*", "type", 0),),
    ),
    LanguageSpec(
        "javascript",
        "JavaScript",
        "js",
        keywords=(
            "async await break case catch class const continue debugger default delete do else export extends false "
            "finally for function if import in instanceof let new null of return static super switch this throw true "
            "try typeof var void while with yield from as"
        ),
        types=(
            "Array Boolean Date Error Function JSON Map Math Number Object Promise RegExp Set String Symbol console "
            "document window undefined NaN Infinity require module exports globalThis fetch"
        ),
        line_comments=("//",),
        regions=C_BLOCK,
        strings=("'", '"', "`"),
    ),
    LanguageSpec(
        "typescript",
        "TypeScript",
        "ts",
        keywords=(
            "abstract any as asserts async await boolean break case catch class const constructor continue declare "
            "default delete do else enum export extends false finally for from function get if implements import in "
            "infer instanceof interface is keyof let namespace never new null number object of private protected "
            "public readonly return set static string super switch symbol this throw true try type typeof undefined "
            "unique unknown var void while yield"
        ),
        types=(
            "Array Boolean Date Error Function JSON Map Math Number Object Promise Record Partial ReadonlyArray "
            "RegExp Set String Symbol console document window NaN Infinity require module exports"
        ),
        line_comments=("//",),
        regions=C_BLOCK,
        strings=("'", '"', "`"),
    ),
    LanguageSpec(
        "java",
        "Java",
        "java",
        keywords=(
            "abstract assert boolean break byte case catch char class const continue default do double else enum "
            "extends final finally float for goto if implements import instanceof int interface long native new "
            "package private protected public record return sealed short static strictfp super switch synchronized "
            "this throw throws transient try var void volatile while true false null"
        ),
        types=(
            "String Integer Double Boolean Long Character Object List ArrayList LinkedList Map HashMap TreeMap Set "
            "HashSet Optional Stream System Math Exception RuntimeException Override Deprecated"
        ),
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
    ),
    LanguageSpec(
        "csharp",
        "C#",
        "cs",
        keywords=(
            "abstract as base bool break byte case catch char checked class const continue decimal default delegate "
            "do double else enum event explicit extern false finally fixed float for foreach goto if implicit in int "
            "interface internal is lock long namespace new null object operator out override params private "
            "protected public readonly record ref return sbyte sealed short sizeof stackalloc static string struct "
            "switch this throw true try typeof uint ulong unchecked unsafe ushort using var virtual void volatile "
            "while async await dynamic nameof when where yield"
        ),
        types="Console String Int32 Int64 Double Boolean DateTime List Dictionary IEnumerable Task Exception Math",
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
    ),
    LanguageSpec(
        "cpp",
        "C / C++",
        "cpp",
        keywords=(
            "alignas alignof asm auto bool break case catch char class const constexpr const_cast continue decltype "
            "default delete do double dynamic_cast else enum explicit export extern false float for friend goto if "
            "inline int long mutable namespace new noexcept nullptr operator private protected public register "
            "reinterpret_cast return short signed sizeof static static_cast struct switch template this throw true "
            "try typedef typeid typename union unsigned using virtual void volatile while include define ifdef "
            "ifndef endif pragma NULL"
        ),
        types="std string vector map set list array size_t uint8_t uint16_t uint32_t uint64_t int8_t int16_t int32_t int64_t printf scanf cout cin endl malloc free memcpy strlen",
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
        extra=((r"^\s*#\s*\w+", "type", 0),),
    ),
    LanguageSpec(
        "go",
        "Go",
        "go",
        keywords=(
            "break case chan const continue default defer else fallthrough for func go goto if import interface map "
            "package range return select struct switch type var nil true false"
        ),
        types=(
            "bool byte complex64 complex128 error float32 float64 int int8 int16 int32 int64 rune string uint uint8 "
            "uint16 uint32 uint64 uintptr make new len cap append copy delete panic recover print println fmt"
        ),
        line_comments=("//",),
        regions=C_BLOCK,
        strings=("'", '"', "`"),
    ),
    LanguageSpec(
        "rust",
        "Rust",
        "rs",
        keywords=(
            "as async await break const continue crate dyn else enum extern false fn for if impl in let loop match "
            "mod move mut pub ref return self Self static struct super trait true type unsafe use where while"
        ),
        types=(
            "bool char f32 f64 i8 i16 i32 i64 i128 isize str u8 u16 u32 u64 u128 usize String Vec Option Result Some "
            "None Ok Err Box HashMap println format vec"
        ),
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
    ),
    LanguageSpec(
        "kotlin",
        "Kotlin",
        "kt",
        keywords=(
            "abstract actual annotation as break by catch class companion const constructor continue crossinline "
            "data delegate do dynamic else enum expect external false final finally for fun get if import in infix "
            "init inline inner interface internal is lateinit noinline null object open operator out override "
            "package private protected public reified return sealed set super suspend tailrec this throw true try "
            "typealias val var vararg when where while"
        ),
        types="String Int Long Double Float Boolean List MutableList Map MutableMap Set Any Unit Nothing println",
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
    ),
    LanguageSpec(
        "swift",
        "Swift",
        "swift",
        keywords=(
            "associatedtype as Any break case catch class continue default defer deinit do else enum extension "
            "fallthrough false fileprivate for func guard if import in init inout internal is let nil open operator "
            "private protocol public repeat rethrows return self Self static struct subscript super switch throw "
            "throws true try typealias var where while"
        ),
        types="String Int Double Float Bool Array Dictionary Set Optional print",
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
    ),
    LanguageSpec(
        "php",
        "PHP",
        "php",
        keywords=(
            "abstract and array as break callable case catch class clone const continue declare default do echo else "
            "elseif empty enum extends final finally fn for foreach function global goto if implements include "
            "include_once instanceof insteadof interface isset list match namespace new or print private protected "
            "public readonly require require_once return static switch throw trait try unset use var while xor yield "
            "true false null"
        ),
        types="string int float bool array object mixed void self parent this echo printf sprintf count strlen",
        line_comments=("//", "#"),
        regions=C_BLOCK,
        strings=QUOTES,
        extra=((r"\$\w+", "type", 0), (r"<\?php|\?>", "keyword", 0)),
    ),
    LanguageSpec(
        "ruby",
        "Ruby",
        "rb",
        keywords=(
            "alias and begin break case class def defined do else elsif end ensure false for if in module next nil "
            "not or redo rescue retry return self super then true undef unless until when while yield"
        ),
        types="attr_accessor attr_reader attr_writer require require_relative puts print lambda proc new each map select String Integer Float Array Hash Symbol",
        line_comments=("#",),
        regions=(("=begin", "=end", "comment"),),
        strings=QUOTES,
        extra=((r"[:@]\w+", "type", 0),),
    ),
    LanguageSpec(
        "shell",
        "Shell (Bash)",
        "sh",
        keywords=(
            "if then else elif fi case esac for while until do done in function select return break continue local "
            "export readonly declare typeset unset shift eval exec exit trap source alias set"
        ),
        types=(
            "echo printf read cd pwd ls cat grep sed awk cut sort uniq head tail wc find xargs chmod chown mkdir rm "
            "cp mv touch curl wget tar zip unzip git python pip docker kubectl"
        ),
        line_comments=("#",),
        strings=QUOTES,
        functions=False,
        extra=((r"\$\{?\w+\}?", "type", 0),),
    ),
    LanguageSpec(
        "powershell",
        "PowerShell",
        "ps1",
        keywords=(
            "begin break catch class continue data define do dynamicparam else elseif end enum exit filter finally "
            "for foreach from function hidden if in param process return switch throw trap try until using var while "
            "workflow true false null"
        ),
        types="Get Set New Remove Write Read Start Stop Out Select Where ForEach Import Export Test Invoke Add Copy Move",
        line_comments=("#",),
        regions=(("<#", "#>", "comment"),),
        strings=QUOTES,
        case_insensitive=True,
        extra=((r"\$\w+", "type", 0), (r"-\w+", "keyword", 0)),
    ),
    LanguageSpec(
        "r",
        "R",
        "R",
        keywords="if else repeat while function for in next break TRUE FALSE NULL Inf NaN NA library require return source",
        types=(
            "c list data.frame matrix vector factor levels names dim nrow ncol apply sapply lapply vapply mapply "
            "tapply aggregate merge subset head tail summary print plot paste paste0 seq rep length mean median sd"
        ),
        line_comments=("#",),
        strings=QUOTES,
        extra=((r"<-|->|%>%|%in%", "keyword", 0),),
    ),
    LanguageSpec(
        "scala",
        "Scala",
        "scala",
        keywords=(
            "abstract case catch class def do else extends false final finally for forSome if implicit import lazy "
            "match new null object override package private protected return sealed super this throw trait try true "
            "type val var while with yield"
        ),
        types="String Int Long Double Float Boolean List Map Set Option Some None Seq Array Any Unit Nothing println",
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
    ),
    LanguageSpec(
        "dart",
        "Dart",
        "dart",
        keywords=(
            "abstract as assert async await break case catch class const continue covariant default deferred do "
            "dynamic else enum export extends extension external factory false final finally for get hide if "
            "implements import in interface is late library mixin new null on operator part required rethrow return "
            "set show static super switch sync this throw true try typedef var void while with yield"
        ),
        types="String int double num bool List Map Set Future Stream print",
        line_comments=("//",),
        regions=C_BLOCK,
        strings=QUOTES,
    ),
    LanguageSpec(
        "lua",
        "Lua",
        "lua",
        keywords="and break do else elseif end false for function goto if in local nil not or repeat return then true until while",
        types="print pairs ipairs require table string math os io tostring tonumber type setmetatable getmetatable",
        line_comments=("--",),
        regions=(("--[[", "]]", "comment"),),
        strings=QUOTES,
    ),
    LanguageSpec(
        "perl",
        "Perl",
        "pl",
        keywords=(
            "if elsif else unless while until for foreach do sub return my our local last next redo goto package use "
            "no require BEGIN END and or not eq ne lt gt le ge cmp"
        ),
        types="print printf say chomp chop split join push pop shift unshift keys values exists delete defined ref bless wantarray scalar",
        line_comments=("#",),
        strings=QUOTES,
        extra=((r"[$@%]\w+", "type", 0),),
    ),
    LanguageSpec(
        "matlab",
        "MATLAB",
        "m",
        keywords="break case catch classdef continue else elseif end for function global if otherwise parfor persistent return spmd switch try while true false",
        types="disp fprintf sprintf size length zeros ones rand numel strcmp isempty plot figure hold axis xlabel ylabel title",
        line_comments=("%",),
        regions=(("%{", "%}", "comment"),),
        strings=QUOTES,
    ),
    LanguageSpec(
        "vba",
        "VBA / VBScript",
        "bas",
        keywords=(
            "and as boolean byref byval call case const continue dim do double each else elseif end enum error exit "
            "explicit false for function get global goto if in integer is let like long loop me mod new next not "
            "nothing object on option optional or preserve private property public redim resume return select set "
            "single static step stop string sub then to true type until variant wend while with xor"
        ),
        types="msgbox range cells sheets worksheets workbooks application debug print cstr cint clng cdbl trim left right mid instr ubound lbound",
        line_comments=("'",),
        strings=('"',),
        case_insensitive=True,
    ),
    LanguageSpec(
        "batch",
        "Batch (CMD)",
        "bat",
        keywords="if else for in do goto call exit set setlocal endlocal shift start pause title cls errorlevel not exist defined equ neq lss leq gtr geq",
        types="echo rem copy move del rd md dir type findstr find xcopy robocopy attrib ping net sc reg",
        line_comments=("::", "rem "),
        strings=('"',),
        case_insensitive=True,
        functions=False,
        extra=((r"%\w+%|%%?\w", "type", 0),),
    ),
    LanguageSpec(
        "html",
        "HTML",
        "html",
        regions=(("<!--", "-->", "comment"),),
        functions=False,
        extra=(
            (r"</?\s*([A-Za-z][\w:-]*)", "keyword", 1),
            (r"([\w:-]+)\s*=", "type", 1),
            (r"\"[^\"]*\"|'[^']*'", "string", 0),
        ),
    ),
    LanguageSpec(
        "xml",
        "XML",
        "xml",
        regions=(("<!--", "-->", "comment"),),
        functions=False,
        extra=(
            (r"</?\s*([A-Za-z_][\w:.-]*)", "keyword", 1),
            (r"([\w:.-]+)\s*=", "type", 1),
            (r"\"[^\"]*\"|'[^']*'", "string", 0),
        ),
    ),
    LanguageSpec(
        "css",
        "CSS",
        "css",
        regions=C_BLOCK,
        strings=QUOTES,
        functions=False,
        keywords="important inherit initial unset auto none block flex grid absolute relative fixed sticky hidden visible",
        extra=(
            (r"([\w-]+)\s*:", "type", 1),
            (r"[.#]?[\w-]+(?=\s*[{,])", "keyword", 0),
            (r"@[\w-]+", "keyword", 0),
            (r"-?\d+(?:\.\d+)?(?:px|em|rem|%|vh|vw|pt|s|ms|deg|fr)?", "number", 0),
            (r"#[0-9A-Fa-f]{3,8}\b", "number", 0),
        ),
    ),
    LanguageSpec(
        "json",
        "JSON",
        "json",
        keywords="true false null",
        strings=('"',),
        functions=False,
        extra=((r"\"(?:[^\"\\]|\\.)*\"\s*:", "type", 0),),
    ),
    LanguageSpec(
        "yaml",
        "YAML",
        "yaml",
        keywords="true false null yes no on off",
        line_comments=("#",),
        strings=QUOTES,
        functions=False,
        extra=((r"^\s*-?\s*([\w.\-/]+)\s*:", "type", 1), (r"^\s*-\s", "keyword", 0)),
    ),
    LanguageSpec(
        "ini",
        "INI / Properties",
        "ini",
        line_comments=(";", "#"),
        strings=QUOTES,
        functions=False,
        extra=((r"^\s*\[[^\]]+\]", "keyword", 0), (r"^\s*([\w.\- ]+)\s*=", "type", 1)),
    ),
    LanguageSpec(
        "markdown",
        "Markdown",
        "md",
        functions=False,
        extra=(
            (r"^\s{0,3}#{1,6}\s.*", "keyword", 0),
            (r"\*\*[^*]+\*\*|__[^_]+__", "type", 0),
            (r"`[^`]+`", "string", 0),
            (r"^\s*[-*+]\s|^\s*\d+\.\s", "number", 0),
            (r"\[[^\]]*\]\([^)]*\)", "function", 0),
            (r"^\s*>.*", "comment", 0),
        ),
    ),
]

SPECS: dict[str, LanguageSpec] = {spec.id: spec for spec in _SPEC_LIST}
# 구버전 데이터 호환 — 예전에는 언어를 'other'로 저장했다.
LANGUAGE_ALIASES = {
    "other": PLAIN_LANGUAGE,
    "기타": PLAIN_LANGUAGE,
    "plain": PLAIN_LANGUAGE,
    "": PLAIN_LANGUAGE,
    "js": "javascript",
    "ts": "typescript",
    "py": "python",
    "c": "cpp",
    "c++": "cpp",
    "bash": "shell",
    "sh": "shell",
    "yml": "yaml",
}


def normalize_language(language: str | None) -> str:
    value = str(language or "").strip().lower()
    value = LANGUAGE_ALIASES.get(value, value)
    return value if value in SPECS else PLAIN_LANGUAGE


def language_spec(language: str | None) -> LanguageSpec:
    return SPECS[normalize_language(language)]


def language_label(language: str | None) -> str:
    return language_spec(language).label


def language_extension(language: str | None) -> str:
    return language_spec(language).extension


def sorted_languages() -> list[LanguageSpec]:
    """텍스트를 맨 앞에 두고 나머지는 이름순으로 정렬한다."""
    rest = [spec for spec in _SPEC_LIST if spec.id != PLAIN_LANGUAGE]
    rest.sort(key=lambda spec: spec.label.lower())
    return [SPECS[PLAIN_LANGUAGE], *rest]


# ---------------------------------------------------------------------------
# 자동 감지
# ---------------------------------------------------------------------------

# (정규식, 언어, 점수) — 점수 합이 가장 높은 언어를 고른다.
DETECT_RULES: tuple[tuple[str, str, int], ...] = (
    (r"^\s*<\?php", "php", 8),
    (r"^\s*<\?xml", "xml", 8),
    (r"^\s*<!DOCTYPE\s+html|<html[\s>]|</(?:div|span|body|head|p|table)>", "html", 6),
    (r"^#!.*\b(?:bash|sh|zsh|ksh)\b", "shell", 8),
    (r"^#!.*\bpython", "python", 8),
    (r"\bSELECT\b[\s\S]*\bFROM\b", "sql", 6),
    (r"\b(?:INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM|CREATE\s+(?:TABLE|VIEW|INDEX)|ALTER\s+TABLE)\b", "sql", 5),
    (r"\b(?:INNER|LEFT|RIGHT|FULL)\s+(?:OUTER\s+)?JOIN\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bWITH\s+\w+\s+AS\s*\(", "sql", 4),
    (r"^\s*(?:def|class)\s+\w+.*:\s*$", "python", 5),
    (r"^\s*(?:from\s+[\w.]+\s+)?import\s+[\w.,*\s]+$", "python", 3),
    (r"^\s*(?:if|for|while|with|try|elif|else|except)\b[^\n]*:\s*$", "python", 2),
    (r"\bprint\(|\bself\.", "python", 2),
    (r"\bfunction\s+\w*\s*\(|=>\s*[{(]|\bconsole\.log\(", "javascript", 4),
    (r"\b(?:const|let)\s+\w+\s*=", "javascript", 2),
    (r"\b(?:interface|type)\s+\w+\s*(?:=|\{)|:\s*(?:string|number|boolean)\b", "typescript", 4),
    (r"\bpublic\s+(?:static\s+)?(?:void|class)\b|System\.out\.print", "java", 5),
    (r"\busing\s+System\b|\bnamespace\s+\w+|Console\.Write", "csharp", 5),
    (r"^\s*#include\s*[<\"]|\bstd::|\bprintf\s*\(", "cpp", 5),
    (r"^\s*package\s+\w+\s*$|\bfunc\s+\w*\s*\(|\bfmt\.Print", "go", 5),
    (r"\bfn\s+\w+\s*\(|\blet\s+mut\b|\bprintln!\(", "rust", 5),
    (r"\bdef\s+\w+.*\bend\b|\bputs\b|\brequire_relative\b", "ruby", 4),
    (r"^\s*(?:echo|export|source)\s+|\$\{\w+\}|\bfi\s*$|\bdone\s*$", "shell", 3),
    (r"\$[A-Za-z_]\w*\s*=|\bGet-\w+|\bWrite-Host\b", "powershell", 4),
    (r"<-\s*(?:function|c)\(|%>%|\blibrary\(", "r", 5),
    (r"^\s*[\w.\-]+\s*:\s*(?:[^\n]*)$(?:\n\s*-\s)", "yaml", 3),
    (r"^\s*---\s*$", "yaml", 3),
    (r"^\s*[.#]?[\w-]+\s*\{[^}]*[\w-]+\s*:\s*[^;]+;", "css", 5),
    (r"^\s*#{1,6}\s+\S|^\s*```", "markdown", 3),
    (r"^\s*\[[\w. ]+\]\s*$", "ini", 3),
    (r"^\s*(?:Sub|Function)\s+\w+\s*\(|\bMsgBox\b|\bDim\s+\w+\s+As\b", "vba", 5),
    (r"^\s*@echo\s+off|%~dp0|\bgoto\s+:\w+", "batch", 5),
    (r"^\s*(?:local\s+\w+\s*=|function\s+\w+\s*\().*\bend\b", "lua", 3),
)

_DETECT_COMPILED = tuple(
    (re.compile(pattern, re.IGNORECASE | re.MULTILINE), language, weight)
    for pattern, language, weight in DETECT_RULES
)


def detect_language(text: str, minimum_score: int = 3) -> str:
    """내용을 보고 언어를 추정한다. 확신이 없으면 'text'를 돌려준다."""
    body = str(text or "").strip()
    if not body:
        return PLAIN_LANGUAGE
    stripped = body.lstrip()
    if stripped[:1] in "{[":
        try:
            json.loads(body)
            return "json"
        except (ValueError, TypeError):
            pass
    scores: dict[str, int] = {}
    for pattern, language, weight in _DETECT_COMPILED:
        if pattern.search(body):
            scores[language] = scores.get(language, 0) + weight
    if not scores:
        return PLAIN_LANGUAGE
    best = max(scores.items(), key=lambda entry: entry[1])
    return best[0] if best[1] >= minimum_score else PLAIN_LANGUAGE


# ---------------------------------------------------------------------------
# 색상 · 하이라이터
# ---------------------------------------------------------------------------

LIGHT_COLORS = {
    "background": "#FFFFFF",
    "foreground": "#1F2433",
    "keyword": "#0033B3",
    "type": "#0F7B8A",
    "string": "#A31515",
    "number": "#098658",
    "comment": "#3E8A50",
    "function": "#795E26",
}

DARK_COLORS = {
    "background": "#1E1F22",
    "foreground": "#D6D9E0",
    "keyword": "#C792EA",
    "type": "#4EC9B0",
    "string": "#CE9178",
    "number": "#B5CEA8",
    "comment": "#6A9955",
    "function": "#DCDCAA",
}


def code_colors(dark: bool) -> dict[str, str]:
    return dict(DARK_COLORS if dark else LIGHT_COLORS)


def is_dark_background(color: str) -> bool:
    """테마 색(#RRGGBB)의 밝기로 어두운 테마인지 판단한다."""
    raw = str(color or "").strip().lstrip("#")
    if len(raw) != 6:
        return False
    try:
        red, green, blue = (int(raw[index : index + 2], 16) for index in (0, 2, 4))
    except ValueError:
        return False
    return (0.299 * red + 0.587 * green + 0.114 * blue) < 128


def _build_formats(dark: bool) -> dict[str, QTextCharFormat]:
    colors = code_colors(dark)
    formats: dict[str, QTextCharFormat] = {}
    for key in ("keyword", "type", "string", "number", "comment", "function"):
        char_format = QTextCharFormat()
        char_format.setForeground(QColor(colors[key]))
        if key == "keyword":
            char_format.setFontWeight(QFont.Weight.Bold)
        if key == "comment":
            char_format.setFontItalic(True)
        formats[key] = char_format
    return formats


def _word_pattern(words: str, case_insensitive: bool) -> re.Pattern | None:
    tokens = sorted({word for word in words.split() if word}, key=len, reverse=True)
    if not tokens:
        return None
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile(r"\b(?:" + "|".join(re.escape(token) for token in tokens) + r")\b", flags)


@dataclass
class _CompiledSpec:
    spec: LanguageSpec
    rules: list[tuple[re.Pattern, str, int]] = field(default_factory=list)


def _compile_spec(spec: LanguageSpec) -> _CompiledSpec:
    compiled = _CompiledSpec(spec)
    compiled.rules.append((re.compile(r"\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?\b"), "number", 0))
    for pattern, key, group in spec.extra:
        compiled.rules.append((re.compile(pattern, re.MULTILINE), key, group))
    if spec.functions:
        compiled.rules.append((re.compile(r"\b([A-Za-z_]\w*)\s*\("), "function", 1))
    types_pattern = _word_pattern(spec.types, spec.case_insensitive)
    if types_pattern is not None:
        compiled.rules.append((types_pattern, "type", 0))
    keyword_pattern = _word_pattern(spec.keywords, spec.case_insensitive)
    if keyword_pattern is not None:
        compiled.rules.append((keyword_pattern, "keyword", 0))
    return compiled


_COMPILED_CACHE: dict[str, _CompiledSpec] = {}


def compiled_spec(language: str) -> _CompiledSpec:
    key = normalize_language(language)
    if key not in _COMPILED_CACHE:
        _COMPILED_CACHE[key] = _compile_spec(SPECS[key])
    return _COMPILED_CACHE[key]


class CodeHighlighter(QSyntaxHighlighter):
    """문자열·주석을 먼저 훑고 남은 구간에만 키워드 규칙을 적용하는 단순 강조기."""

    def __init__(self, document, language: str = PLAIN_LANGUAGE, dark: bool = False) -> None:
        super().__init__(document)
        self._formats = _build_formats(dark)
        self._compiled = compiled_spec(language)
        self._language = normalize_language(language)

    @property
    def language(self) -> str:
        return self._language

    def set_language(self, language: str) -> None:
        normalized = normalize_language(language)
        if normalized == self._language:
            return
        self._language = normalized
        self._compiled = compiled_spec(normalized)
        self.rehighlight()

    def set_dark(self, dark: bool) -> None:
        self._formats = _build_formats(dark)
        self.rehighlight()

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (Qt 시그니처)
        spec = self._compiled.spec
        length = len(text)
        self.setCurrentBlockState(-1)
        if not length:
            return
        plain_spans: list[tuple[int, int]] = []
        span_start = 0
        position = 0
        state = self.previousBlockState()
        while position < length:
            # 1) 이전 줄에서 이어지는 블록 주석/여러 줄 문자열
            if state > 0 and state <= len(spec.regions):
                start_token, end_token, key = spec.regions[state - 1]
                end = text.find(end_token, position)
                if end < 0:
                    self.setFormat(position, length - position, self._formats[key])
                    self.setCurrentBlockState(state)
                    position = length
                    span_start = length
                    break
                self.setFormat(position, end + len(end_token) - position, self._formats[key])
                position = end + len(end_token)
                span_start = position
                state = -1
                continue
            # 2) 한 줄 주석 — 줄 끝까지
            comment_token = next((token for token in spec.line_comments if self._starts_with(text, position, token, spec)), None)
            if comment_token is not None:
                plain_spans.append((span_start, position))
                self.setFormat(position, length - position, self._formats["comment"])
                span_start = length
                position = length
                break
            # 3) 블록 주석/여러 줄 문자열 시작
            region_index = next(
                (index for index, region in enumerate(spec.regions) if text.startswith(region[0], position)),
                None,
            )
            if region_index is not None:
                start_token, end_token, key = spec.regions[region_index]
                plain_spans.append((span_start, position))
                end = text.find(end_token, position + len(start_token))
                if end < 0:
                    self.setFormat(position, length - position, self._formats[key])
                    self.setCurrentBlockState(region_index + 1)
                    position = length
                else:
                    self.setFormat(position, end + len(end_token) - position, self._formats[key])
                    position = end + len(end_token)
                span_start = position
                continue
            # 4) 한 줄 문자열
            char = text[position]
            if char in spec.strings:
                plain_spans.append((span_start, position))
                cursor = position + 1
                while cursor < length:
                    if spec.escape and text[cursor] == "\\":
                        cursor += 2
                        continue
                    if text[cursor] == char:
                        cursor += 1
                        break
                    cursor += 1
                cursor = min(cursor, length)
                self.setFormat(position, cursor - position, self._formats["string"])
                position = cursor
                span_start = position
                continue
            position += 1
        plain_spans.append((span_start, min(position, length)))
        for start, end in plain_spans:
            if end > start:
                self._apply_rules(text, start, end)

    @staticmethod
    def _starts_with(text: str, position: int, token: str, spec: LanguageSpec) -> bool:
        if spec.case_insensitive:
            return text[position : position + len(token)].lower() == token.lower()
        return text.startswith(token, position)

    def _apply_rules(self, text: str, start: int, end: int) -> None:
        segment = text[start:end]
        for pattern, key, group in self._compiled.rules:
            char_format = self._formats.get(key)
            if char_format is None:
                continue
            for match in pattern.finditer(segment):
                match_start, match_end = match.span(group)
                if match_end > match_start:
                    self.setFormat(start + match_start, match_end - match_start, char_format)


# ---------------------------------------------------------------------------
# 위젯 헬퍼
# ---------------------------------------------------------------------------

CODE_FONT_FAMILIES = ("D2Coding", "Cascadia Mono", "Consolas", "Malgun Gothic", "monospace")


def code_font(point_size: int = 10) -> QFont:
    font = QFont()
    font.setFamilies(list(CODE_FONT_FAMILIES))
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(point_size)
    return font


def apply_code_editor_style(editor: QTextEdit, dark: bool, border: str = "#B9C0CC") -> None:
    """스니펫 편집기를 코드 에디터처럼 보이게 만든다."""
    colors = code_colors(dark)
    font = code_font()
    editor.setFont(font)
    editor.document().setDefaultFont(font)
    editor.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
    editor.setTabStopDistance(editor.fontMetrics().horizontalAdvance(" ") * 4)
    editor.setStyleSheet(
        "QTextEdit {"
        f"background: {colors['background']}; color: {colors['foreground']};"
        f"border: 1px solid {border}; border-radius: 7px; padding: 6px;"
        f"selection-background-color: {'#264F78' if dark else '#CCE3FF'};"
        "}"
    )


class LanguageComboBox(QComboBox):
    """검색해서 고르는 언어 선택 콤보 — 목록에 없는 값은 입력해도 되돌린다."""

    language_changed = pyqtSignal(str)

    def __init__(self, language: str = AUTO_LANGUAGE, include_auto: bool = True) -> None:
        super().__init__()
        if include_auto:
            self.addItem("자동 감지", AUTO_LANGUAGE)
        for spec in sorted_languages():
            self.addItem(spec.label, spec.id)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(16)
        self.setMinimumWidth(200)
        line_edit = self.lineEdit()
        line_edit.setPlaceholderText("언어를 검색하세요")
        # 콤보 테두리와 겹치지 않도록 내부 입력칸의 테두리는 없애고, 드롭다운 화살표 자리는 남겨둔다.
        line_edit.setStyleSheet("QLineEdit { border: 0; background: transparent; padding: 0; }")
        self.setStyleSheet(
            "QComboBox { padding-right: 22px; }"
            "QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; "
            "width: 20px; border-left: 1px solid palette(mid); }"
        )
        # 검색어를 입력하기 전에도 클릭 한 번으로 전체 목록을 볼 수 있게 한다.
        line_edit.installEventFilter(self)
        completer = QCompleter(self.model(), self)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setCompleter(completer)
        self.set_language(language)
        self.currentIndexChanged.connect(self._emit_language)
        line_edit.editingFinished.connect(self._restore_text)

    def eventFilter(self, watched, event) -> bool:  # noqa: N802 (Qt 시그니처)
        if watched is self.lineEdit() and event.type() == QEvent.Type.MouseButtonPress:
            if not self.view().isVisible():
                self.showPopup()
        return super().eventFilter(watched, event)

    def _emit_language(self, _index: int = 0) -> None:
        self.language_changed.emit(self.language())

    def _restore_text(self) -> None:
        """목록에 없는 문자열을 직접 입력한 경우 현재 선택으로 되돌린다."""
        text = self.currentText().strip()
        index = self.findText(text, Qt.MatchFlag.MatchFixedString)
        if index < 0:
            self.setCurrentIndex(max(0, self.currentIndex()))
            self.setEditText(self.itemText(max(0, self.currentIndex())))
        elif index != self.currentIndex():
            self.setCurrentIndex(index)

    def language(self) -> str:
        value = self.currentData()
        return str(value) if value else PLAIN_LANGUAGE

    def set_language(self, language: str) -> None:
        target = str(language or AUTO_LANGUAGE)
        if target != AUTO_LANGUAGE:
            target = normalize_language(target)
        index = self.findData(target)
        if index < 0:
            index = 0
        self.setCurrentIndex(index)
        self.setEditText(self.itemText(index))
