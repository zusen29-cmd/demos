# encode tàng hình [fields]
# -*- coding: utf-8 -*-
from typing import Dict, Any, Optional, List
import time, random, datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad


def AES_CBC128(data, key, iv):
    if isinstance(data, str): data = data.encode()
    return AES.new(key, AES.MODE_CBC, iv).encrypt(pad(data, 16))


def _varint(n):
    if n < 0: return b""
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)


def pb_encode(fields):
    parts = []
    for k, v in fields.items():
        k = int(k)
        if isinstance(v, bool):
            parts.append(_varint(k << 3 | 0) + _varint(1 if v else 0))
        elif isinstance(v, int):
            parts.append(_varint(k << 3 | 0) + _varint(v))
        elif isinstance(v, dict):
            nested = pb_encode(v)
            parts.append(_varint(k << 3 | 2) + _varint(len(nested)) + nested)
        elif isinstance(v, (list, tuple)):
            for item in v:
                if isinstance(item, dict):
                    nested = pb_encode(item)
                    parts.append(_varint(k << 3 | 2) + _varint(len(nested)) + nested)
        elif isinstance(v, (str, bytes)):
            ev = v.encode() if isinstance(v, str) else v
            parts.append(_varint(k << 3 | 2) + _varint(len(ev)) + ev)
    return b"".join(parts)


def fstr(s): return str(s)
def getavatar(): return 902046010
def grcolor(): return "FFFFFF"

def Encrypt(uid):
    n = int(uid)
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n: b |= 0x80
        out.append(b)
        if not n: break
    return bytes(out)


