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
        sheet.update_acell("A1", f"✅ 연결 OK @ {now_kst_str()}")
        val = sheet.acell("A1").value
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
            f"현재 대선의 체력값은 '{v_g2}(체력값:G2)', 수련의 체력값은 '{v_i2}(체력값:I2)'입니다."
        )
    except Exception as e:
        await ctx.send(f"❌ 조회 실패: {e}")

def _find_row_by_name(worksheet, name: str) -> int | None:
    # '명단' 시트의 A열에서 정확히 일치하는 첫 행 번호 반환 (없으면 None)
    try:
        colA = worksheet.col_values(1)
        for idx, val in enumerate(colA, start=1):
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

bot.run(DISCORD_TOKEN)
