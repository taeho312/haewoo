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

DICE_EMOJI = {
    1: "🎲1", 2: "🎲2", 3: "🎲3",
    4: "🎲4", 5: "🎲5", 6: "🎲6"
}

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user} ({bot.user.id})')

@bot.command(name="접속", help="현재 봇이 정상 작동 중인지 확인합니다. 만약 봇이 응답하지 않으면 접속 오류입니다. 예) !접속")
async def 접속(ctx):
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    await ctx.send(f"현재 봇이 구동 중입니다.\n{timestamp}")

# ✅ 연결 테스트용 커맨드 (원하면 삭제 가능)
@bot.command(name="시트테스트", help="연결 확인 시트의 A1에 현재 시간을 기록하고 값을 확인합니다. 예) !시트테스트")
async def 시트테스트(ctx):
    try:
        sh = ws("연결 확인")  # '연결 확인' 시트 핸들러
        sh.update_acell("A1", f"✅ 연결 OK @ {now_kst_str()}")
        val = sh.acell("A1").value
        await ctx.send(f"A1 = {val}")
    except Exception as e:
        await ctx.send(f"❌ 시트 접근 실패: {e}")

@bot.command(name="다이스", help="다이스를 굴려 1에서 10까지의 결괏값을 출력합니다. 예) !다이스")
async def 다이스(ctx):
    roll = random.randint(1, 10)
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    await ctx.send(f"1D10 결과: **{roll}**\n{timestamp}")

# ====== 명령어: !합계 / !구매 / !사용 ======

def ws(title: str):
    # 같은 문서 내 워크시트 핸들러
    return gclient.open_by_key(SHEET_KEY).worksheet(title)

@bot.command(name="합계", help="체력값 시트의 대선(G2), 사련(I2) 값을 불러옵니다. 예) !합계")
async def 합계(ctx):
    try:
        sh = ws("체력값")
        v_g2 = sh.acell("G2").value  # 대선
        v_i2 = sh.acell("I2").value  # 사련
        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        await ctx.send(
            f"현재 대선의 체력값은 '{v_g2}', 사련의 체력값은 '{v_i2}'입니다.\n{timestamp}"
        )
    except Exception as e:
        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        await ctx.send(f"❌ 조회 실패: {e}\n{timestamp}")

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
    items = [t.strip() for t in s.split(", ") if t.strip()]
    return ", ".join(items)

@bot.command(name="구매")
async def 구매(ctx, 이름: str, *, 물품명: str):
    """[명단!A열 이름]의 F열(물품목록)에 물품을 콤마로 누적"""
    try:
        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        sh = ws("명단")
        row = _find_row_by_name(sh, 이름)
        if not row:
            
            await ctx.send(f"❌ '{이름}' 이름을 A열에서 찾지 못했습니다.\n{timestamp}")
            return

        cur = _normalize_items_str(sh.acell(f"F{row}").value)
        items = cur.split(",") if cur else []
        items.append(물품명.strip())
        new_val = ",".join([t for t in items if t])  # 공백/빈값 제거
        sh.update_acell(f"F{row}", new_val)

        await ctx.send(f"✅ '{이름}'의 물품 목록 업데이트 완료: {new_val if new_val else '(비어 있음)'}\n{timestamp}")
    except Exception as e:
        await ctx.send(f"❌ 구매 처리 실패: {e}\n{timestamp}")

@bot.command(name="사용")
async def 사용(ctx, 이름: str, *, 물품명: str):
    """[명단!A열 이름]의 F열(물품목록)에서 해당 물품 1개 제거 (콤마 정리 포함)"""
    try:
        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        sh = ws("명단")
        row = _find_row_by_name(sh, 이름)
        if not row:
            await ctx.send(f"❌ '{이름}' 이름을 A열에서 찾지 못했습니다.\n{timestamp}")
            return

        cur = _normalize_items_str(sh.acell(f"F{row}").value)
        if not cur:
            await ctx.send(f"⚠️ '{이름}'의 물품 목록이 비어 있습니다.\n{timestamp}")
            return

        items = cur.split(",")
        try:
            items.remove(물품명.strip())  # 동일 명칭 1회분만 제거
        except ValueError:
            await ctx.send(f"⚠️ '{이름}'의 목록에 '{물품명}'이 없습니다.\n{timestamp}")
            return

        new_val = ",".join([t for t in items if t])
        sh.update_acell(f"F{row}", new_val)
        await ctx.send(f"✅ '{이름}'의 '{물품명}' 사용 처리 완료: {new_val if new_val else '(비어 있음)'}\n{timestamp}")
    except Exception as e:
        await ctx.send(f"❌ 사용 처리 실패: {e}\n{timestamp}")

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

