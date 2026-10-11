import codecs
from pathlib import Path

ENCODINGS = [
    "shift-jis",
    "shift-jis-2004",
    "gb2312",
    "utf-8",
    "gb18030",
    "shift-jisx0213",
]

# BOF:TT 活动里有几个作品的文件编码判定失败，按作品编号手动指定优先编码。
# 该表只对 BOF:TT 有效：编号在其它活动会撞车（例如 134、191 在任何活动都存在），
# 因此通用路径不再自动套用，需要时由调用方显式传入
# （见 bms.get_dir_bms_list 的 id_encoding_table 参数）。
BOFTT_ID_SPECIFIC_ENCODING_TABLE: dict[str, str] = {
    "134": "utf-8",
    "191": "gbk",
    "435": "gbk",
    "439": "gbk",
    # 159 bms文件本身有编码问题
}


class PriorityDecoder:
    def __init__(self, encoding_priority: list[str], final: str = "utf-8") -> None:
        """
        初始化优先级解码器

        Args:
            encoding_priority (List[str]): 编码优先级列表，靠前的编码优先级更高
        """
        # 拷贝一份，避免调用方列表被就地修改
        self.encoding_priority = list(encoding_priority)
        # 预加载所有编码的编解码器
        self.codecs = {enc: codecs.lookup(enc) for enc in encoding_priority}
        # TODO: Impl Final
        self.final = final

    def _decode_byte_sequence(self, byte_data: bytes, start: int = 0) -> tuple[str | None, int]:
        """
        尝试用所有编码解码字节序列，返回第一个成功的解码结果和消耗的字节数

        Args:
            byte_data (bytes): 要解码的字节数据
            start (int): 开始解码的位置

        Returns:
            Tuple[Optional[str], int]: (解码后的字符, 消耗的字节数)
        """
        for enc in self.encoding_priority:
            codec = self.codecs[enc]
            try:
                # 尝试解码1-4个字节（日文编码通常不超过4字节）
                for length in range(1, min(5, len(byte_data) - start + 1)):
                    try:
                        char = codec.decode(byte_data[start : start + length])[0]
                    except UnicodeDecodeError:
                        continue
                    return char, length
            except (UnicodeDecodeError, LookupError):
                continue
        return None, 1  # 所有编码都失败，默认消耗1个字节

    def decode(self, byte_data: bytes, errors: str = "strict") -> str:
        """
        按照编码优先级逐字符解码字节数据

        Args:
            byte_data (bytes): 要解码的字节数据
            errors (str): 错误处理方式 ('strict', 'ignore', 'replace')

        Returns:
            str: 解码后的字符串
        """
        result = []
        position = 0
        total_length = len(byte_data)

        while position < total_length:
            char, consumed = self._decode_byte_sequence(byte_data, position)

            if char is not None:
                result.append(char)
            # 处理解码失败的字节
            elif errors == "strict":
                msg = f"无法用任何编码解码字节: {byte_data[position : position + 1]!r}"
                codec_error_kind = "priority_decode"
                raise UnicodeDecodeError(
                    codec_error_kind,
                    byte_data,
                    position,
                    position + 1,
                    msg,
                )
            elif errors == "replace":
                result.append("�")
                # ignore模式不做任何操作

            position += consumed

        return "".join(result)


def read_file_with_priority(file_path: Path, encoding_priority: list[str], errors: str = "strict") -> str | None:
    """
    读取文件并按照编码优先级逐字符解码

    Args:
        file_path (Path): 文件路径
        encoding_priority (List[str]): 编码优先级列表
        errors (str): 错误处理方式

    Returns:
        Optional[str]: 解码后的内容，失败返回None
    """
    try:
        with file_path.open("rb") as f:
            byte_data = f.read()
            decoder = PriorityDecoder(encoding_priority)
            return decoder.decode(byte_data, errors)
    except (OSError, UnicodeDecodeError) as e:
        print(f"Error: {e}")
        return None


def _build_encoding_priority(encoding: str | None = None) -> list[str]:
    """候选编码顺序：显式指定的排在先，其次 UTF-8，最后是历史优先级；去重保序。"""
    priority = [encoding] if encoding else []
    priority.extend(["utf-8", *ENCODINGS])
    return list(dict.fromkeys(priority))


def get_bms_file_str(file_bytes: bytes, encoding: str | None = None) -> str:
    """解码 BMS 文本。

    先按候选编码整体严格解码（UTF-8 优先），全部失败才退回逐字符解码，
    用于处理混合编码的文件。不能用逐字符优先的方式读整份文件：
    UTF-8 文本会被 Shift-JIS 逐字拼成乱码。
    """
    priority = _build_encoding_priority(encoding)
    for enc in priority:
        try:
            return file_bytes.decode(enc, errors="strict")
        except (UnicodeDecodeError, LookupError):
            continue
    decoder = PriorityDecoder(priority)
    try:
        return decoder.decode(file_bytes, errors="strict")
    except UnicodeDecodeError:
        return file_bytes.decode("utf-8", errors="ignore")


def get_bmson_file_str(file_bytes: bytes, encoding: str | None = None) -> str:
    """BMSON 规范固定 UTF-8；只在 UTF-8 解码失败时才回退到优先级解码器。"""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return get_bms_file_str(file_bytes, encoding)


# 解码器测试
if __name__ == "__main__":
    # 测试数据
    # "こんにちは" + "①" (shift-jis不支持的字符)
    test_bytes = b"\x82\xb1\x82\xf1\x82\xc9\x82\xbf\x82\xcd\x87\x40"

    # 编码优先级
    # encodings = ["shift_jis", "shift_jis_2004", "euc-jp"]
    encodings = ["shift_jis", "shift_jis_2004", "euc-jp"]

    # 创建解码器
    decoder = PriorityDecoder(encodings)

    # 测试解码
    print("== strict模式 ==")
    try:
        result = decoder.decode(test_bytes)
        print(f"解码结果: {result}")
    except UnicodeDecodeError as e:
        print(f"解码失败: {e}")

    print("\n== replace模式 ==")
    result = decoder.decode(test_bytes, errors="replace")
    print(f"解码结果: {result}")  # 会显示"こんにちは�"

    print("\n== ignore模式 ==")
    result = decoder.decode(test_bytes, errors="ignore")
    print(f"解码结果: {result}")  # 会显示"こんにちは"
