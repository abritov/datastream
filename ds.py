import datetime as dt
from binascii import hexlify
from struct import unpack, pack
import types

BYTE = 1
INT16 = 2
UINT16 = 3
ASTRING = 4
WSTRING = 5
CONTAINER = 6
TIME = 7
BYTE_ARRAY = 8
UINT32 = 9
INT32 = 10
FLOAT32 = 11
BOOL = 12


class Type:
    def __init__(self, typeid, struct=None, length=None, int32=False):
        self.__type = typeid
        self.__length = length  # if length is None, reads from ds(cuint)
        self.__struct = struct
        self.__int32 = int32
        if typeid == CONTAINER and struct is None:
            raise Exception("CONTAINER struct not defined")

    def __eq__(self, _type):
        return self.__type == _type

    @property
    def length(self):
        return self.__length

    @property
    def struct(self):
        return self.__struct

    @property
    def typeid(self):
        return self.__type

    @property
    def int32(self):
        return self.__int32


class DataStream:
    def __init__(self, buffer=bytearray(), swaped=False):
        if isinstance(buffer, bytearray):
            self.__buffer = buffer
        elif isinstance(buffer, str):
            self.__buffer = bytearray.fromhex(buffer)
        elif isinstance(buffer, list):
            self.__buffer = bytearray(buffer)
        else:
            raise Exception("Wrong data passed to DataStream")
        self.swaped = swaped
        self.__last_swap = self.swaped
        self.__count = len(self.__buffer)
        self.__pos = 0

    def __str__(self):
        return "{}".format(hexlify(self.__buffer[:16]))

    @property
    def count(self):
        return self.__count

    @property
    def buffer(self):
        "Stores a copy of internal buffer"
        return bytearray(self.__buffer[self.__pos:self.__count])

    @property
    def pos(self):
        return self.__pos

    @pos.setter
    def pos(self, value):
        if value >= self.__count:
            raise Exception('value >= count')
        self.__pos = value

    def __round_up(self, length):
        i = 16
        while length > i:
            i <<= 1
        return i

    def reserve(self, _count):
        size = self.__round_up(_count)
        if len(self.__buffer) == 0:
            self.__buffer = bytearray([0 for _ in range(size)])
        if _count > len(self.__buffer):
            self.__buffer.extend([0 for _ in range(size)])

    def can_read(self, length=1):
        return self.__pos + length <= self.__count

    def skip(self, count):
        if self.__pos + self.__count > count:
            raise Exception("pos + count > Count")
        self.__pos += count

    def flush(self):
        if self.__pos == 0:
            return
        length = self.__count - self.__pos
        self.position = 0
        self.__count = length

    def reset(self):
        self.__pos = 0

    def clear(self):
        self.__pos = 0
        self.__count = 0

    def save_swap(self):
        self.__last_swap = self.swaped

    def load_swap(self):
        self.swaped = self.__last_swap

    def buffer_copy(self):
        return self.__buffer[:]

    def write_bytes(self, data, swap=False, data_offset=None, length=None):
        if data_offset is not None:
            data = data[data_offset:]
        if length is None:
            length = len(data)
        if swap:
            data = data[::-1]
        self.reserve(self.__count + length)
        for i in range(length):
            self.__buffer[self.__count] = data[i]
            self.__count += 1

    def read_bytes(self, count, swap=False):
        if self.__pos + count > self.__count:
            raise Exception('pos + len > count')
        ret = self.__buffer[self.__pos:self.__pos + count]
        self.__pos += count
        return ret[::-1] if swap else ret

    def read_byte(self):
        if self.__pos >= self.__count:
            raise Exception('pos >= count')
        self.__pos += 1
        return self.__buffer[self.__pos-1]

    def read_bool(self):
        return True if self.read_byte() == 1 else False

    def read_word(self, swap=None, signed=False):
        if swap is None:
            swap = self.swaped
        order = 'big' if swap else 'little'
        return int.from_bytes(self.read_bytes(2),
                              byteorder=order, signed=signed)

    def read_dword(self, swap=None, signed=False):
        if swap is None:
            swap = self.swaped
        order = 'big' if swap else 'little'
        return int.from_bytes(self.read_bytes(4),
                              byteorder=order, signed=signed)

    def read_float32(self, swap=None, signed=False):
        if swap is None:
            swap = self.swaped
        fmt = '>f' if swap else '<f'
        return unpack(fmt, self.read_bytes(4))[0]

    def read_time(self, swap=None):
        timestamp = self.read_dword()
        if timestamp == 0:
            return 0
        return dt.datetime.fromtimestamp(timestamp)

    def try_read_cuint32(self):
        "Returns tuple (cuint32, status)"
        if not self.can_read():
            return None, False
        switch = self.__buffer[self.pos] & 0xE0
        if switch == 0xE0:
            if not self.can_read(5):
                return None, False
            self.read_byte()
            return self.read_dword(True), True
        elif switch == 0xC0:
            if not self.can_read(4):
                return None, False
            return self.read_dword(True) & 0x3fffffff, True
        elif switch == 0x80 or switch == 0xA0:
            if not self.can_read(2):
                return None, False
            return self.read_word(True) & 0x3fff, True
        else:
            return self.read_byte(), True

    def read_cuint32(self):
        if not self.can_read():
            raise Exception("!can_read()")
        switch = self.__buffer[self.pos] & 0xE0
        if switch == 0xE0:
            self.read_byte()
            return self.read_dword(True)
        elif switch == 0xC0:
            return self.read_dword(True) & 0x3fffffff
        elif switch == 0x80 or switch == 0xA0:
            return self.read_word(True) & 0x3fff
        else:
            return self.read_byte()

    def read_data(self, int32=False):
        length = self.read_dword() if int32 else self.read_cuint32()
        return self.read_bytes(length)

    def read_ds(self):
        return DataStream(self.read_data(False))

    def read_string(self, wchar=True, int32=False):
        encoding = 'ascii' if not wchar else 'utf-16'
        return self.read_data(int32=int32).decode(encoding)

    def read_container(self, param):
        if param.length is None:
            length = self.read_cuint32()
        else:
            length = param.length
        container = [param.struct() for _ in range(length)]
        for item in container:
            if not hasattr(item, '_fields_'):
                "if class have not fields try to use his own method"
                item._deserialize(self)
            else:
                self.read_class(item)
        return container

    def read_class(self, _class):
        if not hasattr(_class, '_fields_'):
            raise Exception("%s does not support class reading" % _class)
        name, param = None, None
        try:
            for name, param in _class.__class__._fields_:
                setattr(_class, name, self.read(param))
        except Exception as e:
            raise Exception('class_read %s error: %s' % (name, e))

    def _get_param_length(self, param):
        if param.length is None:
            return self.read_dword() if param.int32 else self.read_cuint32()
        else:
            return param.length

    def _write_param_length(self, x, param):
        length = len(x) if param.length is None else param.length
        self.write_dword(length) if param.int32 else self.write_cuint32(length)

    def read(self, param):
        if param == BYTE:
            return self.read_byte()
        elif param == BYTE_ARRAY:
            length = self._get_param_length(param)
            return self.read_bytes(length)
        elif param == UINT32:
            return self.read_dword(signed=False)
        elif param == INT32:
            return self.read_dword(signed=True)
        elif param == UINT16:
            return self.read_word(signed=False)
        elif param == INT16:
            return self.read_word(signed=True)
        elif param == WSTRING:
            return self.read_string(wchar=True)
        elif param == ASTRING:
            return self.read_string(wchar=False)
        elif param == FLOAT32:
            return self.read_float32()
        elif param == TIME:
            return self.read_time()
        elif param == BOOL:
            return self.read_bool()
        elif param == CONTAINER:
            return self.read_container(param)
        else:
            raise Exception('read type % not implemented' % param.typeid)

    def write_cuint32(self, x):
        if x < 0x80:
            self.write_byte(x)
        elif x < 0x4000:
            self.write_word((x | 0x8000), swap=True)
        elif x < 0x20000000:
            self.write_dword((x | 0xC0000000), swap=True)
        else:
            self.write_byte(0xE0)
            self.write_dword(x, True)

    def write_byte(self, x):
        self.reserve(self.__count + 1)
        self.__buffer[self.__count] = x
        self.__count += 1

    def write_dword(self, x, swap=None, signed=False):
        if swap is None:
            swap = self.swaped
        order = 'big' if swap else 'little'
        self.write_bytes(x.to_bytes(4, order, signed=signed))

    def write_word(self, x, swap=None, signed=False):
        if swap is None:
            swap = self.swaped
        order = 'big' if swap else 'little'
        self.write_bytes(x.to_bytes(2, order, signed=signed))

    def write_float32(self, x, swap=None):
        if swap is None:
            swap = self.swaped
        fmt = '>f' if swap else '<f'
        self.write_bytes(pack(fmt, x))

    def write_bool(self, x):
        self.write_byte(1 if x else 0)

    def write_string(self, x, wchar=True, int32=False):
        encoding = 'ascii' if not wchar else 'utf-16'
        str_byte = bytes(x, encoding)
        if wchar:
            str_byte = str_byte[2:]
        if int32:
            self.write_dword(len(str_byte))
        else:
            self.write_cuint32(len(str_byte))
        self.write_bytes(str_byte)

    def write_class(self, _class):
        name, param = None, None
        try:
            if not hasattr(_class.__class__, '_fields_'):
                "if class have not fields try to use his own method"
                _class._serialize(self)
            else:
                for name, param in _class.__class__._fields_:
                    self.write(getattr(_class, name), param)
        except Exception as e:
            raise Exception('class_write %s error: %s' % (name, e))

    def write(self, x, param):
        if param == BYTE:
            self.write_byte(x)
        elif param == BYTE_ARRAY:
            self._write_param_length(x, param)
            self.write_bytes(x)
        elif param == UINT32:
            self.write_dword(x)
        elif param == INT32:
            self.write_dword(x, signed=True)
        elif param == UINT16:
            self.write_word(x)
        elif param == INT16:
            self.write_word(x, signed=True)
        elif param == WSTRING:
            self.write_string(x, wchar=True)
        elif param == ASTRING:
            self.write_string(x, wchar=False)
        elif param == FLOAT32:
            self.write_float32(x)
        elif param == BOOL:
            self.write_bool(x)
        elif param == CONTAINER:
            self.write_class(x)
        else:
            raise Exception('read type % not implemented' % param.typeid)

