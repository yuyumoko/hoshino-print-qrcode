import asyncio
from io import BytesIO
from pathlib import Path

import pyzbar.pyzbar as pyzbar
from hoshino import Message, MessageSegment, Service, aiorequests, get_bot, priv
from PIL import Image
from pyzbar import pyzbar

sv_help = """
发二维码的能不能照顾一下PC端
""".strip()

sv = Service(
    name="pqrcode",  # 功能名
    use_priv=priv.NORMAL,  # 使用权限
    manage_priv=priv.ADMIN,  # 管理权限
    visible=True,  # 可见性
    enable_on_default=True,  # 默认启用
    bundle="",  # 分组归类
    help_=sv_help,  # 帮助说明
)

bot = get_bot()
cache = {"coolq_directory": "", "self_info": None}


def decode(file):
    if isinstance(file, bytes):
        barcodes = pyzbar.decode(Image.open(BytesIO(file)))
        for barcode in barcodes:
            yield barcode.data.decode("utf-8")
    else:
        with file.open("rb") as f:
            barcodes = pyzbar.decode(Image.open(f))
            for barcode in barcodes:
                yield barcode.data.decode("utf-8")


async def aio_image(url, md5):
    # print(f"正在获取 {md5}")
    req = await aiorequests.get(url)
    file = await req.content
    if file:
        return file
    else:
        base_url = "http://gchat.qpic.cn/gchatpic_new/0/0-0-%s/0?term=2"
        req = await aiorequests.get(base_url % md5.upper())
        file = await req.content
        return file


async def handle_forward_msg(forward_list):
    imgs = []
    for f_msg in forward_list:
        if isinstance(f_msg["content"], list):
            imgs += await handle_forward_msg(f_msg["content"])
        else:
            imgs += await process_img(Message(f_msg["content"]))
    return imgs


async def process_img(message):
    imgs = []
    for msg in message:
        if msg.type == "forward":
            forward_msg = await bot.get_forward_msg(message_id=msg.data["id"])
            imgs += await handle_forward_msg(forward_msg["messages"])
        if msg.type == "image":
            imgs.append(msg.data)
    return imgs


async def read_img(message: Message):
    aio_cor = []
    imgs = await process_img(message)
    for img_data in imgs:
        cq_img_info = await bot.get_image(file=img_data["file"])
        file = cache["coolq_directory"] / cq_img_info["file"]
        if file.suffix == ".image":
            aio_cor.append(aio_image(img_data["url"], cq_img_info["filename"]))
        else:
            for data in decode(file):
                yield data

    if aio_cor:
        for raw in await asyncio.gather(*aio_cor):
            for data in decode(raw):
                yield data


def add_forward_msg(msg):
    return [
        {
            "type": "node",
            "data": {
                "name": cache["self_info"]["nickname"],
                "uin": cache["self_info"]["user_id"],
                "content": [MessageSegment.text(f"{msg}")],
            },
        }
    ]


@sv.on_message("group")
async def on_input_chara_name(bot, ev):
    forward_msg_list = []

    if not cache["coolq_directory"]:
        cq_info = await bot.get_version_info()
        cache["coolq_directory"] = Path(cq_info["coolq_directory"])

    if not cache["self_info"]:
        self_info = await bot.get_login_info()
        cache["self_info"] = self_info

    async for data in read_img(ev.message):
        forward_msg_list += add_forward_msg(data)

    if forward_msg_list:
        try:
            await bot.send_group_forward_msg(
                group_id=ev["group_id"], messages=forward_msg_list
            )
        except Exception as e:
            await bot.send(
                ev, [x["data"]["content"][0] for x in forward_msg_list], at_sender=True
            )
