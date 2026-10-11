from bms.parse import BMSInfo


def get_valid_fs_name(ori_name: str) -> str:
    """
    Signs:
    ：＼／＊？＂＜＞｜
    """
    return (
        ori_name.replace(":", "：")
        .replace("\\", "＼")
        .replace("/", "／")
        .replace("*", "＊")
        .replace("?", "？")
        .replace("!", "！")
        .replace('"', "＂")
        .replace("<", "＜")
        .replace(">", "＞")
        .replace("|", "｜")
    )


def get_work_folder_name(work_id: str, info: BMSInfo) -> str:
    return f"{work_id}. {get_valid_fs_name(info.title)} [{get_valid_fs_name(info.artist)}]"