@bot.command(name="추가", help="!추가 이름 수치 → 기존 체력값에 수치만큼 더합니다. 예: !추가 홍길동 5")
async def 추가(ctx, 이름: str, 수치: str):
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    
    if not 수치.isdigit():
        await ctx.send("⚠️ 수치는 양의 정수여야 합니다. 예) `!추가 홍길동 5`\n{timestamp}")
        return
    delta = int(수치)

    row, cur_val, new_val = _apply_delta_to_hp(이름, delta)
    if row is None:
        await ctx.send(f"❌ '체력값' 시트 B열에서 '{이름}'을 찾지 못했습니다.\n{timestamp}")
        return

    await ctx.send(f"✅ '{이름}' 체력값 {cur_val} → +{delta} = **{new_val}** (행 {row}, D열)")

@bot.command(name="차감", help="!차감 이름 수치 → 기존 체력값에서 수치만큼 뺍니다. 예: !차감 홍길동 5\n{timestamp}")
async def 차감(ctx, 이름: str, 수치: str):
    timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
    if not 수치.isdigit():
        await ctx.send("⚠️ 수치는 양의 정수여야 합니다. 예) `!차감 홍길동 3`\n{timestamp}")
        return
    delta = -int(수치)  # 무조건 감소

    row, cur_val, new_val = _apply_delta_to_hp(이름, delta)
    if row is None:
        await ctx.send(f"❌ '체력값' 시트 B열에서 '{이름}'을 찾지 못했습니다.\n{timestamp}")
        return

    await ctx.send(f"✅ '{이름}' 체력값 {cur_val} → -{abs(delta)} = **{new_val}** (행 {row}, D열)\n{timestamp}")

# ====== 도움말: 고정 순서/설명으로 보기 좋게 출력 ======

# 기본 help 제거 (중복 방지)
bot.remove_command("help")

# 도움말 표기 고정(오버라이드) 사전
HELP_OVERRIDES = {
    "도움말":  "현재 사용 가능한 명령어 목록을 표시합니다.",
    "시트테스트":    "연결 확인 시트의 A1에 현재 시간을 기록하고 값을 확인합니다. 예) !시트테스트",
    "합계":   "체력값 시트의 대선(G2), 사련(I2) 값을 불러옵니다. 예) !합계",
    "구매":   "명단 시트에서 B열의 이름을 찾아 같은 행 F열 물품목록에 아이템을 추가(콤마 누적)합니다. 예) !구매 홍길동 붕대",
    "사용":   "명단 시트에서 B열의 이름을 찾아 같은 행 F열에서 해당 아이템 1개를 제거합니다. 예) !사용 홍길동 붕대",
    "전체":   "!전체 +수치 / -수치 → 체력값 시트 D6부터 마지막 데이터 행까지 숫자 셀에 수치만큼 일괄 증감합니다. 예) !전체 +5, !전체 -3",
    "추가":   "체력값 시트에서 B열의 이름을 찾아 같은 행 D열(체력값)에 수치만큼 더합니다. 예) !추가 홍길동 5",
    "차감":   "체력값 시트에서 B열의 이름을 찾아 같은 행 D열(체력값)에서 수치만큼 뺍니다. 예) !차감 홍길동 5",
    "접속":   "현재 봇이 정상 작동 중인지 확인합니다.",
    "다이스":    "다이스를 굴려 1에서 10까지의 결괏값을 출력합니다. 예) !다이스",
    "전투":    "전투에 참여하는 플레이어 이름을 입력하여 전투를 진행합니다. 예) !전투 이름1 이름2"
}

