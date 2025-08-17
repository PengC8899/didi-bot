from aiogram.fsm.state import State, StatesGroup


class OrderCreationFlow(StatesGroup):
    asking_content = State()  # 询问订单详情
    asking_amount = State()   # 询问金额