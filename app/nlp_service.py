import json
import logging
from datetime import datetime

from openai import AsyncOpenAI, APIError

from app.config import OPENAI_API_KEY, OPENAI_MODEL, TIMEZONE

logger = logging.getLogger(__name__)

_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """당신은 캘린더 관리 어시스턴트입니다.
사용자의 한국어 메시지를 분석하여 의도(intent)를 파악하고, 필요한 정보를 JSON으로 반환하세요.

## 의도(intent) 종류

1. **add** - 일정 추가
2. **delete** - 일정 삭제
3. **edit** - 일정 수정
4. **query_today** - 오늘 일정 조회
5. **query_week** - 이번 주 일정 조회
6. **search** - 일정 검색 (특정 날짜, 키워드)
7. **other** - 일정과 무관한 메시지

## 각 intent별 JSON 형식

### add (일정 추가)
{
  "intent": "add",
  "title": "일정 제목",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM 또는 null",
  "description": "설명 또는 null"
}

### delete (일정 삭제)
{
  "intent": "delete",
  "title": "삭제할 일정 제목 (부분 일치 가능)",
  "date": "YYYY-MM-DD"
}

### edit (일정 수정)
{
  "intent": "edit",
  "title": "수정할 일정 제목 (부분 일치 가능)",
  "date": "YYYY-MM-DD",
  "changes": {
    "title": "새 제목 또는 null",
    "date": "새 날짜 또는 null",
    "start_time": "새 시작시간 또는 null",
    "end_time": "새 종료시간 또는 null",
    "description": "새 설명 또는 null"
  }
}

### query_today (오늘 일정 조회)
{
  "intent": "query_today"
}

### query_week (이번 주 일정 조회)
{
  "intent": "query_week"
}

### search (일정 검색)
{
  "intent": "search",
  "keyword": "검색 키워드 또는 null",
  "date_from": "YYYY-MM-DD 또는 null",
  "date_to": "YYYY-MM-DD 또는 null"
}

### other (일정 무관)
{
  "intent": "other",
  "response": "적절한 한국어 응답"
}

## 규칙
1. 반드시 위 JSON 형식 중 하나로만 응답하세요.
2. 날짜가 상대적이면 (내일, 다음주 등) 오늘 날짜 기준으로 절대 날짜로 변환하세요.
3. 사용자가 "일정 알려줘", "뭐 있어?" 등 조회 요청을 하면 query_today 또는 query_week으로 판단하세요.
4. "이번 주", "이번주", "주간" 등이 포함되면 query_week으로 판단하세요.
5. 특정 날짜나 키워드로 검색하는 경우 search로 판단하세요.
6. "삭제", "취소", "없애줘", "지워줘" 등이 포함되면 delete로 판단하세요.
7. "변경", "수정", "바꿔", "옮겨" 등이 포함되면 edit로 판단하세요."""


async def parse_message(user_message: str) -> dict | None:
    today = datetime.now(TIMEZONE)
    today_str = today.strftime("%Y-%m-%d")
    weekday_names = ["월요일", "화요일", "수요일", "목요일", "금요일", "토요일", "일요일"]
    today_weekday = weekday_names[today.weekday()]

    user_prompt = f"오늘 날짜: {today_str} ({today_weekday})\n\n메시지: {user_message}"

    try:
        response = await _client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)

        intent = parsed.get("intent")
        if not intent:
            logger.warning("NLP response missing intent: %s", content)
            return None

        # Validate required fields per intent
        if intent == "add":
            required = ("title", "date", "start_time")
            if not all(parsed.get(k) for k in required):
                logger.warning("Add intent missing fields: %s", content)
                return None

        elif intent == "delete":
            if not parsed.get("title") or not parsed.get("date"):
                logger.warning("Delete intent missing fields: %s", content)
                return None

        elif intent == "edit":
            if not parsed.get("title") or not parsed.get("date"):
                logger.warning("Edit intent missing fields: %s", content)
                return None

        return parsed

    except json.JSONDecodeError:
        logger.error("NLP returned invalid JSON: %s", content)
        return None
    except APIError as e:
        logger.error("OpenAI API error: %s", e)
        return None
    except Exception:
        logger.exception("Unexpected error in parse_message")
        return None
