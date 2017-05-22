import os
import unittest
from ds import *
from binascii import hexlify


class Nested:
    _fields_ = [
        ('x', Type(INT32)),
        ('y', Type(INT16))
    ]


class TestContainer:
    _fields_ = [
        ('byte', Type(BYTE)),
        ('int16', Type(INT16)),
        ('uint16', Type(UINT16)),
        ('astring', Type(ASTRING)),
        ('wstring', Type(WSTRING)),
        ('byte_array', Type(BYTE_ARRAY)),
        ('uint32', Type(UINT32)),
        ('int32', Type(INT32)),
        ('float32', Type(FLOAT32)),
        ('bool', Type(BOOL)),
        ('nested', Type(CONTAINER, Nested, 1))
    ]


class DsBuildTestCase(unittest.TestCase):
    def test_create_from_list(self):
        ds = DataStream([1, 2, 3, 4])

    def test_overwrite(self):
        a, b = [1, 2, 3, 4], [5, 6, 7, 8]
        ds = DataStream(a)
        ds.write_bytes(b, swap=True)
        self.assertEqual(b, [5, 6, 7, 8])
        ds.write_bytes(b, data_offset=1, swap=True)
        self.assertEqual(b, [5, 6, 7, 8])

    def test_write_offset_length(self):
        a, b = [1, 2, 3, 4], [5, 6, 7, 8]
        ds = DataStream(a)
        ds.write_bytes(b, data_offset=1, length=2)
        self.assertEqual(ds.buffer, bytearray([1, 2, 3, 4, 6, 7]))

    def test_write_bytes(self):
        a, b = [1, 2, 3, 4], [5, 6, 7, 8]
        ds = DataStream(a)
        self.assertEqual(len(ds.buffer), 4)
        ds.write_bytes(b)
        self.assertEqual(ds.buffer, bytearray(a+b))
        self.assertEqual(len(ds.buffer), 8)
        ds.write_bytes((a + b), data_offset=2)
        self.assertEqual(ds.buffer, bytearray(a+b + ((a + b)[2:])))
        self.assertEqual(len(ds.buffer), 14)

    def cuint_read(self, ds):
        ds_copy = DataStream(ds.buffer_copy())
        old_len = len(ds_copy.buffer)
        typeid = ds_copy.read_cuint32()
        cuint = ds_copy.read_cuint32()
        self.assertEqual(cuint + ds_copy.pos, old_len, msg=str(ds))
        self.read_all_packets(ds_copy, typeid, cuint)

    def read_all_packets(self, ds, typeid, cuint):
        if typeid == 0:
            while ds.can_read():
                if ds.read_cuint32() == 0x22:
                    buffer_len = ds.read_cuint32()
                    container_len = ds.read_cuint32() - 2
                    container_type = ds.read_word()
                    container_ds = DataStream(ds.read_bytes(container_len))
                else:
                    container_type = 0x45
                    # container_ds = 
        ds.flush()

    def copy_bytes(self, ds):
        copy = ds.buffer_copy()
        copy.pop(0)
        self.assertNotEqual(len(copy), len(ds.buffer))

    def test_wchar_string(self):
        string = 'Test string'
        encoded_string = bytearray(string, encoding='utf-16')[2:]
        encoded_string.insert(0, len(encoded_string))
        ds = DataStream(encoded_string)
        ds_string = ds.read_string()
        self.assertEqual(string, ds_string)


class WriteTestCase(unittest.TestCase):
    def test_write(self):
        ds = DataStream()
        ds.write_dword(150)
        ds.write_float32(3.141590118408203)
        ds.write_bool(True)
        ds.write_bool(False)
        ds.write_byte(255)
        ds.write_string("testStringWrite")
        t = TestContainer()
        t.byte = 1
        t.int16 = 1024
        t.uint16 = 65535
        t.astring = 'astringTest'
        t.wstring = 'wstringTestW'
        t.byte_array = bytearray([1, 2, 3, 4, 5, 6, 7, 8, 9])
        t.uint32 = 0xffffffff
        t.int32 = 65536
        t.float32 = 3.141590118408203
        t.bool = True
        t.nested = Nested()
        t.nested.x = 65536
        t.nested.y = 256
        ds.write_class(t)

        self.assertEqual(ds.read_dword(), 150)
        self.assertEqual(ds.read_float32(), 3.141590118408203)
        self.assertEqual(ds.read_bool(), True)
        self.assertEqual(ds.read_bool(), False)
        self.assertEqual(ds.read_byte(), 255)
        self.assertEqual(ds.read_string(), "testStringWrite")
        del t
        t = TestContainer()
        ds.read_class(t)
        self.assertTrue(t.byte == 1)
        self.assertTrue(t.int16 == 1024)
        self.assertTrue(t.uint16 == 65535)
        self.assertTrue(t.astring == 'astringTest')
        self.assertTrue(t.wstring == 'wstringTestW')
        self.assertTrue(t.byte_array == bytearray([1, 2, 3, 4, 5, 6, 7, 8, 9]))
        self.assertTrue(t.uint32 == 0xffffffff)
        self.assertTrue(t.int32 == 65536)
        self.assertTrue(t.float32 == 3.141590118408203)
        self.assertTrue(t.bool)
        self.assertTrue(t.nested[0].x == 65536)
        self.assertTrue(t.nested[0].y == 256)


class CuintTestCase(unittest.TestCase):
    def test_cuint_rw(self):
        ds = DataStream()
        for i in range(0, 0x2000):
            ds.write_cuint32(i)
            self.assertEqual(ds.read_cuint32(), i)

if __name__ == '__main__':
    unittest.main()