# 표기 순서 고정
HELP_ORDER = ["도움말", "시트테스트", "합계", "구매", "사용", "전체", "추가", "차감", "접속", "다이스", "전투"]

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

@bot.command(
    name="전체",
    help="!전체 +수치 / -수치 → 체력값 시트 D6부터 마지막 데이터 행까지 숫자 셀에 수치만큼 일괄 증감합니다. 예) !전체 +5, !전체 -3"
)
async def 전체(ctx, 수치: str):
    s = (수치 or "").strip()
    if not (s.startswith("+") or s.startswith("-")):
        await ctx.send("⚠️ 수치는 + 또는 -로 시작해야 합니다. 예) `!전체 +5` 또는 `!전체 -3`")
        return
    try:
        delta = int(s)
    except ValueError:
        await ctx.send("⚠️ 수치는 정수여야 합니다. 예) `!전체 +5` 또는 `!전체 -3`")
        return

    try:
        sh = ws("체력값")

        # 마지막 행 계산 (D열에서)
        col_d = sh.col_values(4)  # D열 전체 값
        last_row = len(col_d)
        if last_row < 6:
            await ctx.send("⚠️ D6 이후 데이터가 없습니다.")
            return

        rng = f"D6:D{last_row}"
        rows = sh.get(rng)
        new_rows, changed = [], 0

        for r in rows:
            raw = (r[0] if r else "").strip()
            if raw == "":
                new_rows.append([raw])  # 빈칸 유지
                continue
            try:
                cur = int(raw)
                new_rows.append([cur + delta])
                changed += 1
            except ValueError:
                new_rows.append([raw])  # 숫자 아님 → 유지

        # 시트 업데이트
        sh.update(rng, new_rows, value_input_option="USER_ENTERED")

        # 최종 수정자 닉네임 기록 (D2)
        sh.update_acell("D2", ctx.author.display_name)

        # 결과 메시지 + 타임스탬프
        sign = "+" if delta >= 0 else ""
        timestamp = now_kst_str()
        await ctx.send(
            f"✅ 전체 체력값에 적용 완료했습니다.\n{timestamp}"
        )

    except Exception as e:
        await ctx.send(f"❌ 일괄 증감 실패: {e}")


# ✅ 전투 기능 시작
active_battles = {}

def get_hp_bar(current, max_hp=50, bar_length=10):
    filled_length = int(bar_length * max(current, 0) / max_hp)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)
    return f"[{bar}] {max(current, 0)}/{max_hp}"

class BattleAttackButton(Button):
    def __init__(self, channel_id):
        super().__init__(label="공격", style=discord.ButtonStyle.danger)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        data = active_battles[self.channel_id]
        if data["단계"] != "공격":
            await interaction.response.send_message("지금은 공격할 수 없습니다.", ephemeral=False)
            return

        attacker = data["턴"]
        defender = data["상대"]

        # 공격 주사위 4개 (1D6 × 4)
        rolls = [random.randint(1, 6) for _ in range(4)]
        total_attack = sum(rolls)
        dice_text = " + ".join(str(r) for r in rolls)

        data["최근공격"] = total_attack
        data["공격자"] = attacker
        data["방어자"] = defender
        data["단계"] = "방어"

        hp1 = get_hp_bar(data["체력"][data["플레이어1"]])
        hp2 = get_hp_bar(data["체력"][data["플레이어2"]])
        timestamp = datetime.now(KST).strftime("%Y/%m/%d %H:%M:%S")

        msg = (
            f"{attacker}의 공격 차례입니다.\n"
            f"공격 {dice_text} → 총 {total_attack}\n\n"
            f"{defender}의 방어 차례입니다.\n\n"
            f"{data['플레이어1']}: {hp1}\n"
            f"{data['플레이어2']}: {hp2}\n"
            f"{timestamp}"
        )
        await interaction.channel.send(msg, view=BattleView(self.channel_id))
        await interaction.response.defer()