class TAO_PACKET:
    def __init__(self, logindata, jsdata):
        self.iv = bytes(jsdata.get("iv"))
        self.key = bytes(jsdata.get("key"))
        self.account_id = logindata.get(str(1))
        self.account_region = jsdata.get("LockRegion")
        self.account_name = jsdata.get("UserNickName")
        self.client_version = jsdata.get("ClientVersion")

        self.rc = ((lambda s: "%02X" % s[self.account_region.upper()]
                    if self.account_region.upper() in s else None)
                   ({s["2"].upper(): s["1"] for s in logindata["19"]}))
        self.region_code = self.rc

        self._builder = lambda fields: (
            lambda packet, length: bytes.fromhex(
                "%02x%s%s%s%s" % (fields[0][1], self.region_code,
                str(0) * (8 - len(length)) if len(length) < 8 else '',
                length, packet)))(
            * (lambda header: (header, hex(len(header) // 2)[2:]))
            (AES_CBC128(pb_encode(dict(fields[1:])), self.key, self.iv).hex()))

        self.digtstimes = lambda s=datetime.datetime.utcnow(): int(
            (s + datetime.timedelta(days=(7 - s.weekday())))
            .replace(hour=6, minute=0, second=0, microsecond=0)
            .timestamp())

    def open_squad(self, tc):
        fields = {
            0: 5, '1': 1,
            '2': {
                '10': b"\x01\x07\t\n\x0b\x12\x19\x1a ')",
                '11': 1, '13': 1,
                '14': {
                    '1': (b'080380301ABA279402010000000000000005000100040000F1FA740A'
                          b'0F0000004676251400000000000000000000000000000000000000ff'
                          b'00000000cacfa16d'),
                    '10': 2,
                    '11': (b'\x03bbSQ67nzZ/J0AdV2KyoVlYRIvdLC0ggc1SIsxSJO8MXrgUkvxAk'
                           b'mhEqpVCVKdh4a7LxqKFYvy+y5zjI+1dGPHOuVubJoKDp0pr/Yq6MttgX'
                           b'gfYtvMrbAt6vRoRLEEpda3wLewWn00dRBgYY9M3nZVWmaVaxLsI8erqa'
                           b'JNKudc8L0KcKhQy5gzD9xT+PhpDNC4aENmAzy0dZwlIpf4CAwzXcRGS2'
                           b'UsDipni8CqiTrFh/JkipNOLxUAr4lTLoDMBBLocusy/+u8+MgrgO4PET'
                           b'Oy0fVThcf4XbHbbKbob06z0LKcYCtK3kPYs+wUJzZHvDmMTNQG56raMM'
                           b'KlvbfBfyw/Ch3MkoOsBK/VwFbSseEQFyqBNBfVov55UCK6ggZQNcYX5T'
                           b'eVXWUYe8QYadeLelsF1IXmWxj/sqlUdz6BT6qfhcDrWXT1grfKjmntvH'
                           b'TdCbJzut57sbsuTk5yBvPYN2eahhpeWJoG3JUGEqKeLBCyLcIO1+KBm1'
                           b'PqV9iRrY5yYWCXFlVnowSZySFSZPkh220l/L2tYlPFGxWWcunSBGkpJ7'
                           b'HwiTxekah+4J7OskqQL7bUHMbC8aQCzHBwHe3aoZLCA=='),
                    '2': 45,
                    '3': (b'uZ_T\x10\x08\x08O\x06\x03\x0b\nU\x02\x02\x01'
                          b'\x0e\x0e\x03\x06Q\x02\n\x04P\x06\x02\\Y\x03PQWU\x05Q'
                          b'R\x02\rZ\x10\x02\x02Ov^CEJ\x11\x08\x1f\x02\x1a\x10\x02'
                          b'\x01O\x1aAir_TCwr]UHfzH\x18Z\\K\x06QDBiUib\x0e\x10\x02'
                          b'O\x18\x06^t\x16j\x02Az\x06PdDcq\x16UVAFIDQ`\x01\x02\r'
                          b'\x05\x10\x02\x00OPK\n\x02\x01sK\x0bP\x06x\x07U\x05\x1a'
                          b'KM\x0eqG\x03\x03`zyWb\x04\x1b\x0bO\\Kk\n|G\n{\nfbXU[\x04v'
                          b'XCPRIB{IfX@\x0c\x10\x0bDeaDu\x06{q_\x05\x12ZAZ_\\`YpR_'
                          b'\x16sCt[w\x0b\x0e\x10\x08O\x0cMJRKZg\x04\x7f\tqky\x18^UPJdYGE'
                          b'`lf^~\x0e\x10\x02\x0bMR\x0eyu|BPKByT\x06jB{\\]ZX_R\x04'
                          b'\x7f\x16i]D\x0e\x10\x00Op\x1e\x7f_rKx|{G_riw~YJvbg[rrgv|_'
                          b'\x0e\x10\x07O\x02\x7f\x1cgXir|JDg{e[W\x7ftN\x18@\x01q\x03j'
                          b'\x1ch\\\x04\x1b\x01\x03O\x07a\x03\x0bpfn\x7ff@rwgp}\x7f'
                          b'@\tyEazI\x07YZx\x0e\x1a\rOQ\x02|APtu@Pig\x04t^fJ_\x01gOu'
                          b'pFf\x03\x06v\x0e'),
                    '4': b'}\\]V', '6': 11,
                    '7': b'\x17\rydRQ\x00w\x17\x17',
                    '8': b'1.130.20', '9': 3
                },
                '19': 329, '2': b'\x01', '21': b'O\x19',
                '24': [{'1': 3, '2': 391}, {'1': 4, '2': 385},
                       {'1': 5, '2': 192}, {'1': 29, '2': 204},
                       {'1': 22, '2': 120}, {'1': 14, '2': 175}, {'1': 21}],
                '27': b'a_2045012438551707759', '3': 1,
                '30': (b'https://dl-sg-production.freefiremobile.com/'
                       b'D5A73B5E05EC88BB7181_7104104913_107_1767710870_0'),
                '4': int(tc - 1), '5': b'vn',
                '8': {'1': b'IDC1', '2': 3000, '3': b'VN'}, '9': 1
            }
        }
        return self._builder(fields=list(fields.items()))

    def invite_squad(self, user_id, invite_type):
        fields = {0: 5, 1: 2, 2: {}}
        fields[2][1] = int(user_id)
        fields[2][2] = self.account_region
        fields[2][4] = int(invite_type)
        return self._builder(fields=list(fields.items()))

    def send_message(self, message, messageType, chatid):
        fields = {0: 18, 1: 1, 2: {}}
        fields[2][1] = self.account_id
        fields[2][2] = int(chatid)
        fields[2][4] = fstr(str(message))
        fields[2][5] = int(time.time())
        if messageType:
            fields[2][3] = int(messageType)
            fields[2][7] = 0x2
        fields[2][9] = {
            1: self.account_name, 2: getavatar(), 3: 901027033,
            4: 228, 5: 827001005, 10: 1, 11: 1, 12: 1,
            13: {1: 2},
            14: {1: self.account_id, 2: 8,
                 3: bytes([15,6,21,8,10,11,19,12,17,4,14,20,7,2,1,5,16,3,13,18])}
        }
        fields[2][10] = self.account_region.lower()
        fields[2][13] = {2: 0x1, 3: 0x1}
        fields[2][14] = {1: {1: 1, 2: 1, 3: random.randint(1, 100),
                            4: 36, 5: self.digtstimes(), 6: self.account_region}}
        return self._builder(fields=list(fields.items()))

    def join_squad(self, tc):
        fields = {0: 5, '1': 4, '2': {}}
        f2 = fields['2']
        f2['11'] = {'1': b'IDC1', '2': 3000, '3': b'VN'}
        f2['13'] = b'vn'
        f2['16'] = b'O\x19'
        f2['20'] = [{'1': 3, '2': 391}, {'1': 4, '2': 385},
                    {'1': 5, '2': 192}, {'1': 29, '2': 204},
                    {'1': 22, '2': 120}, {'1': 14, '2': 175}, {'1': 21}]
        f2['23'] = b'a_2045012438551707759'
        f2['24'] = (b'https://dl-sg-production.freefiremobile.com/'
                    b'D5A73B5E05EC88BB7181_7104104913_107_1767710870_0')
        f2['27'] = {'1': 55, '2': 8}
        f2['4'] = b"\x01\x07\t\n\x0b\x12\x19\x1a ')"
        f2['5'] = str(tc).encode()
        f2['6'] = 6
        f2['8'] = 1
        f2['9'] = {
            '1': (b'080380301ABA279402010000000000000005000100040000F1FA740A'
                  b'0F0000004676251400000000000000000000000000000000000000ff'
                  b'00000000cacfa16d'),
            '10': 2,
            '11': (b'\x03bbSQ67nzZ/J0AdV2KyoVlYRIvdLC0ggc1SIsxSJO8MXrgUkvxAk'
                   b'mhEqpVCVKdh4a7LxqKFYvy+y5zjI+1dGPHOuVubJoKDp0pr/Yq6MttgX'
                   b'gfYtvMrbAt6vRoRLEEpda3wLewWn00dRBgYY9M3nZVWmaVaxLsI8erqa'
                   b'JNKudc8L0KcKhQy5gzD9xT+PhpDNC4aENmAzy0dZwlIpf4CAwzXcRGS2'
                   b'UsDipni8CqiTrFh/JkipNOLxUAr4lTLoDMBBLocusy/+u8+MgrgO4PET'
                   b'Oy0fVThcf4XbHbbKbob06z0LKcYCtK3kPYs+wUJzZHvDmMTNQG56raMM'
                   b'KlvbfBfyw/Ch3MkoOsBK/VwFbSseEQFyqBNBfVov55UCK6ggZQNcYX5T'
                   b'eVXWUYe8QYadeLelsF1IXmWxj/sqlUdz6BT6qfhcDrWXT1grfKjmntvH'
                   b'TdCbJzut57sbsuTk5yBvPYN2eahhpeWJoG3JUGEqKeLBCyLcIO1+KBm1'
                   b'PqV9iRrY5yYWCXFlVnowSZySFSZPkh220l/L2tYlPFGxWWcunSBGkpJ7'
                   b'HwiTxekah+4J7OskqQL7bUHMbC8aQCzHBwHe3aoZLCA=='),
            '2': 33,
            '3': (b'uZ_T\x10\x08\x08O\x06\x03\x0b\nU\x02\x02\x01'
                  b'\x0e\x0e\x03\x06Q\x02\n\x04P\x06\x02\\Y\x03PQWU\x05Q'
                  b'R\x02\rZ\x10\x02\x02Ov^CEJ\x11\x08\x1f\x02\x1a\x10\x02'
                  b'\x01O\x1aAir_TCwr]UHfzH\x18Z\\K\x06QDBiUib\x0e\x10\x02'
                  b'O\x18\x06^t\x16j\x02Az\x06PdDcq\x16UVAFIDQ`\x01\x02\r'
                  b'\x05\x10\x02\x00OPK\n\x02\x01sK\x0bP\x06x\x07U\x05\x1a'
                  b'KM\x0eqG\x03\x03`zyWb\x04\x1b\x0bO\\Kk\n|G\n{\nfbXU[\x04v'
                  b'XCPRIB{IfX@\x0c\x10\x0bDeaDu\x06{q_\x05\x12ZAZ_\\`YpR_'
                  b'\x16sCt[w\x0b\x0e\x10\x08O\x0cMJRKZg\x04\x7f\tqky\x18^UPJdYGE'
                  b'`lf^~\x0e\x10\x02\x0bMR\x0eyu|BPKByT\x06jB{\\]ZX_R\x04'
                  b'\x7f\x16i]D\x0e\x10\x00Op\x1e\x7f_rKx|{G_riw~YJvbg[rrgv|_'
                  b'\x0e\x10\x07O\x02\x7f\x1cgXir|JDg{e[W\x7ftN\x18@\x01q\x03j'
                  b'\x1ch\\\x04\x1b\x01\x03O\x07a\x03\x0bpfn\x7ff@rwgp}\x7f'
                  b'@\tyEazI\x07YZx\x0e\x1a\rOQ\x02|APtu@Pig\x04t^fJ_\x01gOu'
                  b'pFf\x03\x06v\x0e'),
            '4': b'}\\]V', '6': 11,
            '7': b'\x17\rydRQ\x00w\x17\x17',
            '8': b'1.130.20', '9': 3
        }
        return self._builder(fields=list(fields.items()))

    def leave_squad(self, uid=0x1):
        fields = {0: 5, 1: 7, 2: {1: int(uid)}}
        return self._builder(fields=list(fields.items()))

    def ghost_send(self, Uid, Nm, sQ):
        fields = {0: 5, 1: 61, 2: {}}
        f2 = fields[2]
        f2[1] = int(Uid)
        f2[2] = {1: int(Uid), 2: 1159, 3: str(Nm), 5: 12, 6: 9999999,
                 7: 1, 8: {2: 1, 3: 1}, 9: 3}
        f2[3] = sQ
        return self._builder(fields=list(fields.items()))

    def ghost(self, uid, hv, name):
        colors = ["[FF0000]", "[00FF00]", "[0000FF]", "[FFFF00]", "[FF00FF]", "[00FFFF]"]
        color = random.choice(colors)
        fields = {0: 5, 1: 61, 2: {}}
        fields[2][1] = int(uid)
        fields[2][2] = {1: int(uid), 3: f"[b][i][c]{color}{name}",
                        6: self.digtstimes(), 7: 0x01, 9: 0x01}
        fields[2][3] = str(hv)
        return self._builder(fields=list(fields.items()))

    def play_emote(self, eid, ids=[]):
        fields = {0: 5, 1: 21, 2: {}}
        fields[2][1] = self.account_id
        fields[2][2] = 0x362E3D41
        fields[2][5] = [{1: id, 3: eid} for id in ids]
        return self._builder(fields=list(fields.items()))

    def join_channel(self, cid, ccode, ctype):
        fields = {0: 18, 1: 3, 2: {}}
        if cid: fields[2][1] = int(cid)
        if ctype: fields[2][2] = int(ctype)
        if ccode: fields[2][4] = str(ccode)
        fields[2][3] = self.account_region.lower()
        return self._builder(fields=list(fields.items()))
