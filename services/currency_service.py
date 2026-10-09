from database.currency import get_balance, add_balance, subtract_balance
from config.constants import CURRENCY_NAME

# === 经验兑换为遗迹晶核 ===
def convert_exp_to_currency(user, xp_amount):
    if xp_amount < 100:
        raise ValueError("至少需要100经验才能兑换遗迹晶核")

    crystal_amount = round(xp_amount / 100, 2)  # 小数点精度
    user.text_xp -= xp_amount
    add_balance(user.user_id, crystal_amount)
    return crystal_amount

# === 玩家之间转账遗迹晶核 ===
def transfer_currency(sender_id, receiver_id, amount):
    if amount <= 0:
        raise ValueError("转账金额必须大于 0")

    fee = round(max(0.1, amount * 0.1), 2)  # 最低 0.1 晶核，保留两位小数
    total_deduction = amount + fee

    sender_balance = get_balance(sender_id)
    if sender_balance < total_deduction:
        raise ValueError(f"余额不足，无法支付 {amount} {CURRENCY_NAME} 和 {fee} {CURRENCY_NAME} 的手续费")

    subtract_balance(sender_id, total_deduction)
    add_balance(receiver_id, amount)

    return amount, fee