class BattleDefendButton(Button):
    def __init__(self, channel_id):
        super().__init__(label="방어", style=discord.ButtonStyle.primary)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        data = active_battles[self.channel_id]
        if data["단계"] != "방어":
            await interaction.response.send_message("지금은 방어할 수 없습니다.", ephemeral=False)
            return

        defender = data["방어자"]
        attacker = data["공격자"]
        last_dmg = data.get("최근공격", 0)

        # 방어 주사위 2개 (1D6 × 2)
        rolls = [random.randint(1, 6) for _ in range(2)]
        defense = sum(rolls)
        net_dmg = max(0, last_dmg - defense)
        data["체력"][defender] -= net_dmg

        dice_text = " + ".join(str(r) for r in rolls)

        hp1_val = data["체력"][data["플레이어1"]]
        hp2_val = data["체력"][data["플레이어2"]]
        hp1 = get_hp_bar(hp1_val)
        hp2 = get_hp_bar(hp2_val)
        timestamp = datetime.now(KST).strftime("%Y/%m/%d %H:%M:%S")

        # 방어 후 체력 0 이하인 경우
        if data["체력"][defender] <= 0:
            if not data.get("최종반격", False) and defender == data["후공"]:
                # 후공만 최종 반격 1회 부여
                data["최종반격"] = True
                data["턴"], data["상대"] = defender, attacker
                data["단계"] = "공격"

                msg = (
                    f"{defender}의 방어 차례입니다.\n"
                    f"방어 {dice_text} - 누적 데미지 {last_dmg}\n"
                    f"{defender}의 체력이 0이 되었지만, 마지막 반격 기회를 얻습니다.\n\n"
                    f"{defender}의 마지막 공격 차례입니다.\n\n"
                    f"{data['플레이어1']}: {hp1}\n"
                    f"{data['플레이어2']}: {hp2}\n"
                    f"{timestamp}"
                )
                await interaction.channel.send(msg, view=BattleView(self.channel_id))
                await interaction.response.defer()
                return
            else:
                # 반격 없음 또는 (선공 사망 등) → 즉시 종료 (공격자 승)
                msg = (
                    f"{defender}의 방어 차례입니다.\n"
                    f"방어 {dice_text} - 누적 데미지 {last_dmg}\n"
                    f"{defender}의 체력이 0이 되었습니다.\n\n"
                    f"전투가 종료되었습니다. {attacker}의 승리입니다.\n"
                    f"{data['플레이어1']}: {hp1}\n"
                    f"{data['플레이어2']}: {hp2}\n"
                    f"{timestamp}"
                )
                await interaction.channel.send(msg)
                await interaction.response.defer()
                del active_battles[self.channel_id]
                return

        result_line = (
            f"방어 {dice_text} - 누적 데미지 {last_dmg} → 총 {net_dmg}"
            if net_dmg > 0 else
            f"방어 {dice_text} - 누적 데미지 {last_dmg} → 완전 방어에 성공합니다."
        )

        # 최종 반격이 진행 중이었다면(= 이번 방어가 선공의 방어) → 여기서 체력 비교로 종료
        if data.get("최종반격", False):
            # 강제 종료 규칙과 동일한 비교식 사용
            if hp1_val <= 0 and hp2_val > 0:
                winner = data["플레이어2"]
            elif hp2_val <= 0 and hp1_val > 0:
                winner = data["플레이어1"]
            elif hp1_val <= 0 and hp2_val <= 0:
                # 둘 다 0 이하면 0에 가까운 쪽 승리 (값이 더 큰 쪽)
                if hp1_val > hp2_val:
                    winner = data["플레이어1"]
                elif hp2_val > hp1_val:
                    winner = data["플레이어2"]
                else:
                    winner = None
            else:
                # 둘 다 양수면 높은 체력 승
                if hp1_val > hp2_val:
                    winner = data["플레이어1"]
                elif hp2_val > hp1_val:
                    winner = data["플레이어2"]
                else:
                    winner = None

            result = f"전투가 종료되었습니다. {winner}의 승리입니다." if winner else "전투가 종료되었습니다. 무승부입니다."

            msg = (
                f"{defender}의 방어 차례입니다.\n"
                f"{result_line}\n\n"
                f"{result}\n"
                f"{data['플레이어1']}: {hp1}\n"
                f"{data['플레이어2']}: {hp2}\n"
                f"{timestamp}"
            )
            await interaction.channel.send(msg)
            await interaction.response.defer()
            del active_battles[self.channel_id]
            return

        # 일반 턴 전환
        data["턴"], data["상대"] = defender, attacker
        data["단계"] = "공격"

        msg = (
            f"{defender}의 방어 차례입니다.\n"
            f"{result_line}\n\n"
            f"{defender}의 공격 차례입니다.\n\n"
            f"{data['플레이어1']}: {hp1}\n"
            f"{data['플레이어2']}: {hp2}\n"
            f"{timestamp}"
        )
        await interaction.channel.send(msg, view=BattleView(self.channel_id))
        await interaction.response.defer()

