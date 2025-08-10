# 🔐 라이브러리 및 기본 설정
import discord
from discord.ext import commands
from discord.ui import Button, View
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, timezone
import random
import os
import json
import sys

KST = timezone(timedelta(hours=9))

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 🔐 환경변수 확인
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDS")
SHEET_KEY = os.getenv("SHEET_KEY")

missing = [k for k, v in {
    "DISCORD_BOT_TOKEN": DISCORD_TOKEN,
    "GOOGLE_CREDS": GOOGLE_CREDS,
    "SHEET_KEY": SHEET_KEY
}.items() if not v]
if missing:
    print(f"❌ 누락된 환경변수: {', '.join(missing)}")
    sys.exit(1)

# 🔐 구글 시트 인증
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
try:
    creds_dict = json.loads(GOOGLE_CREDS)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    gclient = gspread.authorize(creds)
    sheet = gclient.open_by_key(SHEET_KEY).sheet1  # 기본은 1번째 시트
except Exception as e:
    print("❌ 구글 스프레드시트 인증/접속 실패:", e)
    sys.exit(1)

# 🧰 유틸
def now_kst_str(fmt="%Y-%m-%d %H:%M:%S"):
    return datetime.now(KST).strftime(fmt)

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} ({bot.user.id})')

@bot.command()
async def 접속(ctx):
    await ctx.send('현재 봇이 구동 중입니다.')

# ✅ 연결 테스트용 커맨드 (원하면 삭제 가능)
@bot.command(name="시트테스트")
async def 시트테스트(ctx):
    try:
        sh = ws("연결 확인")  # '연결 확인' 시트 핸들러
        sh.update_acell("A1", f"✅ 연결 OK @ {now_kst_str()}")
        val = sh.acell("A1").value
        await ctx.send(f"A1 = {val}")
    except Exception as e:
        await ctx.send(f"❌ 시트 접근 실패: {e}")

# ====== 명령어: !합계 / !구매 / !사용 ======

def ws(title: str):
    # 같은 문서 내 워크시트 핸들러
    return gclient.open_by_key(SHEET_KEY).worksheet(title)

@bot.command(name="합계")
async def 합계(ctx):
    try:
        sh = ws("체력값")
        v_g2 = sh.acell("G2").value  # 대선
        v_i2 = sh.acell("I2").value  # 수련
        await ctx.send(
            f"현재 대선의 체력값은 '{v_g2}', 수련의 체력값은 '{v_i2}'입니다."
        )
    except Exception as e:
        await ctx.send(f"❌ 조회 실패: {e}")

def _find_row_by_name(worksheet, name: str) -> int | None:
    # '명단' 시트의 B열에서 정확히 일치하는 첫 행 번호 반환 (없으면 None)
    try:
        colB = worksheet.col_values(2)  # B열 = index 2
        for idx, val in enumerate(colB, start=1):
            if (val or "").strip() == name.strip():
                return idx
        return None
    except Exception:
        return None

def _normalize_items_str(s: str | None) -> str:
    # 콤마로 구분된 아이템 문자열 정규화 (공백 제거, 빈 토큰 제거)
    if not s:
        return ""
    items = [t.strip() for t in s.split(",") if t.strip()]
    return ",".join(items)

@bot.command(name="구매")
async def 구매(ctx, 이름: str, *, 물품명: str):
    """[명단!A열 이름]의 F열(물품목록)에 물품을 콤마로 누적"""
    try:
        sh = ws("명단")
        row = _find_row_by_name(sh, 이름)
        if not row:
            await ctx.send(f"❌ '{이름}' 이름을 A열에서 찾지 못했습니다.")
            return

        cur = _normalize_items_str(sh.acell(f"F{row}").value)
        items = cur.split(",") if cur else []
        items.append(물품명.strip())
        new_val = ",".join([t for t in items if t])  # 공백/빈값 제거
        sh.update_acell(f"F{row}", new_val)

        await ctx.send(f"✅ '{이름}'의 물품 목록 업데이트 완료: {new_val if new_val else '(비어 있음)'}")
    except Exception as e:
        await ctx.send(f"❌ 구매 처리 실패: {e}")

@bot.command(name="사용")
async def 사용(ctx, 이름: str, *, 물품명: str):
    """[명단!A열 이름]의 F열(물품목록)에서 해당 물품 1개 제거 (콤마 정리 포함)"""
    try:
        sh = ws("명단")
        row = _find_row_by_name(sh, 이름)
        if not row:
            await ctx.send(f"❌ '{이름}' 이름을 A열에서 찾지 못했습니다.")
            return

        cur = _normalize_items_str(sh.acell(f"F{row}").value)
        if not cur:
            await ctx.send(f"⚠️ '{이름}'의 물품 목록이 비어 있습니다.")
            return

        items = cur.split(",")
        try:
            items.remove(물품명.strip())  # 동일 명칭 1회분만 제거
        except ValueError:
            await ctx.send(f"⚠️ '{이름}'의 목록에 '{물품명}'이 없습니다.")
            return

        new_val = ",".join([t for t in items if t])
        sh.update_acell(f"F{row}", new_val)
        await ctx.send(f"✅ '{이름}'의 '{물품명}' 사용 처리 완료: {new_val if new_val else '(비어 있음)'}")
    except Exception as e:
        await ctx.send(f"❌ 사용 처리 실패: {e}")

