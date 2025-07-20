import json
import os
import re
from datetime import datetime

import cv2
from pixivpy3 import AppPixivAPI

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Nodes
from astrbot.core.platform import MessageType
from astrbot.core.star.filter.permission import PermissionType
from data.plugins.astrbot_plugins_pixiv.pixiv_auth import refresh

global access_token, refresh_token, last_refresh_time, white_list_group, white_list_user
access_token = ""
refresh_token = ""
white_list_path = "./data/plugins/astrbot_plugins_pixiv/white_list.json"


def get_access_token():
    global access_token, refresh_token, white_list_group, white_list_user
    # 读取token数据
    with open('./data/plugins/astrbot_plugins_pixiv/tokens.json', 'r') as json_file:
        tokens = json.load(json_file)

    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]

    with open(white_list_path, 'r') as file:
        data = json.load(file)
        white_list_group = data["groupIDs"]
        white_list_user = data["userIDs"]


def save_access_token():
    global access_token, refresh_token
    # 保存token数据
    tokens = {
        "access_token": access_token,
        "refresh_token": refresh_token
    }

    # 存储到 JSON 文件
    with open('./data/plugins/astrbot_plugins_pixiv/tokens.json', 'w') as json_file:
        json.dump(tokens, json_file, indent=4)

    print("Tokens have been saved to 'tokens.json'.")


def get_id_from_text(str):
    num_list = re.findall(r'\d+', str)
    result_number = ""
    for i in range(len(num_list)):
        result_number += num_list[i]
    return result_number


@register("pixiv", "orchidsziyou", "一个简单的 pixiv 插件", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        global access_token, refresh_token, last_refresh_time
        get_access_token()
        access_token, refresh_token = refresh(refresh_token)
        save_access_token()
        last_refresh_time = int(datetime.now().timestamp())

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command_group("p")
    async def pixiv_group(self, event: AstrMessageEvent) -> MessageEventResult:
        """pixiv 相关命令"""

    @pixiv_group.command("d")
    async def pixiv_download(self, event: AstrMessageEvent, id: str) -> MessageEventResult:
        """下载插画"""
        global access_token, refresh_token, last_refresh_time
        Current_Picture_time = int(datetime.now().timestamp())
        time_diff_in_seconds = Current_Picture_time - last_refresh_time
        if time_diff_in_seconds > 3000:
            access_token, refresh_token = refresh(refresh_token)
            save_access_token()
            last_refresh_time = Current_Picture_time
        api = AppPixivAPI()

        api.set_auth(access_token, refresh_token)

        R18Tag = False

        if len(id) >= 15:
            id = str(get_id_from_text(id))
            print(id)

        try:
            json_result = api.illust_detail(id)
            illust = json_result.illust
            title = illust.title
            taglist = illust.tags
            # print(illust)
            author = illust.user.name

            tagstr = ""
            for tag in taglist:
                if tag.name == 'R-18' or tag.name == 'R18':
                    R18Tag = True
                    # print("R18Tag")
                tagstr += tag.name + " "
            if os.path.exists("./data/plugins/astrbot_plugins_pixiv/test.jpg"):
                os.remove("./data/plugins/astrbot_plugins_pixiv/test.jpg")
            api.download(illust.image_urls.large, fname="./data/plugins/astrbot_plugins_pixiv/test.jpg")
        except Exception as e:
            print(e)
            yield event.plain_result("下载失败")
            return

        # mark标记是否发送图片
        mark = True
        if event.get_message_type() == MessageType.GROUP_MESSAGE:
            if event.get_group_id() not in white_list_group:
                mark = False
        else:
            if event.get_sender_id() not in white_list_user:
                mark = False

        if R18Tag:
            # 打开图片
            file_path = "./data/plugins/astrbot_plugins_pixiv/test.jpg"
            # img = cv2.imread(file_path)
            # # 插入白图防止被gank
            # rotated_img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            # # 覆盖原图片，直接使用原文件路径
            # cv2.imwrite(file_path, rotated_img)

            from PIL import Image as ProcessImage

            original_image = ProcessImage.open(file_path)
            # 获取原始图片的宽度和高度
            width, height = original_image.size
            # 创建一张新的空白图片，大小为原图的宽度和五倍高度
            new_image = ProcessImage.new('RGB', (width, height * 3), color=(255, 255, 255))
            # 将原图粘贴到新图片的下半部分
            new_image.paste(original_image, (0, height * 2))
            # 保存最终结果
            new_image.save(file_path)

        botid = event.get_self_id()
        from astrbot.api.message_components import Node, Plain, Image
        node = Node(
            uin=botid,
            name="仙人",
            content=
            [
                Plain("Pid:" + id + '\n'),
                Plain("标题:" + title + '\n'),
                Plain("作者:" + author + '\n'),
                Plain("Tag:" + tagstr + '\n'),
                Plain("若有多张图，只会下载第一张\n")
            ]
        )
        picture_node = Node(
            uin=botid,
            name="仙人",
            content=
            [
                Image.fromFileSystem("./data/plugins/astrbot_plugins_pixiv/test.jpg")
            ]
        )
        resNode = Nodes(
            nodes=[node, picture_node]
        )

        try:
            if mark:
                yield event.chain_result([resNode])
            else:
                yield event.chain_result([node])
        except:
            yield event.plain_result("发送失败")

    @filter.permission_type(PermissionType.ADMIN)
    @pixiv_group.command("promote")
    async def pixiv_promote(self, event: AstrMessageEvent, type: str, name: str) -> MessageEventResult:
        """设为管理员"""
        global white_list_group, white_list_user
        if type == "group":
            if name in white_list_group:
                yield event.plain_result("该群已经在白名单中")
                return
            else:
                white_list_group.append(name)
                with open(white_list_path, 'w') as file:
                    data = {
                        "groupIDs": white_list_group,
                        "userIDs": white_list_user,
                    }
                    json.dump(data, file)
                yield event.plain_result("该群已成功加入白名单")
        if type == "user":
            if name in white_list_user:
                yield event.plain_result("该用户已经在白名单中")
                return
            else:
                white_list_user.append(name)
                with open(white_list_path, 'w') as file:
                    data = {
                        "groupIDs": white_list_group,
                        "userIDs": white_list_user,
                    }
                    json.dump(data, file)
                yield event.plain_result("该用户已成功加入白名单")

    @filter.permission_type(PermissionType.ADMIN)
    @pixiv_group.command("demote")
    async def jm_demote_command(self, event: AstrMessageEvent, type: str, name: str):
        ''' 这是一个 撤销某人的权限 的指令'''
        if type == "group":
            if name in white_list_group:
                white_list_group.remove(name)
                with open(white_list_path, 'w') as file:
                    data = {
                        "groupIDs": white_list_group,
                        "userIDs": white_list_user,
                    }
                    json.dump(data, file)
                yield event.plain_result("该群已成功撤销白名单")
            else:
                yield event.plain_result("该群不在白名单中")
        if type == "user":
            if name in white_list_user:
                white_list_user.remove(name)
                with open(white_list_path, 'w') as file:
                    data = {
                        "groupIDs": white_list_group,
                        "userIDs": white_list_user,
                    }
                    json.dump(data, file)
                yield event.plain_result("该用户已成功撤销白名单")
            else:
                yield event.plain_result("该用户不在白名单中")