class BattleEndButton(Button):
    def __init__(self, channel_id):
        super().__init__(label="종료", style=discord.ButtonStyle.secondary)
        self.channel_id = channel_id

    async def callback(self, interaction: discord.Interaction):
        data = active_battles.get(self.channel_id)
        if not data:
            await interaction.response.send_message("종료할 전투가 없습니다.", ephemeral=False)
            return

        hp1_val = data["체력"][data["플레이어1"]]
        hp2_val = data["체력"][data["플레이어2"]]
        hp1_bar = get_hp_bar(hp1_val)
        hp2_bar = get_hp_bar(hp2_val)
        timestamp = datetime.now(KST).strftime("%Y/%m/%d %H:%M:%S")

        # 강제 종료 승패 규칙
        if hp1_val <= 0 and hp2_val > 0:
            result = f"{data['플레이어2']}의 승리입니다."
        elif hp2_val <= 0 and hp1_val > 0:
            result = f"{data['플레이어1']}의 승리입니다."
        elif hp1_val <= 0 and hp2_val <= 0:
            # 둘 다 0 이하 → 0에 가까운 쪽 승리 (값이 더 큰 쪽)
            if hp1_val > hp2_val:
                result = f"{data['플레이어1']}의 승리입니다."
            elif hp2_val > hp1_val:
                result = f"{data['플레이어2']}의 승리입니다."
            else:
                result = "무승부입니다."
        else:
            # 둘 다 양수 → 높은 체력 승
            if hp1_val > hp2_val:
                result = f"{data['플레이어1']}의 승리입니다."
            elif hp2_val > hp1_val:
                result = f"{data['플레이어2']}의 승리입니다."
            else:
                result = "무승부입니다."

        msg = (
            f"전투가 강제로 종료되었습니다.\n\n"
            f"{data['플레이어1']}: {hp1_bar}\n"
            f"{data['플레이어2']}: {hp2_bar}\n\n"
            f"{result}\n"
            f"{timestamp}"
        )
        await interaction.channel.send(msg)
        await interaction.response.defer()
        del active_battles[self.channel_id]

class BattleView(View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.channel_id = channel_id
        self.add_item(BattleAttackButton(channel_id))
        self.add_item(BattleDefendButton(channel_id))
        self.add_item(BattleEndButton(channel_id))

@bot.command()
async def 전투(ctx, 플레이어1: str, 플레이어2: str):
    channel_id = ctx.channel.id
    if channel_id in active_battles:
        await ctx.send("이미 이 채널에서 전투가 진행 중입니다.")
        return

    first = random.choice([플레이어1, 플레이어2])
    second = 플레이어2 if first == 플레이어1 else 플레이어1

    active_battles[channel_id] = {
        "플레이어1": 플레이어1,
        "플레이어2": 플레이어2,
        "체력": {플레이어1: 50, 플레이어2: 50},
        "단계": "공격",
        "턴": first,
        "상대": second,
        "최종반격": False,
        "선공": first,
        "후공": second
    }

    await ctx.send(
        f"전투를 준비합니다.\n{플레이어1} vs {플레이어2}\n선공: {first}\n\n{first}, 공격을 시작하세요.",
        view=BattleView(channel_id)
    )
# ✅ 전투 기능 끝

bot.run(DISCORD_TOKEN)