# ====== 체력 증감 공통 유틸 ======

def _find_row_in_colB(sh, name: str):
    """B열에서 이름 정확 일치 행 번호 반환 (없으면 None)"""
    colB = sh.col_values(2)
    target = (name or "").strip()
    for idx, val in enumerate(colB, start=1):
        if (val or "").strip() == target:
            return idx
    return None

def _read_hp_D(sh, row: int) -> int:
    """해당 행의 D열(체력값) 정수 읽기 (비정상/공백은 0)"""
    raw = (sh.cell(row, 4).value or "0").strip()
    try:
        return int(raw)
    except ValueError:
        return 0

def _write_hp_D(sh, row: int, value: int):
    """해당 행의 D열 값 쓰기"""
    sh.update_cell(row, 4, value)

def _apply_delta_to_hp(name: str, delta: int):
    """
    '체력값' 시트에서 이름(B열) 찾아, 같은 행 D열에 delta만큼 반영.
    반환: (row, cur_val, new_val)
    """
    sh = ws("체력값")
    row = _find_row_in_colB(sh, name)
    if not row:
        return None, None, None
    cur_val = _read_hp_D(sh, row)
    new_val = cur_val + delta
    _write_hp_D(sh, row, new_val)
    return row, cur_val, new_val

# ====== 명령어: !추가 / !차감 ======

@bot.command(name="추가", help="!추가 이름 수치 → 기존 체력값에 수치만큼 더합니다. 예: !추가 대선 5")
async def 추가(ctx, 이름: str, 수치: str):
    if not 수치.isdigit():
        await ctx.send("⚠️ 수치는 양의 정수여야 합니다. 예) `!추가 대선 5`")
        return
    delta = int(수치)

    row, cur_val, new_val = _apply_delta_to_hp(이름, delta)
    if row is None:
        await ctx.send(f"❌ '체력값' 시트 B열에서 '{이름}'을 찾지 못했습니다.")
        return

    await ctx.send(f"✅ '{이름}' 체력값 {cur_val} → +{delta} = **{new_val}** (행 {row}, D열)")

@bot.command(name="차감", help="!차감 이름 수치 → 기존 체력값에서 수치만큼 뺍니다. 예: !차감 대선 5")
async def 차감(ctx, 이름: str, 수치: str):
    if not 수치.isdigit():
        await ctx.send("⚠️ 수치는 양의 정수여야 합니다. 예) `!차감 수련 3`")
        return
    delta = -int(수치)  # 무조건 감소

    row, cur_val, new_val = _apply_delta_to_hp(이름, delta)
    if row is None:
        await ctx.send(f"❌ '체력값' 시트 B열에서 '{이름}'을 찾지 못했습니다.")
        return

    await ctx.send(f"✅ '{이름}' 체력값 {cur_val} → -{abs(delta)} = **{new_val}** (행 {row}, D열)")

# ====== 도움말: 고정 순서/설명으로 보기 좋게 출력 ======

# 기본 help 제거 (중복 방지)
bot.remove_command("help")

# 도움말 표기 고정(오버라이드) 사전
HELP_OVERRIDES = {
    "도움말":  "현재 사용 가능한 명령어 목록을 표시합니다.",
    "시트테스트": "연결 확인 시트의 A1에 현재 시간을 기록하고 값을 확인합니다. 예) !시트테스트",
    "합계":   "체력값 시트의 대선(G2), 수련(I2) 값을 불러옵니다. 예) !합계",
    "구매":   "명단 시트에서 B열의 이름을 찾아 같은 행 F열 물품목록에 아이템을 추가(콤마 누적)합니다. 예) !구매 홍길동 붕대",
    "사용":   "명단 시트에서 B열의 이름을 찾아 같은 행 F열에서 해당 아이템 1개를 제거합니다. 예) !사용 홍길동 붕대",
    "추가":   "체력값 시트에서 B열의 이름을 찾아 같은 행 D열(체력값)에 수치만큼 더합니다. 예) !추가 대선 5",
    "차감":   "체력값 시트에서 B열의 이름을 찾아 같은 행 D열(체력값)에서 수치만큼 뺍니다. 예) !차감 대선 5",
    "접속":   "현재 봇이 정상 작동 중인지 확인합니다.",
}

# 표기 순서 고정
HELP_ORDER = ["도움말", "시트테스트", "합계", "구매", "사용", "추가", "차감", "접속"]

@bot.command(name="도움말")
async def 도움말(ctx):
    # 현재 로드된 커맨드들
    loaded = {cmd.name: cmd for cmd in bot.commands if not cmd.hidden}

    # 우선 순서대로 정리 + 로드되지 않은 항목은 건너뜀
    lines = ["**사용 가능한 명령어**\n"]
    for name in HELP_ORDER:
        if name in loaded:
            desc = HELP_OVERRIDES.get(name) or (loaded[name].help or "설명 없음")
            lines.append(f"**!{name}** — {desc}")

    # HELP_ORDER에 없지만 로드된 커맨드가 더 있다면 뒤에 추가
    for name, cmd in sorted(loaded.items()):
        if name in HELP_ORDER:
            continue
        desc = HELP_OVERRIDES.get(name) or (cmd.help or "설명 없음")
        lines.append(f"**!{name}** — {desc}")

    await ctx.send("\n".join(lines))

bot.run(DISCORD_TOKEN)
